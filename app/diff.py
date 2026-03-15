"""
Diff generation between base and tailored LaTeX source.

Produces a line-by-line unified diff for display in the Streamlit UI.
Lines are classified as added, removed, or unchanged for color rendering.
"""

import difflib
from dataclasses import dataclass
from typing import Literal


@dataclass
class DiffLine:
    kind: Literal["added", "removed", "unchanged"]
    text: str


def generate_diff(base_tex: str, tailored_tex: str) -> list[DiffLine]:
    """
    Compare base and tailored LaTeX line by line.

    Returns a list of DiffLine objects representing the full diff.
    Empty inputs return an empty list rather than raising.
    """
    if not base_tex and not tailored_tex:
        return []

    base_lines = base_tex.splitlines(keepends=False)
    tailored_lines = tailored_tex.splitlines(keepends=False)

    diff_lines: list[DiffLine] = []

    matcher = difflib.SequenceMatcher(None, base_lines, tailored_lines, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for line in base_lines[i1:i2]:
                diff_lines.append(DiffLine(kind="unchanged", text=line))
        elif op in ("replace", "delete"):
            for line in base_lines[i1:i2]:
                diff_lines.append(DiffLine(kind="removed", text=line))
            if op == "replace":
                for line in tailored_lines[j1:j2]:
                    diff_lines.append(DiffLine(kind="added", text=line))
        elif op == "insert":
            for line in tailored_lines[j1:j2]:
                diff_lines.append(DiffLine(kind="added", text=line))

    return diff_lines


def diff_to_html(diff_lines: list[DiffLine]) -> str:
    """
    Render a diff as an HTML string for st.markdown(unsafe_allow_html=True).

    Added lines:   green background
    Removed lines: red background
    Unchanged:     plain
    """
    styles = {
        "added":     "background-color:#1a472a; color:#90ee90; font-family:monospace; white-space:pre; display:block; padding:0 4px;",
        "removed":   "background-color:#4a1a1a; color:#ff9090; font-family:monospace; white-space:pre; display:block; padding:0 4px;",
        "unchanged": "font-family:monospace; white-space:pre; display:block; padding:0 4px; color:#cccccc;",
    }
    prefix = {"added": "+ ", "removed": "- ", "unchanged": "  "}

    html_parts = ['<div style="background:#1e1e1e; padding:8px; border-radius:4px; overflow-x:auto;">']
    for line in diff_lines:
        escaped = line.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts.append(
            f'<span style="{styles[line.kind]}">{prefix[line.kind]}{escaped}</span>'
        )
    html_parts.append("</div>")
    return "\n".join(html_parts)


def has_changes(diff_lines: list[DiffLine]) -> bool:
    """Return True if the diff contains any added or removed lines."""
    return any(line.kind != "unchanged" for line in diff_lines)
