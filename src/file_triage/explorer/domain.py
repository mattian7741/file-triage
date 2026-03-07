"""
Domain types and pure logic for Explorer listing/tags.

No I/O, no Flask, no sqlite. All functions are deterministic and testable.
"""

from __future__ import annotations

from typing import Any


def effective_tags(explicit: list[str], inherited: list[str], negation: list[str]) -> set[str]:
    """Compute effective tag set: (explicit ∪ inherited) ∖ negation. Pure."""
    return (set(explicit) | set(inherited)) - set(negation)


def entry_empty(
    is_dir: bool,
    size: int,
    *,
    recursive_empty: bool = True,
    has_vpath_children: bool = False,
) -> bool:
    """
    Whether an entry counts as empty for display.

    - File: empty iff size == 0.
    - Dir: empty iff recursive_empty and not has_vpath_children.
    """
    if not is_dir:
        return size == 0
    return recursive_empty and not has_vpath_children


def effective_path(entry: dict[str, Any]) -> str:
    """EFFECTIVE_PATH = vpath or path; for sorting/display. Case-insensitive."""
    return (entry.get("vpath") or entry.get("path") or "").lower()


def should_exclude_by_hide_tags(
    effective: set[str],
    hide_tags: set[str],
) -> bool:
    """True if entry should be excluded because effective tags intersect hide_tags."""
    return bool(hide_tags and (effective & hide_tags))


def build_listing_entry(
    *,
    name: str,
    path: str,
    is_dir: bool,
    size: int = 0,
    empty: bool = False,
    tags: list[str],
    tags_inherited: list[str],
    tags_negation: list[str],
    hide_tags: set[str],
    display_style: str = "normal",
    vpath: str | None = None,
    virtual: bool = False,
    has_direct_match: bool | None = None,
) -> dict[str, Any] | None:
    """
    Build one listing entry dict or None if excluded by hide_tags.

    All tag lists and hide_tags are used to compute effective set; if
    effective & hide_tags is non-empty, returns None. Otherwise returns
    the full entry dict for API response.
    """
    eff = effective_tags(tags, tags_inherited, tags_negation)
    if should_exclude_by_hide_tags(eff, hide_tags):
        return None
    entry: dict[str, Any] = {
        "name": name,
        "path": path,
        "is_dir": is_dir,
        "size": size,
        "empty": empty,
        "tags": tags,
        "tags_inherited": tags_inherited,
        "tags_negation": tags_negation,
        "display_style": display_style,
    }
    if vpath is not None:
        entry["vpath"] = vpath
    if virtual:
        entry["virtual"] = True
    if has_direct_match is not None:
        entry["has_direct_match"] = has_direct_match
    return entry
