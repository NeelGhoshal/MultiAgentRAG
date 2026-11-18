"""Streamlit UI: Ask, Quiz, and How it works tabs.

Run: streamlit run app.py
"""
import re
import time

import streamlit as st

from tutor.ingest import get_collection
from tutor.llm import backend_name
from tutor.quizzer import grade, load_progress, next_question
from tutor.tutor import ask

st.set_page_config(page_title="Course Tutor", page_icon="📐", layout="centered")

st.markdown("""
<style>
  .block-container { padding-top: 2.5rem; max-width: 820px; }
  h1 { font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0 !important; }
  [data-testid="stCaptionContainer"] { margin-bottom: 0.5rem; }
  .step { display: flex; gap: .6rem; align-items: baseline; padding: .15rem 0; font-size: .92rem; }
  .step .agent { font-weight: 600; min-width: 7.5rem; }
  .step .time { margin-left: auto; opacity: .55; font-variant-numeric: tabular-nums; }
</style>
""", unsafe_allow_html=True)

SAMPLE_QUESTIONS = {
    "📑 Lecture": [
        "What is the grading breakdown for this course?",
        "According to the slides, what is the Cholesky decomposition?",
        "What does the lecture say about the E-step and M-step of the EM algorithm?",
        "In the lecture slides, what is the policy gradient trick?",
    ],
    "📘 Textbook": [
        "How does the textbook derive PCA from the maximum variance perspective?",
        "What is the textbook's definition of a vector space?",
        "How is the Moore-Penrose pseudo-inverse used in linear regression?",
    ],
    "🚫 Off-topic (refused)": [
        "How does multi-head attention work in transformers?",
        "Who won the 2022 FIFA World Cup?",
    ],
}

QUIZ_TOPICS = ["Eigenvalues", "Singular value decomposition", "Gram-Schmidt", "Gradient descent",
               "Bayes' theorem", "Gaussian distribution", "Backpropagation", "Support vector machines",
               "Maximum likelihood estimation", "Convex optimization"]

AGENT_ICONS = {"Router": "🧭", "Retriever": "🔎", "Tutor": "📖", "Verifier": "✅", "Tutor (retry)": "🔁",
               "Quizzer": "❓", "Grader": "📝"}


@st.cache_resource
def chunk_counts() -> dict:
    col = get_collection()
    metas = col.get(include=["metadatas"])["metadatas"]
    return {"total": len(metas), "lecture": sum(m["source"] == "lecture" for m in metas),
            "textbook": sum(m["source"] == "textbook" for m in metas)}


