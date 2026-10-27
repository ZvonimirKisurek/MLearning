"""Run the real FastAPI app against a throwaway embedded Postgres+pgvector seeded with DEMO data.

    python scripts/demo_server.py [--port 8000]

No API keys, Docker or network needed - handy for building/looking at the UI. The articles are made up and their
"embeddings" are synthetic (random vectors nudged toward a skill vector), so relevance badges are illustrative only.
"""
import argparse
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# (title, source, category, skill, closeness 0.15 weak / 0.27 moderate / 0.38 strong, engagement, hours_ago, excerpt, ai_summary)
ARTICLES = [
    ("Chunking strategies for production RAG", "LlamaIndex Blog", "engineering_blog", "rag", 0.38, None, 5,
     "We compare fixed-size, recursive and semantic chunking across three corpora.",
     "Compares fixed-size, recursive and semantic chunking on three corpora; recursive splitting with overlap gave the best recall per token."),
    ("pgvector 0.8: iterative index scans and better filtered search", "pgvector Releases", "engineering_blog", "vector-db", 0.38, 212, 9,
     "Release notes for pgvector 0.8.", "Release notes: iterative HNSW scans fix under-filled results when a WHERE clause is selective."),
    ("Writing a training loop from scratch in PyTorch", "Sebastian Raschka", "researcher", "pytorch", 0.38, None, 14,
     "A walkthrough of autograd, optimizers and mixed precision.",
     "Walks through autograd, optimizers, gradient accumulation and mixed precision by building a loop without a trainer abstraction."),
    ("Hybrid search: when BM25 still beats embeddings", "Qdrant Articles", "engineering_blog", "rag", 0.27, 88, 20,
     "Lexical and dense retrieval complement each other.", "Argues that fusing BM25 with dense retrieval (RRF) fixes exact-term queries that embeddings miss."),
    ("Show HN: A tiny vector database in 500 lines of Rust", "Show HN - AI", "community", "vector-db", 0.27, 341, 26,
     "HN discussion (57 comments)", "Show HN project implementing HNSW in ~500 lines of Rust; discussion focuses on memory layout and recall."),
    ("LoRA vs full fine-tuning: what the new evidence says", "Hugging Face Blog", "engineering_blog", "llm-finetuning", 0.38, None, 30,
     "New experiments on rank, alpha and target modules.", "Experiments suggest LoRA matches full fine-tuning on most tasks if rank and target modules are chosen carefully."),
    ("Serving LLMs with vLLM: continuous batching explained", "NVIDIA Technical Blog", "engineering_blog", "mlops", 0.38, None, 33,
     "How continuous batching raises GPU utilisation.", "Explains continuous batching and paged attention, and why they raise throughput for variable-length requests."),
    ("Evaluating RAG: retrieval metrics are not enough", "Hamel Husain", "researcher", "llm-evals", 0.38, None, 40,
     "Why recall@k can look great while answers are wrong.", "Shows why recall@k can hide bad answers and proposes grading groundedness and answer relevance separately."),
    ("Attention Is Still All You Need: a 2026 retrospective", "arXiv cs.LG", "research", "classical-ml", 0.15, 54, 44,
     "A retrospective on transformer scaling.", "Retrospective on transformer scaling laws and what changed since 2017; mostly historical context."),
    ("OpenAI ships new embedding models with 3x cheaper pricing", "TechCrunch AI", "industry_news", "vector-db", 0.27, None, 47,
     "The company announced updated embedding models.", "OpenAI released cheaper embedding models; the post lists pricing and dimension options but no benchmark details."),
    ("OpenAI ships new embedding models", "The Verge AI", "industry_news", "vector-db", 0.27, None, 46, "Pricing and availability.", None),
    ("How Netflix serves personalised rows with a hybrid retrieval stack", "Netflix TechBlog", "engineering_blog", "rag", 0.27, 160, 52,
     "Candidate generation and re-ranking at scale.", "Describes candidate generation with embeddings followed by learned re-ranking, and the latency budget for each stage."),
    ("A gentle introduction to gradient boosting", "Machine Learning Mastery", "research", "classical-ml", 0.38, None, 60,
     "Trees, residuals and shrinkage.", "Beginner-friendly tour of boosting: fit trees to residuals, shrink each step, and tune depth and learning rate."),
    ("MLflow 3: tracing and evaluation for GenAI apps", "MLflow Blog", "engineering_blog", "mlops", 0.27, None, 66,
     "Tracing, prompt versioning and evals in one place.", "Adds tracing and evaluation primitives for LLM apps next to the classic experiment-tracking API."),
    ("Ask HN: how are you evaluating LLM features in production?", "Hacker News - LLM", "community", "llm-evals", 0.27, 420, 70,
     "HN discussion (212 comments)", "Thread collecting practices: golden sets, LLM-as-judge with spot checks, and shadow deployments."),
    ("Why your fine-tune forgot everything: catastrophic forgetting", "Interconnects", "newsletter", "llm-finetuning", 0.27, None, 75,
     "Mixing replay data and lowering the learning rate.", "Practical tips against catastrophic forgetting: replay data, lower learning rates and freezing early layers."),
    ("The Batch: agents, open weights and a quiet week for chips", "The Batch", "newsletter", "rag", 0.15, None, 80, "This week in AI.", None),
    ("Quantization 101: int8, int4 and what you lose", "Philipp Schmid", "researcher", "mlops", 0.27, None, 90,
     "A practical look at quantised inference.", "Practical overview of int8/int4 quantisation: memory savings, typical accuracy loss and when to use each."),
    ("A weekend project: semantic search over my notes with pgvector", "DEV - rag", "community", "vector-db", 0.38, 36, 96,
     "Embedding markdown files and querying them.", "Hands-on post embedding markdown notes with OpenAI embeddings and querying them through pgvector and SQL."),
]
# Filler so the feed spans more than one page (default page size is 20) and "Load more" can be tried.
_TOPICS = [("rag", "retrieval"), ("pytorch", "PyTorch"), ("mlops", "model serving"), ("llm-evals", "LLM evals"), ("vector-db", "vector search"), ("llm-finetuning", "fine-tuning")]
ARTICLES += [
    (f"Weekly roundup #{n}: {t}", "Latent Space", "newsletter", sk, 0.15 + 0.06 * (n % 3), None, 100 + n * 5,
     f"Links and commentary on {t}.", f"Collection of links and short commentary about {t}, with no single deep dive.")
    for n, (sk, t) in enumerate(_TOPICS * 3, start=1)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-briefing", action="store_true", help="skip today's briefing to see the empty state")
    args = ap.parse_args()

    import pixeltable_pgserver as pgs

    server = pgs.get_server(tempfile.mkdtemp(prefix="mle-demo-pg-"), cleanup_mode="stop")
    uri = server.get_uri()
    with psycopg.connect(uri, autocommit=True) as c:
        for m in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
            c.execute(m.read_text())
    os.environ["DATABASE_URL"] = uri
    os.environ.setdefault("TIMEZONE", "UTC")

    from app.config import Settings, get_settings
    from app.curriculum import generators
    from app.db import get_pool
    from app.ingestion import repository as irepo
    from app.ingestion.models import RawItem, SourceSpec

    get_settings.cache_clear()
    rng = np.random.default_rng(42)
    unit = lambda v: (v / np.linalg.norm(v)).astype(np.float32)  # noqa: E731

    skill_vecs = {}
    with get_pool().connection() as conn:
        for r in conn.execute("select slug from skills").fetchall():
            skill_vecs[r["slug"]] = unit(rng.normal(size=1536))
            conn.execute("update skills set embedding=%s where slug=%s", (skill_vecs[r["slug"]], r["slug"]))

    specs = {}
    for a in ARTICLES:
        specs.setdefault(a[2:3] + (a[1],), SourceSpec(slug=re.sub(r"[^a-z0-9]+", "-", a[1].lower()).strip("-"), name=a[1], category=a[2], url="https://example.test/feed"))
    irepo.upsert_sources(specs.values())
    states = irepo.load_source_states()
    now = datetime.now(timezone.utc)
    ids = {}
    for i, (title, src, cat, skill, close, eng, hrs, excerpt, ai) in enumerate(ARTICLES):
        slug = re.sub(r"[^a-z0-9]+", "-", src.lower()).strip("-")
        is_dup = title == "OpenAI ships new embedding models"
        base = skill_vecs[skill] if not is_dup else None
        vec = unit(close * skill_vecs[skill] + (1 - close) * unit(rng.normal(size=1536))) if not is_dup else ids["emb"]
        item = RawItem(title=title, url=f"https://example.test/{i}", summary=excerpt, published_at=now - timedelta(hours=hrs), engagement=eng)
        dup_of = ids["openai"] if is_dup else None
        new_id = irepo.insert_article(states[slug].id, item, item.url, f"demo{i}", vec.tolist(), dup_of, 0.97 if is_dup else None)
        if title.startswith("OpenAI ships new embedding models with"):
            ids["openai"], ids["emb"] = new_id, vec
        if ai:
            with get_pool().connection() as conn:
                conn.execute("update articles set ai_summary=%s, ai_summary_at=now() where id=%s", (ai, new_id))

    class DemoLLM:
        """Stands in for Claude: writes plausible, schema-valid content from the prompt it is given."""
        def generate(self, *, system, user, output_model, grounding, **_):
            arts = re.findall(r'<article id="(A\d+)"[^>]*related_skill="([^"]+)">\n<title>(.*?)</title>', user)
            if output_model.__name__ == "WeeklyThemeOutput":
                plan = [("Understand embeddings and cosine similarity", "vector-db", "normal"), ("Chunk documents and store vectors in pgvector", "rag", "normal"),
                        ("Implement hybrid retrieval (BM25 + dense)", "rag", "stretch"), ("Write a PyTorch training loop for a tiny reranker", "pytorch", "normal"),
                        ("Evaluate retrieval with recall@k and groundedness", "llm-evals", "normal"), ("Wire retrieval into a small FastAPI endpoint", "mlops", "light"),
                        ("Review the week and write up what you learned", "rag", "light")]
                d = {"title": "Build a retrieval pipeline on pgvector and measure it",
                     "rationale": "Several engineering posts this week show teams moving retrieval into Postgres and measuring it properly. Your Postgres strength lets you move fast while closing the RAG, vector-DB and evaluation gaps.",
                     "market_signals": ["pgvector keeps gaining features for filtered search", "Teams are adding retrieval-specific evals, not just answer quality", "Hybrid BM25 + dense retrieval is becoming the default"],
                     "focus_skills": ["rag", "vector-db"],
                     "learning_objectives": ["Explain cosine similarity and HNSW trade-offs", "Chunk and embed a corpus into pgvector", "Measure recall@k before and after hybrid search"],
                     "key_article_ids": [a[0] for a in arts[:3]],
                     "daily_plan": [{"day": i + 1, "focus": f, "skill_slug": s, "intensity": it, "reading_hint": "an engineering post on this topic", "build_hint": "a small, runnable script"} for i, (f, s, it) in enumerate(plan)]}
            else:
                rid, rskill, rtitle = arts[0]
                d = {"morning_reading": {"article_id": rid, "skill_slug": rskill if rskill in grounding.skill_slugs else "rag", "difficulty": 2,
                                         "why_it_matters": "Directly relevant to this week's retrieval theme and the trade-offs you will hit when you chunk your own documents.",
                                         "guiding_questions": ["Which design choice drives most of the result?", "How would you measure it on your own data?", "What would you try differently?"], "estimated_minutes": 25},
                     "hands_on_task": {"title": "Chunk a PDF and store the embeddings in pgvector", "skill_slug": "rag", "difficulty": 2,
                                       "objective": "Split a PDF into overlapping chunks, embed them, and answer a query with a cosine-similarity SQL lookup.",
                                       "prerequisites": ["Python 3.11", "Postgres with pgvector"],
                                       "steps": ["Extract text from a PDF you care about", "Split into ~400-token chunks with 50-token overlap", "Embed each chunk and INSERT into a vector(1536) column", "Query the 5 nearest chunks with ORDER BY embedding <=> query", "Print the chunks and judge whether they answer the question"],
                                       "deliverable": "chunk_and_search.py that prints the top-5 chunks for a query", "docs_to_consult": ["pypdf PdfReader", "pgvector HNSW index"], "estimated_minutes": 55,
                                       "stretch_goal": "Add a BM25 score and fuse the two rankings with reciprocal rank fusion."},
                     "market_insight": {"headline": "Postgres is becoming the default vector store for product teams", "body": "Multiple recent posts describe pgvector in production, and releases keep improving filtered search - the main reason teams used to reach for a dedicated vector database.",
                                        "career_angle": "Your Postgres and Supabase experience transfers directly; retrieval engineering is a credible bridge into ML engineering roles.", "skill_slug": "vector-db", "evidence_article_ids": [a[0] for a in arts[1:3]] or [rid]}}
            return output_model.model_validate(d, context=grounding)

    s = Settings(timezone="UTC", min_candidates=5)
    if not args.no_briefing:
        generators.generate_daily_briefing(llm=DemoLLM(), embedder=None, settings=s)
    # history so the skill chart has something to show
    with get_pool().connection() as conn:
        for slug, lvl in {"pytorch": 24.5, "classical-ml": 31, "rag": 33.2, "vector-db": 41.8, "llm-finetuning": 12.4, "mlops": 33, "llm-evals": 19.1}.items():
            conn.execute("update skills set level=%s where slug=%s", (lvl, slug))
            for d in (6, 4, 2):
                conn.execute("insert into skill_history (skill_id, level, delta, recorded_at) select id, %s, 0.6, now() - %s * interval '1 day' from skills where slug=%s", (lvl - d * 0.3, d, slug))

    import uvicorn
    from app.main import create_app

    print(f"\nDEMO API ready on http://localhost:{args.port}  (docs at /docs)  - Ctrl+C to stop\n", flush=True)
    try:
        uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        server.cleanup()


if __name__ == "__main__":
    main()
