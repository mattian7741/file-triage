"""
Input validation at API boundaries.

Return an error response tuple to return from the route, or None if valid.
Use before processing path/tag/pattern so invalid input is rejected with the canonical error envelope.
"""

from __future__ import annotations

from pathlib import Path

from .errors import error_response


def require_path(path_raw: str) -> tuple | None:
    """Validate that path argument is non-empty. Returns error (response, status) tuple or None."""
    if not (path_raw or "").strip():
        return error_response("PATH_REQUIRED", "path required", 400)
    return None


def require_path_allowed(path: Path, roots: list[Path]) -> tuple | None:
    """If path is not under allowed roots, return error response tuple; else None."""
    from .roots import is_path_allowed
    if not is_path_allowed(path, roots):
        return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
    return None


def require_tag(tag: str) -> tuple | None:
    """Validate tag: non-empty, no comma/slash/backslash (reserved). Returns error tuple if invalid, else None."""
    t = (tag or "").strip()
    if not t:
        return error_response("TAG_REQUIRED", "tag required", 400)
    if "," in t or "/" in t or "\\" in t:
        return error_response("INVALID_TAG", "tag contains invalid characters", 400)
    return None


def require_pattern(pattern: str) -> tuple | None:
    """Validate pattern is non-empty. Returns error response tuple if invalid, else None."""
    if not (pattern or "").strip():
        return error_response("PATTERN_REQUIRED", "pattern required", 400)
    return None
