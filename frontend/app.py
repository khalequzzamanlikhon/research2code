"""
Streamlit UI: task input -> live progress -> approve/reject gate -> report.

Run with:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from graph.build_graph import build_graph  # noqa: E402
from graph.state import new_state  # noqa: E402

st.set_page_config(page_title="Research → Code → Review", layout="wide")
st.title("Research → Code → Review Agent Pipeline")

if "app" not in st.session_state:
    st.session_state.app = build_graph()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = None

app = st.session_state.app

with st.sidebar:
    st.subheader("Run config")
    max_iters = st.slider("Max coder/reviewer retries", 1, 5, 3)
    if st.session_state.thread_id:
        st.caption(f"thread_id: `{st.session_state.thread_id}`")

task = st.text_area("Describe the task", placeholder="e.g. Implement an LRU cache and write tests for it")

if st.button("Run", disabled=st.session_state.awaiting_approval is not None):
    st.session_state.thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    with st.spinner("Running research → coder → reviewer..."):
        result = app.invoke(new_state(task, max_iterations=max_iters), config=config)

    state = app.get_state(config)
    if state.next and "human_approval" in state.next:
        st.session_state.awaiting_approval = state.tasks[0].interrupts[0].value
    else:
        st.session_state.final_report = result.get("final_report")

if st.session_state.awaiting_approval:
    payload = st.session_state.awaiting_approval
    st.warning("Human approval required before writing code to disk / executing further.")
    if payload.get("last_test_result"):
        st.write("Last test result:", payload["last_test_result"])
    st.code(payload["code"], language="python")

    feedback = st.text_input("Feedback (optional)")
    col1, col2 = st.columns(2)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    if col1.button("✅ Approve"):
        result = app.invoke(Command(resume={"approved": True, "feedback": feedback or None}), config=config)
        st.session_state.awaiting_approval = None
        st.session_state.final_report = result.get("final_report")
        st.rerun()

    if col2.button("❌ Reject"):
        result = app.invoke(Command(resume={"approved": False, "feedback": feedback or None}), config=config)
        st.session_state.awaiting_approval = None
        st.session_state.final_report = result.get("final_report")
        st.rerun()

if st.session_state.get("final_report"):
    st.subheader("Final Report")
    st.markdown(st.session_state.final_report)
