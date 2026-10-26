from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


SYSTEM_PROMPT = """
You are StudyPlannerAgent. Keep answers concise. Always use tools when saving or reading user memory.
If user request contradicts stored preferences, point it out and ask to confirm override.
""".strip()


@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    effort: str = "medium"


def build_messages(history_messages: List[Dict[str, Any]], user_text: str) -> List[Dict[str, Any]]:
    return history_messages + [{"role": "user", "content": user_text}]
