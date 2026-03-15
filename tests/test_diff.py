"""
Tests for diff.py — diff generation and rendering.

Covers:
  [C] Diff correctness: added/removed/unchanged lines classified correctly
      Edge cases: empty inputs, identical inputs, no base
"""

from app.diff import DiffLine, diff_to_html, generate_diff, has_changes


class TestGenerateDiff:
    def test_unchanged_lines_when_identical(self):
        tex = "line1\nline2\nline3"
        diff = generate_diff(tex, tex)
        assert all(line.kind == "unchanged" for line in diff)

    def test_detects_added_line(self):
        base = "line1\nline2"
        tailored = "line1\nline2\nline3 added"
        diff = generate_diff(base, tailored)
        added = [l for l in diff if l.kind == "added"]
        assert any("line3 added" in l.text for l in added)

    def test_detects_removed_line(self):
        base = "line1\nline2\nline3"
        tailored = "line1\nline3"
        diff = generate_diff(base, tailored)
        removed = [l for l in diff if l.kind == "removed"]
        assert any("line2" in l.text for l in removed)

    def test_detects_changed_line(self):
        base = "Built internal tools"
        tailored = "Designed and built scalable REST APIs"
        diff = generate_diff(base, tailored)
        kinds = {l.kind for l in diff}
        assert "removed" in kinds
        assert "added" in kinds

    def test_empty_inputs_returns_empty_list(self):
        assert generate_diff("", "") == []

    def test_empty_base_all_added(self):
        diff = generate_diff("", "new content\nmore content")
        assert all(l.kind == "added" for l in diff)

    def test_empty_tailored_all_removed(self):
        diff = generate_diff("old content\nmore", "")
        assert all(l.kind == "removed" for l in diff)


class TestHasChanges:
    def test_returns_false_for_identical(self):
        tex = "same\ncontent"
        diff = generate_diff(tex, tex)
        assert not has_changes(diff)

    def test_returns_true_when_diff_exists(self):
        diff = generate_diff("old", "new")
        assert has_changes(diff)

    def test_returns_false_for_empty_diff(self):
        assert not has_changes([])


class TestDiffToHtml:
    def test_returns_html_string(self):
        diff = [
            DiffLine(kind="unchanged", text="same line"),
            DiffLine(kind="added", text="new line"),
            DiffLine(kind="removed", text="old line"),
        ]
        html = diff_to_html(diff)
        assert "<div" in html
        assert "new line" in html
        assert "old line" in html

    def test_escapes_html_special_chars(self):
        diff = [DiffLine(kind="added", text="\\textbf{<Hello>}")]
        html = diff_to_html(diff)
        assert "&lt;Hello&gt;" in html
        assert "<Hello>" not in html

    def test_empty_diff_returns_wrapper_div(self):
        html = diff_to_html([])
        assert "<div" in html
