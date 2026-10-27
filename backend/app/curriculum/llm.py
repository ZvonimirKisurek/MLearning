"""Anthropic client wrapper: schema-constrained generation + validation + repair loop.

Control flow of `StructuredLLM.generate`:

    prompt ──► Claude (JSON-schema constrained) ──► Pydantic validate (+ grounding context)
                    ▲                                     │ ok  ──► return typed object
                    │                                     │ fail
                    └──── append the model's answer and the exact validation errors ◄──┘  (max N times)

Why a repair loop? Constrained decoding guarantees the JSON *parses and has the right fields*, not that its
*values are acceptable* (an article id we never showed it, a URL, 9 steps when the limit is 8). Showing the
model its own output plus a precise error list is cheap and almost always fixes it on the first retry -
far more reliable than hoping a stricter prompt prevents every mistake.

Reliability layers: the SDK retries 429/5xx/connection errors with exponential backoff (llm_sdk_retries);
refusals and truncation are surfaced as typed errors rather than silently parsed; Celery adds an outer retry.
"""
from __future__ import annotations

import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.curriculum.errors import LLMBudgetExceeded, LLMError, LLMRefusal, LLMTruncated, LLMValidationFailed  # noqa: F401 (re-exported)
from app.curriculum.schemas import GroundingContext
from app.curriculum.usage import DbUsage

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)




def format_errors(exc: ValidationError) -> str:
    # Locations + messages only. Echoing input values could replay a large or injected payload back to the model.
    return "\n".join(f"- {'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}" for e in exc.errors())


class StructuredLLM:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None, usage=None) -> None:
        self._s = settings
        self._usage = usage or DbUsage(settings)
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key or None, max_retries=settings.llm_sdk_retries)

    def generate(self, *, system: str, user: str, output_model: type[T], grounding: GroundingContext,
                 model: str | None = None, effort: str | None = None) -> T:
        s = self._s
        # transform_schema = Pydantic JSON Schema minus constraints the API grammar can't express
        # (min/max/length); those remain enforced by Pydantic on our side.
        schema = anthropic.transform_schema(output_model)
        messages: list[dict] = [{"role": "user", "content": user}]
        last_errors = ""
        for attempt in range(s.llm_max_repairs + 1):
            kwargs: dict = dict(
                model=model or s.llm_model, max_tokens=s.llm_max_tokens, system=system, messages=messages,
                output_config={"effort": effort or s.llm_effort, "format": {"type": "json_schema", "schema": schema}},
            )
            self._usage.check()  # hard daily cap: refuse BEFORE spending, on every attempt including repairs
            resp = self._client.messages.create(**kwargs)
            self._usage.record(output_model.__name__, kwargs["model"], resp.usage.input_tokens, resp.usage.output_tokens)
            log.info("llm attempt=%d in=%s out=%s stop=%s", attempt, resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason)

            if resp.stop_reason == "refusal":
                raise LLMRefusal(f"model refused: {getattr(resp, 'stop_details', None)}")
            if resp.stop_reason == "max_tokens":
                raise LLMTruncated(f"output hit max_tokens={s.llm_max_tokens}; raise LLM_MAX_TOKENS or lower LLM_EFFORT")
            text = next((b.text for b in resp.content if b.type == "text"), "")
            try:
                return output_model.model_validate_json(text, context=grounding)
            except ValidationError as exc:
                last_errors = format_errors(exc)
                log.warning("validation failed (attempt %d):\n%s", attempt, last_errors)
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "Your JSON failed validation:\n" + last_errors
                     + "\nReturn the complete corrected JSON object."},
                ]
        raise LLMValidationFailed(f"still invalid after {s.llm_max_repairs} repairs:\n{last_errors}")
