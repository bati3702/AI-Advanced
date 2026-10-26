from __future__ import annotations

from typing import Any, Dict, List

from shared.state import StateStore


def _log(msg: str) -> None:
    print(f"[API/harness/context.py] {msg}")


def build_relevant_context(user_text: str, state_store: StateStore) -> Dict[str, Any]:
    state = state_store.load()
    lowered = user_text.lower()
    matched_courses = [c for c in state.courses if c["name"].lower() in lowered]
    if not matched_courses and state.courses:
        matched_courses = state.courses[:2]

    relevant = {
        "preferences": state.preferences,
        "courses": matched_courses,
        "recent_sessions": state.study_sessions[-3:],
        "recent_decisions": state.decisions[-5:],
    }
    _log("context built with compact relevant state")
    return relevant


def inject_context_message(messages: List[Dict[str, Any]], relevant: Dict[str, Any]) -> List[Dict[str, Any]]:
    context_message = {
        "role": "system",
        "content": f"RELEVANT_CONTEXT={relevant}",
    }
    _log("context injected")
    return [context_message] + messages
