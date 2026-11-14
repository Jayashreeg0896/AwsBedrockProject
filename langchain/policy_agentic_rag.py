"""
Internal Policy Assistant — AGENTIC RAG version
(builds on policy_rag_graph.py and reuses its S3 Vectors store, role filter, reranker, guardrails and cache)

Workflow RAG (policy_rag_graph.py):  rewrite -> retrieve -> generate          (same fixed steps every time)
Agentic RAG (this file):             the LLM DECIDES and CHECKS ITS OWN WORK

  START -> rewrite_query -> plan --direct------> greet -> END
                                 --out_of_scope-> decline -> END
                                 --retrieve-----> check_cache --hit--> END
                                                       | miss
                                                       v
                              +-------------------> retrieve -> grade_docs --relevant--> generate -> check_grounding --grounded--> save_cache -> END
                              |                                   | none relevant           ^              | not grounded
                              +----- transform_query <------------+ (retry, max 2)          +--------------+ (regenerate, max 1 retry)
                                                                  | still nothing                          | still not grounded
                                                                  v                                        v
                                                               fallback -> END                          fallback -> END

The 3 agentic decisions:
  1. plan             - does this need retrieval at all? which policy area (topic -> department filter)?
  2. grade_docs       - are the retrieved chunks really relevant? if not, transform_query writes a
                        better search and tries again WITHOUT the topic filter (in case plan picked the wrong area)
  3. check_grounding  - is every fact in the answer supported by the chunks? if not, regenerate once,
                        then fall back to HR instead of returning an unsupported answer

Security does NOT depend on the LLM: the audience (role) filter is always added in code.
The LLM can narrow the search (department), never widen access.

Run (PowerShell):
    $env:VECTOR_BUCKET = "<your-vector-bucket>"
    python langchain\\policy_agentic_rag.py
"""

import os
from typing import Annotated, Literal
from typing_extensions import TypedDict

from pydantic import BaseModel, Field
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

import policy_rag_graph as base      # reuse components from the workflow version

REGION = base.REGION
JUDGE_MODEL = os.getenv("JUDGE_MODEL", base.LLM_MODEL)   # planner / grader / grounding checker
MAX_RETRIEVALS = 2                                         # first search + 1 corrected search
MAX_GENERATIONS = 2                                        # first answer + 1 regeneration

# Topic chosen by the planner -> department metadata filter
TOPIC_TO_DEPARTMENT = {"leave": "HR", "compensation": "HR", "travel_expense": "Finance", "it_security": "IT"}

judge = ChatBedrockConverse(model=JUDGE_MODEL, region_name=REGION, temperature=0, max_tokens=400)


# ---------------------------------------------------------------------------
# Structured outputs for the LLM's decisions
# ---------------------------------------------------------------------------
class Plan(BaseModel):
    action: Literal["retrieve", "direct", "out_of_scope"] = Field(
        description="retrieve: needs company policy information. direct: greeting, thanks or 'what can you do'. "
                    "out_of_scope: not about Northwind company policies (e.g. weather, coding help, poems)")
    topic: Literal["leave", "travel_expense", "it_security", "compensation", "unknown"] = Field(
        description="Policy area the question is about; 'unknown' if unsure or several areas")


class Grades(BaseModel):
    relevant_ids: list[int] = Field(description="Numbers of the documents that help answer the question")
    reason: str = Field(description="One short sentence")


class Grounding(BaseModel):
    grounded: bool = Field(description="True only if every fact, number and date in the answer appears in the documents")
    unsupported_claims: list[str] = Field(description="Facts in the answer not found in the documents; empty if grounded")


planner = judge.with_structured_output(Plan)
grader = judge.with_structured_output(Grades)
grounding_checker = judge.with_structured_output(Grounding)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgenticState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_role: str
    search_query: str
    tried_queries: list
    route: str                  # retrieve / direct / out_of_scope
    topic: str
    docs: list
    retrievals: int
    generations: int
    grounding_feedback: str
    cache_hit: bool
    cache_similarity: float
    cached_sources: list
    steps: list                 # trace of the agent's decisions (printed in the demo)


