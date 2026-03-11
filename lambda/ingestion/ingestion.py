import boto3
import json
import os
import math
import time

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
textract = boto3.client("textract")

BUCKET = os.getenv("DOCUMENTS_BUCKET")
EMBEDDINGS_PREFIX = "embeddings/"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def extract_text_from_pdf(bucket, key):
    """Extract text from multi-page PDF using Textract async API"""
    # Start async job
    response = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = response["JobId"]
    print(f"Textract job started: {job_id}")

    # Poll until complete
    while True:
        result = textract.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]
        print(f"Textract status: {status}")
        if status == "SUCCEEDED":
            break
        elif status == "FAILED":
            raise Exception(f"Textract job failed: {result}")
        time.sleep(5)

    # Collect all pages
    pages = []
    next_token = None
    while True:
        if next_token:
            result = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        else:
            result = textract.get_document_text_detection(JobId=job_id)

        text = " ".join(
            block["Text"]
            for block in result["Blocks"]
            if block["BlockType"] == "LINE"
        )
        pages.append(text)

        next_token = result.get("NextToken")
        if not next_token:
            break

    return " ".join(pages)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def embed_text(text):
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        # Skip embeddings folder and non-PDFs
        if key.startswith(EMBEDDINGS_PREFIX) or not key.lower().endswith(".pdf"):
            print(f"Skipping: {key}")
            continue

        print(f"Processing: {key}")

        # Extract text
        text = extract_text_from_pdf(bucket, key)
        print(f"Extracted {len(text)} characters")

        # Chunk text
        chunks = chunk_text(text)
        print(f"Created {len(chunks)} chunks")

        # Embed each chunk
        embeddings_data = []
        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            embeddings_data.append({
                "chunk_id": i,
                "source": key,
                "text": chunk,
                "embedding": embedding
            })
            print(f"Embedded chunk {i+1}/{len(chunks)}")

        # Save embeddings to S3
        doc_name = key.replace("/", "_").replace(".pdf", "")
        embeddings_key = f"{EMBEDDINGS_PREFIX}{doc_name}.json"
        s3.put_object(
            Bucket=BUCKET,
            Key=embeddings_key,
            Body=json.dumps(embeddings_data),
            ContentType="application/json"
        )
        print(f"Saved embeddings to s3://{BUCKET}/{embeddings_key}")

    return {"statusCode": 200, "body": "Ingestion complete"}