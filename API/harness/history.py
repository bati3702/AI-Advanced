from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _log(msg: str) -> None:
    print(f"[API/harness/history.py] {msg}")


class HistoryStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            _log("load -> empty")
            return []
        lines = self.file_path.read_text(encoding="utf-8").splitlines()
        _log(f"load -> {len(lines)} messages")
        return [json.loads(line) for line in lines if line.strip()]

    def append(self, message: Dict[str, Any]) -> None:
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
        _log("append -> 1 message")
