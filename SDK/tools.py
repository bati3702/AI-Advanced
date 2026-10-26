from __future__ import annotations

from typing import Any, Dict, List

from shared.tools import StudyPlannerTools


def build_sdk_toolset(shared_tools: StudyPlannerTools) -> Dict[str, Any]:
    return {
        "specs": StudyPlannerTools.specs(),
        "dispatch": shared_tools.dispatch,
    }


def execute_for_sdk(shared_tools: StudyPlannerTools, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    result = shared_tools.dispatch(tool_name, payload)
    return {
        "ok": result.ok,
        "is_error": result.is_error,
        "data": result.data,
    }
