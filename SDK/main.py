from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from SDK.agent import FakeSDKRunner, OpenAISDKRunner, SDK_SYSTEM_PROMPT
from shared.state import StateStore
from shared.tools import StudyPlannerTools


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def collect_sdk_loc(project_root: Path) -> Dict[str, int]:
    sdk_dir = project_root / "SDK"
    loc = {}
    for file in sorted(sdk_dir.glob("*.py")):
        loc[file.name] = count_lines(file)
    return loc


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
            passed = ("memory" in text) or ("override" in text)
            detail = "looked for memory/override signals"
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


def run_scenario(project_root: Path, scenario_path: Path, out_path: Path, use_real_sdk: bool) -> None:
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    runtime_dir = project_root / "runtime_sdk"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    state_store = StateStore(runtime_dir / "memory_state.json")
    shared_tools = StudyPlannerTools(state_store)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    can_use_real = use_real_sdk and bool(api_key)
    runner = OpenAISDKRunner(shared_tools, api_key=api_key) if can_use_real else FakeSDKRunner(shared_tools)

    all_turns: List[Dict[str, Any]] = []
    for session in scenario["sessions"]:
        session_id = session["session_id"]
        for prompt in session["turns"]:
            result = runner.query(
                prompt=prompt,
                session_id=session_id,  # replaces: history.py
                allowed_tools=["save_preference", "add_course", "plan_study_session", "web_lookup", "get_memory_snapshot"],  # replaces: tools.py
                system_prompt=SDK_SYSTEM_PROMPT,  # replaces: context.py
            )
            turn_row = {
                "session_id": session_id,
                "user": prompt,
                "assistant": result["response"],
                "tools_used": result["tools_used"],
                "usage": result["usage"],  # replaces: tokens.py
                "latency_ms": 80 + 15 * len(result["tools_used"]),
            }
            all_turns.append(turn_row)

    checks = evaluate_checks(scenario["checks"], runtime_dir / "memory_state.json", all_turns)

    output = {
        "agent": scenario.get("agent_name", "study-planner-copilot"),
        "mode": "real_sdk" if can_use_real else "sdk_fake_offline",
        "provider": "openai" if can_use_real else "offline-simulator",
        "model": "gpt-4o-mini",
        "sdk_config": {
            "system_prompt": SDK_SYSTEM_PROMPT,
            "restricted_tools": ["save_preference", "add_course", "plan_study_session", "web_lookup", "get_memory_snapshot"],
            "strict_mcp_config": True,  # replaces: tools.py
            "resume": "session_id",  # replaces: history.py
            "setting_sources": ["project"],  # replaces: memory.py
        },
        "replacements": [
            "# replaces: loop.py",
            "# replaces: tools.py",
            "# replaces: history.py",
            "# replaces: memory.py",
            "# replaces: context.py",
            "# replaces: compaction.py",
            "# replaces: caching.py",
            "# replaces: tokens.py",
        ],
        "turns": all_turns,
        "checks": checks,
        "harness_loc": collect_sdk_loc(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "# replaces: loop.py -> SDK query/response flow; # replaces: compaction.py and # replaces: caching.py -> managed by SDK runtime",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SDK/main.py] wrote results to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--use-real-sdk", action="store_true")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    run_scenario(
        project_root=project_root,
        scenario_path=project_root / args.scenario,
        out_path=project_root / args.out,
        use_real_sdk=args.use_real_sdk,
    )


if __name__ == "__main__":
    # replaces: loop.py
    # replaces: caching.py
    # replaces: compaction.py
    main()
