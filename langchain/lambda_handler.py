"""
Lambda handler for the agentic policy assistant (behind API Gateway HTTP API + Cognito JWT authorizer).

Request:   POST /ask   Authorization: Bearer <Cognito ID token>
           {"question": "How many leave days do I get?", "session_id": "optional"}
Response:  {"answer": "...", "sources": [...], "session_id": "...", "steps": [...]}

- WHO the user is and their ROLE come from the verified JWT (Cognito group "manager" or "employee"),
  never from the request body, so nobody can make themselves a manager.
- Chat history: last 5 turns per user + session in DynamoDB (7-day TTL), because Lambda keeps nothing
  between invocations. The graph runs without a checkpointer and gets the history in `messages`.
"""

import os
import json
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.messages import HumanMessage, AIMessage

import policy_agentic_rag as rag

TABLE = boto3.resource("dynamodb").Table(os.environ["HISTORY_TABLE"])
HISTORY_TURNS = 5
TTL_DAYS = 7
MAX_QUESTION_CHARS = 1000

graph = rag.build_graph(with_memory=False)        # built once per Lambda container (warm starts reuse it)


def response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def user_from_token(event: dict):
    """API Gateway has already verified the JWT; we only read its claims."""
    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    groups = claims.get("cognito:groups", "")          # e.g. "[manager]" in HTTP API payloads
    role = "manager" if "manager" in groups else "employee"
    return claims["sub"], role


def load_history(pk: str) -> list:
    items = TABLE.query(KeyConditionExpression=Key("pk").eq(pk), ScanIndexForward=False,
                        Limit=HISTORY_TURNS)["Items"]
    messages = []
    for item in reversed(items):                        # oldest first
        messages += [HumanMessage(content=item["question"]), AIMessage(content=item["answer"])]
    return messages


def save_turn(pk: str, question: str, answer: str):
    now = int(time.time())
    TABLE.put_item(Item={"pk": pk, "sk": time.time_ns(), "question": question, "answer": answer,
                         "ttl": now + TTL_DAYS * 86400})


def handler(event, context):
    if os.getenv("SYSTEM_STATE") == "HIBERNATED":
        return response(503, {"error": "The assistant is hibernated. Set SystemState=ACTIVE to use it."})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "Body must be JSON"})

    question = (body.get("question") or "").strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        return response(400, {"error": f"'question' is required (max {MAX_QUESTION_CHARS} characters)"})

    user_id, role = user_from_token(event)
    session_id = body.get("session_id") or uuid.uuid4().hex
    pk = f"{user_id}#{session_id}"                      # history is per user AND session

    result = graph.invoke({"messages": load_history(pk) + [HumanMessage(content=question)], "user_role": role},
                          {"recursion_limit": 25})
    answer = result["messages"][-1].content
    save_turn(pk, question, answer)

    found = result.get("route") == "retrieve" and not answer.startswith("I couldn't")
    if result.get("cache_hit"):
        sources = result.get("cached_sources") or []
    else:
        sources = sorted({rag.base.cite(d) for d in (result.get("docs") or [])}) if found else []

    print(json.dumps({"user": user_id, "role": role, "steps": result.get("steps", []),
                      "cache_hit": bool(result.get("cache_hit"))}))   # CloudWatch trace of the agent's decisions
    return response(200, {"answer": answer, "sources": sources, "session_id": session_id, "role": role,
                          "steps": result.get("steps", [])})
