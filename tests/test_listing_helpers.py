"""Tests for listing_helpers: resolve_tags, build_listing_entry_from_meta, compute_empty."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from file_triage.explorer.listing_helpers import (
    resolve_tags,
    build_listing_entry_from_meta,
    compute_empty,
)


class TestResolveTags:
    """Single tag-resolution path."""

    def test_none_accessor_returns_empty(self):
        tags, inherited, nulls = resolve_tags(None, "/some/path")
        assert tags == []
        assert inherited == []
        assert nulls == []

    def test_uses_accessor_get_tags(self):
        acc = MagicMock()
        acc.get_tags.return_value = ["a", "b"]
        acc.get_tags_from_rules.return_value = []
        acc.get_ancestor_tags.return_value = []
        acc.get_tag_nulls.return_value = []
        tags, inherited, nulls = resolve_tags(acc, "/p")
        assert tags == ["a", "b"]
        acc.get_tags.assert_called_once_with("/p")

    def test_combines_rules_and_ancestors_for_inherited(self):
        acc = MagicMock()
        acc.get_tags.return_value = []
        acc.get_tags_from_rules.return_value = ["r1"]
        acc.get_ancestor_tags.return_value = ["a1"]
        acc.get_tag_nulls.return_value = []
        _, inherited, _ = resolve_tags(acc, "/p", scope_for_rules="/scope")
        assert set(inherited) == {"r1", "a1"}
        acc.get_tags_from_rules.assert_called_once_with("/scope")
        acc.get_ancestor_tags.assert_called_once_with("/p")

    def test_returns_nulls(self):
        acc = MagicMock()
        acc.get_tags.return_value = []
        acc.get_tags_from_rules.return_value = []
        acc.get_ancestor_tags.return_value = []
        acc.get_tag_nulls.return_value = ["n1"]
        _, _, nulls = resolve_tags(acc, "/p")
        assert nulls == ["n1"]


class TestBuildListingEntryFromMeta:
    """Single entry-build path."""

    def test_none_accessor_builds_entry_with_no_tags(self):
        entry = build_listing_entry_from_meta(
            None,
            "/p/x",
            "x",
            is_dir=False,
            size=0,
            hide_tags=set(),
            path_obj=None,
        )
        assert entry is not None
        assert entry["name"] == "x"
        assert entry["path"] == "/p/x"
        assert entry["tags"] == []
        assert entry["tags_inherited"] == []
        assert entry["tags_null"] == []
        assert entry["empty"] is True

    def test_excluded_by_hide_tags_returns_none(self):
        acc = MagicMock()
        acc.get_tags.return_value = ["a"]
        acc.get_tags_from_rules.return_value = []
        acc.get_ancestor_tags.return_value = []
        acc.get_tag_nulls.return_value = []
        entry = build_listing_entry_from_meta(
            acc,
            "/p",
            "x",
            is_dir=False,
            size=0,
            hide_tags={"a"},
        )
        assert entry is None

    def test_file_empty_from_size(self):
        entry = build_listing_entry_from_meta(
            None,
            "/p/f",
            "f",
            is_dir=False,
            size=0,
            hide_tags=set(),
        )
        assert entry["empty"] is True

    def test_file_non_empty_from_size(self):
        entry = build_listing_entry_from_meta(
            None,
            "/p/f",
            "f",
            is_dir=False,
            size=42,
            hide_tags=set(),
        )
        assert entry["empty"] is False

    def test_dir_no_path_obj_empty_true(self):
        entry = build_listing_entry_from_meta(
            None,
            "/p/d",
            "d",
            is_dir=True,
            size=0,
            hide_tags=set(),
            path_obj=None,
        )
        assert entry["empty"] is True

    def test_dir_with_path_obj_uses_compute_empty(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        entry = build_listing_entry_from_meta(
            None,
            str(empty_dir),
            "empty",
            is_dir=True,
            size=0,
            hide_tags=set(),
            path_obj=empty_dir,
            scope_for_vpath_children=str(empty_dir),
        )
        assert entry["empty"] is True

    def test_includes_vpath_and_display_style(self):
        entry = build_listing_entry_from_meta(
            None,
            "/p",
            "x",
            is_dir=False,
            size=0,
            hide_tags=set(),
            vpath="/v/p",
            display_style="moved_here",
        )
        assert entry["vpath"] == "/v/p"
        assert entry["display_style"] == "moved_here"


class TestComputeEmpty:
    """Single empty-computation path."""

    def test_file_zero_size(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("")
        assert compute_empty(f, False, 0, None) is True

    def test_file_nonzero_size(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("x")
        assert compute_empty(f, False, 1, None) is False

    def test_nonexistent_dir_returns_true(self):
        p = Path("/nonexistent/path/xyz")
        assert compute_empty(p, True, 0, None) is True
