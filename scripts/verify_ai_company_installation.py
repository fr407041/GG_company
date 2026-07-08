from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "agent_os_mvp" / "frontend"
BACKEND_DIR = ROOT / "agent_os_mvp" / "backend"


@dataclass
class CheckResult:
    name: str
    ok: bool
    command: str
    details: str


Validator = Callable[[int, str], tuple[bool, str]]
CheckSpec = tuple[str, list[str], Path | None, Validator | None]


def command_to_text(command: list[str], cwd: Path | None = None) -> str:
    prefix = f"(cd {cwd}) " if cwd else ""
    return prefix + " ".join(command)


def decode_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError:
        return output.decode(locale.getpreferredencoding(False), errors="replace")


def run_check(
    name: str,
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    validator: Validator | None = None,
) -> CheckResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    display = command_to_text(command, cwd)
    print(f"\n==> {name}")
    print(display)
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd or ROOT),
            env=merged_env,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
    except FileNotFoundError as exc:
        return CheckResult(name, False, display, f"Command not found: {exc}")
    except subprocess.TimeoutExpired as exc:
        output = decode_output(exc.stdout)
        return CheckResult(name, False, display, f"Timed out after {exc.timeout}s\n{output[-4000:]}")

    output = decode_output(completed.stdout)
    if output.strip():
        print(output[-4000:])
    ok = completed.returncode == 0
    details = output[-4000:]
    if validator and ok:
        ok, validation_note = validator(completed.returncode, output)
        if validation_note:
            details = f"{details}\n{validation_note}"[-4000:]
            print(validation_note)
    return CheckResult(name, ok, display, details)


def extract_last_json_object(output: str) -> dict:
    decoder = json.JSONDecoder()
    last: dict | None = None
    index = 0
    while index < len(output):
        start = output.find("{", index)
        if start == -1:
            break
        try:
            parsed, end = decoder.raw_decode(output[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(parsed, dict):
            last = parsed
        index = start + max(end, 1)
    if last is None:
        raise ValueError("No JSON object found in command output.")
    return last


def watchdog_must_not_escalate(_returncode: int, output: str) -> tuple[bool, str]:
    try:
        report = extract_last_json_object(output)
    except ValueError as exc:
        return False, f"Watchdog validation failed: {exc}"
    status = str(report.get("watchdog_status", ""))
    if status == "escalated":
        action = report.get("last_action", "")
        return False, f"Watchdog validation failed: watchdog_status=escalated last_action={action}"
    if status not in {"healthy", "repairing", "disabled", "skipped"}:
        return False, f"Watchdog validation failed: unexpected watchdog_status={status!r}"
    return True, f"Watchdog validation passed: watchdog_status={status}"


def find_pnpm() -> str | None:
    found = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if found:
        return found

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidate = (
            Path(user_profile)
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "bin"
            / "pnpm.cmd"
        )
        if candidate.exists():
            return str(candidate)

    return None


def frontend_dependency_hint() -> str:
    return (
        "Hint: install frontend dependencies with "
        "'cd agent_os_mvp/frontend && pnpm install', then rerun verification; "
        "or use --skip-frontend for a core-only check."
    )


def build_checks(args: argparse.Namespace) -> list[CheckSpec]:
    python = sys.executable
    checks: list[CheckSpec] = [
        ("Docs encoding", [python, "scripts/check_docs_encoding.py"], ROOT, None),
        ("Core Python tests", [python, "-m", "unittest", "discover", "-s", "tests"], ROOT, None),
        (
            "Mock success E2E",
            [
                python,
                "scripts/run_ai_company_task_harness.py",
                "docs/ai_specs/general-task-mock-success.json",
                "--mode",
                "mock",
            ],
            ROOT,
            None,
        ),
        (
            "Watchdog once after mock success",
            [python, "scripts/run_ai_company_watchdog.py", "--once"],
            ROOT,
            watchdog_must_not_escalate,
        ),
        (
            "Mock replan E2E",
            [
                python,
                "scripts/run_ai_company_task_harness.py",
                "docs/ai_specs/general-task-mock-replan.json",
                "--mode",
                "mock",
            ],
            ROOT,
            None,
        ),
    ]

    if not args.skip_dashboard:
        checks.append(
            (
                "Dashboard backend tests",
                [python, "-m", "unittest", "discover", "-s", "tests"],
                BACKEND_DIR,
                None,
            )
        )

    if not args.skip_frontend:
        pnpm = find_pnpm()
        if pnpm:
            checks.append(("Dashboard frontend build", [pnpm, "run", "build"], FRONTEND_DIR, None))
        else:
            checks.append(("Dashboard frontend build", ["pnpm", "run", "build"], FRONTEND_DIR, None))

    if args.include_live_llm:
        checks.append(("Offline live LLM E2E", [python, "scripts/verify_ai_company_live_llm.py"], ROOT, None))

    if args.include_browser_smoke:
        checks.append(("Dashboard browser smoke", [python, "scripts/smoke_dashboard_browser.py"], ROOT, None))

    return checks


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Run install/regression checks for GG_company without requiring live LLM access."
    )
    parser.add_argument("--skip-dashboard", action="store_true", help="Skip backend dashboard tests.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip Vite frontend build.")
    parser.add_argument("--include-live-llm", action="store_true", help="Also run the offline live LLM E2E case.")
    parser.add_argument("--include-browser-smoke", action="store_true", help="Also launch the dashboard and verify it with a headless browser.")
    args = parser.parse_args()

    results: list[CheckResult] = []
    for name, command, cwd, validator in build_checks(args):
        results.append(run_check(name, command, cwd, validator=validator))

    print("\nVerification summary")
    print("====================")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}  {result.name}")
        if not result.ok:
            print(f"      {result.command}")
            if result.name == "Dashboard frontend build":
                print(f"      {frontend_dependency_hint()}")
            if result.name == "Dashboard browser smoke":
                print("      Hint: install Playwright in the test environment, or rerun without --include-browser-smoke.")

    failed = [item for item in results if not item.ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
