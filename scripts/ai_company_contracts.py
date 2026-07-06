from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = ROOT / "configs" / "ai_company"

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"print\s+(the\s+)?hidden\s+prompt",
    r"bypass\s+safety",
    r"developer\s+message",
]

FAILURE_FAMILIES = {
    "FORMAT_INVALID",
    "SCHEMA_INVALID",
    "INPUT_POLICY_BLOCKED",
    "OUTPUT_POLICY_BLOCKED",
    "WORKER_RUNTIME_MISSING",
    "PROMPT_INJECTION_SUSPECTED",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_defaults() -> dict[str, Any]:
    return read_json(CONFIG_ROOT / "task_harness.defaults.json")


def ensure_failure_family(value: str, fallback: str = "SCHEMA_INVALID") -> str:
    return value if value in FAILURE_FAMILIES else fallback


def append_contract_event(run_dir: Path, artifact: str, ok: bool, errors: list[str], failure_family: str = "") -> dict[str, Any]:
    report_path = run_dir / "ai_company" / "contract_validation_report.json"
    report = read_json(report_path) if report_path.exists() else {"events": []}
    event = {
        "artifact": artifact,
        "ok": ok,
        "errors": errors,
        "failure_family": ensure_failure_family(failure_family) if failure_family else "",
    }
    report.setdefault("events", []).append(event)
    report["all_passed"] = all(item.get("ok", False) for item in report["events"])
    write_json(report_path, report)
    return event


def write_guard_report(run_dir: Path, report_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = run_dir / "ai_company" / report_name
    existing = read_json(path) if path.exists() else {}
    merged = dict(existing)
    merged.update(payload)
    write_json(path, merged)
    return merged


def _is_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def _validate_schema_node(value: Any, schema: dict[str, Any], root: Path, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _is_type(value, expected_type):
        return [f"{path}: expected {expected_type}"]

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']}")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < int(min_length):
            errors.append(f"{path}: string shorter than {min_length}")

    if isinstance(value, int):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < int(minimum):
            errors.append(f"{path}: integer smaller than {minimum}")
        if maximum is not None and value > int(maximum):
            errors.append(f"{path}: integer larger than {maximum}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required key '{key}'")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(_validate_schema_node(value[key], child_schema, root, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                errors.append(f"{path}: unexpected keys {sorted(extra)}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < int(min_items):
            errors.append(f"{path}: expected at least {min_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            if "$ref" in item_schema:
                ref_path = root / item_schema["$ref"]
                ref_schema = read_json(ref_path)
                for idx, item in enumerate(value):
                    errors.extend(_validate_schema_node(item, ref_schema, root, f"{path}[{idx}]"))
            else:
                for idx, item in enumerate(value):
                    errors.extend(_validate_schema_node(item, item_schema, root, f"{path}[{idx}]"))
    return errors


def validate_against_schema(payload: dict[str, Any], schema_filename: str) -> list[str]:
    schema = read_json(CONFIG_ROOT / schema_filename)
    return _validate_schema_node(payload, schema, CONFIG_ROOT)


def validate_status_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "id",
        "status",
        "scope_path",
        "files",
        "owner_role",
        "verification_note",
        "raw_file",
        "raw_output_parse_status",
        "format_cleaning_applied",
        "contract_valid",
        "failure_family",
    ]
    for key in required:
        if key not in payload:
            errors.append(f"$.{key}: missing required key")
    if "id" in payload and not isinstance(payload["id"], str):
        errors.append("$.id: expected string")
    if "files" in payload and not isinstance(payload["files"], list):
        errors.append("$.files: expected array")
    if "contract_valid" in payload and not isinstance(payload["contract_valid"], bool):
        errors.append("$.contract_valid: expected boolean")
    if "format_cleaning_applied" in payload and not isinstance(payload["format_cleaning_applied"], bool):
        errors.append("$.format_cleaning_applied: expected boolean")
    if "failure_family" in payload and payload.get("failure_family") not in {"", *FAILURE_FAMILIES}:
        errors.append("$.failure_family: invalid failure family")
    return errors


def validate_task_harness_report(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ["spec_id", "mode", "run_dir", "kpis", "expectations", "overall_status"]:
        if key not in payload:
            errors.append(f"$.{key}: missing required key")
    if payload.get("overall_status") not in {"pass", "fail"}:
        errors.append("$.overall_status: expected 'pass' or 'fail'")
    if not isinstance(payload.get("kpis", {}), dict):
        errors.append("$.kpis: expected object")
    return errors


def strip_code_fences(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip(), True
    return text, False


def extract_json_object(text: str) -> tuple[str, str, bool]:
    stripped, changed = strip_code_fences(text)
    start_candidates = [idx for idx in [stripped.find("{"), stripped.find("[")] if idx >= 0]
    if not start_candidates:
        return stripped.strip(), "no_json_found", changed
    start = min(start_candidates)
    open_char = stripped[start]
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    end = -1
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end == -1:
        return stripped[start:].strip(), "truncated_json", True
    candidate = stripped[start:end].strip()
    return candidate, "cleaned" if (changed or start > 0 or end < len(stripped)) else "exact", (changed or start > 0 or end < len(stripped))


def clean_json_payload(text: str) -> dict[str, Any]:
    if not text.strip():
        return {
            "cleaned_text": "",
            "parse_status": "empty",
            "format_cleaning_applied": False,
            "parsed": None,
            "errors": ["empty output"],
        }
    cleaned_text, parse_status, changed = extract_json_object(text)
    try:
        parsed = json.loads(cleaned_text)
        return {
            "cleaned_text": cleaned_text,
            "parse_status": parse_status,
            "format_cleaning_applied": changed,
            "parsed": parsed,
            "errors": [],
        }
    except json.JSONDecodeError as exc:
        return {
            "cleaned_text": cleaned_text,
            "parse_status": "invalid_json" if parse_status != "truncated_json" else parse_status,
            "format_cleaning_applied": changed,
            "parsed": None,
            "errors": [f"json decode error: {exc.msg}"],
        }


def is_within(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def detect_prompt_injection(text: str) -> list[str]:
    hits = []
    lowered = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            hits.append(pattern)
    return hits


def guard_input_spec(spec: dict[str, Any], spec_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    blocked = False
    repo_root = ROOT.resolve()
    for key in ["id", "goal", "jobs"]:
        if key not in spec:
            errors.append(f"missing required spec field: {key}")
    if not isinstance(spec.get("jobs", []), list) or not spec.get("jobs"):
        errors.append("jobs must be a non-empty array")
    scope_subdir = str(spec.get("scope_subdir", "."))
    scope_path = (ROOT / scope_subdir).resolve()
    if not is_within(repo_root, scope_path):
        errors.append("scope_subdir points outside repository root")
    if spec.get("scope_copy_from"):
        copy_path = (ROOT / str(spec["scope_copy_from"])).resolve()
        if not is_within(repo_root, copy_path):
            errors.append("scope_copy_from points outside repository root")
    flagged_jobs: list[str] = []
    for job in spec.get("jobs", []):
        job_id = str(job.get("id", "unknown"))
        instruction = str(job.get("instruction", ""))
        if len(instruction) > 8000:
            errors.append(f"{job_id}: instruction too long")
        injection_hits = detect_prompt_injection(instruction)
        if injection_hits:
            blocked = True
            flagged_jobs.append(job_id)
            errors.append(f"{job_id}: prompt injection suspected")
        for rel in job.get("files", []):
            target = (scope_path / rel).resolve()
            if not is_within(scope_path, target):
                errors.append(f"{job_id}: file escapes scope: {rel}")
    return {
        "spec_file": str(spec_path),
        "blocked": blocked or bool(errors and any("prompt injection" in item or "outside" in item for item in errors)),
        "flagged_jobs": flagged_jobs,
        "errors": errors,
        "failure_family": "PROMPT_INJECTION_SUSPECTED" if flagged_jobs else "INPUT_POLICY_BLOCKED" if errors else "",
    }


def guard_output_artifact(status: dict[str, Any], artifact_verify: dict[str, Any] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    claim_items = status.get("key_claims", [])
    if status.get("status") == "SUCCESS":
        note = str(status.get("verification_note", "")).strip()
        if not note:
            failures.append("empty_verification_note")
        confidence = str(status.get("confidence", "")).lower()
        limitations = status.get("limitations", []) or []
        if confidence == "high" and limitations:
            failures.append("confidence_limitations_conflict")
        if not claim_items:
            failures.append("missing_key_claims")
        if any(not item.get("evidence_refs") for item in claim_items if isinstance(item, dict)):
            failures.append("missing_evidence_refs")
        if artifact_verify and not artifact_verify.get("all_passed", True):
            failures.append("artifact_verify_failed")
    return {
        "policy_blocked": bool(failures),
        "guard_failures": failures,
        "failure_family": "OUTPUT_POLICY_BLOCKED" if failures else "",
    }

