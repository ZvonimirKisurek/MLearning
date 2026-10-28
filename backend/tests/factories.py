"""Builders for valid LLM outputs and synthetic articles."""
from datetime import datetime, timedelta, timezone

import numpy as np

from app.curriculum.types import Candidate, Skill


_SENTENCES = [
    "Representation learning turns raw inputs into vectors whose geometry reflects meaning, and that single idea underlies retrieval, ranking and generation.",
    "Two inputs that mean similar things should land close together, while unrelated inputs should land far apart in the learned space.",
    "An engineer should therefore treat an embedding model as a function with a measurable contract rather than as a black box that magically understands text.",
    "The cost of getting this wrong is silent: a retrieval system can look healthy in a demo and still miss half of the relevant documents in production.",
    "Measuring recall at a fixed cutoff gives a number that can be tracked across changes, which is the foundation of disciplined iteration on such systems.",
    "Each design decision, from chunk size to index parameters, shifts the balance between coverage and noise, and the balance must be chosen deliberately.",
]


def prose(words: int, cites=()) -> str:
    """Paragraphs of plain prose with at least `words` words; citations like [A1] are sprinkled in."""
    out, n, i, cites = [], 0, 0, list(cites)
    para = []
    while n < words:
        sent = _SENTENCES[i % len(_SENTENCES)]
        if cites and i % 4 == 0:
            sent = sent[:-1] + f" [{cites[(i // 4) % len(cites)]}]."
        para.append(sent)
        n += len(sent.split())
        i += 1
        if len(para) == 4:
            out.append(" ".join(para)); para = []
    if para:
        out.append(" ".join(para))
    return "\n\n".join(out)


def weekly_dict(article_ids, skills=("rag", "vector-db")):
    ids = sorted(article_ids, key=lambda x: (len(x), x))
    return {
        "title": "Building RAG pipelines with PyTorch and pgvector",
        "rationale": "Retrieval is showing up in most of this week's engineering posts.",
        "seminar_overview": prose(470, cites=ids[:3]),
        "core_questions": ["What makes two texts close in embedding space?", "How do we measure retrieval quality?", "When does hybrid search win?"],
        "market_signals": ["Vector search is moving into Postgres", "Teams are shipping RAG evals"],
        "focus_skills": list(skills),
        "learning_objectives": ["Chunk a document", "Store embeddings in pgvector", "Measure retrieval recall"],
        "key_article_ids": ids[:3],
        "daily_plan": [
            {"day": d, "focus": f"Day {d} focus", "skill_slug": skills[d % len(skills)],
             "intensity": "light" if d > 5 else "normal", "reading_hint": "a chapter on the concept", "build_hint": "a small script"}
            for d in range(1, 8)
        ],
    }


def rubric_dict():
    return {"pass_score": 6, "criteria": [
        {"name": "Correct cosine function", "description": "cosine(a, b) matches the definition on the test vectors", "max_points": 5, "must_pass": True},
        {"name": "Output consistent with code", "description": "pasted output matches what the code prints", "max_points": 3, "must_pass": False},
        {"name": "Tests included", "description": "at least two assertions or tests", "max_points": 2, "must_pass": False},
    ]}


def daily_dict(article_id, skill="rag", evidence=None, minutes=(30, 45)):
    """A valid DailyPlanOutput (stage 1 of the daily chain)."""
    return {
        "reading": {"chapter_title": "Embeddings and Cosine Similarity from Scratch", "skill_slug": skill, "difficulty": 2,
                    "learning_goals": ["Define an embedding", "Compute cosine similarity", "Explain why normalising matters"],
                    "sections": [{"heading": f"Section {i}", "key_points": "Establish the concept, the formula and a worked example.", "target_words": 240} for i in range(1, 9)],
                    "inspiration_article_ids": [article_id], "estimated_minutes": minutes[0]},
        "hands_on_task": {"title": "Chunk a PDF", "skill_slug": skill, "difficulty": 2, "objective": "Implement cosine similarity and test it.",
                          "prerequisites": ["Python 3.11"], "project_layout": ["lab/cosine.py", "lab/test_cosine.py"],
                          "steps": [{"title": f"Step {i}", "instructions": f"Create lab/file{i}.py and implement part {i}.", "commands": ["python lab/cosine.py"],
                                     "expected_output": "Prints 1.0 for identical vectors."} for i in range(1, 5)],
                          "deliverable": "cosine.py that prints similarities", "submission_instructions": "Paste cosine.py and the terminal output.",
                          "docs_to_consult": ["numpy.linalg.norm"], "estimated_minutes": minutes[1], "stretch_goal": None, "rubric": rubric_dict()},
        "market_insight": {"headline": "Postgres is becoming the default vector store", "thesis": "Teams consolidate vector search into Postgres.",
                           "skill_slug": "vector-db", "evidence_article_ids": evidence or [article_id]},
    }


