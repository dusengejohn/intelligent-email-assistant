"""Claude Code PostToolUse hook: format + lint any Python file Claude edits.

Claude Code sends JSON describing the edit on stdin. If the edited file is a
.py file inside one of the Python projects (backend/, generator/), we run
`ruff format` and `ruff check --fix` on it with that project's ruff and config.
If ruff still finds problems it can't auto-fix, we exit with code 2 — Claude Code
then shows the error text to Claude, who fixes it immediately.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS = [REPO_ROOT / "backend", REPO_ROOT / "generator"]


def ruff(*args: str, project: Path, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--quiet", "ruff", *args, str(target)],
        cwd=project,
        capture_output=True,
        text=True,
    )


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return 0

    path = Path(file_path).resolve()
    project = next((p for p in PROJECTS if path.is_relative_to(p)), None)
    if project is None:
        return 0  # not inside a Python project
    target = path.relative_to(project)

    ruff("format", project=project, target=target)
    result = ruff("check", "--fix", project=project, target=target)
    if result.returncode != 0:
        print(
            f"ruff found problems it could not auto-fix in "
            f"{project.name}/{target.as_posix()}:\n"
            f"{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