def log(state, text: str) -> list:
    return state.get("steps", []) + [text]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def plan(state: AgenticState):
    """Decision 1: retrieve or not, and which policy area. Also resets per-turn fields."""
    p = planner.invoke(
        "You route questions for Northwind Tech's internal policy assistant (leave, travel and expenses, "
        "IT security, manager compensation).\n"
        f"Question: {base.latest_question(state)}\nStandalone version: {state['search_query']}")
    return {"route": p.action, "topic": p.topic, "docs": [], "tried_queries": [state["search_query"]],
            "retrievals": 0, "generations": 0, "grounding_feedback": "",
            "cache_hit": False, "cache_similarity": 0.0, "cached_sources": [],
            "steps": [f"plan: action={p.action}, topic={p.topic}"]}


def decline(state: AgenticState):
    return {"messages": [AIMessage(content=
        "I can only help with Northwind Tech's company policies, such as leave, travel and expenses, and IT security.")]}


def retrieve(state: AgenticState):
    allowed = base.ROLE_ACCESS.get(state.get("user_role", "employee"), ["all"])
    audience_filter = {"audience": {"$in": allowed}}                 # ALWAYS applied, in code
    dept = TOPIC_TO_DEPARTMENT.get(state.get("topic"))
    filt = {"$and": [audience_filter, {"department": {"$eq": dept}}]} if dept else audience_filter

    query = state["search_query"]
    candidates = base.vectorstore.similarity_search(query, k=base.CANDIDATES_K, filter=filt)
    docs = candidates[:base.FINAL_K]
    if candidates and base.USE_RERANK:
        docs = [d for d in base.reranker.compress_documents(candidates, query)
                if d.metadata.get("relevance_score", 1) >= base.MIN_RERANK_SCORE]
    n = state.get("retrievals", 0) + 1
    return {"docs": docs, "retrievals": n,
            "steps": log(state, f"retrieve #{n}: query={query!r}, department={dept or 'any'} -> {len(docs)} chunk(s)")}


def grade_docs(state: AgenticState):
    """Decision 2: keep only chunks that actually help answer the question."""
    docs = state["docs"]
    if not docs:
        return {"steps": log(state, "grade: nothing to grade")}
    numbered = "\n\n".join(f"[{i}] {d.page_content[:800]}" for i, d in enumerate(docs))
    question = state["tried_queries"][0]       # grade against the user's ORIGINAL question, not a rewrite
    g = grader.invoke(f"Question: {question}\n\nDocuments:\n{numbered}\n\n"
                      "Which documents contain information that helps answer the question?")
    keep = [docs[i] for i in g.relevant_ids if 0 <= i < len(docs)]
    return {"docs": keep, "steps": log(state, f"grade: {len(keep)}/{len(docs)} relevant ({g.reason})")}


def transform_query(state: AgenticState):
    """Self-correction: write a different search query and search all policy areas."""
    new_q = judge.invoke(
        "A search of company policy documents found nothing relevant.\n"
        f"User question: {base.latest_question(state)}\nQueries already tried: {state['tried_queries']}\n"
        "Write ONE different search query using the words an HR, finance or IT policy document would use "
        "(synonyms, formal terms). Return only the query.").content
    new_q = (new_q if isinstance(new_q, str) else str(new_q)).strip().strip('"')
    return {"search_query": new_q, "topic": "unknown", "tried_queries": state["tried_queries"] + [new_q],
            "steps": log(state, f"transform_query: {new_q!r} (topic filter removed)")}


def generate(state: AgenticState):
    question = base.latest_question(state)
    if state.get("grounding_feedback"):
        question += ("\n\n(Your previous answer contained claims not supported by the documents: "
                     f"{state['grounding_feedback']}. Answer again using ONLY the documents.)")
    answer = base.answer_chain.invoke({"context": base.format_docs(state["docs"]), "hr_contact": base.HR_CONTACT,
                                       "history": base.chat_history(state)[-10:], "question": question})
    n = state.get("generations", 0) + 1
    return {"messages": [AIMessage(content=answer)], "generations": n, "steps": log(state, f"generate #{n}")}


def check_grounding(state: AgenticState):
    """Decision 3: is the answer supported by the retrieved chunks?"""
    answer = state["messages"][-1].content
    if answer.startswith("I couldn't find"):
        return {"grounding_feedback": "", "steps": log(state, "grounding: 'not found' answer, nothing to check")}
    g = grounding_checker.invoke(f"Documents:\n{base.format_docs(state['docs'])}\n\nAnswer:\n{answer}\n\n"
                                 "Is every fact, number and date in the answer supported by the documents?")
    fb = "" if g.grounded else "; ".join(g.unsupported_claims) or "unsupported content"
    return {"grounding_feedback": fb,
            "steps": log(state, "grounding: OK" if g.grounded else f"grounding: FAILED ({fb})")}


