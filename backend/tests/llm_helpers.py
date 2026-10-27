"""Build a REAL openai.OpenAI client whose HTTP layer is mocked, so tests exercise the SDK's request/response handling."""
import json

import httpx2
import openai

from app.config import Settings
from app.curriculum.llm import StructuredLLM


def completion(text="", finish="stop", refusal=None, prompt=10, out=5) -> dict:
    return {"id": "chatcmpl-1", "object": "chat.completion", "created": 0, "model": "gpt-4o",
            "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": text, "refusal": refusal}}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": out, "total_tokens": prompt + out}}


def make_llm(responses, captured=None, usage=None, **settings):
    """responses: list of completion() dicts, or (status, json_body) tuples for HTTP errors. Returns (llm, sent_requests)."""
    queue, sent = list(responses), []

    def handler(req: httpx2.Request):
        sent.append(json.loads(req.content))
        if captured is not None:
            captured.append(sent[-1])
        item = queue.pop(0)
        return httpx2.Response(item[0], json=item[1]) if isinstance(item, tuple) else httpx2.Response(200, json=item)

    client = openai.OpenAI(api_key="k", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    return StructuredLLM(Settings(openai_api_key="k", **settings), client=client, usage=usage), sent