def safely(fn, *args, **kwargs):
    """Run an agent call and show errors in the page instead of crashing it."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - UI boundary: surface anything (rate limit, ...)
        st.error(f"{type(e).__name__}: {e}")
        return None


def md_math(text: str) -> str:
    r"""LLMs often write LaTeX as \[...\] / \(...\); Streamlit only renders $$...$$ / $...$."""
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: f"$${m.group(1).strip()}$$", text, flags=re.S)
    return re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.S)


def step_html(entry: dict) -> str:
    icon = AGENT_ICONS.get(entry["agent"], "•")
    detail = re.sub(r"`([^`]+)`", r"<code>\1</code>", entry["detail"])  # raw HTML: markdown isn't parsed
    return (f'<div class="step"><span class="agent">{icon} {entry["agent"]}</span>'
            f'<span>{detail}</span><span class="time">{entry["seconds"]:.1f}s</span></div>')


def render_trace(trace: list[dict], label: str = "Agent calls") -> None:
    total = sum(e["seconds"] for e in trace)
    with st.expander(f"{label} · {len(trace)} steps · {total:.1f}s"):
        st.markdown("".join(step_html(e) for e in trace), unsafe_allow_html=True)


def timed(agent: str, fn, describe, *args):
    start = time.perf_counter()
    out = safely(fn, *args)
    if out is None:
        return None, None
    return out, {"agent": agent, "detail": describe(out), "seconds": round(time.perf_counter() - start, 1)}


# ---- Header & sidebar ------------------------------------------------------

st.title("📐 Course Tutor")
st.caption("A multi-agent RAG tutor for *Mathematics for Machine Learning*. It answers only from the lecture "
           "slides and textbook, cites every claim, checks its own answers, and quizzes you on what you missed.")

with st.sidebar:
    st.subheader("Missed topics")
    missed = load_progress()["missed"]
    if missed:
        for m in missed:
            st.markdown(f"**{m['topic']}** ×{m['misses']}  \n<small>{m['last_citation']}</small>",
                        unsafe_allow_html=True)
        st.caption("The next quiz with no topic reviews these first.")
    else:
        st.caption("None yet. Topics you get wrong in the Quiz tab show up here.")
    st.divider()
    st.subheader("Under the hood")
    st.markdown(f"**Model:** {backend_name()}")
    try:
        n = chunk_counts()
        st.markdown(f"**Index:** {n['total']:,} chunks  \n{n['lecture']:,} lecture · {n['textbook']:,} textbook")
    except Exception:  # noqa: BLE001 - informational only
        st.markdown("**Index:** not built yet. Run `python -m tutor.ingest`.")

ask_tab, quiz_tab, how_tab = st.tabs(["💬 Ask", "🎯 Quiz", "⚙️ How it works"])

# ---- Ask -------------------------------------------------------------------

def _pick_sample(key: str) -> None:
    st.session_state.pending_question = st.session_state[key]
    st.session_state[key] = None


with ask_tab:
    st.markdown("##### Try an example")
    for i, (group, questions) in enumerate(SAMPLE_QUESTIONS.items()):
        st.pills(group, questions, key=f"sample_{i}", on_change=_pick_sample, args=(f"sample_{i}",))

    with st.form("ask", border=False):
        typed = st.text_input("Or ask your own", placeholder="e.g. What is the rank of a matrix?")
        submitted = st.form_submit_button("Ask", type="primary")

    question = st.session_state.pop("pending_question", None) or (typed.strip() if submitted else None)
    if question:
        st.session_state.ask_question = question
        with st.status("Running agents…", expanded=True) as status:
            box = st.empty()
            live = []

            def on_step(entry):
                live.append(step_html(entry))
                box.markdown("".join(live), unsafe_allow_html=True)

            result = safely(ask, question, on_step=on_step)
            status.update(label="Done" if result else "Failed", state="complete" if result else "error",
                          expanded=False)
        st.session_state.ask_result = result

    result = st.session_state.get("ask_result")
    if result:
        st.markdown(f"#### {st.session_state.ask_question}")
        route = result["route"]
        verdict = result["verdict"]
        badges = {"lecture": ("Lecture slides", "blue"), "textbook": ("Textbook", "violet"),
                  "off_topic": ("Off-topic", "gray")}
        text, color = badges[route]
        row = f":{color}-badge[Source: {text}]"
        if verdict and not result["retried"]:
            row += " :green-badge[✓ Verified]"
        elif verdict:
            row += f" :orange-badge[Revised after {len(verdict['unsupported_claims'])} flagged claim(s)]"
        st.markdown(row)

        with st.container(border=True):
            st.markdown(md_math(result["answer"]))

        render_trace(result["trace"])
        if result["retried"]:
            with st.expander("What the Verifier caught"):
                st.markdown("**First draft:**")
                st.markdown(md_math(result["first_answer"]))
                st.markdown("**Unsupported claims:**")
                for c in verdict["unsupported_claims"]:
                    st.markdown(f"- {c}")
        if result["chunks"]:
            with st.expander(f"Retrieved excerpts ({len(result['chunks'])})"):
                for c in result["chunks"]:
                    st.markdown(f"**{c['citation']}**")
                    st.caption(c["text"])

# ---- Quiz ------------------------------------------------------------------

def _new_quiz(topic: str | None) -> None:
    label = f"from “{topic}”" if topic else "(missed topics first, else random)"
    with st.spinner(f"Quizzer is writing a question {label}…"):
        quiz, entry = timed("Quizzer", next_question,
                            lambda q: f"wrote a question from {q['citation']}"
                                      + (f" (reviewing “{q['review_of']}”)" if q["review_of"] else ""),
                            topic)
    st.session_state.quiz = quiz
    st.session_state.quiz_trace = [entry] if entry else []
    st.session_state.grade = None


def _pick_topic() -> None:
    st.session_state.pending_topic = st.session_state.topic_pill or ""
    st.session_state.topic_pill = None


with quiz_tab:
    st.markdown("##### Pick a topic")
    st.pills("Topics", QUIZ_TOPICS, key="topic_pill", on_change=_pick_topic, label_visibility="collapsed")
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    custom = c1.text_input("Or type one", placeholder="Leave empty to review missed topics first")
    if c2.button("Quiz me", type="primary", use_container_width=True):
        st.session_state.pending_topic = custom.strip()

    if "pending_topic" in st.session_state:
        _new_quiz(st.session_state.pop("pending_topic") or None)

    quiz = st.session_state.get("quiz")
    if quiz:
        tag = f":orange-badge[Review: {quiz['review_of']}]" if quiz["review_of"] else f":blue-badge[{quiz['topic']}]"
        st.markdown(tag)
        with st.container(border=True):
            st.markdown(f"**{md_math(quiz['question'])}**")

        graded = st.session_state.get("grade")
        with st.form("answer", border=False):
            reply = st.text_area("Your answer", disabled=graded is not None, height=110)
            if st.form_submit_button("Submit", type="primary", disabled=graded is not None):
                with st.spinner("Grader is checking your answer…"):
                    graded, entry = timed("Grader", grade,
                                          lambda g: ("correct" if g["correct"] else "incorrect, topic logged")
                                          + " · progress.json updated", quiz, reply)
                if graded:
                    st.session_state.grade = graded
                    st.session_state.quiz_trace.append(entry)
                    st.rerun()  # refresh the sidebar's missed topics

        if graded:
            lead = "Correct!" if graded["correct"] else "Not quite."
            fb = re.sub(rf"^\s*{re.escape(lead)}\s*", "", graded["feedback"])  # the grader often opens with it too
            (st.success if graded["correct"] else st.error)(f"**{lead}** {md_math(fb)}")
            with st.expander("Reference answer"):
                st.markdown(f"{quiz['answer']} {quiz['citation']}")
            if st.button("Next question →"):
                st.session_state.pending_topic = ""
                st.rerun()
        if st.session_state.get("quiz_trace"):
            render_trace(st.session_state.quiz_trace)

# ---- How it works ----------------------------------------------------------

with how_tab:
    st.markdown("Four small agents, each one call to the model, built on a single Chroma vector index of the "
                "course PDFs. Every chunk is tagged with its `source` (lecture or textbook), file and page.")
    st.graphviz_chart("""
