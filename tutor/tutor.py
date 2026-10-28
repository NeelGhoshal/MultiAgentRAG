"""Tutor agent: retrieves chunks from the routed source and answers with citations.

Run: python -m tutor.tutor "What is the rank of a matrix?"
"""
from tutor.config import TOP_K
from tutor.ingest import get_collection
from tutor.llm import complete
from tutor.router import OFF_TOPIC_REPLY, route
from tutor.verifier import feedback, verify

SYSTEM = """You are a tutor for a "Mathematics for Machine Learning" course.
Answer the student's question using ONLY the course excerpts provided. Do not add facts, formulas or examples
that are not in the excerpts, even if you know them.

- After every claim, cite the excerpt it came from using its label exactly, e.g. [05_Eigenvalues.pdf p.12].
- Excerpts are extracted from PDFs, so math may be garbled; reconstruct notation only where the meaning is clear.
- If the excerpts don't contain enough to answer, say what is missing instead of guessing.
- Be concise and clear, like a good TA."""


def citation(meta: dict) -> str:
    return f"[{meta['file']} p.{meta['page']}]"


def retrieve(question: str, source: str, k: int = TOP_K) -> list[dict]:
    res = get_collection().query(query_texts=[question], n_results=k, where={"source": source})
    return [
        {"text": doc, "metadata": meta, "citation": citation(meta)}
        for doc, meta in zip(res["documents"][0], res["metadatas"][0])
    ]


def _prompt(question: str, chunks: list[dict], feedback: str | None) -> str:
    excerpts = "\n\n".join(f"{c['citation']}\n{c['text']}" for c in chunks)
    prompt = f"<excerpts>\n{excerpts}\n</excerpts>\n\nQuestion: {question}"
    if feedback:
        # Used by the Verifier's single retry (step 3).
        prompt += (f"\n\nA reviewer found these claims in your previous answer unsupported by the excerpts:\n"
                   f"{feedback}\nRewrite the answer so every claim is supported, or drop the claim.")
    return prompt


def answer(question: str, source: str, feedback: str | None = None,
           chunks: list[dict] | None = None) -> dict:
    """Returns {"answer": str, "chunks": [...]}. Pass `chunks` to reuse a previous retrieval."""
    chunks = chunks if chunks is not None else retrieve(question, source)
    if not chunks:
        return {"answer": OFF_TOPIC_REPLY, "chunks": []}
    return {"answer": complete(SYSTEM, _prompt(question, chunks, feedback)), "chunks": chunks}


def ask(question: str) -> dict:
    """Router -> Tutor -> Verifier, with at most one Tutor retry.

    Returns {"route", "answer", "chunks", "verdict", "retried", "first_answer"}.
    `verdict` is the Verifier's check of the first answer; the retry is not re-verified.
    """
    r = route(question)
    if r == "off_topic":
        return {"route": r, "answer": OFF_TOPIC_REPLY, "chunks": [], "verdict": None,
                "retried": False, "first_answer": None}

    first = answer(question, r)
    if not first["chunks"]:
        return {"route": r, **first, "verdict": None, "retried": False, "first_answer": None}

    verdict = verify(first["answer"], first["chunks"])
    result = {"route": r, **first, "verdict": verdict, "retried": False, "first_answer": first["answer"]}
    if not verdict["supported"]:
        retry = answer(question, r, feedback=feedback(verdict), chunks=first["chunks"])
        result.update(answer=retry["answer"], retried=True)
    return result


if __name__ == "__main__":
    import sys

    result = ask(" ".join(sys.argv[1:]) or "What is the rank of a matrix?")
    print(f"route: {result['route']}")
    if result["retried"]:
        print("verifier flagged:\n" + feedback(result["verdict"]))
        print(f"\nfirst answer:\n{result['first_answer']}\n\nafter retry:")
    print(f"\n{result['answer']}\n")
    for c in result["chunks"]:
        print("  source:", c["citation"])
