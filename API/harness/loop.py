from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Dict, List

from API.agent import AgentConfig, SYSTEM_PROMPT, build_messages
from API.harness.caching import apply_cache_control
from API.harness.compaction import compact_if_needed
from API.harness.context import build_relevant_context, inject_context_message
from API.harness.history import HistoryStore
from API.harness.tokens import UsageRecord, add_usage, parse_usage
from API.harness.tools import execute_tool, get_tool_specs
from shared.tools import StudyPlannerTools


def _log(msg: str) -> None:
    print(f"[API/harness/loop.py] {msg}")


class AgentLoop:
    def __init__(
        self,
        model_client: Any,
        config: AgentConfig,
        history_store: HistoryStore,
        tools: StudyPlannerTools,
    ) -> None:
        self.model_client = model_client
        self.config = config
        self.history_store = history_store
        self.tools = tools

    def run_turn(self, user_text: str) -> Dict[str, Any]:
        turn_start = time.perf_counter()
        history = self.history_store.load()
        messages = build_messages(history, user_text)
        relevant = build_relevant_context(user_text, self.tools.store)
        messages = inject_context_message(messages, relevant)
        messages = compact_if_needed(messages)
        messages = apply_cache_control(messages)

        self.history_store.append({"role": "user", "content": user_text})

        turn_usage = UsageRecord(model_calls=0)
        tools_used: List[str] = []
        response_text = ""

        while True:
            _log("calling model")
            response = self.model_client.create_message(
                model=self.config.model,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=get_tool_specs(),
                effort=self.config.effort,
            )

            usage = parse_usage(response)
            turn_usage = add_usage(turn_usage, usage)

            stop_reason = response.get("stop_reason", "end_turn")
            content_blocks = response.get("content", [])
            messages.append({"role": "assistant", "content": content_blocks})
            self.history_store.append({"role": "assistant", "content": content_blocks})

            tool_calls = [block for block in content_blocks if block.get("type") == "tool_use"]
            text_blocks = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
            if text_blocks:
                response_text = "\n".join(tb for tb in text_blocks if tb.strip())

            if stop_reason == "tool_use" and tool_calls:
                tool_results = []
                for call in tool_calls:
                    name = call.get("name")
                    inp = call.get("input", {})
                    tool_use_id = call.get("id")
                    tools_used.append(name)
                    result = execute_tool(self.tools, name, inp, tool_use_id=tool_use_id)
                    tool_results.append(result)
                messages.append({"role": "user", "content": tool_results})
                self.history_store.append({"role": "user", "content": tool_results})
                continue
            break

        elapsed_ms = int((time.perf_counter() - turn_start) * 1000)
        _log(f"turn completed in {elapsed_ms}ms")
        return {
            "user": user_text,
            "assistant": response_text,
            "tools_used": tools_used,
            "usage": asdict(turn_usage),
            "latency_ms": elapsed_ms,
        }
