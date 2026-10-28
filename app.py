"""Streamlit UI with Ask and Quiz tabs.

Run: streamlit run app.py
"""
import streamlit as st

from tutor.quizzer import grade, load_progress, next_question
from tutor.tutor import ask

st.set_page_config(page_title="Course Tutor", page_icon="📐")
st.title("Course Tutor")
st.caption("Answers only from your lecture slides and textbook, and quizzes you on them.")


def safely(fn, *args, **kwargs):
    """Run an agent call and show errors in the page instead of crashing it."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - UI boundary: surface anything (missing key, rate limit, ...)
        st.error(f"{type(e).__name__}: {e}")
        return None


with st.sidebar:
    st.header("Missed topics")
    missed = load_progress()["missed"]
    if missed:
        for m in missed:
            st.markdown(f"- **{m['topic']}** ×{m['misses']}  \n  <small>{m['last_citation']}</small>",
                        unsafe_allow_html=True)
    else:
        st.write("None yet.")

ask_tab, quiz_tab = st.tabs(["Ask", "Quiz"])

# ---- Ask -------------------------------------------------------------------
with ask_tab:
    with st.form("ask"):
        question = st.text_input("Your question", placeholder="What is the Cholesky decomposition?")
        submitted = st.form_submit_button("Ask")
    if submitted and question.strip():
        with st.spinner("Routing, retrieving, answering, verifying..."):
            st.session_state.ask_result = safely(ask, question)

    result = st.session_state.get("ask_result")
    if result:
        st.markdown(f"**Source:** `{result['route']}`")
        st.markdown(result["answer"])

        verdict = result["verdict"]
        if verdict and not result["retried"]:
            st.success("Verifier: every claim is supported by the retrieved excerpts.")
        elif verdict:
            st.warning(f"Verifier flagged {len(verdict['unsupported_claims'])} claim(s); "
                       "the answer above is the Tutor's single retry.")
            with st.expander("What the Verifier caught"):
                st.markdown("**First answer:**")
                st.markdown(result["first_answer"])
                st.markdown("**Unsupported claims:**")
                for c in verdict["unsupported_claims"]:
                    st.markdown(f"- {c}")

        if result["chunks"]:
            with st.expander(f"Retrieved excerpts ({len(result['chunks'])})"):
                for c in result["chunks"]:
                    st.markdown(f"**{c['citation']}**")
                    st.text(c["text"])

# ---- Quiz ------------------------------------------------------------------
with quiz_tab:
    topic = st.text_input("Topic (optional)", placeholder="Leave empty to review missed topics first")
    if st.button("New question"):
        with st.spinner("Writing a question..."):
            st.session_state.quiz = safely(next_question, topic.strip() or None)
        st.session_state.grade = None

    quiz = st.session_state.get("quiz")
    if quiz:
        label = f"Review: {quiz['review_of']}" if quiz["review_of"] else quiz["topic"]
        st.markdown(f"**{label}**")
        st.markdown(quiz["question"])

        graded = st.session_state.get("grade")
        with st.form("answer"):
            reply = st.text_area("Your answer", disabled=graded is not None)
            if st.form_submit_button("Submit", disabled=graded is not None):
                with st.spinner("Grading..."):
                    st.session_state.grade = graded = safely(grade, quiz, reply)
                if graded:
                    st.rerun()  # refresh the sidebar's missed topics

        if graded:
            (st.success if graded["correct"] else st.error)(
                ("Correct! " if graded["correct"] else "Not quite. ") + graded["feedback"])
            with st.expander("Reference answer"):
                st.markdown(f"{quiz['answer']} {quiz['citation']}")
