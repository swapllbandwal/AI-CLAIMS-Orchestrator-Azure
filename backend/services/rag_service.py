"""In-memory RAG over the dummy JSON dataset.

Loads policies.json and past_claims.json at startup, embeds the searchable
text with sentence-transformers (local CPU, no API calls), and exposes simple
top-k cosine searches. Replaces the parent project's Qdrant usage with a
zero-dependency-network-call alternative — appropriate for the MVP demo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

log = logging.getLogger(__name__)


def _cosine_top_k(query_vec: np.ndarray, matrix: np.ndarray, k: int) -> List[int]:
    if matrix.size == 0:
        return []
    q = query_vec / (np.linalg.norm(query_vec) + 1e-12)
    norms = np.linalg.norm(matrix, axis=1) + 1e-12
    sims = matrix @ q / norms
    top = np.argsort(-sims)[:k]
    return top.tolist()


class RAGService:
    """Tiny on-disk RAG. Embeds once on init, then searches in memory."""

    def __init__(self, data_dir: Path, embedding_model_name: str):
        self.data_dir = Path(data_dir)
        self._model_name = embedding_model_name
        self._model = None  # lazy-loaded

        self.policies: List[Dict[str, Any]] = []
        self.past_claims: List[Dict[str, Any]] = []
        self.fraud_patterns: List[Dict[str, Any]] = []

        self._policy_vecs: Optional[np.ndarray] = None
        self._claim_vecs: Optional[np.ndarray] = None

    # ------------------------------------------------------------------------

    def initialize(self) -> None:
        """Load JSON files and pre-compute embeddings."""
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedding model: %s", self._model_name)
        self._model = SentenceTransformer(self._model_name)

        self.policies = self._load("policies.json")
        self.past_claims = self._load("past_claims.json")
        self.fraud_patterns = self._load("fraud_patterns.json")

        if self.policies:
            self._policy_vecs = self._embed([
                self._policy_text(p) for p in self.policies
            ])
        if self.past_claims:
            self._claim_vecs = self._embed([
                self._claim_text(c) for c in self.past_claims
            ])

        log.info(
            "RAG initialised: %d policies, %d past claims, %d fraud patterns",
            len(self.policies), len(self.past_claims), len(self.fraud_patterns),
        )

    def _load(self, filename: str) -> List[Dict[str, Any]]:
        path = self.data_dir / filename
        if not path.exists():
            log.warning("RAG data file missing: %s", path)
            return []
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _embed(self, texts: List[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, show_progress_bar=False), dtype=np.float32)

    # ------------------------------------------------------------------------

    @staticmethod
    def _policy_text(p: Dict[str, Any]) -> str:
        return (
            f"Policy {p.get('policy_number','')} for {p.get('holder_name','')}. "
            f"Type {p.get('coverage_type','')}, status {p.get('status','')}. "
            f"Notes: {p.get('notes','')}"
        )

    @staticmethod
    def _claim_text(c: Dict[str, Any]) -> str:
        return (
            f"Claim {c.get('claim_id','')} type {c.get('claim_type','')} "
            f"amount {c.get('amount', 0)} status {c.get('status','')}. "
            f"Description: {c.get('description','')}"
        )

    # ------------------------------------------------------------------------

    def find_policy(self, policy_number: str) -> Optional[Dict[str, Any]]:
        """Direct lookup by policy number — no embeddings needed."""
        for p in self.policies:
            if p.get("policy_number", "").upper() == policy_number.upper():
                return p
        return None

    def search_policies(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if self._policy_vecs is None or not self.policies:
            return []
        q_vec = self._embed([query])[0]
        idxs = _cosine_top_k(q_vec, self._policy_vecs, k)
        return [self.policies[i] for i in idxs]

    def similar_past_claims(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if self._claim_vecs is None or not self.past_claims:
            return []
        q_vec = self._embed([query])[0]
        idxs = _cosine_top_k(q_vec, self._claim_vecs, k)
        results = []
        for rank, i in enumerate(idxs):
            item = dict(self.past_claims[i])
            item["_rank"] = rank + 1
            results.append(item)
        return results
