from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Any


ROOT = Path(__file__).resolve().parent.parent


class RateLimitTimeout(RuntimeError):
    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__("LLM_RATE_LIMIT_TIMEOUT")
        self.result = result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_state_file(value: str | Path | None) -> Path:
    configured = Path(str(value or "tmp/ai_company_llm_rate_limit.json"))
    return configured if configured.is_absolute() else ROOT / configured


def _acquire_file_lock(
    lock_path: Path,
    timeout_sec: float,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> float:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = now()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"pid": os.getpid(), "created_at": time.time()}))
            return max(0.0, now() - started)
        except FileExistsError:
            if now() - started >= timeout_sec:
                raise RateLimitTimeout(
                    {
                        "enabled": True,
                        "permit_acquired": False,
                        "wait_sec": round(max(0.0, now() - started), 3),
                        "request_count_window": 0,
                        "failure_family": "LLM_RATE_LIMIT_TIMEOUT",
                        "reason": "Timed out waiting for rate limiter lock.",
                    }
                )
            sleep(min(0.1, max(0.01, timeout_sec / 20)))


def acquire_llm_rate_limit(
    *,
    enabled: bool = True,
    requests_per_minute: int = 20,
    state_file: str | Path | None = None,
    timeout_sec: float = 300,
    now: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Acquire a process-safe permit for one LLM API request.

    The limiter combines a minimum inter-request spacing with a 60-second sliding
    window so it protects both steady-state and future parallel worker runs.
    """
    now_fn = now or time.time
    sleep_fn = sleep or time.sleep
    if not enabled:
        return {
            "enabled": False,
            "permit_acquired": True,
            "wait_sec": 0.0,
            "request_count_window": 0,
        }

    rpm = max(1, int(requests_per_minute))
    timeout = max(0.0, float(timeout_sec))
    state_path = _resolve_state_file(state_file)
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    started = now_fn()
    lock_wait = 0.0

    while True:
        try:
            lock_wait += _acquire_file_lock(lock_path, max(0.0, timeout - (now_fn() - started)), now_fn, sleep_fn)
            try:
                state = _read_json(state_path)
                current = now_fn()
                timestamps = [
                    float(item)
                    for item in state.get("request_timestamps", [])
                    if isinstance(item, (int, float)) and current - float(item) < 60.0
                ]
                last_request_at = float(state.get("last_request_at", 0.0) or 0.0)
                min_interval = 60.0 / float(rpm)
                wait_for_spacing = max(0.0, (last_request_at + min_interval) - current)
                wait_for_window = max(0.0, (timestamps[0] + 60.0) - current) if len(timestamps) >= rpm else 0.0
                wait_needed = max(wait_for_spacing, wait_for_window)
                elapsed = current - started
                if wait_needed <= 0:
                    timestamps.append(current)
                    _write_json(
                        state_path,
                        {
                            "request_timestamps": timestamps[-rpm:],
                            "last_request_at": current,
                            "requests_per_minute": rpm,
                            "updated_at": time.time(),
                        },
                    )
                    return {
                        "enabled": True,
                        "permit_acquired": True,
                        "wait_sec": round(max(0.0, current - started), 3),
                        "request_count_window": len(timestamps),
                        "requests_per_minute": rpm,
                        "state_file": str(state_path),
                    }
                if elapsed + wait_needed > timeout:
                    raise RateLimitTimeout(
                        {
                            "enabled": True,
                            "permit_acquired": False,
                            "wait_sec": round(elapsed, 3),
                            "request_count_window": len(timestamps),
                            "requests_per_minute": rpm,
                            "state_file": str(state_path),
                            "failure_family": "LLM_RATE_LIMIT_TIMEOUT",
                            "reason": "Timed out waiting for next LLM request slot.",
                        }
                    )
            finally:
                try:
                    lock_path.unlink()
                except OSError:
                    pass

            sleep_fn(min(wait_needed, max(0.01, timeout - (now_fn() - started))))
        except RateLimitTimeout:
            raise
