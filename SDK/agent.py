from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from SDK.tools import execute_for_sdk
from shared.tools import StudyPlannerTools


SDK_SYSTEM_PROMPT = """
You are StudyPlannerAgent (OpenAI SDK). Keep answers short, use tools for memory updates, and highlight contradictions with saved preferences.
""".strip()


@dataclass
class SDKConfig:
    model: str = "gpt-4o-mini"
    effort: str = "medium"
    strict_mcp_config: bool = True


class FakeSDKRunner:
    def __init__(self, shared_tools: StudyPlannerTools) -> None:
        self.shared_tools = shared_tools

    def query(self, prompt: str, session_id: str, allowed_tools: List[str], system_prompt: str) -> Dict[str, Any]:
        tools_used: List[str] = []
        txt = prompt.lower()

        if "העדפה" in txt or "preference" in txt or "remember" in txt or "תשמור" in txt:
            tools_used.append("save_preference")
            execute_for_sdk(self.shared_tools, "save_preference", {"key": "preferred_study_time", "value": "evening" if "ערב" in txt else "morning"})
        elif "קורס" in txt or "course" in txt:
            tools_used.append("add_course")
            execute_for_sdk(self.shared_tools, "add_course", {"name": "Algorithms", "weekly_hours": 6})
        elif "ויקיפד" in txt or "search" in txt or "resource" in txt:
            tools_used.append("web_lookup")
            execute_for_sdk(self.shared_tools, "web_lookup", {"query": "Pomodoro Technique"})
        elif "זוכר" in txt or "memory" in txt:
            tools_used.append("get_memory_snapshot")
            execute_for_sdk(self.shared_tools, "get_memory_snapshot", {"topic": "all"})
        elif "לימוד" in txt or "session" in txt:
            tools_used.append("plan_study_session")
            execute_for_sdk(self.shared_tools, "plan_study_session", {"course": "Algorithms", "duration_min": 90, "date": "2026-10-27"})

        response_text = "Done via SDK harness. Memory-aware response generated."
        usage = {
            "input_tokens": 170 + 20 * len(tools_used),
            "cache_read_tokens": 50,
            "cache_write_tokens": 12,
            "output_tokens": 75,
            "model_calls": 1,
            "total_cost_usd": round((170 + 20 * len(tools_used)) / 1000 * 0.015 + 75 / 1000 * 0.075, 6),
        }
        return {
            "response": response_text,
            "tools_used": tools_used,
            "usage": usage,
        }


class OpenAISDKRunner:
    def __init__(self, shared_tools: StudyPlannerTools, api_key: str, model: str = "gpt-4o-mini") -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        self.shared_tools = shared_tools
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def query(self, prompt: str, session_id: str, allowed_tools: List[str], system_prompt: str) -> Dict[str, Any]:
        tool_specs = [spec for spec in StudyPlannerTools.specs() if spec["name"] in allowed_tools]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec.get("description", ""),
                    "parameters": spec.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for spec in tool_specs
        ]

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        total_usage = {
            "input_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
            "model_calls": 0,
            "total_cost_usd": 0.0,
        }
        tools_used: List[str] = []
        final_text = ""

        while True:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0,
            )

            usage = resp.usage
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            total_usage["input_tokens"] += input_tokens
            total_usage["output_tokens"] += output_tokens
            total_usage["model_calls"] += 1

            msg = resp.choices[0].message
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
            }

            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in msg.tool_calls
                ]
            messages.append(assistant_msg)

            if msg.content:
                final_text = msg.content

            if not msg.tool_calls:
                break

            for call in msg.tool_calls:
                tool_name = call.function.name
                arguments = call.function.arguments or "{}"
                try:
                    parsed_args = json.loads(arguments)
                except Exception:  # noqa: BLE001
                    parsed_args = {}
                tools_used.append(tool_name)
                result = execute_for_sdk(self.shared_tools, tool_name, parsed_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result["data"], ensure_ascii=False),
                    }
                )

        total_usage["total_cost_usd"] = round(
            (total_usage["input_tokens"] / 1000 * 0.005)
            + (total_usage["output_tokens"] / 1000 * 0.015),
            6,
        )
        return {
            "response": final_text or "Done via OpenAI SDK harness.",
            "tools_used": tools_used,
            "usage": total_usage,
        }
