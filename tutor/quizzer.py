"""Quizzer agent: asks a question from a course chunk, grades the reply, logs missed topics.

    quiz = next_question()            # missed topics first, else a random chunk
    result = grade(quiz, "my answer") # -> {"correct", "feedback"}; updates progress.json

Run: python -m tutor.quizzer [topic]
"""
import json
import random
from datetime import date
from pathlib import Path

from tutor.config import PROGRESS_FILE
from tutor.ingest import get_collection
from tutor.llm import complete_json
from tutor.tutor import citation

MIN_CHUNK_CHARS = 400  # skip title/outline slides
MAX_TRIES = 5

QUESTION_SYSTEM = """You write quiz questions for a "Mathematics for Machine Learning" course.
You get one excerpt from the course materials. Write ONE short-answer question that:
- tests understanding of a concept, definition, property or method in the excerpt (not dates, names or slide layout);
- can be answered fully from the excerpt alone, in one to three sentences;
- does not mention "the excerpt", "the slide" or page numbers.
Also give the reference answer (from the excerpt) and a short topic label (2-6 words, e.g. "Gram-Schmidt process").
If the excerpt has no substantive content to ask about (title page, outline, references, garbled text),
set "usable" to false and leave the other fields empty."""

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "usable": {"type": "boolean"},
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "topic": {"type": "string"},
    },
    "required": ["usable", "question", "answer", "topic"],
    "additionalProperties": False,
}

GRADE_SYSTEM = """You grade a student's answer to a course quiz question.
Judge only against the course excerpt and reference answer. Accept any wording, notation or level of detail
that captures the key idea correctly; mark it incorrect if the key idea is missing, wrong, or only vaguely gestured at.
Feedback: 1-3 sentences, addressed to the student. If incorrect, explain what the right answer is,
citing the excerpt label given."""

GRADE_SCHEMA = {
    "type": "object",
    "properties": {"correct": {"type": "boolean"}, "feedback": {"type": "string"}},
    "required": ["correct", "feedback"],
    "additionalProperties": False,
}


# ---- progress.json ---------------------------------------------------------

def load_progress(path: Path = PROGRESS_FILE) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"missed": [], "history": []}


def save_progress(progress: dict, path: Path = PROGRESS_FILE) -> None:
    path.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def missed_topics(path: Path = PROGRESS_FILE) -> list[str]:
    return [m["topic"] for m in load_progress(path)["missed"]]


def _record(quiz: dict, correct: bool, path: Path) -> None:
    """Missed topics form a queue: a miss goes to the back, a correct review removes it."""
    progress = load_progress(path)
    topic = quiz["review_of"] or quiz["topic"]
    existing = next((m for m in progress["missed"] if m["topic"].lower() == topic.lower()), None)
    if existing:
        progress["missed"].remove(existing)
    if not correct:
        progress["missed"].append({
            "topic": topic,
            "misses": (existing["misses"] if existing else 0) + 1,
            "last_citation": quiz["citation"],
        })
    progress["history"].append({
        "date": date.today().isoformat(), "topic": quiz["topic"], "citation": quiz["citation"],
        "correct": correct,
    })
    save_progress(progress, path)


# ---- question selection ----------------------------------------------------

def _random_chunks():
    """Yield substantive chunks from the whole collection in random order."""
    res = get_collection().get(include=["documents", "metadatas"])
    pool = [(d, m) for d, m in zip(res["documents"], res["metadatas"]) if len(d) >= MIN_CHUNK_CHARS]
    random.shuffle(pool)
    yield from pool


def _topic_chunks(topic: str, k: int = 8):
    """Yield the chunks closest to `topic`, shuffled so repeat reviews get different questions."""
    res = get_collection().query(query_texts=[topic], n_results=k)
    pool = [(d, m) for d, m in zip(res["documents"][0], res["metadatas"][0]) if len(d) >= MIN_CHUNK_CHARS]
    random.shuffle(pool)
    yield from pool


def next_question(topic: str | None = None, path: Path = PROGRESS_FILE) -> dict:
    """Pick a chunk (explicit topic > oldest missed topic > random) and write a question from it.

    Returns {"question", "answer", "topic", "citation", "chunk", "review_of"}.
    `review_of` is the missed topic being reviewed, or None.
    """
    missed = missed_topics(path)
    review_of = None
    if topic is None and missed:
        topic = review_of = missed[0]
    chunks = _topic_chunks(topic) if topic else _random_chunks()

    for _, (text, meta) in zip(range(MAX_TRIES), chunks):
        label = citation(meta)
        q = complete_json(QUESTION_SYSTEM, f"{label}\n{text}", QUESTION_SCHEMA, effort="low")
        if q["usable"]:
            return {"question": q["question"], "answer": q["answer"], "topic": q["topic"],
                    "citation": label, "chunk": {"text": text, "metadata": meta}, "review_of": review_of}
    raise RuntimeError(f"Couldn't find a usable chunk for a question (topic={topic!r}).")


# ---- grading ---------------------------------------------------------------

def grade(quiz: dict, student_answer: str, path: Path = PROGRESS_FILE) -> dict:
    """Grade the reply, update progress.json, and return {"correct", "feedback"}."""
    if not student_answer.strip():
        result = {"correct": False, "feedback": f"No answer given. Reference answer: {quiz['answer']} {quiz['citation']}"}
    else:
        prompt = (f"<excerpt>\n{quiz['citation']}\n{quiz['chunk']['text']}\n</excerpt>\n\n"
                  f"Question: {quiz['question']}\nReference answer: {quiz['answer']}\n\n"
                  f"Student answer: {student_answer}")
        result = complete_json(GRADE_SYSTEM, prompt, GRADE_SCHEMA, effort="low")
    _record(quiz, result["correct"], path)
    return result


if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) or None
    while True:
        quiz = next_question(topic)
        tag = f"review: {quiz['review_of']}" if quiz["review_of"] else quiz["topic"]
        print(f"\n[{tag}]  {quiz['question']}")
        reply = input("> ")
        if reply.strip().lower() in {"q", "quit", "exit"}:
            break
        result = grade(quiz, reply)
        print(("Correct! " if result["correct"] else "Not quite. ") + result["feedback"])
        print(f"Missed topics: {missed_topics() or 'none'}")
        if input("\nAnother? [Y/n] ").strip().lower() == "n":
            break
