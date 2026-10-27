"""Retrieval: pick the ~50 articles worth showing the LLM out of the ~1000 ingested this week.

This is the "R" in RAG (Retrieval-Augmented Generation). An LLM's context window is finite and
expensive, and its attention degrades on irrelevant text, so we *retrieve* a small, relevant evidence
set first and *augment* the prompt with it, instead of dumping everything in.

HOW EMBEDDING SIMILARITY WORKS HERE
Every article and every skill description is a vector (1536 numbers). We L2-normalise them so the dot
product of two vectors equals the cosine of the angle between them:  cos = a.b / (|a||b|) = a.b.
cos=1 means "same direction/meaning", ~0 means unrelated. `articles @ skills.T` therefore yields, in one
matrix multiply, how related each article is to each skill - no LLM call needed, milliseconds for 1000 rows.

The final score blends semantic relevance with cheap signals that embeddings can't see: source quality,
recency and community engagement. Weights are heuristics - tune them by reading what lands in the top 50.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from app.curriculum.types import Candidate, RankedArticle, Skill

W_RELEVANCE, W_QUALITY, W_RECENCY, W_ENGAGEMENT = 0.55, 0.15, 0.15, 0.15
RECENCY_HALF_LIFE_DAYS = 3.0


def _unit(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(n == 0, 1, n)


def rank_articles(
    candidates: list[Candidate],
    skills: list[Skill],
    *,
    top_n: int,
    max_per_source: int,
    now: datetime | None = None,
    exclude_ids: set[str] | None = None,
    skill_boost: dict[str, float] | None = None,
) -> list[RankedArticle]:
    """Return up to `top_n` articles, best first, labelled A1..An.

    skill_boost: multiply a skill's weight (e.g. {"rag": 1.25}) to bias retrieval toward today's focus.
    exclude_ids: article uuids that must not appear (e.g. already used as a reading).
    """
    now = now or datetime.now(timezone.utc)
    exclude_ids = exclude_ids or set()
    skill_boost = skill_boost or {}
    pool = [c for c in candidates if c.id not in exclude_ids]
    usable = [s for s in skills if s.embedding is not None]
    if not pool or not usable:
        return []

    articles = _unit(np.stack([c.embedding for c in pool]).astype(np.float32))   # (n, d)
    skill_m = _unit(np.stack([s.embedding for s in usable]).astype(np.float32))  # (k, d)
    sims = articles @ skill_m.T                                                  # (n, k) cosine similarities

    # A skill we're far from target on should attract more articles. 0.5 floor keeps maxed skills visible.
    weights = np.array([(0.5 + 0.5 * s.gap) * skill_boost.get(s.slug, 1.0) for s in usable], dtype=np.float32)
    weighted = sims * weights
    best = weighted.argmax(axis=1)
    relevance = weighted.max(axis=1)
    span = float(relevance.max() - relevance.min())
    relevance_norm = (relevance - relevance.min()) / span if span > 1e-9 else np.zeros_like(relevance)

    scored: list[tuple[float, int]] = []
    for i, c in enumerate(pool):
        age_days = max(0.0, (now - c.published_at).total_seconds() / 86400)
        recency = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
        engagement = min(1.0, math.log1p(c.engagement or 0) / math.log1p(1000))
        quality = min(1.0, c.source_weight / 1.5)
        scored.append((W_RELEVANCE * float(relevance_norm[i]) + W_QUALITY * quality
                       + W_RECENCY * recency + W_ENGAGEMENT * engagement, i))
    scored.sort(reverse=True)

    out: list[RankedArticle] = []
    per_source: Counter[str] = Counter()
    for score, i in scored:
        c = pool[i]
        if per_source[c.source_slug] >= max_per_source:
            continue
        per_source[c.source_slug] += 1
        out.append(RankedArticle(f"A{len(out) + 1}", c, round(score, 4), usable[int(best[i])].slug, float(sims[i, best[i]])))
        if len(out) == top_n:
            break
    return out
