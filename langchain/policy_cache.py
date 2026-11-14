"""
Semantic cache for the policy assistant — S3 Vectors only.

Index "policy-answer-cache" (same vector bucket as the policies):
  - vector:   embedding of the past standalone question
  - metadata: role        (filterable)  -> never reuse another role's answer
              created_at  (filterable)  -> expiry: only entries newer than 7 days are matched
              answer, sources, model_id (non-filterable) -> returned on a cache hit

Expiry: S3 Vectors has no TTL, so lookups filter on created_at >= now - 7 days.
Old entries are removed whenever policies are re-ingested (the whole index is deleted).
"""

import os
import time
import uuid

from langchain_aws.vectorstores import AmazonS3Vectors

CACHE_INDEX = "policy-answer-cache"
CACHE_TTL_DAYS = 7
# Cosine similarity needed to reuse an answer. Start strict; tune using the printed similarity.
MIN_SIMILARITY = float(os.getenv("CACHE_MIN_SIMILARITY", "0.92"))


class SemanticCache:
    def __init__(self, vector_bucket: str, embeddings, region: str):
        self.vectors = AmazonS3Vectors(
            vector_bucket_name=vector_bucket,
            index_name=CACHE_INDEX,
            distance_metric="cosine",
            embedding=embeddings,
            region_name=region,
            # Large fields we never filter on -> non-filterable (fixed when the index is created)
            non_filterable_metadata_keys=["_page_content", "answer", "sources", "model_id"],
            create_index_if_not_exist=True,
        )

    def lookup(self, question: str, role: str):
        """Return (cached_metadata or None, similarity or None)."""
        cutoff = int(time.time()) - CACHE_TTL_DAYS * 86400
        try:
            results = self.vectors.similarity_search_with_score(
                question, k=1,
                filter={"$and": [
                    {"role": {"$eq": role}},              # per-role cache
                    {"created_at": {"$gte": cutoff}},     # 7-day expiry
                ]},
            )
        except Exception:
            return None, None                             # cache index not created yet
        if not results:
            return None, None

        doc, distance = results[0]
        similarity = 1 - distance                         # cosine distance -> similarity
        if similarity < MIN_SIMILARITY:
            return None, similarity
        return doc.metadata, similarity                   # has "answer" and "sources"

    def save(self, question: str, role: str, answer: str, sources: list, model_id: str):
        self.vectors.add_texts(
            [question],
            metadatas=[{
                "role": role,
                "created_at": int(time.time()),
                "answer": answer,
                "sources": sources,
                "model_id": model_id,
            }],
            ids=[uuid.uuid4().hex],
        )

    def clear(self):
        """Invalidate the cache (called after policies are re-ingested)."""
        try:
            self.vectors.delete()            # ids=None -> delete the whole cache index
            print("Semantic cache cleared.")
        except Exception:
            pass                             # nothing to clear yet