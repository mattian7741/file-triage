"""
Configuration for folder semantics: ignore list, hide list, and name aliases.

- folder.ignore: foldernames/patterns to treat as leaves (included in graph, not recursed into).
  Lines may contain * or ? as glob patterns; matching is case-insensitive.
- folder.hide: foldernames/patterns to omit from the graph when they are logical leaves only.
  Same format as folder.ignore; hidden folders are not rendered at all.
- folder.alias: lines of space-separated equivalent foldernames/patterns; first is primary.
  Tokens containing * or ? are treated as glob patterns; matching is case-insensitive.

Names with spaces: use double quotes (e.g. "my documents") or backslash-escape the space
(e.g. my\\ documents). Same for all folder.* config files.
"""

from __future__ import annotations

import fnmatch
import shlex
from pathlib import Path


def _tokenize_line(s: str) -> list[str]:
    """Split line into tokens, respecting double quotes and backslash escapes. Uses shlex."""
    try:
        return shlex.split(s, posix=True)
    except ValueError:
        return []  # e.g. unbalanced quotes


def _is_glob(token: str) -> bool:
    """True if token contains * or ? (glob pattern)."""
    return "*" in token or "?" in token


def load_folder_ignore(config_path: Path) -> tuple[set[str], list[str]]:
    """
    Load folder.ignore: one foldername or pattern per line (strip, skip blank and #).

    Tokens containing * or ? are glob patterns; others are literal. Matching is case-insensitive.

    Returns:
        exact_ignore: set of lowercase literal names to ignore
        ignore_patterns: list of lowercase glob patterns to ignore
    """
    exact_ignore: set[str] = set()
    ignore_patterns: list[str] = []
    if not config_path.is_file():
        return exact_ignore, ignore_patterns
    for line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        for key in _tokenize_line(s):
            key_lower = key.lower()
            if _is_glob(key):
                ignore_patterns.append(key_lower)
            else:
                exact_ignore.add(key_lower)
    return exact_ignore, ignore_patterns


def should_ignore(name: str, exact_ignore: set[str], ignore_patterns: list[str]) -> bool:
    """True if the given foldername should be ignored (not recursed into). Case-insensitive."""
    key = name.lower()
    if key in exact_ignore:
        return True
    return any(fnmatch.fnmatch(key, p) for p in ignore_patterns)


def load_folder_hide(config_path: Path) -> tuple[set[str], list[str]]:
    """
    Load folder.hide: one foldername or pattern per line (strip, skip blank and #).

    Same format as folder.ignore. Matching is case-insensitive. Only folders that are
    logical leaves (no children on disk, or in folder.ignore) may be hidden.

    Returns:
        exact_hide: set of lowercase literal names to hide when logical leaf
        hide_patterns: list of lowercase glob patterns to hide when logical leaf
    """
    exact_hide: set[str] = set()
    hide_patterns: list[str] = []
    if not config_path.is_file():
        return exact_hide, hide_patterns
    for line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        for key in _tokenize_line(s):
            key_lower = key.lower()
            if _is_glob(key):
                hide_patterns.append(key_lower)
            else:
                exact_hide.add(key_lower)
    return exact_hide, hide_patterns


def should_hide(name: str, exact_hide: set[str], hide_patterns: list[str]) -> bool:
    """True if the given foldername matches the hide list. Case-insensitive."""
    key = name.lower()
    if key in exact_hide:
        return True
    return any(fnmatch.fnmatch(key, p) for p in hide_patterns)


def load_folder_alias(config_path: Path) -> tuple[dict[str, str], dict[str, list[str]], list[tuple[str, str]]]:
    """
    Load folder.alias: each line is space-separated names/patterns; first is primary.

    Tokens containing * or ? are glob patterns (e.g. backup*, *_archive); others are literal.
    Matching is case-insensitive. Node labels keep original tokens from the file.

    Returns:
        name_to_primary: map from lowercase literal name -> canonical (lowercase primary)
        primary_to_group: map from canonical (lowercase) -> full list [primary, alias1, ...] for node label
        alias_patterns: list of (pattern_lower, canonical) for glob matching
    """
    name_to_primary: dict[str, str] = {}
    primary_to_group: dict[str, list[str]] = {}
    alias_patterns: list[tuple[str, str]] = []
    if not config_path.is_file():
        return name_to_primary, primary_to_group, alias_patterns
    for line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        tokens = _tokenize_line(s)
        if not tokens:
            continue
        primary = tokens[0]
        canonical = primary.lower()
        group = list(dict.fromkeys(tokens))  # preserve order, no dupes (original casing)
        primary_to_group[canonical] = group
        for name in group:
            key = name.lower()
            if _is_glob(name):
                alias_patterns.append((key, canonical))
            else:
                name_to_primary[key] = canonical
    return name_to_primary, primary_to_group, alias_patterns
