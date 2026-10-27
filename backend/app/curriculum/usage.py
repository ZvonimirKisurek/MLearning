"""Spend tracking and the in-app hard cap.

Defence in depth against a runaway bill: (1) provider-side limits on the API keys, (2) THIS ledger: every call is
recorded with its token counts and estimated cost, and a call is refused once the last 24 hours exceed
LLM_DAILY_BUDGET_USD, no matter what triggered it (a retry storm, a stuck scheduler, a button held down).
The estimate uses the price table below; update it when pricing changes. An unknown model is priced at the most
expensive tier so the guard errs on the safe side.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.curriculum.errors import LLMBudgetExceeded
from app.db import get_pool

log = logging.getLogger(__name__)

# USD per million tokens: (input, output). Thinking tokens are billed as output.
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0), "claude-fable-5-1": (10.0, 50.0),
}
UNKNOWN_MODEL_PRICE = (10.0, 50.0)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, UNKNOWN_MODEL_PRICE)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


def spent_last_24h() -> float:
    with get_pool().connection() as conn:
        return float(conn.execute("select coalesce(sum(cost_usd), 0) as s from llm_usage where at > now() - interval '24 hours'").fetchone()["s"])


class DbUsage:
    def __init__(self, settings: Settings) -> None:
        self._budget = settings.llm_daily_budget_usd

    def check(self) -> None:
        spent = spent_last_24h()
        if spent >= self._budget:
            raise LLMBudgetExceeded(f"spent ${spent:.2f} in the last 24h; cap is ${self._budget:.2f} (LLM_DAILY_BUDGET_USD). "
                                    "Run `python -m app.cli usage` to see where it went.")

    def record(self, purpose: str, model: str, input_tokens: int, output_tokens: int) -> None:
        try:  # never lose a paid-for answer because the ledger write failed
            with get_pool().connection() as conn:
                conn.execute("insert into llm_usage (purpose, model, input_tokens, output_tokens, cost_usd) values (%s,%s,%s,%s,%s)",
                             (purpose, model, input_tokens, output_tokens, round(estimate_cost(model, input_tokens, output_tokens), 5)))
        except Exception:
            log.exception("could not record LLM usage")


class NullUsage:
    def check(self) -> None: ...
    def record(self, *a, **k) -> None: ...


def usage_report(days: int = 7) -> str:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """select date_trunc('day', at)::date as day, purpose, model, count(*) calls, sum(input_tokens) in_tok,
                      sum(output_tokens) out_tok, sum(cost_usd) cost
               from llm_usage where at > now() - make_interval(days => %s) group by 1,2,3 order by 1 desc, 2""", (days,)).fetchall()
    lines = [f"{'day':10} {'purpose':22} {'model':18} {'calls':>5} {'in_tok':>9} {'out_tok':>9} {'cost$':>8}"]
    lines += [f"{r['day']} {r['purpose']:22} {r['model']:18} {r['calls']:5d} {r['in_tok']:9d} {r['out_tok']:9d} {float(r['cost']):8.4f}" for r in rows]
    lines.append(f"\nlast 7 days total: ${sum(float(r['cost']) for r in rows):.3f}   last 24h: ${spent_last_24h():.3f}")
    return "\n".join(lines)
