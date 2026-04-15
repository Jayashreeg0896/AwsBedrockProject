import boto3
import json
import os

s3_presign = boto3.client("s3", region_name="us-east-1")
bedrock = boto3.client("bedrock-runtime")
s3vectors = boto3.client("s3vectors", region_name="us-east-1")

SYSTEM_STATE = os.getenv("SYSTEM_STATE", "ACTIVE")
DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET")
VECTORS_BUCKET = os.getenv("VECTORS_BUCKET")
INDEX_NAME = "aws-docs-index"
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


def retrieve_context(question):
    try:
        # Embed the question
        question_embedding = embed_text(question)

        # Query S3 Vectors — replaces cosine similarity loop
        response = s3vectors.query_vectors(
            vectorBucketName=VECTORS_BUCKET,
            indexName=INDEX_NAME,
            queryVector={"float32": question_embedding},
            topK=TOP_K,
            returnMetadata=True
        )

        matches = response.get("vectors", [])
        if not matches:
            print("No vectors found")
            return "", []

        # Extract context and sources from metadata
        sources = list(set(m["metadata"]["source"] for m in matches))
        context = "\n\n".join(m["metadata"]["text"] for m in matches)
        return context, sources

    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return "", []


def handler(event, context):
    if SYSTEM_STATE == "HIBERNATED":
        return {"statusCode": 503, "body": "System parked"}

    body = json.loads(event.get("body", "{}"))

    # Handle presign request for PDF upload
    if body.get("action") == "presign":
        filename = body.get("filename", "document.pdf")
        url = s3_presign.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": DOCUMENTS_BUCKET,
                "Key": filename,
                "ContentType": "application/pdf"
            },
            ExpiresIn=300
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"upload_url": url})
        }

    # Normal chat request
    q = body.get("question", "hello")
    history = body.get("history", [])

    # Retrieve context from S3 Vectors
    rag_context, sources = retrieve_context(q)

    # Build system prompt
    if rag_context:
        system_prompt = f"""You are a helpful, friendly AWS assistant. Answer questions in a natural, conversational way.
Use the context below to inform your answers, but never mention that you are using "context" or "documentation".
Format responses clearly using bullet points, bold text, and short paragraphs where appropriate.
If the question is casual like a greeting, respond warmly and naturally without bullet points.

Context:
{rag_context}"""
    else:
        system_prompt = """You are a helpful, friendly AWS assistant. Answer questions in a natural, conversational way.
Format responses clearly using bullet points, bold text, and short paragraphs where appropriate.
If the question is casual like a greeting, respond warmly and naturally without bullet points."""

    # Build messages with history
    messages = []
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["text"]}]
        })
    messages.append({
        "role": "user",
        "content": [{"text": q}]
    })

    # Call Claude
    response = bedrock.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        system=[{"text": system_prompt}],
        messages=messages,
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