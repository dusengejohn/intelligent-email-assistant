"""Claude Code PostToolUse hook: lint + auto-fix any frontend TS/JS file Claude edits.

Same idea as ruff_after_edit.py, for the frontend: run `eslint --fix` on the edited
file. Exit code 2 sends the remaining problems back to Claude to fix.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(EXTENSIONS):
        return 0

    try:
        target = Path(file_path).resolve().relative_to(FRONTEND)
    except ValueError:
        return 0  # not inside frontend/

    if not (FRONTEND / "node_modules").exists() or shutil.which("npx") is None:
        print("eslint hook skipped: run `npm install` in frontend/ first", file=sys.stderr)
        return 0

    result = subprocess.run(
        ["npx", "--no-install", "eslint", "--fix", str(target)],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"eslint found problems it could not auto-fix in frontend/{target.as_posix()}:\n"
            f"{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
