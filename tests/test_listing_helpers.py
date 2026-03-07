"""Tests for listing_helpers: resolve_tags, build_listing_entry_from_meta, compute_empty."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from file_triage.explorer.listing_helpers import (
    resolve_tags,
    build_listing_entry_from_meta,
    compute_empty,
)
from file_triage.meta import init_db, add_tag, add_tag_null
from file_triage.meta.accessor import MetaAccessor


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
        acc.get_parent_effective_tags.return_value = []
        acc.get_tag_nulls.return_value = []
        tags, inherited, nulls = resolve_tags(acc, "/p")
        assert tags == ["a", "b"]
        acc.get_tags.assert_called_once_with("/p")

    def test_combines_rules_and_parent_for_inherited(self):
        acc = MagicMock()
        acc.get_tags.return_value = []
        acc.get_tags_from_rules.return_value = ["r1"]
        acc.get_parent_effective_tags.return_value = ["a1"]
        acc.get_tag_nulls.return_value = []
        _, inherited, _ = resolve_tags(acc, "/p", scope_for_rules="/scope")
        assert set(inherited) == {"r1", "a1"}
        acc.get_tags_from_rules.assert_called_once_with("/scope")
        acc.get_parent_effective_tags.assert_called_once_with("/p")

    def test_returns_nulls(self):
        acc = MagicMock()
        acc.get_tags.return_value = []
        acc.get_tags_from_rules.return_value = []
        acc.get_parent_effective_tags.return_value = []
        acc.get_tag_nulls.return_value = ["n1"]
        _, _, nulls = resolve_tags(acc, "/p")
        assert nulls == ["n1"]


class TestParentOnlyInheritance:
    """Parent-only inheritance: soft from parent's effective set; parent's negation → child absent."""

    def test_parent_has_tag_child_has_soft(self, tmp_path):
        """Parent has tag T → child has soft T."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" in inherited

    def test_parent_has_negation_child_absent(self, tmp_path):
        """Parent has negation T → child absent for T."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag_null
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag_null(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" not in inherited

    def test_grandparent_has_tag_parent_negation_child_absent(self, tmp_path):
        """Grandparent has T, parent has negation T → child absent for T."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag, add_tag_null
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag(db_path, tmp_path / "a", "T")
        add_tag_null(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" not in inherited


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
        acc.get_parent_effective_tags.return_value = []
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


class TestParentOnlyInheritance:
    """Parent-only inheritance: soft from parent's effective set; parent's negation → child absent."""

    def test_parent_has_tag_t_child_has_soft_t(self, tmp_path):
        """Parent has tag T → child has soft T (in inherited)."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" in inherited

    def test_parent_has_negation_t_child_absent_for_t(self, tmp_path):
        """Parent has negation T → child absent for T (T not in inherited)."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag_null
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag_null(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" not in inherited

    def test_grandparent_has_t_parent_has_negation_t_child_absent(self, tmp_path):
        """Grandparent has T, parent has negation T → child absent for T."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        db_path = tmp_path / "meta.db"
        from file_triage.meta import init_db, add_tag, add_tag_null
        from file_triage.meta.accessor import MetaAccessor

        init_db(db_path)
        add_tag(db_path, tmp_path / "a", "T")
        add_tag_null(db_path, tmp_path / "a" / "b", "T")
        acc = MetaAccessor(db_path)
        _, inherited, _ = resolve_tags(acc, str(tmp_path / "a" / "b" / "c"))
        assert "T" not in inherited


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
