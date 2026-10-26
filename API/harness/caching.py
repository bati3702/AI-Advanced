from __future__ import annotations

from typing import Any, Dict, List


def _log(msg: str) -> None:
    print(f"[API/harness/caching.py] {msg}")


def apply_cache_control(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return messages
    patched = [*messages]
    first_system_idx = next((idx for idx, m in enumerate(patched) if m.get("role") == "system"), None)
    if first_system_idx is not None:
        patched[first_system_idx] = {
            **patched[first_system_idx],
            "cache_control": {"type": "ephemeral"},
        }
        _log("cache_control applied to system context")
    return patched
