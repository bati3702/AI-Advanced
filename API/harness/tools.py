from __future__ import annotations

from typing import Any, Dict, List

from shared.tools import StudyPlannerTools


def _log(msg: str) -> None:
    print(f"[API/harness/tools.py] {msg}")


def get_tool_specs() -> List[Dict[str, Any]]:
    specs = StudyPlannerTools.specs()
    _log(f"loaded {len(specs)} tool specs")
    return specs


def execute_tool(tools: StudyPlannerTools, name: str, tool_input: Dict[str, Any], tool_use_id: str | None = None) -> Dict[str, Any]:
    result = tools.dispatch(name, tool_input)
    _log(f"tool call -> {name}, ok={result.ok}, is_error={result.is_error}")
    payload = {
        "type": "tool_result",
        "tool_name": name,
        "is_error": result.is_error,
        "content": result.data,
    }
    if tool_use_id:
        payload["tool_use_id"] = tool_use_id
    return payload
