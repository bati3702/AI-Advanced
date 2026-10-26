from __future__ import annotations

import json
from pathlib import Path

from API.main import run_scenario as run_api
from SDK.main import run_scenario as run_sdk


def test_api_offline_scenario(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_file = tmp_path / "api_results.json"
    run_api(project_root, project_root / "scenario.json", out_file, use_real_api=False)
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["mode"] == "fake_offline"
    assert len(data["turns"]) == 7
    assert any(t for t in data["turns"] if "web_lookup" in t["tools_used"])
    assert sum(1 for c in data["checks"] if c["passed"]) >= 4


def test_sdk_offline_scenario(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_file = tmp_path / "sdk_results.json"
    run_sdk(project_root, project_root / "scenario.json", out_file, use_real_sdk=False)
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["mode"] == "sdk_fake_offline"
    assert len(data["turns"]) == 7
    assert data["sdk_config"]["strict_mcp_config"] is True
    assert sum(1 for c in data["checks"] if c["passed"]) >= 4
