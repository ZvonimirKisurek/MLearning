"""Builders for valid LLM outputs and synthetic articles."""
from datetime import datetime, timedelta, timezone

import numpy as np

from app.curriculum.types import Candidate, Skill


def weekly_dict(article_ids, skills=("rag", "vector-db")):
    ids = sorted(article_ids)
    return {
        "title": "Building RAG pipelines with PyTorch and pgvector",
        "rationale": "Retrieval is showing up in most of this week's engineering posts.",
        "market_signals": ["Vector search is moving into Postgres", "Teams are shipping RAG evals"],
        "focus_skills": list(skills),
        "learning_objectives": ["Chunk a document", "Store embeddings in pgvector", "Measure retrieval recall"],
        "key_article_ids": ids[:3],
        "daily_plan": [
            {"day": d, "focus": f"Day {d} focus", "skill_slug": skills[d % len(skills)],
             "intensity": "light" if d > 5 else "normal", "reading_hint": "an engineering post", "build_hint": "a small script"}
            for d in range(1, 8)
        ],
    }


def daily_dict(article_id, skill="rag", evidence=None, minutes=(20, 45)):
    return {
        "morning_reading": {"article_id": article_id, "skill_slug": skill, "difficulty": 2, "why_it_matters": "Explains chunking trade-offs.",
                            "guiding_questions": ["What chunk size do they use?", "How do they evaluate?"], "estimated_minutes": minutes[0]},
        "hands_on_task": {"title": "Chunk a PDF", "skill_slug": skill, "difficulty": 2, "objective": "Split a PDF into overlapping chunks.",
                          "prerequisites": ["Python 3.11"], "steps": ["Load the PDF", "Split by tokens", "Print stats"],
                          "deliverable": "chunk.py that prints chunk counts", "docs_to_consult": ["pypdf PdfReader"],
                          "estimated_minutes": minutes[1], "stretch_goal": None},
        "market_insight": {"headline": "Postgres is becoming the default vector store", "body": "Several posts describe pgvector in production.",
                           "career_angle": "Your Postgres skills transfer directly.", "skill_slug": "vector-db",
                           "evidence_article_ids": evidence or [article_id]},
    }


def unit_vec(rng, dim=1536):
    v = rng.normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def make_skills(rng, n_embedded=True):
    specs = [("pytorch", 20), ("rag", 25), ("vector-db", 35)]
    return [Skill(s, s.title(), lvl, 80, f"{s} things", unit_vec(rng) if n_embedded else None) for s, lvl in specs]


def make_candidate(i, rng, source="src", emb=None, age_days=1.0, engagement=None, weight=1.0):
    return Candidate(f"id-{i}", f"Title {i}", f"Summary {i}", f"https://x.test/{i}", datetime.now(timezone.utc) - timedelta(days=age_days),
                     source, source.title(), "engineering_blog", weight, engagement, emb if emb is not None else unit_vec(rng))
