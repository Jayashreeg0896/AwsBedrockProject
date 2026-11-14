"""
Internal Policy Assistant — ingestion into Amazon S3 Vectors (incremental: only changed policies)

PDF policies -> load -> split -> attach policy metadata -> Titan v2 embeddings -> S3 Vectors

Runs locally OR in GitHub Actions on every push (see .github/workflows/deploy.yaml):
  - first run: every policy is NEW and gets ingested
  - later runs: only policies whose PDF or metadata changed are re-ingested; the rest are skipped

How it knows what changed (no manifest file to lose):
  Every chunk in S3 Vectors stores `source` (file name) and `version_hash`.
  version_hash = SHA-256 of (PDF bytes + that policy's entry in policy_metadata.json)
  so changing the PDF OR its metadata (e.g. audience all -> managers) counts as an update.

  Each run lists what's in the index and compares:
    NEW        -> not in the index yet          -> ingest
    UNCHANGED  -> same version_hash             -> skip (no embedding cost)
    UPDATED    -> different version_hash        -> delete that policy's old chunks, ingest the new version
    REMOVED    -> PDF deleted, or its metadata entry removed -> delete its chunks
  Any change also clears the semantic cache so outdated answers aren't reused.

Metadata per chunk (from policy_metadata.json):
  policy_name, policy_id, department, audience ("all"/"managers"), effective_date,
  source, page, chunk_id, version_hash

Run locally (PowerShell):
    $env:VECTOR_BUCKET = "bedrock-rag-vectors-<account-id>"
    python langchain\\policy_ingestion.py

To update a policy: replace the PDF in policies\\ (same file name) and/or edit its entry in
policy_metadata.json, then commit and push. Only that policy is re-ingested.
"""

import os
import sys
import glob
import json
import hashlib

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_aws import BedrockEmbeddings
from langchain_aws.vectorstores import AmazonS3Vectors

from policy_cache import SemanticCache

REGION = os.getenv("AWS_REGION", "us-east-1")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY_DIR = os.path.join(BASE_DIR, "policies")
METADATA_FILE = os.path.join(BASE_DIR, "policy_metadata.json")

VECTOR_BUCKET = os.environ.get("VECTOR_BUCKET")
INDEX_NAME = "company-policies"

CHUNK_SIZE = 1000          # characters (~150-200 words)
CHUNK_OVERLAP = 150        # ~15% overlap

embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name=REGION)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def get_vectorstore() -> AmazonS3Vectors:
    if not VECTOR_BUCKET:
        raise SystemExit("Set the VECTOR_BUCKET environment variable to your S3 vector bucket name.")
    return AmazonS3Vectors(
        vector_bucket_name=VECTOR_BUCKET,
        index_name=INDEX_NAME,
        distance_metric="cosine",
        embedding=embeddings,
        region_name=REGION,
        non_filterable_metadata_keys=["_page_content"],   # chunk text: large, never filtered
        create_index_if_not_exist=True,                    # created on the first add
    )


# ---------------------------------------------------------------------------
# What's already in S3 Vectors?
# ---------------------------------------------------------------------------
def indexed_policies(vectorstore: AmazonS3Vectors) -> dict:
    """{source file: {"version_hash": ..., "keys": [vector keys]}} for everything in the index."""
    state, token = {}, None
    try:
        while True:
            kwargs = {"vectorBucketName": vectorstore.vector_bucket_name,
                      "indexName": vectorstore.index_name, "returnMetadata": True}
            if token:
                kwargs["nextToken"] = token
            page = vectorstore.client.list_vectors(**kwargs)
            for v in page.get("vectors", []):
                meta = v.get("metadata", {})
                entry = state.setdefault(meta.get("source", "?"), {"version_hash": meta.get("version_hash"), "keys": []})
                entry["keys"].append(v["key"])
            token = page.get("nextToken")
            if not token:
                break
    except vectorstore.client.exceptions.NotFoundException:
        return {}                      # first run: index doesn't exist yet
    return state


