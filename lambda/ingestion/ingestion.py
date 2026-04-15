import boto3
import json
import os
import time

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
textract = boto3.client("textract")
s3vectors = boto3.client("s3vectors", region_name="us-east-1")

DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET")
VECTORS_BUCKET = os.getenv("VECTORS_BUCKET")
INDEX_NAME = "aws-docs-index"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def create_index_if_not_exists():
    try:
        s3vectors.get_index(
            vectorBucketName=VECTORS_BUCKET,
            indexName=INDEX_NAME
        )
        print(f"Index {INDEX_NAME} already exists")
    except Exception:
        print(f"Creating index {INDEX_NAME}")
        s3vectors.create_index(
            vectorBucketName=VECTORS_BUCKET,
            indexName=INDEX_NAME,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine"
        )
        print(f"Index {INDEX_NAME} created")


def extract_text_from_pdf(bucket, key):
    response = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = response["JobId"]
    print(f"Textract job started: {job_id}")

    while True:
        result = textract.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]
        print(f"Textract status: {status}")
        if status == "SUCCEEDED":
            break
        elif status == "FAILED":
            raise Exception(f"Textract job failed: {result}")
        time.sleep(5)

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
    create_index_if_not_exists()

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        if not key.lower().endswith(".pdf"):
            print(f"Skipping non-PDF: {key}")
            continue

        print(f"Processing: {key}")

        # Extract text
        text = extract_text_from_pdf(bucket, key)
        print(f"Extracted {len(text)} characters")

        # Chunk text
        chunks = chunk_text(text)
        print(f"Created {len(chunks)} chunks")

        # Embed and store in S3 Vectors (max 100 per batch)
        batch = []
        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            batch.append({
                "key": f"{key}-chunk-{i}",
                "data": {"float32": embedding},
                "metadata": {
                    "source": key,
                    "text": chunk,
                    "chunk_id": str(i)
                }
            })
            print(f"Embedded chunk {i+1}/{len(chunks)}")

            if len(batch) == 100:
                s3vectors.put_vectors(
                    vectorBucketName=VECTORS_BUCKET,
                    indexName=INDEX_NAME,
                    vectors=batch
                )
                print(f"Stored batch of 100 vectors")
                batch = []

        # Store remaining batch
        if batch:
            s3vectors.put_vectors(
                vectorBucketName=VECTORS_BUCKET,
                indexName=INDEX_NAME,
                vectors=batch
            )
            print(f"Stored final batch of {len(batch)} vectors")

        print(f"Done: {key}")

    return {"statusCode": 200, "body": "Ingestion complete"}