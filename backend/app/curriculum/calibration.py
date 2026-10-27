"""Calibrating the relevance thresholds with YOUR judgement.

THE PROBLEM. Embedding similarity is a number (e.g. 0.37); "is this article worth my time?" is a yes/no.
A threshold turns one into the other, and every threshold is a trade-off between two kinds of mistake:

    precision = of the articles we SHOW, how many are actually relevant?   (high => little noise)
    recall    = of ALL relevant articles, how many do we show?              (high => we miss little)

Raise the threshold: fewer, purer results (precision up, recall down). Lower it: more coverage, more noise
(recall up, precision down). There is no free lunch; you choose a point on the curve according to which mistake
hurts more. F-beta scores combine both: beta=2 weights recall twice as much as precision, beta=0.5 the reverse.
We map that to the two UI buckets: "related" (moderate) = best F2 (don't miss things), "strong" = best F0.5
(be sure).

THE METHOD. You label a sample of real articles (without seeing their scores, to avoid anchoring). The sample is
stratified by equal-count similarity bins with one pick per bin, so every article has the same inclusion
probability: precision/recall computed on it are unbiased estimates for the whole feed, yet the whole similarity
range is covered. 40 labels give a rough answer; 100+ give a stable one (the table shows how few items sit behind
each number).
"""
from __future__ import annotations

import json
import random
from collections.abc import Callable
from pathlib import Path

from app.config import Settings, get_settings
from app.db import get_pool

CANDIDATES_SQL = """
select a.id::text as id, a.title, a.summary, s.name as source, best.slug as skill_slug, best.name as skill_name,
       best.sim::double precision as sim
from articles a join sources s on s.id = a.source_id
join lateral (select k.slug, k.name, 1 - (a.embedding <=> k.embedding) as sim from skills k
              where k.embedding is not null order by a.embedding <=> k.embedding limit 1) best on true
where a.duplicate_of is null and a.embedding is not null
  and coalesce(a.published_at, a.fetched_at) > now() - interval '14 days'
"""


def fetch_candidates() -> list[dict]:
    with get_pool().connection() as conn:
        return conn.execute(CANDIDATES_SQL).fetchall()


def stats_report(sims: list[float], settings: Settings | None = None) -> str:
    """How the best-skill similarity is distributed over recent articles, and what the current cutoffs do to it."""
    import numpy as np

    s = settings or get_settings()
    if not sims:
        return "no embedded articles in the last 14 days - run ingestion (and embed-skills) first"
    a = np.asarray(sims)
    q = np.percentile(a, [10, 25, 50, 75, 90, 99])
    strong = float((a >= s.match_strong).mean())
    related = float(((a >= s.match_moderate) & (a < s.match_strong)).mean())
    return "\n".join([
        f"articles (last 14 days, canonical): {len(a)}",
        "best-skill cosine similarity   p10    p25    p50    p75    p90    p99",
        "                               " + "  ".join(f"{x:.3f}" for x in q),
        f"current cutoffs: strong >= {s.match_strong}, moderate >= {s.match_moderate}",
        f"=> strong {strong:.0%} | moderate {related:.0%} | weak {1 - strong - related:.0%} of articles",
        "Rule of thumb before you have labels: strong ~5-10%, strong+moderate ~25-35%. Then run `calibrate`:",
        "your own judgement beats any rule of thumb."])


