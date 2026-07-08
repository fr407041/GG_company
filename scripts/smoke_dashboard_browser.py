from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "agent_os_mvp"
BACKEND_DIR = APP_ROOT / "backend"
FRONTEND_DIR = APP_ROOT / "frontend"
LOG_DIR = APP_ROOT / "logs"


def find_pnpm() -> str:
    found = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if found:
        return found
    bundled = (
        Path(os.environ.get("USERPROFILE", ""))
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "bin"
        / "pnpm.cmd"
    )
    return str(bundled) if bundled.exists() else "pnpm"


def wait_http(url: str, timeout_sec: int) -> str:
    deadline = time.time() + timeout_sec
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.read().decode("utf-8", errors="replace")
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not become ready within {timeout_sec}s. Last error: {last_error}")


def start_process(command: list[str], cwd: Path, env: dict[str, str], log_name: str) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    handle = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )


def run_browser_assertions(frontend_url: str, timeout_sec: int) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for the browser smoke. Install it in the test environment "
            "or run this check only in CI jobs that provide Playwright."
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(frontend_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            page.get_by_text("Run Operations").wait_for(timeout=timeout_sec * 1000)
            for label in ["Overview", "Agents", "Guards", "Artifacts", "Runs", "Debug"]:
                page.get_by_role("button", name=label).click(timeout=5000)
                page.get_by_text(label).first.wait_for(timeout=5000)
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch dashboard on temporary ports and verify the first screen in a browser.")
    parser.add_argument("--backend-port", type=int, default=8041)
    parser.add_argument("--frontend-port", type=int, default=5207)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--skip-browser", action="store_true", help="Only run HTTP/API readiness checks.")
    args = parser.parse_args()

    backend_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not backend_python.exists():
        backend_python = Path(sys.executable)

    env = os.environ.copy()
    backend = start_process(
        [
            str(backend_python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.backend_port),
        ],
        BACKEND_DIR,
        env,
        f"browser-smoke-backend-{args.backend_port}.log",
    )

    frontend_env = dict(env)
    frontend_env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{args.backend_port}"
    frontend = start_process(
        [find_pnpm(), "run", "dev", "--host", "127.0.0.1", "--port", str(args.frontend_port)],
        FRONTEND_DIR,
        frontend_env,
        f"browser-smoke-frontend-{args.frontend_port}.log",
    )

    try:
        wait_http(f"http://127.0.0.1:{args.backend_port}/health", args.timeout_sec)
        monitor = wait_http(f"http://127.0.0.1:{args.backend_port}/api/ai-company-monitor", args.timeout_sec)
        if "latest_run" not in monitor or "recent_runs" not in monitor:
            raise RuntimeError("Monitor API payload is missing expected run fields.")
        wait_http(f"http://127.0.0.1:{args.frontend_port}/", args.timeout_sec)
        if not args.skip_browser:
            run_browser_assertions(f"http://127.0.0.1:{args.frontend_port}/", args.timeout_sec)
    finally:
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.terminate()
        for proc in (frontend, backend):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    print(
        {
            "backend": f"http://127.0.0.1:{args.backend_port}",
            "frontend": f"http://127.0.0.1:{args.frontend_port}",
            "browser_checked": not args.skip_browser,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
