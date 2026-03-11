import boto3
import json
import os
import re

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")

BUCKET = os.getenv("DOCUMENTS_BUCKET")
EMBEDDINGS_PREFIX = "embeddings/"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def extract_text_from_pdf(bucket, key):
    """Extract text from PDF using Textract"""
    textract = boto3.client("textract")
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    text = " ".join(
        block["Text"]
        for block in response["Blocks"]
        if block["BlockType"] == "LINE"
    )
    return text


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks"""
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
    """Get embeddings from Titan Embeddings v2"""
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def handler(event, context):
    """Triggered when a PDF is uploaded to S3"""
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        # Only process PDFs
        if not key.lower().endswith(".pdf"):
            print(f"Skipping non-PDF file: {key}")
            continue

        print(f"Processing: {key}")

        # Extract text
        text = extract_text_from_pdf(bucket, key)
        print(f"Extracted {len(text)} characters")

        # Chunk text
        chunks = chunk_text(text)
        print(f"Created {len(chunks)} chunks")

        # Embed each chunk and save
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
        print(f"Saved embeddings to {embeddings_key}")

    return {"statusCode": 200, "body": "Ingestion complete"}