"""Embeddings.

An embedding maps text to a point in a high-dimensional space (1536-d for text-embedding-3-small)
such that semantically similar texts land close together. We compare points with cosine similarity
(angle between vectors), so two headlines about the same event score ~0.9+ even if worded differently,
while unrelated texts score ~0.2-0.4. This is the same primitive RAG uses to retrieve relevant chunks.
"""
from __future__ import annotations

import logging
from typing import Protocol

import openai
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.config import Settings

log = logging.getLogger(__name__)
MAX_CHARS = 8000  # ~2k tokens; well under the model's 8191-token input limit


def _is_transient(exc: BaseException) -> bool:
    """Retry rate limits and server/network errors, but NOT 'insufficient_quota' (the account is out of credit: retrying
    cannot help and only delays the error)."""
    if isinstance(exc, openai.RateLimitError):
        return getattr(exc, "code", None) != "insufficient_quota"
    return isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError))


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def embedding_input(title: str, summary: str) -> str:
    """Title first: it carries most of the signal and survives truncation."""
    return f"{title}\n\n{summary}"[:MAX_CHARS]


class OpenAIEmbedder:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = openai.OpenAI(api_key=settings.openai_api_key, max_retries=0)  # we own retries (below)
        self._model = settings.embedding_model
        self._batch = settings.embed_batch_size

    # Exponential backoff with jitter on rate limits / transient server errors.
    @retry(
        retry=retry_if_exception(_is_transient),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            out.extend(self._embed_batch(texts[i : i + self._batch]))
        return out
