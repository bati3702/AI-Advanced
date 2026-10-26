from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from API.agent import AgentConfig
from API.harness.history import HistoryStore
from API.harness.loop import AgentLoop
from API.harness.memory import create_state_store
from shared.tools import StudyPlannerTools


class FakeMessagesClient:
    def __init__(self) -> None:
        self.call_index = 0

    def create_message(self, model: str, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], effort: str) -> Dict[str, Any]:
        self.call_index += 1
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                last_user = msg["content"]
                break

        tool_results = self._extract_latest_tool_results(messages)
        if tool_results:
            text = self._final_text_from_results(last_user, tool_results)
            return self._text_response(text, input_tokens=220, output_tokens=95)

        tool_call = self._decide_tool_call(last_user)
        if tool_call:
            return {
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": 260,
                    "cache_read_input_tokens": 60,
                    "cache_creation_input_tokens": 30,
                    "output_tokens": 40,
                },
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"toolu_{self.call_index}",
                        "name": tool_call["name"],
                        "input": tool_call["input"],
                    }
                ],
            }

        return self._text_response("I can help with your study planning.", input_tokens=180, output_tokens=60)

    @staticmethod
    def _extract_latest_tool_results(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not messages:
            return []
        msg = messages[-1]
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            blocks = msg["content"]
            if blocks and isinstance(blocks[0], dict) and blocks[0].get("type") == "tool_result":
                return blocks
        return []

    @staticmethod
    def _final_text_from_results(last_user: str, tool_results: List[Dict[str, Any]]) -> str:
        payload = tool_results[0].get("content", {}) if tool_results else {}
        if "error" in payload:
            return f"Tool failed: {payload['error']}"
        return f"Done. Based on your request '{last_user[:80]}', I used tools and updated memory safely."

    @staticmethod
    def _decide_tool_call(user_text: str) -> Dict[str, Any] | None:
        txt = user_text.lower()
        if any(k in txt for k in ["תשמור", "remember", "preference", "העדפה"]):
            key = "preferred_study_time"
            value = "evening"
            if "בוקר" in txt or "morning" in txt:
                value = "morning"
            if "ערב" in txt or "evening" in txt:
                value = "evening"
            return {"name": "save_preference", "input": {"key": key, "value": value}}
        if any(k in txt for k in ["קורס", "course", "add course"]):
            course = "Algorithms"
            match = re.search(r"course[:\s]+([a-zA-Z\s]+)", user_text, flags=re.IGNORECASE)
            if match:
                course = match.group(1).strip()
            if "מסדי" in txt:
                course = "Databases"
            return {"name": "add_course", "input": {"name": course, "weekly_hours": 6}}
        if any(k in txt for k in ["schedule", "session", "לימוד", "מפגש"]):
            return {
                "name": "plan_study_session",
                "input": {"course": "Algorithms", "duration_min": 90, "date": "2026-10-27"},
            }
        if any(k in txt for k in ["ויקיפד", "resource", "search", "חפש", "lookup"]):
            query = "Pomodoro Technique"
            if "database" in txt or "מסדי" in txt:
                query = "Database"
            return {"name": "web_lookup", "input": {"query": query}}
        if any(k in txt for k in ["מה אתה זוכר", "memory", "remembered", "זוכר"]):
            return {"name": "get_memory_snapshot", "input": {"topic": "all"}}
        return None

    @staticmethod
    def _text_response(text: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        return {
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "output_tokens": output_tokens,
            },
            "content": [{"type": "text", "text": text}],
        }


class OpenAIMessagesClient:
    def __init__(self, api_key: str) -> None:
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _convert_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for tool in tools:
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
            )
        return converted

    @staticmethod
    def _convert_messages(system: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if isinstance(content, str):
                converted.append({"role": role, "content": content})
                continue
            if isinstance(content, list):
                if role == "assistant":
                    text_parts = [b.get("text", "") for b in content if b.get("type") == "text" and b.get("text")]
                    tool_uses = [b for b in content if b.get("type") == "tool_use"]
                    assistant_msg: Dict[str, Any] = {"role": "assistant"}
                    if text_parts:
                        assistant_msg["content"] = "\n".join(text_parts)
                    if tool_uses:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": b.get("id") or f"call_{idx}",
                                "type": "function",
                                "function": {
                                    "name": b.get("name"),
                                    "arguments": json.dumps(b.get("input", {}), ensure_ascii=False),
                                },
                            }
                            for idx, b in enumerate(tool_uses)
                        ]
                    converted.append(assistant_msg)
                elif role == "user":
                    tool_results = [b for b in content if b.get("type") == "tool_result"]
                    if tool_results:
                        for idx, b in enumerate(tool_results):
                            converted.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": b.get("tool_use_id") or f"tool_res_{idx}",
                                    "content": json.dumps(b.get("content", {}), ensure_ascii=False),
                                }
                            )
        return converted

    def create_message(self, model: str, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], effort: str) -> Dict[str, Any]:
        prepared_messages = self._convert_messages(system, messages)
        prepared_tools = self._convert_tools(tools)

        response = self.client.chat.completions.create(
            model=model,
            messages=prepared_messages,
            tools=prepared_tools,
            tool_choice="auto",
            temperature=0,
        )

        choice = response.choices[0]
        msg = choice.message

        content_blocks: List[Dict[str, Any]] = []
        if msg.content:
            content_blocks.append({"type": "text", "text": msg.content})

        if msg.tool_calls:
            for call in msg.tool_calls:
                arguments = call.function.arguments or "{}"
                try:
                    parsed_input = json.loads(arguments)
                except Exception:  # noqa: BLE001
                    parsed_input = {}
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.function.name,
                        "input": parsed_input,
                    }
                )

        finish_reason = choice.finish_reason or "stop"
        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"
        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return {
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": prompt_tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "output_tokens": completion_tokens,
            },
            "content": content_blocks,
        }


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def collect_harness_loc(project_root: Path) -> Dict[str, int]:
    harness_dir = project_root / "API" / "harness"
    return {
        file.name: count_lines(file)
        for file in sorted(harness_dir.glob("*.py"))
    }