def version_hash(path: str, meta: dict) -> str:
    """Fingerprint of the PDF AND its metadata: changes if either changes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    h.update(json.dumps(meta, sort_keys=True).encode())
    return h.hexdigest()


def delete_chunks(vectorstore: AmazonS3Vectors, keys: list):
    if keys:
        vectorstore.delete(ids=keys)


# ---------------------------------------------------------------------------
# Ingest one policy
# ---------------------------------------------------------------------------
def ingest_policy(vectorstore: AmazonS3Vectors, path: str, meta: dict, vhash: str) -> int:
    filename = os.path.basename(path)
    pages = PyPDFLoader(path).load()
    chunks = splitter.split_documents(pages)

    for i, chunk in enumerate(chunks):
        chunk.metadata = {
            **meta,                                   # policy_name, policy_id, department, audience, effective_date
            "source": filename,
            "page": chunk.metadata.get("page", 0),
            "chunk_id": i,
            "version_hash": vhash,                    # which version of the policy this chunk came from
        }
        chunk.page_content = f"{meta['policy_name']} ({meta['policy_id']})\n{chunk.page_content}"

    vectorstore.add_documents(chunks, ids=[f"{filename}-chunk-{i}" for i in range(len(chunks))])
    print(f"  {filename}: {len(pages)} page(s), {len(chunks)} chunks, audience={meta['audience']}")
    return len(chunks)


def sync_policies(vectorstore: AmazonS3Vectors) -> dict:
    """Bring S3 Vectors in line with policies/ + policy_metadata.json. Returns a summary."""
    with open(METADATA_FILE, encoding="utf-8") as f:
        policy_meta = json.load(f)
    indexed = indexed_policies(vectorstore)
    pdfs = {os.path.basename(p): p for p in sorted(glob.glob(os.path.join(POLICY_DIR, "*.pdf")))}
    summary = {"new": [], "updated": [], "unchanged": [], "removed": []}

    for filename, path in pdfs.items():
        if filename not in policy_meta:
            print(f"SKIP {filename}: no entry in policy_metadata.json (unknown audience = not searchable)")
            continue
        vhash = version_hash(path, policy_meta[filename])
        old = indexed.get(filename)

        if old and old["version_hash"] == vhash:
            print(f"UNCHANGED {filename}")
            summary["unchanged"].append(filename)
            continue
        if old:
            print(f"UPDATED {filename}: deleting {len(old['keys'])} old chunks")
            delete_chunks(vectorstore, old["keys"])
            summary["updated"].append(filename)
        else:
            print(f"NEW {filename}")
            summary["new"].append(filename)
        ingest_policy(vectorstore, path, policy_meta[filename], vhash)

    # In the index but no longer a known policy (PDF deleted or metadata entry removed) -> remove
    for filename, entry in indexed.items():
        if filename not in pdfs or filename not in policy_meta:
            print(f"REMOVED {filename}: deleting {len(entry['keys'])} chunks")
            delete_chunks(vectorstore, entry["keys"])
            summary["removed"].append(filename)

    return summary


def quick_test(vectorstore: AmazonS3Vectors):
    """Check retrieval + the access-control filter."""
    q = "What is the salary revision budget?"
    for role, allowed in [("employee", ["all"]), ("manager", ["all", "managers"])]:
        docs = vectorstore.similarity_search(q, k=2, filter={"audience": {"$in": allowed}})
        print(f"[{role}] top results for '{q}': {[d.metadata.get('policy_id') for d in docs]}")
    # employee should NOT see HR-CONF-010; manager should


def main():
    vectorstore = get_vectorstore()
    summary = sync_policies(vectorstore)
    changed = summary["new"] or summary["updated"] or summary["removed"]

    print(f"\nSummary: {len(summary['new'])} new, {len(summary['updated'])} updated, "
          f"{len(summary['unchanged'])} unchanged, {len(summary['removed'])} removed")

    if changed:
        # Policies changed -> cached answers may be outdated, so invalidate the semantic cache
        SemanticCache(VECTOR_BUCKET, embeddings, REGION).clear()
        quick_test(vectorstore)
    else:
        print("No policy changes - nothing to do.")

    # Show the summary on the GitHub Actions run page
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("### Policy ingestion\n| Status | Policies |\n|---|---|\n")
            for k in ("new", "updated", "unchanged", "removed"):
                f.write(f"| {k} | {', '.join(summary[k]) or '-'} |\n")


if __name__ == "__main__":
    sys.exit(main())