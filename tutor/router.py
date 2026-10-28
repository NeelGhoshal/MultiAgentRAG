"""Router agent: picks which course source to search, or rejects the question.

    route("What is the rank of a matrix?")  -> "lecture"
    route("Derive PCA as in the textbook")  -> "textbook"
    route("Best pizza in town?")            -> "off_topic"
"""
from typing import Literal

from tutor.config import DATA_DIR
from tutor.llm import complete_json

Route = Literal["lecture", "textbook", "off_topic"]

OFF_TOPIC_REPLY = "That's not covered in your course materials."

TEXTBOOK_CHAPTERS = [
    "Introduction and Motivation", "Linear Algebra", "Analytic Geometry", "Matrix Decompositions",
    "Vector Calculus", "Probability and Distributions", "Continuous Optimization",
    "When Models Meet Data", "Linear Regression", "Dimensionality Reduction with PCA",
    "Density Estimation with Gaussian Mixture Models", "Classification with Support Vector Machines",
]

SCHEMA = {
    "type": "object",
    "properties": {"route": {"type": "string", "enum": ["lecture", "textbook", "off_topic"]}},
    "required": ["route"],
    "additionalProperties": False,
}


def _lecture_titles() -> list[str]:
    # "05_Linear_Algebra_Eigenvalues.pdf" -> "05 Linear Algebra Eigenvalues"
    return [p.stem.replace("_", " ").strip() for p in sorted((DATA_DIR / "lecture").glob("*.pdf"))]


def _system_prompt() -> str:
    lectures = "\n".join(f"- {t}" for t in _lecture_titles())
    chapters = "\n".join(f"- Ch. {i}: {t}" for i, t in enumerate(TEXTBOOK_CHAPTERS, start=1))
    return f"""You route a student's question for a "Mathematics for Machine Learning" course tutor.
The course has two sources:

LECTURE SLIDES (one file per lecture):
{lectures}

TEXTBOOK (Deisenroth, Faisal & Ong, "Mathematics for Machine Learning"):
{chapters}

Pick exactly one route:
- "lecture": the question is about course material and is best answered from the slides. Use this when the
  student mentions the lecture, slides, class, or course logistics (grading, exams), and as the default for
  course topics that appear in the lecture list.
- "textbook": the student mentions the textbook, book, a chapter, section, example or exercise, asks for a
  full derivation or proof, or the topic only appears in the textbook (e.g. PCA, analytic geometry).
- "off_topic": the question is not about this course's material (other subjects, general chit-chat,
  machine learning topics outside the lists above such as transformers or reinforcement learning libraries,
  programming help unrelated to the math)."""


def route(question: str) -> Route:
    result = complete_json(_system_prompt(), question, SCHEMA, effort="low", max_tokens=4000)
    return result["route"]


if __name__ == "__main__":
    import sys

    print(route(" ".join(sys.argv[1:]) or "What is an eigenvector?"))
