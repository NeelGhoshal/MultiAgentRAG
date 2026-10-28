"""Verifier agent: checks a Tutor answer against the chunks it was given.

    verify(answer, chunks) -> {"supported": True, "unsupported_claims": []}
                           or {"supported": False, "unsupported_claims": ["claim ...", ...]}
"""
from tutor.llm import complete_json

SYSTEM = """You are a strict fact-checker for a course tutor.
You get course excerpts (each labelled like [file p.N]) and an answer written from them.
Split the answer into its factual claims and check each one against the excerpts only, not your own knowledge.

A claim is UNSUPPORTED if:
- no excerpt states or directly implies it (even if it is true in general), or
- it contradicts an excerpt (wrong numbers, definitions, conditions), or
- it cites an excerpt label that doesn't exist or doesn't contain that claim.

Not claims: statements that the excerpts don't cover something, restating the question, and harmless
connecting phrases. Reasonable reconstruction of garbled PDF math is fine if the meaning is clear.

For each unsupported claim, quote or closely paraphrase it and say briefly why it fails.
Set "supported" to true only if there are no unsupported claims."""

SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["supported", "unsupported_claims"],
    "additionalProperties": False,
}


def verify(answer: str, chunks: list[dict]) -> dict:
    excerpts = "\n\n".join(f"{c['citation']}\n{c['text']}" for c in chunks)
    prompt = f"<excerpts>\n{excerpts}\n</excerpts>\n\n<answer>\n{answer}\n</answer>"
    result = complete_json(SYSTEM, prompt, SCHEMA, effort="medium")
    # Keep the two fields consistent even if the model disagrees with itself.
    result["supported"] = result["supported"] and not result["unsupported_claims"]
    return result


def feedback(verdict: dict) -> str:
    return "\n".join(f"- {c}" for c in verdict["unsupported_claims"])
