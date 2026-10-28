# Course Tutor — Multi-Agent RAG

A tutor that answers questions only from the course's own lecture notes and textbook, and quizzes the student on them.

## Agents (4)

| Agent | Input | Output | Notes |
|---|---|---|---|
| **Router** | user question | `lecture` \| `textbook` \| `off_topic` | Also acts as the relevance check. `off_topic` → fail-safe reply: "That's not covered in your course materials." |
| **Tutor** | question + route | answer with citations `[file p.N]` | Vector search in Chroma filtered by `where={"source": route}`. Answers only from retrieved chunks. |
| **Verifier** | answer + retrieved chunks | `supported` or a list of unsupported claims | If anything is unsupported, the Tutor gets **one** retry with that feedback. Never loops more than once. |
| **Quizzer** | topic (or none) | question → grade → log | Generates a question from a random chunk, grades the student's reply, appends missed topics to `progress.json`. The next quiz draws from missed topics first. |

## Flow

```
Question → Router ─┬─ off_topic → fail-safe message
                   └─ lecture/textbook → Tutor → Verifier ─┬─ ok → answer
                                                           └─ unsupported → Tutor (1 retry) → answer
Quiz mode: Quizzer picks topic (missed first) → asks → grades → updates progress.json
```

## Deliberately kept simple

- Plain vector search (Chroma default embeddings). No BM25 or hybrid search.
- One Chroma collection; each chunk's `source` metadata is `lecture` or `textbook`.
- Progress is a JSON file, not a database.
- Evaluation is ~15 hand-written test questions, not a formal eval suite.

## Layout

```
data/lecture/*.pdf     lecture notes
data/textbook/*.pdf    textbook
tutor/config.py        paths, model, chunk settings
tutor/ingest.py        PDF → chunks → Chroma (python -m tutor.ingest)
tutor/llm.py           shared Anthropic call helper (complete / complete_json)
tutor/router.py        Router agent: route(question) -> lecture | textbook | off_topic
tutor/tutor.py         Tutor agent: retrieve(), answer(), ask() = Router -> Tutor -> Verifier (1 retry)
tutor/verifier.py      Verifier agent: verify(answer, chunks) -> {supported, unsupported_claims}
tests/questions.json   15 test questions (5 lecture, 5 textbook, 5 off_topic)
tests/run_questions.py python -m tests.run_questions [--route]
tests/check_verifier.py forced wrong answer must be caught (python -m tests.check_verifier)
tutor/quizzer.py       Quizzer agent: next_question(topic?) -> grade(quiz, reply); CLI: python -m tutor.quizzer
tests/check_quizzer.py offline check of progress.json logic, LLM stubbed (python -m tests.check_quizzer)
app.py                 Streamlit UI with Ask and Quiz tabs (step 5)
chroma_db/             persisted vector store (gitignored)
progress.json          {"missed": [queue of {topic, misses, last_citation}], "history": [...]} (gitignored)
```

## Conventions

- LLM: Anthropic Python SDK, model `claude-opus-5-5` (set in `tutor/config.py`). Key comes from `ANTHROPIC_API_KEY` in `.env`.
- Chunk metadata: `source`, `file`, `page`, `chunk_id`. Citations are built from `file` + `page`.
- Re-running ingestion rebuilds the collection from scratch.
