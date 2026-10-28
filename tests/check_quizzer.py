"""Check the Quizzer's progress logic without API calls (the LLM is stubbed out).

Run: python -m tests.check_quizzer
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

from tutor import quizzer


def fake_llm(system, prompt, schema, **kwargs):
    if schema is quizzer.QUESTION_SCHEMA:
        # Label the topic by the cited file so we can tell where the chunk came from.
        label = prompt.split("\n", 1)[0]
        return {"usable": True, "question": f"Q about {label}?", "answer": "A", "topic": f"topic {label}"}
    return {"correct": "RIGHT" in prompt, "feedback": "stub"}


def main() -> None:
    path = Path(tempfile.mkdtemp()) / "progress.json"
    with patch.object(quizzer, "complete_json", fake_llm):
        # 1. Fresh start: random chunk, nothing to review.
        q1 = quizzer.next_question(path=path)
        assert q1["review_of"] is None
        quizzer.grade(q1, "wrong", path=path)
        assert quizzer.missed_topics(path) == [q1["topic"]], "miss not logged"

        # 2. A second miss on a different topic queues behind the first.
        q2 = quizzer.next_question(topic="singular value decomposition", path=path)
        quizzer.grade(q2, "wrong", path=path)
        assert quizzer.missed_topics(path) == [q1["topic"], q2["topic"]]

        # 3. Next quiz reviews the oldest missed topic first.
        q3 = quizzer.next_question(path=path)
        assert q3["review_of"] == q1["topic"], "missed topic not drawn first"

        # 4. Getting it wrong again moves it to the back and counts the miss.
        quizzer.grade(q3, "wrong", path=path)
        assert quizzer.missed_topics(path) == [q2["topic"], q1["topic"]]
        assert quizzer.load_progress(path)["missed"][1]["misses"] == 2

        # 5. Getting a review right removes it from the queue.
        q4 = quizzer.next_question(path=path)
        assert q4["review_of"] == q2["topic"]
        quizzer.grade(q4, "RIGHT", path=path)
        assert quizzer.missed_topics(path) == [q1["topic"]]

        # 6. Empty answers count as a miss without calling the grader.
        assert quizzer.grade(q4, "   ", path=path)["correct"] is False

        assert len(quizzer.load_progress(path)["history"]) == 5
    print("PASS: misses logged, missed topics drawn first, correct reviews cleared")


if __name__ == "__main__":
    main()
