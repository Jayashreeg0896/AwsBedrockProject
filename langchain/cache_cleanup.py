"""
Delete semantic-cache entries older than 7 days from S3 Vectors.

Run manually:
    $env:VECTOR_BUCKET = "<your-vector-bucket>"
    python langchain\\cache_cleanup.py

Or deploy as a Lambda (handler: cache_cleanup.lambda_handler) triggered daily
by an EventBridge schedule, e.g. rate(1 day). The Lambda role needs
s3vectors:ListVectors and s3vectors:DeleteVectors on the cache index.
"""

import os

from langchain_aws import BedrockEmbeddings

from policy_cache import SemanticCache

REGION = os.getenv("AWS_REGION", "us-east-1")


def run() -> int:
    bucket = os.environ["VECTOR_BUCKET"]
    embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name=REGION)
    deleted = SemanticCache(bucket, embeddings, REGION).delete_expired()
    print(f"Deleted {deleted} expired cache entries.")
    return deleted


def lambda_handler(event, context):
    return {"deleted": run()}


if __name__ == "__main__":
    run()
