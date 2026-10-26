from __future__ import annotations

from pathlib import Path

from shared.state import StateStore


def _log(msg: str) -> None:
    print(f"[API/harness/memory.py] {msg}")


def create_state_store(runtime_dir: Path) -> StateStore:
    memory_file = runtime_dir / "memory_state.json"
    _log(f"state store -> {memory_file}")
    return StateStore(memory_file)