def chapter_text(words: int = 1700, cites=("A1",)) -> str:
    sections = ["Why this exists", "Intuition", "The mathematics", "A worked example", "Implementation", "Pitfalls and failure modes", "In production"]
    per = max(60, words // len(sections))
    parts = []
    for i, h in enumerate(sections):
        parts.append(f"## {h}\n\n" + prose(per, cites=cites if i in (0, 6) else ()))
        if h == "The mathematics":
            parts.append("The similarity of two vectors is $\\cos\\theta = \\frac{a \\cdot b}{\\|a\\|\\|b\\|}$, which in display form reads\n\n$$\\cos\\theta = \\frac{\\sum_i a_i b_i}{\\sqrt{\\sum_i a_i^2}\\sqrt{\\sum_i b_i^2}}$$\n")
        if h in ("A worked example", "Implementation"):
            parts.append("```python\nimport numpy as np\n\n\ndef cosine(a, b):\n    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))\n\n\nprint(cosine(np.array([1.0, 0.0]), np.array([1.0, 1.0])))\n```\n")
    parts.append("## Check Your Understanding\n\n1. Why divide by the norms?\n2. What is the similarity of a vector with itself?\n3. When can cosine mislead?\n4. How would you test it?")
    return "\n\n".join(parts)


def essay_text(words: int = 520, cites=("A1", "A2")) -> str:
    return prose(words, cites=cites)


def evaluation_dict(rubric: dict, full: bool = True) -> dict:
    """A TaskEvaluationSchema payload whose score/passed are consistent with the rubric arithmetic."""
    from app.curriculum.schemas import CriterionResult, Rubric, compute_grade

    rb = Rubric.model_validate(rubric)
    criteria = [{"criterion": c.name, "points": c.max_points if full else 0, "max_points": c.max_points, "evidence": "line 3 of the submission"} for c in rb.criteria]
    score, passed = compute_grade(rb, [CriterionResult.model_validate(c) for c in criteria])
    return {"criteria": criteria, "score": score, "passed": passed,
            "summary": "Solid work." if passed else "The core computation is wrong.",
            "strengths": ["Clear structure"] if passed else ["You attempted every step"],
            "problems": [] if passed else ["cosine() never divides by the norms"],
            "how_to_improve": ["Add a test for orthogonal vectors"] if passed else ["Divide by np.linalg.norm(a) * np.linalg.norm(b)"],
            "feedback_markdown": "### What you did well\nClear.\n### What needs work and why\nNothing major.\n### How to fix it\nAdd tests."}


def unit_vec(rng, dim=1536):
    v = rng.normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def make_skills(rng, n_embedded=True):
    specs = [("pytorch", 20), ("rag", 25), ("vector-db", 35)]
    return [Skill(s, s.title(), lvl, 80, f"{s} things", unit_vec(rng) if n_embedded else None) for s, lvl in specs]


def make_candidate(i, rng, source="src", emb=None, age_days=1.0, engagement=None, weight=1.0):
    return Candidate(f"id-{i}", f"Title {i}", f"Summary {i}", f"https://x.test/{i}", datetime.now(timezone.utc) - timedelta(days=age_days),
                     source, source.title(), "engineering_blog", weight, engagement, emb if emb is not None else unit_vec(rng))
