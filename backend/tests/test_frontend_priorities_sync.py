"""The frontend's copy of the priority labels and colors must match app/priorities.py.

Python and TypeScript can't share one file, so frontend/src/priorities.ts mirrors
the backend. This test reads that TS file and fails if the copies drift apart
(story 2.5, issue #50).
"""

import re
from pathlib import Path

from app.priorities import PRIORITIES

TS_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "priorities.ts"

# One entry per priority, e.g.:  critical: { label: 'Critical', color: '#DC2626' },
ENTRY = re.compile(r"(\w+):\s*\{\s*label:\s*'([^']+)',\s*color:\s*'(#[0-9A-Fa-f]{6})'\s*\}")


def test_frontend_labels_and_colors_match_the_backend() -> None:
    frontend = {
        name: (label, color.upper()) for name, label, color in ENTRY.findall(TS_FILE.read_text())
    }
    backend = {p.value: (info.label, info.color.upper()) for p, info in PRIORITIES.items()}

    assert frontend == backend
