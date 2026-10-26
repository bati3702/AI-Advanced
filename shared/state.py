from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PlannerState:
    user_profile: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    courses: List[Dict[str, Any]] = field(default_factory=list)
    study_sessions: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)


class StateStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PlannerState:
        if not self.file_path.exists():
            return PlannerState()
        data = json.loads(self.file_path.read_text(encoding="utf-8"))
        return PlannerState(**data)

    def save(self, state: PlannerState) -> None:
        self.file_path.write_text(
            json.dumps(state.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_decision(self, state: PlannerState, title: str, details: str) -> None:
        state.decisions.append(
            {
                "title": title,
                "details": details,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
