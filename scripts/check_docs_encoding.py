from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PATHS = [
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "agent_os_mvp" / "README.zh-TW.md",
]

MOJIBAKE_MARKERS = [
    "\ufffd",
    "?\uea53",
    "?\uf388",
    "?\uf55d",
    "\u5697",
    "\u929d",
    "\u96ff",
    "\u761d",
    "\u6470",
    "\u876f",
]


def iter_markdown_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
    return files


def check_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"cannot decode as UTF-8: {exc}"]

    failures: list[str] = []
    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            failures.append(f"contains mojibake marker {marker!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Chinese docs are UTF-8 and not mojibake.")
    parser.add_argument("paths", nargs="*", help="Files or directories to check. Defaults to README and docs.")
    args = parser.parse_args()

    paths = [Path(item).resolve() for item in args.paths] if args.paths else DEFAULT_PATHS
    files = iter_markdown_files(paths)
    if not files:
        print("No markdown files found.")
        return 1

    failures: list[tuple[Path, list[str]]] = []
    for file_path in files:
        result = check_file(file_path)
        if result:
            failures.append((file_path, result))

    if failures:
        print("Documentation encoding check failed:")
        for file_path, reasons in failures:
            rel = file_path.relative_to(ROOT) if file_path.is_relative_to(ROOT) else file_path
            print(f"- {rel}")
            for reason in reasons:
                print(f"  - {reason}")
        return 1

    print(f"Documentation encoding check passed ({len(files)} markdown files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
