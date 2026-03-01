"""Preview and preview-file API routes."""

import logging
import mimetypes
import string
from pathlib import Path
from urllib.parse import quote

from flask import jsonify, request, send_file

from ..errors import error_response
from ..roots import is_path_allowed

_LOG = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".ico"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
_IMAGE_MIMETYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".avif": "image/avif", ".ico": "image/x-icon",
}
_VIDEO_MIMETYPES = {".mp4": "video/mp4", ".mov": "video/quicktime"}


def _content_mime_type(data: bytes) -> str | None:
    try:
        import magic
        return magic.from_buffer(data, mime=True) or None
    except Exception:
        return None


def _is_text_by_heuristic(data: bytes) -> bool:
    if not data:
        return True
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return False
    replacements = text.count("\ufffd")
    if len(text) > 0 and replacements / len(text) > 0.02:
        return False
    printable = set(string.printable) | {"\x0b", "\x0c"}
    non_printable = sum(1 for c in text if c not in printable and c != "\ufffd")
    if len(text) > 0 and non_printable / len(text) > 0.05:
        return False
    return True


def _is_text_file_content(data: bytes) -> bool:
    mime = _content_mime_type(data[:8192])
    if mime is not None and mime.startswith("text/"):
        return True
    return _is_text_by_heuristic(data)


def register_preview_routes(app, roots):
    """Register /api/preview and /api/preview-file."""
    @app.route("/api/preview")
    def api_preview():
        raw = (request.args.get("path") or "").strip()
        if not raw:
            return error_response("PATH_REQUIRED", "path required", 400)
        path = Path(raw)
        if not is_path_allowed(path, roots):
            return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
        try:
            if path.is_dir():
                return jsonify({"kind": "none", "reason": "directory"})
            suffix = path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                return jsonify({"kind": "image", "url": "/api/preview-file?path=" + quote(str(path.resolve()))})
            if suffix in VIDEO_EXTENSIONS:
                return jsonify({"kind": "video", "url": "/api/preview-file?path=" + quote(str(path.resolve()))})
            text_exts = {
                ".txt", ".md", ".log", ".py", ".js", ".ts", ".tsx", ".json", ".toml",
                ".ini", ".cfg", ".conf", ".yaml", ".yml", ".html", ".css", ".csv",
            }
            max_bytes = 100 * 1024
            data = path.read_bytes()
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            if suffix in text_exts:
                content = data.decode("utf-8", errors="replace")
                return jsonify({"kind": "text", "path": str(path.resolve()), "truncated": truncated, "content": content})
            if _is_text_file_content(data):
                content = data.decode("utf-8", errors="replace")
                return jsonify({"kind": "text", "path": str(path.resolve()), "truncated": truncated, "content": content})
            return jsonify({"kind": "unsupported", "reason": f"extension {suffix!r} not previewable"})
        except OSError:
            _LOG.exception("Preview failed for path")
            return error_response("INTERNAL_ERROR", "Preview failed", 500, retryable=True)

    @app.route("/api/preview-file")
    def api_preview_file():
        raw = (request.args.get("path") or "").strip()
        if not raw:
            return error_response("PATH_REQUIRED", "path required", 400)
        path = Path(raw)
        if not is_path_allowed(path, roots):
            return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
        if not path.is_file():
            return error_response("NOT_A_FILE", "not a file", 400)
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
            return error_response("UNSUPPORTED_TYPE", "unsupported type", 400)
        mimetype, _ = mimetypes.guess_type(str(path), strict=False)
        if not mimetype or not (mimetype.startswith("image/") or mimetype.startswith("video/")):
            mimetype = _IMAGE_MIMETYPES.get(suffix) or _VIDEO_MIMETYPES.get(suffix, "application/octet-stream")
        try:
            return send_file(path, mimetype=mimetype, as_attachment=False)
        except OSError:
            _LOG.exception("Preview file failed")
            return error_response("INTERNAL_ERROR", "Failed to send file", 500, retryable=True)