def fallback(state: AgenticState):
    return {"messages": [AIMessage(content=
        f"I couldn't find that in the policies available to you. Please contact HR at {base.HR_CONTACT}.")],
            "steps": log(state, "fallback")}


def save_cache(state: AgenticState):
    """Only verified (grounded) answers are cached."""
    base.save_cache(state)
    return {"steps": log(state, "save_cache")}


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------
def after_plan(state) -> Literal["greet", "decline", "check_cache"]:
    return {"direct": "greet", "out_of_scope": "decline"}.get(state["route"], "check_cache")


def after_cache(state) -> Literal["retrieve", "__end__"]:
    return END if state.get("cache_hit") else "retrieve"


def after_grade(state) -> Literal["generate", "transform_query", "fallback"]:
    if state["docs"]:
        return "generate"
    return "transform_query" if state["retrievals"] < MAX_RETRIEVALS else "fallback"


def after_grounding(state) -> Literal["save_cache", "generate", "fallback"]:
    if not state.get("grounding_feedback"):
        return "save_cache"
    return "generate" if state["generations"] < MAX_GENERATIONS else "fallback"


def build_graph(with_memory: bool = True):
    """with_memory=False for Lambda: history is loaded from DynamoDB and passed in messages."""
    b = StateGraph(AgenticState)
    for name, fn in [("rewrite_query", base.rewrite_query), ("plan", plan), ("greet", base.greet),
                     ("decline", decline), ("check_cache", base.check_cache), ("retrieve", retrieve),
                     ("grade_docs", grade_docs), ("transform_query", transform_query), ("generate", generate),
                     ("check_grounding", check_grounding), ("fallback", fallback), ("save_cache", save_cache)]:
        b.add_node(name, fn)
    b.add_edge(START, "rewrite_query")
    b.add_edge("rewrite_query", "plan")
    b.add_conditional_edges("plan", after_plan)
    b.add_conditional_edges("check_cache", after_cache)
    b.add_edge("retrieve", "grade_docs")
    b.add_conditional_edges("grade_docs", after_grade)
    b.add_edge("transform_query", "retrieve")
    b.add_edge("generate", "check_grounding")
    b.add_conditional_edges("check_grounding", after_grounding)
    for n in ("greet", "decline", "fallback", "save_cache"):
        b.add_edge(n, END)
    return b.compile(checkpointer=InMemorySaver() if with_memory else None)


graph = build_graph()


def main():
    role = input("Log in as (employee/manager): ").strip().lower()
    role = role if role in base.ROLE_ACCESS else "employee"
    config = {"configurable": {"thread_id": f"{role}-agentic-1"}, "recursion_limit": 25}
    print(f"Logged in as {role}. Ask about company policies (type 'exit' to quit).")
    while True:
        q = input("\nYou: ").strip()
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break
        result = graph.invoke({"messages": [HumanMessage(content=q)], "user_role": role}, config)
        for s in result.get("steps", []):
            print(f"  [agent] {s}")
        if result.get("cache_hit"):
            print(f"  [agent] cache HIT (similarity {result.get('cache_similarity', 0):.3f})")
        print(f"\nAssistant: {result['messages'][-1].content}")
        sources = result.get("cached_sources") if result.get("cache_hit") else \
            sorted({base.cite(d) for d in (result.get("docs") or [])})
        if result.get("route") == "retrieve" and sources and not result["messages"][-1].content.startswith("I couldn't"):
            print("Sources:", ", ".join(sources))


if __name__ == "__main__":
    main()

# TEST SCRIPT (as employee unless noted):
#   1. "hi"                                             -> plan: direct -> greet (no retrieval)
#   2. "Write me a poem about cats"                     -> plan: out_of_scope -> decline
#   3. "How many days of annual leave do I get?"        -> topic=leave, HR filter, grounded answer
#   4. "Can I bring my own pen drive to work?"          -> topic=it_security; USB rule (IT-POL-002)
#   5. "Do I get money for food when I travel?"         -> daily allowance INR 1,500 (FIN-POL-004)
#   6. "What is the salary revision budget?"            -> nothing visible to employees -> transform_query -> fallback
#   7. As manager: "What is the salary revision budget?" -> 9 percent (HR-CONF-010)
#   Watch the [agent] lines to see each decision.
