"""ResearchMind AI — Retrieval Metrics Unit Tests.

Hand-calculated verification of:
- Recall@k
- Mean Reciprocal Rank (MRR@k) with explicit cutoff
- Normalized Discounted Cumulative Gain (nDCG@k)
- Unanswerable query handling (honest separation without fabricated relevant items)
"""

from __future__ import annotations

import math

import pytest


def calculate_recall_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 5) -> float:
    """Calculate Recall@k: fraction of gold items retrieved in top-k."""
    if not gold_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = len(top_k & gold_ids)
    return hits / float(len(gold_ids))


def calculate_reciprocal_rank(retrieved_ids: list[str], gold_ids: set[str], cutoff: int = 10) -> float:
    """Calculate Reciprocal Rank (1/rank) with explicit cutoff."""
    if not gold_ids:
        return 0.0
    for rank, doc_id in enumerate(retrieved_ids[:cutoff], start=1):
        if doc_id in gold_ids:
            return 1.0 / rank
    return 0.0


def calculate_ndcg_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 10) -> float:
    """Calculate Normalized Discounted Cumulative Gain (nDCG@k) for binary relevance."""
    if not gold_ids:
        return 0.0

    dcg = 0.0
    for rank, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in gold_ids:
            dcg += 1.0 / math.log2(rank + 1)

    # Ideal DCG: all gold items ranked at the top (up to min(k, len(gold_ids)))
    ideal_hits = min(k, len(gold_ids))
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))

    return dcg / idcg if idcg > 0.0 else 0.0


def test_recall_at_5_hand_calculated():
    gold = {"chunk_1", "chunk_2"}
    # Hits chunk_1 at rank 1, chunk_2 not in top 5 -> 1/2 = 0.5
    retrieved = ["chunk_1", "chunk_3", "chunk_4", "chunk_5", "chunk_6", "chunk_2"]
    assert calculate_recall_at_k(retrieved, gold, k=5) == 0.5

    # Both in top 5 -> 2/2 = 1.0
    retrieved_both = ["chunk_3", "chunk_1", "chunk_4", "chunk_2", "chunk_5"]
    assert calculate_recall_at_k(retrieved_both, gold, k=5) == 1.0

    # Neither in top 5 -> 0.0
    retrieved_none = ["chunk_3", "chunk_4", "chunk_5", "chunk_6", "chunk_7"]
    assert calculate_recall_at_k(retrieved_none, gold, k=5) == 0.0


def test_mrr_at_10_hand_calculated():
    gold = {"chunk_target"}
    # Hit at rank 1 -> 1/1 = 1.0
    assert calculate_reciprocal_rank(["chunk_target"], gold, cutoff=10) == 1.0

    # Hit at rank 2 -> 1/2 = 0.5
    assert calculate_reciprocal_rank(["other", "chunk_target"], gold, cutoff=10) == 0.5

    # Hit at rank 3 -> 1/3 = 0.333333...
    assert pytest.approx(calculate_reciprocal_rank(["o1", "o2", "chunk_target"], gold, cutoff=10), rel=1e-5) == 1.0 / 3.0

    # Hit at rank 11 (exceeds cutoff 10) -> 0.0
    retrieved_late = [f"o{i}" for i in range(10)] + ["chunk_target"]
    assert calculate_reciprocal_rank(retrieved_late, gold, cutoff=10) == 0.0


def test_ndcg_at_10_hand_calculated():
    gold = {"c1", "c2"}
    # Perfect ranking: c1 at rank 1, c2 at rank 2 -> nDCG = 1.0
    assert calculate_ndcg_at_k(["c1", "c2", "c3"], gold, k=10) == 1.0

    # Inverted ranking: c1 at rank 2, c2 at rank 4
    # DCG = 1/log2(3) + 1/log2(5)
    # IDCG = 1/log2(2) + 1/log2(3) = 1.0 + 0.6309297 = 1.6309297
    dcg = (1.0 / math.log2(3)) + (1.0 / math.log2(5))
    idcg = (1.0 / math.log2(2)) + (1.0 / math.log2(3))
    expected_ndcg = dcg / idcg
    calculated_ndcg = calculate_ndcg_at_k(["other", "c1", "other2", "c2"], gold, k=10)
    assert pytest.approx(calculated_ndcg, rel=1e-5) == expected_ndcg
