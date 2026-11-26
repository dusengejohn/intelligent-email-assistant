"""Claude Code PostToolUse hook: lint + auto-fix any TS/JS file Claude edits in a web project.

Web projects: the inbox (frontend/) and the generator's page (generator/web/).

Same idea as ruff_after_edit.py, for the frontend: run `eslint --fix` on the edited
file. Exit code 2 sends the remaining problems back to Claude to fix.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_PROJECTS = [REPO_ROOT / "frontend", REPO_ROOT / "generator" / "web"]
EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(EXTENSIONS):
        return 0

    path = Path(file_path).resolve()
    project = next((p for p in WEB_PROJECTS if path.is_relative_to(p)), None)
    if project is None:
        return 0  # not inside a web project
    target = path.relative_to(project)
    name = project.relative_to(REPO_ROOT).as_posix()

    if not (project / "node_modules").exists() or shutil.which("npx") is None:
        print(f"eslint hook skipped: run `npm install` in {name}/ first", file=sys.stderr)
        return 0

    result = subprocess.run(
        ["npx", "--no-install", "eslint", "--fix", str(target)],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"eslint found problems it could not auto-fix in {name}/{target.as_posix()}:\n"
            f"{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
