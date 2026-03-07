"""
Typed request/response shapes for Explorer API boundary.

Use TypedDict for JSON bodies and responses where feasible; keeps contract and code aligned.
"""

from __future__ import annotations

from typing import TypedDict, Any


class ErrorDetail(TypedDict, total=False):
    """Shape of the 'error' object in the canonical error envelope."""
    code: str
    message: str
    retryable: bool
    details: dict[str, Any]


class ErrorEnvelope(TypedDict):
    """Canonical error response: { \"error\": { \"code\", \"message\", \"retryable\"?, \"details\"? } }."""
    error: ErrorDetail


class ListingEntry(TypedDict, total=False):
    """One entry in listing/tagged/tag-search responses."""
    name: str
    path: str
    is_dir: bool
    size: int
    empty: bool
    tags: list[str]
    tags_inherited: list[str]
    tags_negation: list[str]
    vpath: str
    display_style: str
    virtual: bool
    has_direct_match: bool


class ListingResponse(TypedDict, total=False):
    """Response shape for GET /api/listing."""
    path: str
    entries: list[ListingEntry]
    all_tags_in_scope: list[str]
