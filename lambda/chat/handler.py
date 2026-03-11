import boto3
import json
import os
import math

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")

SYSTEM_STATE = os.getenv("SYSTEM_STATE", "ACTIVE")
DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET")
EMBEDDINGS_PREFIX = "embeddings/"
TOP_K = 3


def embed_text(text):
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0
    return dot / (mag_a * mag_b)


def retrieve_context(question):
    try:
        response = s3.list_objects_v2(
            Bucket=DOCUMENTS_BUCKET,
            Prefix=EMBEDDINGS_PREFIX
        )
        if "Contents" not in response:
            print("No embeddings found")
            return "", []

        question_embedding = embed_text(question)

        all_chunks = []
        for obj in response["Contents"]:
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            data = s3.get_object(Bucket=DOCUMENTS_BUCKET, Key=key)
            chunks = json.loads(data["Body"].read())
            all_chunks.extend(chunks)

        scored = []
        for chunk in all_chunks:
            score = cosine_similarity(question_embedding, chunk["embedding"])
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [chunk for _, chunk in scored[:TOP_K]]
        sources = list(set(chunk["source"] for chunk in top_chunks))
        context = "\n\n".join(chunk["text"] for chunk in top_chunks)
        return context, sources

    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return "", []


def handler(event, context):
    if SYSTEM_STATE == "HIBERNATED":
        return {"statusCode": 503, "body": "System parked"}

    body = json.loads(event.get("body", "{}"))
    q = body.get("question", "hello")

    # Retrieve context from documents
    rag_context, sources = retrieve_context(q)

    # Build prompt
    if rag_context:
        prompt = f"""You are a helpful, friendly AWS assistant. Answer the user's question in a natural, conversational way.
Use the context below to inform your answer, but never mention that you are using "context" or "documentation".
Just answer naturally as if you know the information. If the question is casual like a greeting, respond warmly and naturally.

Context:
{rag_context}

User: {q}"""
    else:
        prompt = f"""You are a helpful, friendly AWS assistant. Answer the user's question in a natural, conversational way.

User: {q}"""

    # Call Claude
    response = bedrock.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        inferenceConfig={"maxTokens": 1024}
    )

    result = response["output"]["message"]["content"][0]["text"]

    return {
        "statusCode": 200,
        "body": json.dumps({
            "response": result,
            "sources": sources
        })
    }