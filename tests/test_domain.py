"""Pure domain tests: effective_tags, entry_empty, build_listing_entry, should_exclude_by_hide_tags."""

import pytest
from file_triage.explorer.domain import (
    effective_tags,
    entry_empty,
    build_listing_entry,
    should_exclude_by_hide_tags,
    effective_path,
)


class TestEffectiveTags:
    def test_explicit_only(self):
        assert effective_tags(["a", "b"], [], []) == {"a", "b"}

    def test_union_inherited(self):
        assert effective_tags(["a"], ["b", "c"], []) == {"a", "b", "c"}

    def test_null_removes(self):
        assert effective_tags(["a", "b"], ["c"], ["b"]) == {"a", "c"}

    def test_all_empty(self):
        assert effective_tags([], [], []) == set()


class TestEntryEmpty:
    def test_file_nonzero_size(self):
        assert entry_empty(False, 1) is False

    def test_file_zero_size(self):
        assert entry_empty(False, 0) is True

    def test_dir_recursive_empty_no_vpath_children(self):
        assert entry_empty(True, 0, recursive_empty=True, has_vpath_children=False) is True

    def test_dir_has_vpath_children(self):
        assert entry_empty(True, 0, recursive_empty=True, has_vpath_children=True) is False

    def test_dir_not_recursive_empty(self):
        assert entry_empty(True, 0, recursive_empty=False, has_vpath_children=False) is False


class TestShouldExcludeByHideTags:
    def test_no_hide_tags(self):
        assert should_exclude_by_hide_tags({"a"}, set()) is False

    def test_no_overlap(self):
        assert should_exclude_by_hide_tags({"a"}, {"b"}) is False

    def test_overlap(self):
        assert should_exclude_by_hide_tags({"a", "b"}, {"b"}) is True


class TestBuildListingEntry:
    def test_returns_none_when_excluded_by_hide_tags(self):
        result = build_listing_entry(
            name="x",
            path="/p",
            is_dir=False,
            size=0,
            empty=True,
            tags=["a"],
            tags_inherited=[],
            tags_null=[],
            hide_tags={"a"},
        )
        assert result is None

    def test_returns_entry_when_not_excluded(self):
        result = build_listing_entry(
            name="x",
            path="/p",
            is_dir=False,
            size=0,
            empty=True,
            tags=["a"],
            tags_inherited=[],
            tags_null=[],
            hide_tags={"b"},
        )
        assert result is not None
        assert result["name"] == "x"
        assert result["path"] == "/p"
        assert result["tags"] == ["a"]
        assert result["empty"] is True

    def test_includes_vpath_when_given(self):
        result = build_listing_entry(
            name="x",
            path="/p",
            is_dir=True,
            size=0,
            empty=True,
            tags=[],
            tags_inherited=[],
            tags_null=[],
            hide_tags=set(),
            vpath="/v/p",
        )
        assert result["vpath"] == "/v/p"

    def test_includes_has_direct_match_when_given(self):
        result = build_listing_entry(
            name="x",
            path="/p",
            is_dir=True,
            size=0,
            empty=True,
            tags=[],
            tags_inherited=[],
            tags_null=[],
            hide_tags=set(),
            has_direct_match=True,
        )
        assert result["has_direct_match"] is True


class TestEffectivePath:
    def test_prefers_vpath(self):
        assert effective_path({"path": "/a", "vpath": "/b"}) == "/b"

    def test_falls_back_to_path(self):
        assert effective_path({"path": "/a"}) == "/a"

    def test_lowercase(self):
        assert effective_path({"path": "/A/B"}) == "/a/b"