def stratified_sample(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Sort by similarity, cut into n equal-count bins, pick one at random from each."""
    if n >= len(rows):
        return list(rows)
    ordered = sorted(rows, key=lambda r: r["sim"])
    size = len(ordered) / n
    return [rng.choice(ordered[int(i * size): max(int((i + 1) * size), int(i * size) + 1)]) for i in range(n)]


def precision_recall(labeled: list[dict]) -> list[dict]:
    """For every distinct similarity used as a cutoff: what would precision/recall be if we showed sim >= cutoff?"""
    total_pos = sum(1 for r in labeled if r["relevant"])
    out = []
    for t in sorted({r["sim"] for r in labeled}):
        kept = [r for r in labeled if r["sim"] >= t]
        tp = sum(1 for r in kept if r["relevant"])
        p = tp / len(kept) if kept else 0.0
        rec = tp / total_pos if total_pos else 0.0
        out.append({"threshold": t, "kept": len(kept), "tp": tp, "precision": p, "recall": rec,
                    "f2": fbeta(p, rec, 2.0), "f05": fbeta(p, rec, 0.5)})
    return out


def fbeta(p: float, r: float, beta: float) -> float:
    return 0.0 if p + r == 0 else (1 + beta**2) * p * r / (beta**2 * p + r)


def recommend(labeled: list[dict]) -> dict:
    """moderate = cutoff maximising F2 (recall-leaning); strong = cutoff maximising F0.5 (precision-leaning)."""
    table = precision_recall(labeled)
    if not any(r["relevant"] for r in labeled):
        raise ValueError("no articles were labeled relevant - label more, or your skill descriptions need work")
    moderate = max(table, key=lambda r: (r["f2"], -r["threshold"]))
    strong = max(table, key=lambda r: (r["f05"], r["threshold"]))
    if strong["threshold"] < moderate["threshold"]:
        strong = moderate
    return {"moderate": moderate, "strong": strong, "table": table}


def label_interactively(n: int, path: Path, *, ask: Callable[[str], str] = input, rng: random.Random | None = None,
                        pool: list[dict] | None = None, show: Callable[[str], None] = print) -> list[dict]:
    """Show articles one by one (similarity hidden) and persist every answer, so you can quit and resume."""
    rng = rng or random.Random(7)
    labeled: list[dict] = json.loads(path.read_text()) if path.exists() else []
    done = {r["id"] for r in labeled}
    pool = [r for r in (pool if pool is not None else fetch_candidates()) if r["id"] not in done]
    show(f"{len(labeled)} labels already saved; sampling {max(0, n - len(labeled))} more from {len(pool)} candidates.")
    for r in stratified_sample(pool, max(0, n - len(labeled)), rng):
        show(f"\n[{len(labeled) + 1}/{n}] {r['source']}\n  {r['title']}\n  {(r['summary'] or '')[:240]}\n  best-matching skill: {r['skill_name']}")
        ans = ask("Would you want this in your learning feed?  [y]es / [n]o / [s]kip / [q]uit > ").strip().lower()
        if ans.startswith("q"):
            break
        if ans.startswith("s") or ans not in ("y", "n", "yes", "no"):
            continue
        labeled.append({"id": r["id"], "title": r["title"], "skill": r["skill_slug"], "sim": r["sim"], "relevant": ans.startswith("y")})
        path.write_text(json.dumps(labeled, indent=1))
    return labeled


def report(labeled: list[dict], settings: Settings | None = None) -> str:
    s = settings or get_settings()
    rec = recommend(labeled)
    pos = sum(1 for r in labeled if r["relevant"])
    lines = [f"{len(labeled)} labels, {pos} relevant ({pos / len(labeled):.0%} base rate)  <- what you'd get with NO filter: precision {pos / len(labeled):.2f}, recall 1.00",
             "", "cutoff  shown  precision  recall   F2    F0.5"]
    step = max(1, len(rec["table"]) // 14)
    for r in rec["table"][::step]:
        lines.append(f"{r['threshold']:.3f}  {r['kept']:5d}   {r['precision']:.2f}      {r['recall']:.2f}    {r['f2']:.2f}  {r['f05']:.2f}")
    m, st = rec["moderate"], rec["strong"]
    lines += ["", f"Currently: MATCH_MODERATE={s.match_moderate}  MATCH_STRONG={s.match_strong}",
              f"Suggested: MATCH_MODERATE={m['threshold']:.3f}  (precision {m['precision']:.2f}, recall {m['recall']:.2f})",
              f"           MATCH_STRONG={st['threshold']:.3f}  (precision {st['precision']:.2f}, recall {st['recall']:.2f})",
              "Put these in .env. Small samples are noisy: with <100 labels treat them as a starting point."]
    return "\n".join(lines)
