"""Thin wrapper around an OpenAI-compatible chat API, shared by all agents.

Defaults to the open-weight gpt-oss-120b model hosted on Groq (free tier); see tutor/config.py.
"""
import json
import os
from functools import cache

from dotenv import load_dotenv
from openai import OpenAI

from tutor.config import LLM_BASE_URL, MODEL

load_dotenv()


@cache
def _client() -> OpenAI:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env (see README > Setup).")
    return OpenAI(base_url=LLM_BASE_URL, api_key=key)


def complete(system: str, prompt: str, *, effort: str = "medium", max_tokens: int = 4096,
             schema: dict | None = None) -> str:
    """One-shot call. Returns the text of the reply (valid JSON when `schema` is given).

    `effort` (low | medium | high) sets gpt-oss's reasoning effort.
    """
    kwargs = {}
    if schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "output", "strict": True, "schema": schema},
        }
    response = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
        reasoning_effort=effort,
        **kwargs,
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise RuntimeError(f"Reply cut off at max_tokens={max_tokens}; raise it for this call.")
    return choice.message.content or ""


def complete_json(system: str, prompt: str, schema: dict, **kwargs) -> dict:
    return json.loads(complete(system, prompt, schema=schema, **kwargs))
