from __future__ import annotations

from typing import Any, Dict, List


def _log(msg: str) -> None:
    print(f"[API/harness/compaction.py] {msg}")


def compact_if_needed(messages: List[Dict[str, Any]], threshold: int = 14) -> List[Dict[str, Any]]:
    if len(messages) <= threshold:
        return messages
    head = messages[:4]
    tail = messages[-8:]
    summary = {
        "role": "system",
        "content": "SUMMARY: conversation compacted to preserve token budget.",
    }
    _log(f"compacted {len(messages)} -> {len(head) + 1 + len(tail)}")
    return head + [summary] + tail
