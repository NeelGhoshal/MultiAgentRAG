"""Thin LLM wrapper shared by all agents.

Two backends, picked at runtime:
- Groq (hosted, free tier) when GROQ_API_KEY is set -- used by the Render deployment.
- A local Ollama model otherwise. Needs the Ollama app running and the model pulled:
  `ollama pull qwen3:8b` (see tutor/config.py).
"""
import json
import os
from functools import cache

from dotenv import load_dotenv

from tutor.config import GROQ_MODEL, MODEL, NUM_CTX

load_dotenv()  # picks up GROQ_API_KEY / OLLAMA_HOST from .env


def _use_groq() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


# ---- Groq --------------------------------------------------------------------

@cache
def _groq():
    from groq import Groq
    return Groq(max_retries=5)  # retries 429s with backoff; the free tier has low per-minute limits


def _complete_groq(system: str, prompt: str, effort: str, max_tokens: int, schema: dict | None) -> str:
    model = os.environ.get("GROQ_MODEL", GROQ_MODEL)
    kwargs = {}
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": schema, "strict": True},
        }
    if "gpt-oss" in model:
        kwargs["reasoning_effort"] = effort
        kwargs["include_reasoning"] = False
    response = _groq().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
        **kwargs,
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise RuntimeError(f"Reply cut off at max_tokens={max_tokens}; raise it for this call.")
    return choice.message.content or ""


# ---- Ollama ------------------------------------------------------------------

@cache
def _ollama():
    import ollama
    return ollama.Client()  # defaults to http://localhost:11434, or OLLAMA_HOST


def _think(effort: str) -> bool | str:
    # gpt-oss takes a reasoning level; other thinking models (qwen3, deepseek-r1) take on/off.
    if MODEL.startswith("gpt-oss"):
        return effort
    return effort != "low"


def _complete_ollama(system: str, prompt: str, effort: str, max_tokens: int, schema: dict | None) -> str:
    import ollama
    try:
        response = _ollama().chat(
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


# ---- Public API --------------------------------------------------------------

def complete(system: str, prompt: str, *, effort: str = "medium", max_tokens: int = 4096,
             schema: dict | None = None) -> str:
    """One-shot call. Returns the text of the reply (valid JSON when `schema` is given).

    `effort` (low | medium | high) controls how much the model reasons before answering.
    """
    backend = _complete_groq if _use_groq() else _complete_ollama
    return backend(system, prompt, effort, max_tokens, schema)


def complete_json(system: str, prompt: str, schema: dict, **kwargs) -> dict:
    return json.loads(complete(system, prompt, schema=schema, **kwargs))
