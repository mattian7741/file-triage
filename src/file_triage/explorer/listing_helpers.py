"""
Listing helpers: tag resolution, empty computation, and entry building for Explorer.

Single code path for building listing entries. Used by listing, tagged, and tag-search routes.
No Flask; depends on domain only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import build_listing_entry, effective_path as domain_effective_path


def resolve_tags(
    meta_accessor: Any,
    path_str: str,
    scope_for_rules: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """
    Single tag-resolution path: given path and accessor, return (hard, inherited, negation).

    Inherited = rules-matched tags + ancestor tags (parent-chain semantics; unchanged in this iteration).
    When meta_accessor is None, returns ([], [], []).
    """
    if meta_accessor is None:
        return ([], [], [])
    scope = scope_for_rules if scope_for_rules is not None else path_str
    explicit = meta_accessor.get_tags(path_str)
    from_rules = meta_accessor.get_tags_from_rules(scope)
    from_ancestors = meta_accessor.get_ancestor_tags(path_str)
    inherited = list(dict.fromkeys(from_rules + from_ancestors))
    nulls = meta_accessor.get_tag_nulls(path_str)
    return (explicit, inherited, nulls)


def has_vpath(meta_accessor: Any, path: Path) -> bool:
    """True if path has a meta row with non-null vpath (location state set, e.g. moved/trashed)."""
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
    When meta_accessor is set, paths with location state set (vpath) are treated as not present."""
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
    When path does not exist on disk: dir → True, file → (size == 0).
    """
    if not is_dir:
        return size == 0
    try:
        if not path.exists():
            return True
    except OSError:
        return True
    try:
        empty = is_empty_recursive(path, meta_accessor=meta_accessor)
    except OSError:
        return True
    if empty and meta_accessor and scope_for_vpath_children:
        if meta_accessor.get_entries_by_vpath_parent(scope_for_vpath_children):
            empty = False
    return empty


def _compute_empty_for_entry(
    *,
    path_obj: Path | None,
    is_dir: bool,
    size: int,
    meta_accessor: Any,
    scope_for_vpath_children: str | None,
) -> bool:
    """Compute empty for an entry. Single path; used only by build_listing_entry_from_meta."""
    if not is_dir:
        return size == 0
    if path_obj is None:
        return True
    return compute_empty(
        path_obj,
        is_dir=True,
        size=0,
        meta_accessor=meta_accessor,
        scope_for_vpath_children=scope_for_vpath_children,
    )


def build_listing_entry_from_meta(
    meta_accessor: Any,
    path_str: str,
    name: str,
    is_dir: bool,
    size: int,
    hide_tags: set[str],
    *,
    path_obj: Path | None = None,
    scope_for_vpath_children: str | None = None,
    display_style: str = "normal",
    vpath: str | None = None,
    virtual: bool = False,
    has_direct_match: bool | None = None,
    scope_for_rules: str | None = None,
) -> dict[str, Any] | None:
    """
    Single entry-build path: resolve tags, compute empty, build entry.
    Returns full listing entry or None if excluded by hide_tags.
    When meta_accessor is None, builds entry with no tags (not excluded).
    """
    empty = _compute_empty_for_entry(
        path_obj=path_obj,
        is_dir=is_dir,
        size=size,
        meta_accessor=meta_accessor,
        scope_for_vpath_children=scope_for_vpath_children,
    )
    tags, tags_inherited, tags_null = resolve_tags(
        meta_accessor=meta_accessor,
        path_str=path_str,
        scope_for_rules=scope_for_rules or path_str,
    )
    return build_listing_entry(
        name=name,
        path=path_str,
        is_dir=is_dir,
        size=size,
        empty=empty,
        tags=tags,
        tags_inherited=tags_inherited,
        tags_null=tags_null,
        hide_tags=hide_tags,
        display_style=display_style,
        vpath=vpath,
        virtual=virtual,
        has_direct_match=has_direct_match,
    )
