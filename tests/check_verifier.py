"""Force a wrong answer and confirm the Verifier catches it and the retry fixes it.

Run: python -m tests.check_verifier
"""
from tutor.tutor import answer, retrieve
from tutor.verifier import feedback, verify

QUESTION = "What is the grading breakdown for this course?"
SOURCE = "lecture"

# Slides (01_Course_Introduction.pdf p.3): attendance 10%, assignments & quizzes 30%,
# midterm 30% (3 Nov. 2025), final 30% (29 Dec. 2025).
CORRECT = ("Attendance is 10%, assignments & quizzes 30%, the midterm exam 30% (3 Nov. 2025) and the "
           "final exam 30% (29 Dec. 2025) [01_Course_Introduction.pdf p.3].")
WRONG = ("The final exam is worth 50% and the midterm 20%, with a group project making up the remaining 30% "
         "[01_Course_Introduction.pdf p.3]. Attendance is not graded.")


def main() -> None:
    chunks = retrieve(QUESTION, SOURCE)
    assert any(c["citation"] == "[01_Course_Introduction.pdf p.3]" for c in chunks), "grading slide not retrieved"

    good = verify(CORRECT, chunks)
    print(f"Correct answer -> supported={good['supported']}")
    for c in good["unsupported_claims"]:
        print("   unexpected:", c)

    bad = verify(WRONG, chunks)
    print(f"\nWrong answer   -> supported={bad['supported']}\n{feedback(bad)}")

    fixed = answer(QUESTION, SOURCE, feedback=feedback(bad), chunks=chunks)
    recheck = verify(fixed["answer"], chunks)
    print(f"\nBEFORE:\n{WRONG}\n\nAFTER retry:\n{fixed['answer']}\n\nRetry -> supported={recheck['supported']}")
    for c in recheck["unsupported_claims"]:
        print("   still unsupported:", c)

    passed = good["supported"] and not bad["supported"] and recheck["supported"]
    print(f"\n{'PASS' if passed else 'FAIL'}: correct accepted, wrong caught, retry supported")


if __name__ == "__main__":
    main()
