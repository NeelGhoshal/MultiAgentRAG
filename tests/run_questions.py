"""Run the hand-written test questions through Router -> Tutor.

Run: python -m tests.run_questions            (route + answer)
     python -m tests.run_questions --route    (routing only, cheaper)
"""
import json
import sys
from pathlib import Path

from tutor.router import route
from tutor.tutor import ask

QUESTIONS = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))


def main(route_only: bool) -> None:
    correct = 0
    for q in QUESTIONS:
        result = {"route": route(q["question"])} if route_only else ask(q["question"])
        ok = result["route"] == q["expected"]
        correct += ok
        print(f"{'PASS' if ok else 'FAIL'}  expected={q['expected']:9} got={result['route']:9}  {q['question']}")
        if not route_only:
            print("\n" + result["answer"] + "\n" + "-" * 80)
    print(f"\nRouting: {correct}/{len(QUESTIONS)} correct")


if __name__ == "__main__":
    main(route_only="--route" in sys.argv)
