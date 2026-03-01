"""
Listing helpers: empty computation and entry building for Explorer.

Used by listing and tag-search routes. No Flask; depends on domain only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import build_listing_entry, effective_path as domain_effective_path


def has_vpath(meta_accessor: Any, path: Path) -> bool:
    """True if path has a meta row with non-null vpath (moved/trashed)."""
    if not meta_accessor:
        return False
    try:
        path_str = str(path.resolve())
        meta = meta_accessor.get_path_meta(path_str)
        return meta is not None and bool(meta.get("vpath"))
    except Exception:
        return False


def is_empty_recursive(
    path: Path,
    visited: set[str] | None = None,
    meta_accessor: Any = None,
) -> bool:
    """True if path is a 0-byte file, or a directory with no children or whose descendants are all recursively empty.
    When meta_accessor is set, paths with non-null vpath are treated as not present (moved/trashed)."""
    if visited is None:
        visited = set()
    try:
        resolved = str(path.resolve())
        if resolved in visited:
            return False
        if path.is_file():
            if meta_accessor and has_vpath(meta_accessor, path):
                return True
            return path.stat().st_size == 0
        if not path.is_dir():
            return True
        visited.add(resolved)
        try:
            children = list(path.iterdir())
            if not children:
                return True
            for child in children:
                if meta_accessor and has_vpath(meta_accessor, child):
                    continue
                try:
                    if not is_empty_recursive(child, visited, meta_accessor):
                        return False
                except OSError:
                    return False
            return True
        finally:
            visited.discard(resolved)
    except OSError:
        return False


def entry_effective_path(e: dict) -> str:
    """EFFECTIVE_PATH = vpath or path; used for sorting. Case-insensitive."""
    return domain_effective_path(e)


def compute_empty(
    path: Path,
    is_dir: bool,
    size: int,
    meta_accessor: Any,
    scope_for_vpath_children: str | None = None,
) -> bool:
    """
    Whether the entry counts as empty for display.
    For files: size == 0. For dirs: recursively empty and no vpath children under scope.
    """
    if not is_dir:
        return size == 0
    try:
        empty = is_empty_recursive(path, meta_accessor=meta_accessor)
    except OSError:
        return True
    if empty and meta_accessor and scope_for_vpath_children:
        if meta_accessor.get_entries_by_vpath_parent(scope_for_vpath_children):
            empty = False
    return empty


def build_listing_entry_from_meta(
    meta_accessor: Any,
    path_str: str,
    name: str,
    is_dir: bool,
    size: int,
    empty: bool,
    hide_tags: set[str],
    *,
    display_style: str = "normal",
    vpath: str | None = None,
    virtual: bool = False,
    has_direct_match: bool | None = None,
    scope_for_rules: str | None = None,
) -> dict[str, Any] | None:
    """
    Resolve tags from meta, then build one listing entry (or None if excluded by hide_tags).
    When meta_accessor is None, builds entry with no tags (not excluded).
    """
    if meta_accessor is None:
        return build_listing_entry(
            name=name,
            path=path_str,
            is_dir=is_dir,
            size=size,
            empty=empty,
            tags=[],
            tags_inherited=[],
            tags_null=[],
            hide_tags=hide_tags,
            display_style=display_style,
            vpath=vpath,
            virtual=virtual,
            has_direct_match=has_direct_match,
        )
    scope = scope_for_rules if scope_for_rules is not None else path_str
    explicit = meta_accessor.get_tags(path_str)
    from_rules = meta_accessor.get_tags_from_rules(scope)
    from_ancestors = meta_accessor.get_ancestor_tags(path_str)
    inherited = list(dict.fromkeys(from_rules + from_ancestors))
    nulls = meta_accessor.get_tag_nulls(path_str)
    return build_listing_entry(
        name=name,
        path=path_str,
        is_dir=is_dir,
        size=size,
        empty=empty,
        tags=explicit,
        tags_inherited=inherited,
        tags_null=nulls,
        hide_tags=hide_tags,
        display_style=display_style,
        vpath=vpath,
        virtual=virtual,
        has_direct_match=has_direct_match,
    )
