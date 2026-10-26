from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

import requests

from .state import PlannerState, StateStore


@dataclass
class ToolResult:
    ok: bool
    data: Dict[str, Any]
    is_error: bool = False


def compact_response(payload: Dict[str, Any], max_items: int = 4) -> Dict[str, Any]:
    compact = {}
    for key, value in payload.items():
        if isinstance(value, list):
            compact[key] = value[:max_items]
            compact[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            compact[key] = {k: value[k] for k in list(value.keys())[:8]}
        else:
            compact[key] = value
    return compact


class StudyPlannerTools:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    @staticmethod
    def specs() -> List[Dict[str, Any]]:
        return [
            {
                "name": "save_preference",
                "description": "Save user study preference (e.g., preferred study time).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "name": "add_course",
                "description": "Add a course with weekly target hours.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "weekly_hours": {"type": "number"},
                    },
                    "required": ["name", "weekly_hours"],
                },
            },
            {
                "name": "plan_study_session",
                "description": "Plan one study session for a course.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "course": {"type": "string"},
                        "duration_min": {"type": "number"},
                        "date": {"type": "string"},
                    },
                    "required": ["course", "duration_min", "date"],
                },
            },
            {
                "name": "web_lookup",
                "description": "External tool: fetch short study resource snippet from Wikipedia API.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "get_memory_snapshot",
                "description": "Return concise memory snapshot for context retrieval.",
                "input_schema": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"],
                },
            },
        ]

    def dispatch(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        state = self.store.load()
        handlers: Dict[str, Callable[[PlannerState, Dict[str, Any]], ToolResult]] = {
            "save_preference": self._save_preference,
            "add_course": self._add_course,
            "plan_study_session": self._plan_study_session,
            "web_lookup": self._web_lookup,
            "get_memory_snapshot": self._get_memory_snapshot,
        }
        if tool_name not in handlers:
            return ToolResult(ok=False, data={"error": f"Unknown tool: {tool_name}"}, is_error=True)
        try:
            result = handlers[tool_name](state, tool_input)
            self.store.save(state)
            return result
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, data={"error": str(exc)}, is_error=True)

    def _save_preference(self, state: PlannerState, payload: Dict[str, Any]) -> ToolResult:
        key = payload["key"].strip().lower()
        value = payload["value"].strip()
        state.preferences[key] = value
        self.store.append_decision(state, "preference_saved", f"{key}={value}")
        return ToolResult(ok=True, data=compact_response({"saved": {key: value}}))

    def _add_course(self, state: PlannerState, payload: Dict[str, Any]) -> ToolResult:
        course = {
            "name": payload["name"].strip(),
            "weekly_hours": float(payload["weekly_hours"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state.courses.append(course)
        self.store.append_decision(state, "course_added", course["name"])
        return ToolResult(ok=True, data=compact_response({"course": course, "all_courses": state.courses}))

    def _plan_study_session(self, state: PlannerState, payload: Dict[str, Any]) -> ToolResult:
        session = {
            "course": payload["course"].strip(),
            "duration_min": int(payload["duration_min"]),
            "date": payload["date"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state.study_sessions.append(session)
        self.store.append_decision(state, "study_session_planned", f"{session['course']}:{session['duration_min']}")
        return ToolResult(ok=True, data=compact_response({"session": session, "sessions": state.study_sessions}))

    def _web_lookup(self, state: PlannerState, payload: Dict[str, Any]) -> ToolResult:
        query = payload["query"].strip()
        response = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_"),
            headers={"User-Agent": "study-planner-copilot/1.0 (education-assignment)"},
            timeout=8,
        )
        if response.status_code != 200:
            return ToolResult(ok=False, data={"error": f"lookup failed: {response.status_code}"}, is_error=True)
        data = response.json()
        snippet = {
            "title": data.get("title", query),
            "extract": (data.get("extract") or "")[:320],
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        }
        state.decisions.append({"title": "resource_lookup", "details": query, "saved_at": datetime.now(timezone.utc).isoformat()})
        return ToolResult(ok=True, data=snippet)

    def _get_memory_snapshot(self, state: PlannerState, payload: Dict[str, Any]) -> ToolResult:
        topic = payload["topic"].lower()
        courses = [c for c in state.courses if topic in c["name"].lower()] if topic != "all" else state.courses
        sessions = [s for s in state.study_sessions if topic in s["course"].lower()] if topic != "all" else state.study_sessions
        return ToolResult(
            ok=True,
            data=compact_response(
                {
                    "preferences": state.preferences,
                    "courses": courses,
                    "study_sessions": sessions,
                    "decisions": state.decisions,
                }
            ),
        )
