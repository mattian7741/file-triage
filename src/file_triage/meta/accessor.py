"""
Meta accessor: abstraction over meta DB for Explorer.

Provides an injectable layer so the Explorer does not import meta.db directly.
All methods delegate to the existing db module; no business logic here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import db


class MetaAccessor:
    """
    Default meta accessor: wraps meta.db with a fixed db path.
    All methods take path/tag/etc. only; no db_path in the call.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path).resolve()

    def init_db(self) -> None:
        db.init_db(self._db_path)

    def get_tags(self, path: str | Path) -> list[str]:
        return db.get_tags(self._db_path, path)

    def get_tag_nulls(self, path: str | Path) -> list[str]:
        return db.get_tag_nulls(self._db_path, path)

    def get_path_meta(self, path: str | Path) -> dict[str, Any] | None:
        return db.get_path_meta(self._db_path, path)

    def get_meta_by_vpath(self, vpath: str) -> dict[str, Any] | None:
        return db.get_meta_by_vpath(self._db_path, vpath)

    def get_entries_by_vpath_parent(self, vpath_parent: str) -> list[dict[str, Any]]:
        return db.get_entries_by_vpath_parent(self._db_path, vpath_parent)

    def get_tags_from_rules(self, path: str | Path) -> list[str]:
        return db.get_tags_from_rules(self._db_path, path)

    def get_ancestor_tags(self, path: str | Path) -> list[str]:
        return db.get_ancestor_tags(self._db_path, path)

    def get_parent_effective_tags(self, path: str | Path) -> list[str]:
        """Parent-only inheritance: effective tags of the path's parent."""
        return db.get_parent_effective_tags(self._db_path, path)

    def get_paths_by_tag(self, tag: str) -> list[str]:
        return db.get_paths_by_tag(self._db_path, tag)

    def get_paths_by_tag_null(self, tag: str) -> list[str]:
        return db.get_paths_by_tag_null(self._db_path, tag)

    def get_virtual_children(self, parent_path: str | Path) -> list[str]:
        return db.get_virtual_children(self._db_path, parent_path)

    def get_all_tags(self) -> list[str]:
        return db.get_all_tags(self._db_path)

    def get_all_rules(self) -> list[dict[str, Any]]:
        return db.get_all_rules(self._db_path)

    def get_hidden_tags(self) -> list[str]:
        return db.get_hidden_tags(self._db_path)

    def get_moved_in_scopes(
        self,
        scope_left: str | None,
        scope_right: str | None,
    ) -> list[dict[str, Any]]:
        return db.get_moved_in_scopes(self._db_path, scope_left, scope_right)

    def get_all_meta_for_debug(self) -> list[dict[str, Any]]:
        return db.get_all_meta_for_debug(self._db_path)

    def add_tag(self, path: str | Path, tag: str) -> None:
        db.add_tag(self._db_path, path, tag)

    def remove_tag(self, path: str | Path, tag: str) -> None:
        db.remove_tag(self._db_path, path, tag)

    def add_tag_null(self, path: str | Path, tag: str) -> None:
        db.add_tag_null(self._db_path, path, tag)

    def remove_tag_null(self, path: str | Path, tag: str) -> None:
        db.remove_tag_null(self._db_path, path, tag)

    def add_hidden_tag(self, tag: str) -> None:
        db.add_hidden_tag(self._db_path, tag)

    def remove_hidden_tag(self, tag: str) -> None:
        db.remove_hidden_tag(self._db_path, tag)

    def add_rule_tag(self, pattern: str, tag: str) -> None:
        db.add_rule_tag(self._db_path, pattern, tag)

    def remove_rule_tag(self, pattern: str, tag: str) -> None:
        db.remove_rule_tag(self._db_path, pattern, tag)

    def remove_rule_pattern(self, pattern: str) -> None:
        db.remove_rule_pattern(self._db_path, pattern)

    def update_rule_pattern(self, old_pattern: str, new_pattern: str) -> None:
        db.update_rule_pattern(self._db_path, old_pattern, new_pattern)

    def add_virtual_folder(self, path: str | Path) -> str:
        return db.add_virtual_folder(self._db_path, path)

    def set_vpath(self, path: str | Path, vpath: str | None, job_id: str | None = None) -> None:
        db.set_vpath(self._db_path, path, vpath, job_id)

    def generate_commands(self, job_id: str | None = None) -> list[dict]:
        """Generate filesystem commands to materialize pending vpath changes. No execution."""
        return db.generate_commands(self._db_path, job_id)

    @property
    def db_path(self) -> Path:
        return self._db_path