digraph {
  rankdir=LR; bgcolor="transparent";
  node [shape=box style="rounded,filled" fillcolor="#eef2ff" color="#6366f1" fontname="Helvetica" fontsize=11];
  edge [color="#94a3b8" fontname="Helvetica" fontsize=9];
  Q [label="Question" shape=oval fillcolor="#f1f5f9" color="#94a3b8"];
  R [label="🧭 Router"]; T [label="📖 Tutor"]; V [label="✅ Verifier"];
  DB [label="Chroma\\nlecture + textbook" shape=cylinder fillcolor="#f0fdf4" color="#22c55e"];
  OFF [label="“Not covered in your\\ncourse materials.”" shape=note fillcolor="#fef2f2" color="#ef4444"];
  A [label="Cited answer" shape=oval fillcolor="#f0fdf4" color="#22c55e"];
  Q -> R; R -> OFF [label="off_topic"]; R -> T [label="lecture | textbook"];
  DB -> T [label="top-5 chunks\\nwhere source=route" style=dashed];
  T -> V; V -> A [label="supported"];
  V -> T [label="unsupported\\n(1 retry)" color="#f97316" fontcolor="#f97316"];
}
""")
    st.markdown("""
| Agent | What it does |
|---|---|
| 🧭 **Router** | Classifies the question as `lecture`, `textbook` or `off_topic`. This doubles as the relevance check: off-topic questions get a fixed refusal and never reach retrieval. |
| 📖 **Tutor** | Searches the vector index *only within the routed source* and answers strictly from those excerpts, citing `[file p.N]` after each claim. |
| ✅ **Verifier** | Checks each claim in the answer against the same excerpts. If any is unsupported, the Tutor gets **one** retry with that feedback, and never more. |
| ❓ **Quizzer** | Writes a question from a course chunk (a topic you pick, else your oldest missed topic, else random), grades your reply, and logs misses to `progress.json`. |
""")
    st.markdown("##### Design choices")
    st.markdown("""
- **Grounded by construction:** the Tutor sees only retrieved excerpts, and the Verifier audits it against them.
- **Bounded loops:** at most one retry, so cost and latency stay predictable.
- **Deliberately simple:** plain vector search with Chroma's default embeddings, one collection, and a JSON file for progress.
- **Structured outputs:** the Router, Verifier and Quizzer reply in strict JSON schemas, so there's no parsing guesswork.
""")
    st.caption("Open the *Agent calls* panel under any answer or quiz to see each step and how long it took.")
