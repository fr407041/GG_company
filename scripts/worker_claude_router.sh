#!/usr/bin/env bash
set -u

JOB_PATH="${1:-}"
if [ -z "$JOB_PATH" ]; then
  echo "WORKER_RUNTIME_MISSING: missing job path"
  exit 1
fi

python_bin="${PYTHON_BIN:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python"
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export AI_COMPANY_SCRIPTS_DIR="${AI_COMPANY_SCRIPTS_DIR:-${SCRIPT_DIR}}"

"$python_bin" - "$JOB_PATH" <<'PY'
from __future__ import annotations

import hashlib
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

scripts_dir = os.environ.get("AI_COMPANY_SCRIPTS_DIR", "").strip()
if scripts_dir and scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
else:
    fallback_scripts_dir = Path.cwd() / "scripts"
    if fallback_scripts_dir.exists() and str(fallback_scripts_dir) not in sys.path:
        sys.path.insert(0, str(fallback_scripts_dir))

from ai_company_rate_limiter import RateLimitTimeout, acquire_llm_rate_limit


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(scope_path: Path, files: list[str]) -> dict[str, str]:
    return {item: file_hash(scope_path / item) for item in files}


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return [name for name in after if before.get(name, "") != after.get(name, "")]


def extract_json_object(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def apply_llm_file_payload(raw_output: str, scope_path: Path, allowed_files: list[str]) -> tuple[list[str], str]:
    payload = extract_json_object(raw_output)
    if not payload:
        return [], "no JSON file payload found"
    items = payload.get("files", [])
    if not isinstance(items, list):
        return [], "JSON payload missing files array"

    allowed = set(allowed_files)
    applied: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rel_path = str(item.get("path", "")).replace("\\", "/").strip()
        content = item.get("content")
        if rel_path not in allowed or not isinstance(content, str):
            continue
        target = (scope_path / rel_path).resolve()
        try:
            target.relative_to(scope_path)
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        applied.append(rel_path)
    return applied, str(payload.get("summary", "") or "JSON file payload applied")


def extract_python_block(text: str) -> str:
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    generic = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    return generic.group(1).strip() if generic else ""


def function_segments(source: str) -> dict[str, tuple[int, int, str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    segments: dict[str, tuple[int, int, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and hasattr(node, "end_lineno"):
            start = int(node.lineno) - 1
            end = int(node.end_lineno)
            segments[node.name] = (start, end, "\n".join(lines[start:end]))
    return segments


def apply_python_function_payload(raw_output: str, scope_path: Path, allowed_files: list[str]) -> tuple[list[str], str]:
    code = extract_python_block(raw_output)
    if not code:
        return [], "no python code block found"
    generated = function_segments(code)
    if not generated:
        return [], "python code block did not contain a parseable function"

    applied: list[str] = []
    for rel_path in allowed_files:
        if not rel_path.endswith(".py"):
            continue
        target = (scope_path / rel_path).resolve()
        try:
            target.relative_to(scope_path)
        except ValueError:
            continue
        if not target.exists():
            continue
        original = target.read_text(encoding="utf-8")
        original_segments = function_segments(original)
        lines = original.splitlines()
        changed = False
        if len(generated) == 1 and len(original_segments) == 1:
            _, (_, _, replacement) = next(iter(generated.items()))
            target_name, (start, end, _) = next(iter(original_segments.items()))
            replacement_lines = replacement.splitlines()
            if replacement_lines:
                replacement_lines[0] = re.sub(r"def\s+\w+\s*\(", f"def {target_name}(", replacement_lines[0], count=1)
            lines[start:end] = replacement_lines
            changed = True
        if changed:
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            applied.append(rel_path)
            continue
        for name, (_, _, replacement) in generated.items():
            if name not in original_segments:
                continue
            start, end, _ = original_segments[name]
            lines[start:end] = replacement.splitlines()
            changed = True
            break
        if changed:
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            applied.append(rel_path)
    return applied, "python function code block applied" if applied else "no matching function found in allowed python files"


def normalize_command(command: str) -> list[str]:
    if not command.strip():
        return []
    if os.name == "nt":
        python_bin = os.environ.get("PYTHON_BIN", "").strip()
        stripped = command.strip()
        if python_bin and stripped.startswith("python3 "):
            safe_python_bin = f'"{python_bin}"' if " " in python_bin else python_bin
            command = f'{safe_python_bin} {stripped[len("python3 "):]}'
        elif python_bin and stripped == "python3":
            command = f'"{python_bin}"' if " " in python_bin else python_bin
    if os.name == "nt":
        return ["cmd", "/c", command]
    return ["bash", "-lc", command]


def run_command(command: list[str], cwd: Path, timeout_sec: int) -> tuple[int, str]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_sec,
        )
        return completed.returncode, completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, f"COMMAND_TIMEOUT after {round(time.time() - started, 1)}s\n{output}"


def acquire_llm_permit() -> dict:
    return acquire_llm_rate_limit(
        enabled=os.environ.get("AI_COMPANY_LLM_RATE_LIMIT_ENABLED", "1").strip() != "0",
        requests_per_minute=int(os.environ.get("AI_COMPANY_LLM_REQUESTS_PER_MINUTE", "20")),
        state_file=os.environ.get("AI_COMPANY_LLM_RATE_LIMIT_STATE_FILE", "tmp/ai_company_llm_rate_limit.json"),
        timeout_sec=float(os.environ.get("AI_COMPANY_LLM_RATE_LIMIT_TIMEOUT_SEC", "300")),
    )


def summarize_rate_limit(metrics: list[dict]) -> dict:
    if not metrics:
        return {
            "llm_rate_limit_wait_sec": 0.0,
            "llm_rate_limit_permit_acquired": True,
            "llm_rate_limit_request_count_window": 0,
        }
    return {
        "llm_rate_limit_wait_sec": round(sum(float(item.get("wait_sec", 0.0) or 0.0) for item in metrics), 3),
        "llm_rate_limit_permit_acquired": all(bool(item.get("permit_acquired", False)) for item in metrics),
        "llm_rate_limit_request_count_window": max(int(item.get("request_count_window", 0) or 0) for item in metrics),
    }


def find_runtime() -> tuple[str, list[str]]:
    preferred = os.environ.get("AI_COMPANY_LLM_COMMAND", "").strip()
    if preferred:
        return "custom", shlex.split(preferred, posix=(os.name != "nt"))
    if shutil.which("claude"):
        return "claude", [
            "claude",
            "-p",
            "--bare",
            "--dangerously-skip-permissions",
            "--allowedTools=Read,Edit,Write,Bash",
        ]
    if shutil.which("ccr"):
        return "ccr", ["ccr", "code", "-p"]
    return "", []


def build_prompt(job: dict, scope_path: Path, files: list[str]) -> str:
    file_list = "\n".join(f"- {item}" for item in files)
    acceptance = "\n".join(f"- {item}" for item in job.get("acceptance_criteria", []))
    require_change = bool(job.get("require_change", False))
    change_instruction = (
        "This job requires a real file change. If the target is Python, return ONLY one fenced python code block "
        "containing the complete replacement function(s) with the same function name(s) as the source. "
        "Preserve the exact public function names and the units/exception behavior required by the tests. "
        "If tests assert integer cents, return integer cents; if tests assert an exception for invalid input, raise that exception instead of returning a fallback value. "
        "No prose before or after the code block. If a full-file replacement is safer, return ONLY valid JSON with "
        'this shape: {"summary":"short summary","files":[{"path":"relative/allowed/file","content":"complete replacement file content"}]}.'
        if require_change
        else "This job does not require a file change unless one is necessary to satisfy the task."
    )
    file_context: list[str] = []
    for rel_path in files:
        path = scope_path / rel_path
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            file_context.append(f"--- FILE: {rel_path} ---\n{text[:12000]}\n--- END FILE: {rel_path} ---")
        else:
            file_context.append(f"--- FILE: {rel_path} MISSING ---")
    file_context_text = "\n\n".join(file_context)
    return f"""You are running as one bounded AI-company worker in an offline test environment.

Task id: {job.get('id', '')}
Role: {job.get('owner_role', '')}
Title: {job.get('title', '')}

Goal:
{job.get('instruction', '')}

Allowed working directory:
{scope_path}

Allowed files:
{file_list}

Success check:
{job.get('success_check', '')}

Change requirement:
{change_instruction}

Acceptance criteria:
{acceptance}

Selected file contents:
{file_context_text}

Rules:
- Do not browse the internet.
- Do not use files outside the allowed file list unless needed only to run the assigned tests.
- If changes are required, edit only the allowed files and verify the edit with the test command.
- If a test command is provided, run it after the change.
- For require-change jobs, your final response must be only the replacement code block or JSON patch. For no-change jobs, keep the final response short and include evidence used plus limitations.
"""


def build_repair_prompt(job: dict, scope_path: Path, files: list[str], test_output: str) -> str:
    file_context: list[str] = []
    for rel_path in files:
        path = scope_path / rel_path
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            file_context.append(f"--- CURRENT FILE: {rel_path} ---\n{text[:12000]}\n--- END CURRENT FILE: {rel_path} ---")
    repair_file_list = "\n".join(f"- {item}" for item in files)
    repair_file_context = "\n".join(file_context)
    return f"""The previous bounded patch failed the assigned test command.

Task id: {job.get('id', '')}
Goal:
{job.get('instruction', '')}

Allowed files:
{repair_file_list}

Failed test output:
{test_output[-6000:]}

Current file contents after the failed patch:
{repair_file_context}

Repair rules:
- Return ONLY one fenced python code block with complete replacement function(s), or ONLY the JSON full-file patch shape.
- Preserve exact function names from the current file.
- Preserve the units and error semantics asserted by the tests.
- Do not return prose, explanation, markdown headings, or alternate function names.
"""


def classify_failure(exit_code: int, test_exit_code: int, runtime_name: str, raw_output: str) -> str:
    lowered = raw_output.lower()
    if not runtime_name:
        return "WORKER_RUNTIME_MISSING"
    if exit_code == 124:
        return "OUTPUT_POLICY_BLOCKED"
    if "context window" in lowered or "maximum context" in lowered or "token" in lowered and "overflow" in lowered:
        return "FORMAT_INVALID"
    if exit_code != 0:
        return "OUTPUT_POLICY_BLOCKED"
    if test_exit_code not in {0, None}:
        return "OUTPUT_POLICY_BLOCKED"
    return ""


def main() -> int:
    job_path = Path(sys.argv[1]).resolve()
    job = read_json(job_path)
    run_dir = job_path.parent.parent
    scope_path = Path(str(job.get("scope_path", run_dir / "worktree"))).resolve()
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    prefix = results_dir / job["id"]
    raw_path = prefix.with_suffix(".raw.txt")
    log_path = prefix.with_suffix(".exec.log")
    status_path = prefix.with_suffix(".status.json")
    test_path = prefix.with_suffix(".test.txt")
    prompt_path = prefix.with_suffix(".prompt.txt")

    files = list(job.get("files", []))
    before = snapshot(scope_path, files)
    runtime_name, runtime_cmd = find_runtime()
    timeout_sec = int(os.environ.get("CLAUDE_CHILD_TIMEOUT_SEC", "600"))
    started = time.time()

    if not runtime_cmd:
        note = "Local worker adapter could not find claude or ccr."
        write_text(raw_path, f"WORKER_RUNTIME_MISSING\n{note}\n")
        write_text(log_path, "WORKER_RUNTIME_MISSING\n")
        payload = {
            "id": job["id"],
            "status": "FAILED",
            "scope_path": str(scope_path),
            "require_change": job.get("require_change", False),
            "files": files,
            "owner_role": job.get("owner_role", ""),
            "actual_changed_files": [],
            "actual_changed_count": 0,
            "verification_note": note,
            "subagent_summary": note,
            "key_claims": [{"claim": note, "evidence_refs": [raw_path.name]}],
            "confidence": "low",
            "limitations": [note],
            "handoff_next": "Install claude/ccr or configure AI_COMPANY_LLM_COMMAND.",
            "raw_file": str(raw_path),
            "exec_log_file": str(log_path),
            "success_check": job.get("success_check", ""),
            "test_command": job.get("test_command", ""),
            "test_executed_command": "",
            "test_output_file": str(test_path),
            "test_exit_code": 1,
            "exit_code": 1,
            "duration_sec": 0,
            "raw_output_parse_status": "worker_runtime_missing",
            "format_cleaning_applied": False,
            "contract_valid": True,
            "failure_family": "WORKER_RUNTIME_MISSING",
            "model_name": os.environ.get("CCR_PREFERRED_MODEL", ""),
            "repair_attempted": False,
            "repair_successful": False,
            "format_recovery_used": False,
        }
        write_json(status_path, payload)
        return 1

    prompt = build_prompt(job, scope_path, files)
    write_text(prompt_path, prompt)

    def command_for_prompt(prompt_text: str) -> list[str]:
        if runtime_name in {"ccr", "claude", "custom"}:
            return runtime_cmd + [prompt_text]
        return runtime_cmd

    rate_limit_metrics: list[dict] = []
    command = command_for_prompt(prompt)
    try:
        rate_limit_metrics.append(acquire_llm_permit())
    except RateLimitTimeout as exc:
        rate_limit_metrics.append(exc.result)
        payload = {
            "id": job["id"],
            "status": "FAILED",
            "scope_path": str(scope_path),
            "require_change": bool(job.get("require_change", False)),
            "files": files,
            "owner_role": job.get("owner_role", ""),
            "actual_changed_files": [],
            "actual_changed_count": 0,
            "verification_note": "LLM rate limit timeout before initial request.",
            "subagent_summary": "LLM request was blocked by the shared rate limiter before execution.",
            "key_claims": [],
            "confidence": "low",
            "limitations": ["LLM API request was not sent because the rate limiter timed out."],
            "handoff_next": "Retry later or lower concurrency/request volume.",
            "raw_file": str(raw_path),
            "exec_log_file": str(log_path),
            "success_check": job.get("success_check", ""),
            "test_command": str(job.get("test_command", "")).strip(),
            "test_executed_command": "",
            "test_output_file": str(test_path),
            "test_exit_code": None,
            "exit_code": 124,
            "duration_sec": round(time.time() - started, 3),
            "raw_output_parse_status": "rate_limit_timeout",
            "format_cleaning_applied": False,
            "contract_valid": True,
            "failure_family": "LLM_RATE_LIMIT_TIMEOUT",
            "model_name": os.environ.get("CCR_PREFERRED_MODEL", ""),
            "repair_attempted": False,
            "repair_successful": False,
            "format_recovery_used": False,
            **summarize_rate_limit(rate_limit_metrics),
        }
        write_text(raw_path, "LLM_RATE_LIMIT_TIMEOUT\n")
        write_text(log_path, json.dumps(rate_limit_metrics, ensure_ascii=False, indent=2))
        write_json(status_path, payload)
        return 1

    exit_code, raw_output = run_command(command, scope_path, timeout_sec)
    write_text(raw_path, raw_output)

    applied_files: list[str] = []
    apply_notes: list[str] = []
    format_recovery_used = False
    if bool(job.get("require_change", False)) and exit_code == 0:
        applied_files, apply_note = apply_llm_file_payload(raw_output, scope_path, files)
        if not applied_files:
            applied_files, apply_note = apply_python_function_payload(raw_output, scope_path, files)
            format_recovery_used = bool(applied_files)
        apply_notes.append(f"initial:{apply_note}")

    test_command = str(job.get("test_command", "")).strip()
    test_exit_code: int | None = None
    test_output = ""
    if test_command:
        test_exit_code, test_output = run_command(normalize_command(test_command), scope_path, timeout_sec)
        write_text(test_path, test_output)
    else:
        test_exit_code = 0
        write_text(test_path, "No test command configured.\n")

    repair_attempted = False
    repair_successful = False
    repair_enabled = os.environ.get("AI_COMPANY_WORKER_REPAIR_ENABLED", "1").strip() != "0"
    repair_limit = int(os.environ.get("AI_COMPANY_WORKER_REPAIR_ATTEMPT_LIMIT", "1"))
    if repair_enabled and repair_limit > 0 and bool(job.get("require_change", False)) and test_command and exit_code == 0 and test_exit_code != 0:
        repair_attempted = True
        repair_prompt = build_repair_prompt(job, scope_path, files, test_output)
        repair_prompt_path = results_dir / f"{job['id']}.repair.prompt.txt"
        repair_raw_path = results_dir / f"{job['id']}.repair.raw.txt"
        write_text(repair_prompt_path, repair_prompt)
        repair_command = command_for_prompt(repair_prompt)
        try:
            rate_limit_metrics.append(acquire_llm_permit())
        except RateLimitTimeout as exc:
            rate_limit_metrics.append(exc.result)
            repair_exit_code = 124
            repair_raw_output = "LLM_RATE_LIMIT_TIMEOUT before bounded repair request.\n"
            failure_family = "LLM_RATE_LIMIT_TIMEOUT"
            write_text(repair_raw_path, repair_raw_output)
            raw_output = raw_output + "\n\n--- AI COMPANY BOUNDED REPAIR ATTEMPT ---\n\n" + repair_raw_output
            write_text(raw_path, raw_output)
            exit_code = repair_exit_code
            repair_successful = False
            test_exit_code = test_exit_code if test_exit_code is not None else 1
            after = snapshot(scope_path, files)
            actual_changed = changed_files(before, after)
            duration = round(time.time() - started, 3)
            payload = {
                "id": job["id"],
                "status": "FAILED",
                "scope_path": str(scope_path),
                "require_change": bool(job.get("require_change", False)),
                "files": files,
                "owner_role": job.get("owner_role", ""),
                "actual_changed_files": actual_changed,
                "actual_changed_count": len(actual_changed),
                "verification_note": "LLM rate limit timeout before repair request.",
                "subagent_summary": raw_output.strip()[:1200],
                "key_claims": [],
                "confidence": "low",
                "limitations": ["Bounded repair LLM request was not sent because the rate limiter timed out."],
                "handoff_next": "Retry later or lower concurrency/request volume.",
                "raw_file": str(raw_path),
                "exec_log_file": str(log_path),
                "success_check": job.get("success_check", ""),
                "test_command": test_command,
                "test_executed_command": test_command,
                "test_output_file": str(test_path),
                "test_exit_code": test_exit_code,
                "exit_code": exit_code,
                "duration_sec": duration,
                "raw_output_parse_status": "rate_limit_timeout",
                "format_cleaning_applied": False,
                "contract_valid": True,
                "failure_family": "LLM_RATE_LIMIT_TIMEOUT",
                "model_name": os.environ.get("CCR_PREFERRED_MODEL", ""),
                "repair_attempted": repair_attempted,
                "repair_successful": False,
                "format_recovery_used": format_recovery_used,
                **summarize_rate_limit(rate_limit_metrics),
            }
            write_text(log_path, json.dumps(rate_limit_metrics, ensure_ascii=False, indent=2))
            write_json(status_path, payload)
            return 1
        repair_exit_code, repair_raw_output = run_command(repair_command, scope_path, timeout_sec)
        write_text(repair_raw_path, repair_raw_output)
        raw_output = raw_output + "\n\n--- AI COMPANY BOUNDED REPAIR ATTEMPT ---\n\n" + repair_raw_output
        write_text(raw_path, raw_output)
        if repair_exit_code != 0:
            exit_code = repair_exit_code
        repair_applied_files: list[str] = []
        if repair_exit_code == 0:
            repair_applied_files, repair_apply_note = apply_llm_file_payload(repair_raw_output, scope_path, files)
            if not repair_applied_files:
                repair_applied_files, repair_apply_note = apply_python_function_payload(repair_raw_output, scope_path, files)
                format_recovery_used = bool(repair_applied_files) or format_recovery_used
            apply_notes.append(f"repair:{repair_apply_note}")
            applied_files = sorted(set(applied_files) | set(repair_applied_files))
            test_exit_code, test_output = run_command(normalize_command(test_command), scope_path, timeout_sec)
            write_text(test_path, test_output)
            repair_successful = bool(repair_applied_files) and test_exit_code == 0

    after = snapshot(scope_path, files)
    actual_changed = changed_files(before, after)
    duration = round(time.time() - started, 3)
    failure_family = classify_failure(exit_code, test_exit_code, runtime_name, raw_output)
    require_change = bool(job.get("require_change", False))
    raw_nonempty = len(raw_output.strip()) >= 20
    change_ok = (not require_change) or bool(actual_changed)
    test_ok = test_exit_code == 0
    success = exit_code == 0 and raw_nonempty and change_ok and test_ok

    if not success and not failure_family:
        failure_family = "OUTPUT_POLICY_BLOCKED" if exit_code == 0 else "LLM_RUNTIME_FAILED"

    note_bits = [
        f"runtime={runtime_name}",
        f"llm_exit={exit_code}",
        f"test_exit={test_exit_code}",
        f"changed={','.join(actual_changed) if actual_changed else 'none'}",
    ]
    if apply_notes:
        note_bits.append(f"llm_patch={' | '.join(apply_notes)[:200]}")
    if repair_attempted:
        note_bits.append("bounded_repair_attempted=true")
    if require_change and not actual_changed:
        note_bits.append("required change was not observed")
    if not raw_nonempty:
        note_bits.append("LLM output was empty or too short")

    payload = {
        "id": job["id"],
        "status": "SUCCESS" if success else "FAILED",
        "scope_path": str(scope_path),
        "require_change": require_change,
        "files": files,
        "owner_role": job.get("owner_role", ""),
        "actual_changed_files": actual_changed,
        "actual_changed_count": len(actual_changed),
        "verification_note": "; ".join(note_bits),
        "subagent_summary": raw_output.strip()[:1200] if raw_output.strip() else "LLM produced no usable output.",
        "key_claims": [
            {
                "claim": "Live LLM worker executed the bounded job and produced observable output.",
                "evidence_refs": [raw_path.name, test_path.name],
            }
        ],
        "confidence": "medium" if success else "low",
        "limitations": [] if success else ["Live LLM run did not satisfy all adapter checks."],
        "handoff_next": "Review raw output and test output before accepting the result." if not success else "Proceed to reviewer validation.",
        "raw_file": str(raw_path),
        "exec_log_file": str(log_path),
        "success_check": job.get("success_check", ""),
        "test_command": test_command,
        "test_executed_command": test_command,
        "test_output_file": str(test_path),
        "test_exit_code": test_exit_code,
        "exit_code": exit_code,
        "duration_sec": duration,
        "raw_output_parse_status": "live_llm_text",
        "format_cleaning_applied": False,
        "contract_valid": True,
        "failure_family": "" if success else failure_family,
        "model_name": os.environ.get("CCR_PREFERRED_MODEL", ""),
        "repair_attempted": repair_attempted,
        "repair_successful": repair_successful,
        "format_recovery_used": format_recovery_used,
        **summarize_rate_limit(rate_limit_metrics),
    }

    write_text(
        log_path,
        "\n".join(
            [
                f"runtime={runtime_name}",
                f"command={' '.join(command[:3])} ...",
                f"duration_sec={duration}",
                f"llm_exit_code={exit_code}",
                f"test_exit_code={test_exit_code}",
                f"changed_files={actual_changed}",
                f"bounded_repair_attempted={repair_attempted}",
                f"llm_rate_limit={json.dumps(rate_limit_metrics, ensure_ascii=False)}",
            ]
        )
        + "\n",
    )
    write_json(status_path, payload)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
PY
