"""
Canonical error envelope and response helper for Explorer API.

All error responses use the same shape so clients can rely on a stable contract.
No stack traces or internal details leak in responses; log at the route instead.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify, Response

# Stable error codes for client handling; message is human-readable, code is stable.
ERROR_CODES = (
    "PATH_REQUIRED",
    "PATH_NOT_ALLOWED",
    "VPATH_NOT_ALLOWED",
    "NOT_A_DIRECTORY",
    "NOT_A_FILE",
    "TAG_REQUIRED",
    "INVALID_TAG",
    "PATTERN_REQUIRED",
    "OLD_AND_NEW_PATTERN_REQUIRED",
    "PATTERN_AND_TAG_REQUIRED",
    "PATH_AND_TAG_REQUIRED",
    "PATH_AND_NAME_REQUIRED",
    "PATHS_MUST_BE_LIST",
    "INVALID_FOLDER_NAME",
    "UNSUPPORTED_TYPE",
    "NO_META_DB",
    "CONFLICT",
    "NOT_FOUND",
    "INTERNAL_ERROR",
)


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> tuple[Response, int]:
    """
    Build a canonical error response and HTTP status code.

    All Explorer API errors must use this so the contract is stable.
    Log full diagnostics (e.g. exception) at the route before calling this;
    do not put stack traces or internal details in message or details.

    Args:
        code: Stable error code (e.g. PATH_REQUIRED, PATH_NOT_ALLOWED).
        message: Human-readable message safe to show to the user.
        status_code: HTTP status (400, 403, 404, 409, 500).
        retryable: True if the client may retry the same request.
        details: Optional structured details; must not contain sensitive data.

    Returns:
        (Flask Response, status_code) for use as: return error_response(...)
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        }
    }
    if details:
        body["error"]["details"] = details
    return jsonify(body), status_code
