"""Claude Code PostToolUse hook: format + lint any backend Python file Claude edits.

Claude Code sends JSON describing the edit on stdin. If the edited file is a
.py file inside backend/, we run `ruff format` and `ruff check --fix` on it.
If ruff still finds problems it can't auto-fix, we exit with code 2 — Claude Code
then shows the error text to Claude, who fixes it immediately.
"""

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def ruff(*args: str, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--quiet", "ruff", *args, str(target)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return 0

    try:
        target = Path(file_path).resolve().relative_to(BACKEND)
    except ValueError:
        return 0  # not inside backend/

    ruff("format", target=target)
    result = ruff("check", "--fix", target=target)
    if result.returncode != 0:
        print(
            f"ruff found problems it could not auto-fix in backend/{target.as_posix()}:\n"
            f"{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
