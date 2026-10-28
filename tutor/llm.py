"""Thin wrapper around the Anthropic SDK shared by all agents."""
import json
from functools import cache

import anthropic
from dotenv import load_dotenv

from tutor.config import MODEL

load_dotenv()


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()

# If a safety classifier declines a request, the API re-runs it on Anthropic's
# recommended fallback model instead of returning a refusal.
_FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


def complete(system: str, prompt: str, *, effort: str = "medium", max_tokens: int = 16000,
             schema: dict | None = None) -> str:
    """One-shot call. Returns the text of the reply (valid JSON when `schema` is given)."""
    output_config = {"effort": effort}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    response = _client().beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config=output_config,
        **_FALLBACK,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Model declined the request (request id {response._request_id})")
    return "".join(b.text for b in response.content if b.type == "text")


def complete_json(system: str, prompt: str, schema: dict, **kwargs) -> dict:
    return json.loads(complete(system, prompt, schema=schema, **kwargs))
