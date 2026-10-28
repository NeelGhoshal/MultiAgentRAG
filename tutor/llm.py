"""Thin wrapper around a local Ollama model, shared by all agents.

Needs the Ollama app running and the model pulled: `ollama pull qwen3:8b` (see tutor/config.py).
"""
import json
from functools import cache

import ollama
from dotenv import load_dotenv

from tutor.config import MODEL, NUM_CTX

load_dotenv()  # picks up an optional OLLAMA_HOST from .env


@cache
def _client() -> ollama.Client:
    return ollama.Client()  # defaults to http://localhost:11434, or OLLAMA_HOST


def _think(effort: str) -> bool | str:
    # gpt-oss takes a reasoning level; other thinking models (qwen3, deepseek-r1) take on/off.
    if MODEL.startswith("gpt-oss"):
        return effort
    return effort != "low"


def complete(system: str, prompt: str, *, effort: str = "medium", max_tokens: int = 4096,
             schema: dict | None = None) -> str:
    """One-shot call. Returns the text of the reply (valid JSON when `schema` is given).

    `effort` (low | medium | high) controls how much the model reasons before answering.
    """
    try:
        response = _client().chat(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            format=schema,
            think=_think(effort),
            options={"num_predict": max_tokens, "num_ctx": NUM_CTX},
        )
    except ConnectionError as e:
        raise RuntimeError("Can't reach Ollama. Start the Ollama app (or run `ollama serve`).") from e
    except ollama.ResponseError as e:
        if e.status_code == 404:
            raise RuntimeError(f"Model {MODEL!r} isn't downloaded. Run: ollama pull {MODEL}") from e
        raise
    if response.done_reason == "length":
        raise RuntimeError(f"Reply cut off at max_tokens={max_tokens}; raise it for this call.")
    return response.message.content or ""


def complete_json(system: str, prompt: str, schema: dict, **kwargs) -> dict:
    return json.loads(complete(system, prompt, schema=schema, **kwargs))