def evaluate_checks(checks: List[Dict[str, Any]], state_file: Path, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    results = []
    for check in checks:
        cid = check["id"]
        ctype = check["type"]
        passed = False
        detail = ""
        if ctype == "state_pref_equals":
            key = check["key"]
            expected = check["value"]
            actual = (state.get("preferences") or {}).get(key)
            passed = actual == expected
            detail = f"actual={actual}, expected={expected}"
        elif ctype == "state_course_exists":
            name = check["name"].lower()
            courses = state.get("courses") or []
            passed = any((c.get("name", "").lower() == name) for c in courses)
            detail = f"courses={len(courses)}"
        elif ctype == "state_courses_min":
            min_count = int(check["min_count"])
            courses = state.get("courses") or []
            passed = len(courses) >= min_count
            detail = f"count={len(courses)}, min={min_count}"
        elif ctype == "state_sessions_min":
            min_count = int(check["min_count"])
            sessions = state.get("study_sessions") or []
            passed = len(sessions) >= min_count
            detail = f"count={len(sessions)}, min={min_count}"
        elif ctype == "tools_used_contains":
            tool = check["tool"]
            all_tools = [t for turn in turns for t in turn.get("tools_used", [])]
            passed = tool in all_tools
            detail = f"tools={all_tools}"
        elif ctype == "contradiction_handled":
            text = "\n".join(turn.get("assistant", "") for turn in turns).lower()
            passed = ("updated memory" in text) or ("override" in text)
            detail = "looked for override/update signals"
        elif ctype == "state_decision_exists":
            title = check["title"]
            decisions = state.get("decisions") or []
            passed = any(d.get("title") == title for d in decisions)
            detail = f"decisions={len(decisions)}"
        elif ctype == "state_pref_changed":
            key = check["key"]
            from_value = check["from"]
            to_value = check["to"]
            decisions = state.get("decisions") or []
            details = [d.get("details", "") for d in decisions if d.get("title") == "preference_saved"]
            has_from = any(f"{key}={from_value}" in row for row in details)
            has_to = any(f"{key}={to_value}" in row for row in details)
            current = (state.get("preferences") or {}).get(key)
            passed = has_from and has_to and current == to_value
            detail = f"has_from={has_from}, has_to={has_to}, current={current}"
        results.append({"id": cid, "passed": passed, "detail": detail})
    return results


def run_scenario(project_root: Path, scenario_path: Path, out_path: Path, use_real_api: bool) -> None:
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    runtime_dir = project_root / "runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    can_use_real = use_real_api and bool(api_key) and OpenAI is not None
    model_client = OpenAIMessagesClient(api_key) if can_use_real else FakeMessagesClient()

    all_turns: List[Dict[str, Any]] = []
    for session in scenario["sessions"]:
        session_id = session["session_id"]
        history_store = HistoryStore(runtime_dir / f"history_{session_id}.jsonl")
        state_store = create_state_store(runtime_dir)
        tools = StudyPlannerTools(state_store)
        loop = AgentLoop(model_client, AgentConfig(), history_store, tools)

        for user_text in session["turns"]:
            turn_result = loop.run_turn(user_text)
            turn_result["session_id"] = session_id
            all_turns.append(turn_result)

    checks = evaluate_checks(scenario["checks"], runtime_dir / "memory_state.json", all_turns)
    output = {
        "agent": scenario.get("agent_name", "study-planner-copilot"),
        "mode": "real_api" if can_use_real else "fake_offline",
        "provider": "openai" if can_use_real else "offline-simulator",
        "model": "gpt-4o-mini",
        "effort": "medium",
        "turns": all_turns,
        "checks": checks,
        "harness_loc": collect_harness_loc(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[API/main.py] wrote results to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--use-real-api", action="store_true")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    run_scenario(
        project_root=project_root,
        scenario_path=project_root / args.scenario,
        out_path=project_root / args.out,
        use_real_api=args.use_real_api,
    )


if __name__ == "__main__":
    main()
