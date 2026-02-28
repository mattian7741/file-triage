"""
Flask app for Explorer: read-only file system browser API and static UI.
"""

from __future__ import annotations

import mimetypes
import os
import string
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from flask import Flask, jsonify, request, Response, send_file, stream_with_context

from .roots import get_roots, is_path_allowed

# Package dir for static files
_EXPLORER_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _EXPLORER_DIR / "static"

# Image extensions supported in preview (browser <img> natively)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".ico"}

# Video extensions supported in preview (HTML5 <video>)
VIDEO_EXTENSIONS = {".mp4", ".mov"}

# Fallback mimetypes when guess_type is wrong or missing
_IMAGE_MIMETYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".avif": "image/avif",
    ".ico": "image/x-icon",
}

_VIDEO_MIMETYPES = {".mp4": "video/mp4", ".mov": "video/quicktime"}


def _content_mime_type(data: bytes) -> str | None:
    """Return content-based MIME type if python-magic is available, else None."""
    try:
        import magic
        return magic.from_buffer(data, mime=True) or None
    except Exception:
        return None


def _is_text_by_heuristic(data: bytes) -> bool:
    """True if the byte string looks like UTF-8 text (decodable, mostly printable)."""
    if not data:
        return True
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return False
    # Reject if too many replacement characters (binary)
    replacements = text.count("\ufffd")
    if len(text) > 0 and replacements / len(text) > 0.02:
        return False
    # Require high proportion of printable/whitespace
    printable = set(string.printable) | {"\x0b", "\x0c"}  # vertical tab, form feed
    non_printable = sum(1 for c in text if c not in printable and c != "\ufffd")
    if len(text) > 0 and non_printable / len(text) > 0.05:
        return False
    return True


def _is_text_file_content(data: bytes) -> bool:
    """True if content should be previewed as text (MIME text/* or heuristic)."""
    mime = _content_mime_type(data[:8192])
    if mime is not None and mime.startswith("text/"):
        return True
    return _is_text_by_heuristic(data)


def _has_vpath(meta_db: Path, path: Path) -> bool:
    """True if path has a meta row with non-null vpath (moved/trashed, not logically present)."""
    if not meta_db or not meta_db.exists():
        return False
    try:
        from file_triage.meta import get_path_meta
        path_str = str(path.resolve())
        meta = get_path_meta(meta_db, path_str)
        return meta is not None and bool(meta.get("vpath"))
    except Exception:
        return False


def _is_empty_recursive(
    path: Path,
    visited: set[str] | None = None,
    meta_db: Path | None = None,
) -> bool:
    """True if path is a 0-byte file, or a directory with no children or whose descendants are all recursively empty.
    When meta_db is set, paths with non-null vpath are treated as not present (moved/trashed)."""
    if visited is None:
        visited = set()
    try:
        resolved = str(path.resolve())
        if resolved in visited:
            return False
        if path.is_file():
            if meta_db and _has_vpath(meta_db, path):
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
                if meta_db and _has_vpath(meta_db, child):
                    continue
                try:
                    if not _is_empty_recursive(child, visited, meta_db):
                        return False
                except OSError:
                    return False
            return True
        finally:
            visited.discard(resolved)
    except OSError:
        return False


def _entry_effective_path(e: dict) -> str:
    """EFFECTIVE_PATH = vpath or path; used for sorting. Case-insensitive."""
    return (e.get("vpath") or e["path"]).lower()


def create_app(meta_db_path: Optional[Path] = None) -> Flask:
    app = Flask(__name__, static_folder=str(_STATIC_DIR), static_url_path="")
    roots = get_roots()
    _meta_db = Path(meta_db_path).resolve() if meta_db_path else None
    if _meta_db:
        _meta_db.parent.mkdir(parents=True, exist_ok=True)
        from file_triage.meta import init_db
        init_db(_meta_db)

    @app.route("/")
    def index() -> str:
        html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return html

    @app.route("/api/roots")
    def api_roots():
        return jsonify([str(r) for r in roots])

    @app.route("/api/preview")
    def api_preview():
        raw = (request.args.get("path") or "").strip()
        if not raw:
            return jsonify({"error": "path required"}), 400
        path = Path(raw)
        if not is_path_allowed(path, roots):
            return jsonify({"error": "path not allowed"}), 403
        try:
            if path.is_dir():
                return jsonify({"kind": "none", "reason": "directory"})
            suffix = path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                return jsonify(
                    {
                        "kind": "image",
                        "url": "/api/preview-file?path=" + quote(str(path.resolve())),
                    }
                )
            if suffix in VIDEO_EXTENSIONS:
                return jsonify(
                    {
                        "kind": "video",
                        "url": "/api/preview-file?path=" + quote(str(path.resolve())),
                    }
                )
            # Text preview: known extensions or content-based (MIME / heuristic)
            text_exts = {
                ".txt",
                ".md",
                ".log",
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".json",
                ".toml",
                ".ini",
                ".cfg",
                ".conf",
                ".yaml",
                ".yml",
                ".html",
                ".css",
                ".csv",
            }
            max_bytes = 100 * 1024
            data = path.read_bytes()
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            # Known text extension -> always preview as text
            if suffix in text_exts:
                content = data.decode("utf-8", errors="replace")
                return jsonify(
                    {
                        "kind": "text",
                        "path": str(path.resolve()),
                        "truncated": truncated,
                        "content": content,
                    }
                )
            # Unknown extension: use MIME (if available) or heuristic to detect text
            if _is_text_file_content(data):
                content = data.decode("utf-8", errors="replace")
                return jsonify(
                    {
                        "kind": "text",
                        "path": str(path.resolve()),
                        "truncated": truncated,
                        "content": content,
                    }
                )
            return jsonify({"kind": "unsupported", "reason": f"extension {suffix!r} not previewable"})
        except OSError as e:
            return jsonify({"kind": "error", "error": str(e)}), 500

    @app.route("/api/preview-file")
    def api_preview_file():
        raw = (request.args.get("path") or "").strip()
        if not raw:
            return jsonify({"error": "path required"}), 400
        path = Path(raw)
        if not is_path_allowed(path, roots):
            return jsonify({"error": "path not allowed"}), 403
        if not path.is_file():
            return jsonify({"error": "not a file"}), 400
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
            return jsonify({"error": "unsupported type"}), 400
        mimetype, _ = mimetypes.guess_type(str(path), strict=False)
        if not mimetype or not (mimetype.startswith("image/") or mimetype.startswith("video/")):
            mimetype = _IMAGE_MIMETYPES.get(suffix) or _VIDEO_MIMETYPES.get(suffix, "application/octet-stream")
        try:
            return send_file(
                path,
                mimetype=mimetype,
                as_attachment=False,
            )
        except OSError as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/listing")
    def api_listing():
        raw = request.args.get("path", "").strip()
        hide_tags_raw = request.args.get("hide_tags", "").strip()
        hide_tags = set(t.strip() for t in hide_tags_raw.split(",") if t.strip())
        report_all_tags = request.args.get("report_all_tags", "") == "1"
        if not raw:
            return jsonify({"error": "path required"}), 400
        path = Path(raw)
        try:
            is_virtual = False
            virtual_scope_vpath = None  # when is_virtual: the vpath (scope) we're listing, for child lookups
            canonical_scope_path = None  # when is_virtual and scope is a moved physical folder: its path on disk
            if _meta_db and _meta_db.exists():
                from file_triage.meta import get_path_meta, get_meta_by_vpath
                meta = get_path_meta(_meta_db, raw)
                if meta is not None and meta.get("inode") is None:
                    is_virtual = True
                    virtual_scope_vpath = meta.get("vpath") or raw
                if not is_virtual:
                    meta = get_meta_by_vpath(_meta_db, raw)
                    if meta is not None:
                        # Any row with this vpath is listable by vpath (virtual folder or moved physical folder)
                        is_virtual = True
                        virtual_scope_vpath = meta.get("vpath") or raw
                        if meta.get("inode") is not None:
                            canonical_scope_path = meta["path"]
            if not is_virtual:
                if not is_path_allowed(path, roots):
                    return jsonify({"error": "path not allowed"}), 403
            if not path.is_dir() and not is_virtual:
                return jsonify({"error": "not a directory"}), 400
            entries = []
            all_tags = set()
            tags_by_path = {}
            if _meta_db and _meta_db.exists():
                from file_triage.meta import get_tags, get_paths_by_tag
                if path.exists() and path.is_dir():
                    for p in path.iterdir():
                        try:
                            p_resolved = str(p.resolve())
                            tags_by_path[p_resolved] = get_tags(_meta_db, p_resolved)
                        except Exception:
                            pass
            if is_virtual:
                # Virtual folder: hierarchy is by vpath (tier 1). All direct children of scope = parent(vpath).
                # Single source: get_entries_by_vpath_parent; no resolve() so scope matches DB vpaths on macOS.
                from file_triage.meta import get_entries_by_vpath_parent
                resolved_path = virtual_scope_vpath if virtual_scope_vpath else (str(path.resolve()) if path.exists() else raw)
                # Tags for physical children when scope is a moved physical folder
                if canonical_scope_path and _meta_db and _meta_db.exists():
                    try:
                        canon_path = Path(canonical_scope_path)
                        if canon_path.exists() and canon_path.is_dir():
                            for p in canon_path.iterdir():
                                try:
                                    p_resolved = str(p.resolve())
                                    tags_by_path[p_resolved] = get_tags(_meta_db, p_resolved)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                for moved in get_entries_by_vpath_parent(_meta_db, resolved_path):
                    canon_path = moved["path"]
                    vpath_val = moved["vpath"]
                    try:
                        from file_triage.meta import get_tags_from_rules, get_ancestor_tags, get_tag_nulls
                        meta = get_path_meta(_meta_db, canon_path)
                        if not meta:
                            continue
                        is_virtual_child = meta.get("inode") is None
                        if is_virtual_child:
                            display_path = meta.get("vpath") or canon_path
                            p = Path(display_path)
                            explicit = get_tags(_meta_db, canon_path)
                            from_rules = get_tags_from_rules(_meta_db, vpath_val)
                            from_ancestors = get_ancestor_tags(_meta_db, canon_path)
                            inherited = list(dict.fromkeys(from_rules + from_ancestors))
                            nulls = get_tag_nulls(_meta_db, canon_path)
                            effective = set(explicit) | set(inherited) - set(nulls)
                            if report_all_tags:
                                all_tags |= effective
                            if hide_tags and (effective & hide_tags):
                                continue
                            empty = not get_entries_by_vpath_parent(_meta_db, vpath_val)
                            entry = {
                                "name": p.name,
                                "path": canon_path,
                                "is_dir": True,
                                "size": 0,
                                "empty": empty,
                                "virtual": True,
                                "tags": explicit,
                                "tags_inherited": inherited,
                                "tags_null": nulls,
                                "display_style": "moved_here",
                                "vpath": vpath_val,
                            }
                            entries.append(entry)
                        else:
                            canon_p = Path(canon_path)
                            if canon_p.exists():
                                is_dir = canon_p.is_dir()
                                size = 0 if is_dir else canon_p.stat().st_size
                                if is_dir:
                                    try:
                                        empty = _is_empty_recursive(canon_p, meta_db=_meta_db)
                                    except OSError:
                                        empty = True
                                    if empty:
                                        scope = vpath_val  # effective path for this child
                                        if get_entries_by_vpath_parent(_meta_db, scope):
                                            empty = False
                                else:
                                    empty = size == 0
                            else:
                                is_dir = True
                                size = 0
                                empty = True
                            explicit = get_tags(_meta_db, canon_path)
                            from_rules = get_tags_from_rules(_meta_db, vpath_val)
                            from_ancestors = get_ancestor_tags(_meta_db, canon_path)
                            inherited = list(dict.fromkeys(from_rules + from_ancestors))
                            nulls = get_tag_nulls(_meta_db, canon_path)
                            effective = set(explicit) | set(inherited) - set(nulls)
                            if report_all_tags:
                                all_tags |= effective
                            if hide_tags and (effective & hide_tags):
                                continue
                            entry = {
                                "name": Path(vpath_val).name,
                                "path": canon_path,
                                "vpath": vpath_val,
                                "is_dir": is_dir,
                                "size": size,
                                "empty": empty,
                                "tags": explicit,
                                "tags_inherited": inherited,
                                "tags_null": nulls,
                                "display_style": "moved_here",
                            }
                            entries.append(entry)
                    except Exception:
                        continue
                # When scope is a moved physical folder, also list its contents on disk
                if canonical_scope_path and _meta_db and _meta_db.exists():
                    from file_triage.meta import get_tags_from_rules, get_ancestor_tags, get_tag_nulls, get_path_meta, get_entries_by_vpath_parent
                    canon_path = Path(canonical_scope_path)
                    if canon_path.exists() and canon_path.is_dir():
                        existing_paths = {e["path"] for e in entries}
                        for p in sorted(canon_path.iterdir(), key=lambda x: x.name.lower()):
                            try:
                                entry_path = str(p.resolve())
                                if entry_path in existing_paths:
                                    continue
                                is_dir = p.is_dir()
                                if is_dir:
                                    try:
                                        empty = _is_empty_recursive(p, meta_db=_meta_db)
                                    except OSError:
                                        empty = True
                                    if empty:
                                        meta = get_path_meta(_meta_db, entry_path)
                                        scope = (meta.get("vpath") if meta else None) or entry_path
                                        if get_entries_by_vpath_parent(_meta_db, scope):
                                            empty = False
                                    size = 0
                                else:
                                    try:
                                        size = p.stat().st_size
                                    except OSError:
                                        size = 0
                                    empty = False
                                explicit = tags_by_path.get(entry_path, get_tags(_meta_db, entry_path))
                                meta = get_path_meta(_meta_db, entry_path)
                                from_rules = get_tags_from_rules(_meta_db, (meta.get("vpath") if meta else None) or entry_path)
                                from_ancestors = get_ancestor_tags(_meta_db, entry_path)
                                inherited = list(dict.fromkeys(from_rules + from_ancestors))
                                nulls = get_tag_nulls(_meta_db, entry_path)
                                effective = set(explicit) | set(inherited) - set(nulls)
                                if report_all_tags:
                                    all_tags |= effective
                                if hide_tags and (effective & hide_tags):
                                    continue
                                if meta and meta.get("vpath"):
                                    display_style = "original"
                                    entry_vpath = meta["vpath"]
                                else:
                                    display_style = "normal"
                                    entry_vpath = None
                                entry = {
                                    "name": p.name,
                                    "path": entry_path,
                                    "is_dir": is_dir,
                                    "size": size,
                                    "empty": empty,
                                    "tags": explicit,
                                    "tags_inherited": inherited,
                                    "tags_null": nulls,
                                    "display_style": display_style,
                                }
                                if entry_vpath:
                                    entry["vpath"] = entry_vpath
                                entries.append(entry)
                            except OSError:
                                continue
                entries.sort(key=_entry_effective_path)
                out = {"path": resolved_path, "entries": entries}
                if report_all_tags:
                    out["all_tags_in_scope"] = list(all_tags)
                return jsonify(out)
            for p in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                try:
                    is_dir = p.is_dir()
                    entry_path = str(p.resolve())
                    if is_dir:
                        try:
                            empty = _is_empty_recursive(p, meta_db=_meta_db)
                        except OSError:
                            empty = True
                        if empty and _meta_db and _meta_db.exists():
                            from file_triage.meta import get_path_meta, get_entries_by_vpath_parent
                            meta = get_path_meta(_meta_db, entry_path)
                            scope = (meta.get("vpath") if meta else None) or entry_path
                            if get_entries_by_vpath_parent(_meta_db, scope):
                                empty = False
                        size = 0
                    else:
                        try:
                            size = p.stat().st_size
                        except OSError:
                            size = 0
                        empty = False
                    if _meta_db and _meta_db.exists():
                        from file_triage.meta import get_tags_from_rules, get_ancestor_tags, get_tag_nulls
                        explicit = tags_by_path.get(entry_path, [])
                        meta = get_path_meta(_meta_db, entry_path)
                        from_rules = get_tags_from_rules(_meta_db, (meta.get("vpath") if meta else None) or entry_path)
                        from_ancestors = get_ancestor_tags(_meta_db, entry_path)
                        inherited = list(dict.fromkeys(from_rules + from_ancestors))
                        nulls = get_tag_nulls(_meta_db, entry_path)
                        effective = set(explicit) | set(inherited) - set(nulls)
                        if report_all_tags:
                            all_tags |= effective
                        if hide_tags and (effective & hide_tags):
                            continue
                        if meta and meta.get("vpath"):
                            display_style = "original"
                            entry_vpath = meta["vpath"]
                        else:
                            display_style = "normal"
                            entry_vpath = None
                        entry = {
                            "name": p.name,
                            "path": entry_path,
                            "is_dir": is_dir,
                            "size": size,
                            "empty": empty,
                            "tags": explicit,
                            "tags_inherited": inherited,
                            "tags_null": nulls,
                            "display_style": display_style,
                        }
                        if entry_vpath:
                            entry["vpath"] = entry_vpath
                    else:
                        entry = {
                            "name": p.name,
                            "path": entry_path,
                            "is_dir": is_dir,
                            "size": size,
                            "empty": empty,
                            "tags": [],
                            "tags_inherited": [],
                            "tags_null": [],
                            "display_style": "normal",
                        }
                    entries.append(entry)
                except OSError:
                    continue
            # Merge virtual folders (meta-only, no inode) that are direct children of this path
            if _meta_db and _meta_db.exists():
                from file_triage.meta import get_path_meta, get_entries_by_vpath_parent
                resolved_path = str(path.resolve())
                existing_paths = {e["path"] for e in entries}
                for meta_path in get_virtual_children(_meta_db, resolved_path):
                    if meta_path in existing_paths:
                        continue
                    try:
                        meta = get_path_meta(_meta_db, meta_path)
                        if not meta:
                            continue
                        display_path = meta.get("vpath") or meta_path
                        if display_path in existing_paths:
                            continue
                        p = Path(display_path)
                        explicit = tags_by_path.get(meta_path, get_tags(_meta_db, meta_path))
                        from_rules = get_tags_from_rules(_meta_db, (meta.get("vpath") if meta else None) or display_path)
                        from_ancestors = get_ancestor_tags(_meta_db, meta_path)
                        inherited = list(dict.fromkeys(from_rules + from_ancestors))
                        nulls = get_tag_nulls(_meta_db, meta_path)
                        effective = set(explicit) | set(inherited) - set(nulls)
                        if report_all_tags:
                            all_tags |= effective
                        if hide_tags and (effective & hide_tags):
                            continue
                        if meta.get("vpath"):
                            # Virtual folder shown at its vpath → blue (moved_here), not red (original)
                            display_style = "moved_here"
                            entry_vpath = meta["vpath"]
                        else:
                            display_style = "normal"
                            entry_vpath = None
                        scope = entry_vpath or display_path
                        has_vpath_children = bool(get_entries_by_vpath_parent(_meta_db, scope))
                        entry = {
                            "name": p.name,
                            "path": meta_path,
                            "is_dir": True,
                            "size": 0,
                            "empty": not has_vpath_children,
                            "virtual": True,
                            "tags": explicit,
                            "tags_inherited": inherited,
                            "tags_null": nulls,
                            "display_style": display_style,
                        }
                        if entry_vpath:
                            entry["vpath"] = entry_vpath
                        entries.append(entry)
                    except Exception:
                        continue
                # Add "moved here" entries: meta rows where vpath is a direct child of this folder
                # Skip rows with inode IS NULL (virtual folders) — they are already added above
                for moved in get_entries_by_vpath_parent(_meta_db, resolved_path):
                    canon_path = moved["path"]
                    vpath_val = moved["vpath"]
                    try:
                        meta = get_path_meta(_meta_db, canon_path)
                        if meta is not None and meta.get("inode") is None:
                            continue  # virtual folder, already in get_virtual_children list
                        canon_p = Path(canon_path)
                        if canon_p.exists():
                            is_dir = canon_p.is_dir()
                            size = 0 if is_dir else canon_p.stat().st_size
                            if is_dir:
                                try:
                                    empty = _is_empty_recursive(canon_p, meta_db=_meta_db)
                                except OSError:
                                    empty = True
                                if empty and get_entries_by_vpath_parent(_meta_db, vpath_val):
                                    empty = False
                            else:
                                empty = size == 0
                        else:
                            is_dir = True
                            size = 0
                            empty = True
                        explicit = get_tags(_meta_db, canon_path)
                        from_rules = get_tags_from_rules(_meta_db, vpath_val)
                        from_ancestors = get_ancestor_tags(_meta_db, canon_path)
                        inherited = list(dict.fromkeys(from_rules + from_ancestors))
                        nulls = get_tag_nulls(_meta_db, canon_path)
                        effective = set(explicit) | set(inherited) - set(nulls)
                        if report_all_tags:
                            all_tags |= effective
                        if hide_tags and (effective & hide_tags):
                            continue
                        entry = {
                            "name": Path(vpath_val).name,
                            "path": canon_path,
                            "vpath": vpath_val,
                            "is_dir": is_dir,
                            "size": size,
                            "empty": empty,
                            "tags": explicit,
                            "tags_inherited": inherited,
                            "tags_null": nulls,
                            "display_style": "moved_here",
                        }
                        entries.append(entry)
                    except Exception:
                        continue
                entries.sort(key=_entry_effective_path)
            out = {"path": str(path.resolve()), "entries": entries}
            if report_all_tags:
                out["all_tags_in_scope"] = list(all_tags)
            return jsonify(out)
        except OSError as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/parent")
    def api_parent():
        raw = request.args.get("path", "").strip()
        if not raw:
            return jsonify({"parent": None})
        # Single special rule: Up from "/" goes to "/Volumes" (toggle)
        if raw == "/":
            return jsonify({"parent": "/Volumes"})
        path = Path(raw).resolve()
        if not is_path_allowed(path, roots):
            return jsonify({"error": "path not allowed"}), 403
        parent = path.parent
        if parent == path:
            return jsonify({"parent": None})
        if not is_path_allowed(parent, roots):
            return jsonify({"parent": None})
        return jsonify({"parent": str(parent)})

    if _meta_db:
        from file_triage.meta import (
            add_tag,
            remove_tag,
            get_tags,
            get_all_tags,
            get_paths_by_tag,
            get_paths_by_tag_null,
            get_tag_nulls,
            get_tags_from_rules,
            get_ancestor_tags,
            get_all_rules,
            add_rule_tag,
            remove_rule_tag,
            remove_rule_pattern,
            update_rule_pattern,
            add_tag_null,
            remove_tag_null,
            get_hidden_tags,
            add_hidden_tag,
            remove_hidden_tag,
            add_virtual_folder,
            get_virtual_children,
            get_path_meta,
            get_entries_by_vpath_parent,
            get_meta_by_vpath,
            get_all_meta_for_debug,
            get_moved_in_scopes,
            set_vpath,
        )

        def _parse_hide_tags():
            raw = request.args.get("hide_tags", "").strip()
            if not raw:
                return set()
            return set(t.strip() for t in raw.split(",") if t.strip())

        @app.route("/api/tags")
        def api_get_tags():
            raw = request.args.get("path", "").strip()
            if not raw:
                return jsonify({"error": "path required"}), 400
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            tags = get_tags(_meta_db, raw)
            return jsonify({"path": raw, "tags": tags})

        @app.route("/api/tag-names")
        def api_tag_names():
            tags = get_all_tags(_meta_db)
            return jsonify({"tags": tags})

        @app.route("/api/tagged")
        def api_tagged():
            tag = request.args.get("tag", "").strip()
            hide_tags_raw = request.args.get("hide_tags", "").strip()
            hide_tags = set(t.strip() for t in hide_tags_raw.split(",") if t.strip())
            report_all_tags = request.args.get("report_all_tags", "") == "1"
            show_null_tagged = request.args.get("show_null_tagged", "") == "1"
            if not tag:
                return jsonify({"error": "tag required"}), 400
            paths = list(get_paths_by_tag(_meta_db, tag))
            if show_null_tagged:
                paths = list(dict.fromkeys(paths + get_paths_by_tag_null(_meta_db, tag)))
            entries = []
            all_tags = set()
            for path_str in paths:
                try:
                    p = Path(path_str)
                    if not p.exists():
                        continue
                    explicit = get_tags(_meta_db, path_str)
                    from_rules = get_tags_from_rules(_meta_db, path_str)
                    from_ancestors = get_ancestor_tags(_meta_db, path_str)
                    inherited = list(dict.fromkeys(from_rules + from_ancestors))
                    nulls = get_tag_nulls(_meta_db, path_str)
                    effective = set(explicit) | set(inherited) - set(nulls)
                    if report_all_tags:
                        all_tags |= effective
                    if hide_tags and (effective & hide_tags):
                        continue
                    entries.append({
                        "name": p.name,
                        "path": path_str,
                        "is_dir": p.is_dir(),
                        "tags": explicit,
                        "tags_inherited": inherited,
                        "tags_null": nulls,
                    })
                except OSError:
                    continue
            out = {"tag": tag, "entries": entries}
            if report_all_tags:
                out["all_tags_in_scope"] = list(all_tags)
            return jsonify(out)

        @app.route("/api/tag-search")
        def api_tag_search():
            """Return all paths under scope (path) that have the given tag as hard or soft (effective).
            mode=matches: each matching path (file or dir). mode=contains: each folder under scope that contains at least one match.
            If stream=1 and mode=matches, yields NDJSON: {"type":"entry","entry":{...}} per match, then {"type":"done"}."""
            import json
            tag = request.args.get("tag", "").strip()
            raw_scope = request.args.get("path", "").strip()
            mode = request.args.get("mode", "matches").strip().lower() or "matches"
            stream_mode = request.args.get("stream", "") == "1" and mode == "matches"
            hide_tags_raw = request.args.get("hide_tags", "").strip()
            hide_tags = set(t.strip() for t in hide_tags_raw.split(",") if t.strip())
            if not tag:
                return jsonify({"error": "tag required"}), 400
            if not raw_scope:
                return jsonify({"error": "path required"}), 400
            scope = Path(raw_scope).resolve()
            if not scope.is_dir():
                return jsonify({"error": "path is not a directory"}), 400
            if not is_path_allowed(scope, roots):
                return jsonify({"error": "path not allowed"}), 403
            report_all_tags = request.args.get("report_all_tags", "") == "1"
            # When searching for a tag, don't exclude paths just because that tag is hidden in the UI
            hide_tags_filter = hide_tags - {tag} if tag else hide_tags
            show_null_tagged = request.args.get("show_null_tagged", "") == "1"
            visited = set()

            def walk(scope_path: Path, all_tags_set: set, emit_progress: bool = False):
                try:
                    resolved = str(scope_path.resolve())
                    if resolved in visited:
                        return
                    visited.add(resolved)
                except OSError:
                    return
                try:
                    entries = list(scope_path.iterdir())
                except OSError:
                    entries = []
                entries.sort(key=lambda p: p.name.lower())
                if emit_progress:
                    dir_names = [p.name for p in entries if p.is_dir()]
                    yield ("progress", resolved, dir_names)
                try:
                    for p in entries:
                        try:
                            entry_path = str(p.resolve())
                            if not is_path_allowed(p, roots):
                                continue
                            explicit = get_tags(_meta_db, entry_path)
                            from_rules = get_tags_from_rules(_meta_db, entry_path)
                            from_ancestors = get_ancestor_tags(_meta_db, entry_path)
                            inherited = list(dict.fromkeys(from_rules + from_ancestors))
                            nulls = get_tag_nulls(_meta_db, entry_path)
                            effective = set(explicit) | set(inherited) - set(nulls)
                            if report_all_tags:
                                all_tags_set |= effective
                            if hide_tags_filter and (effective & hide_tags_filter):
                                continue
                            if tag not in effective and not (show_null_tagged and tag in nulls):
                                if p.is_dir():
                                    yield from walk(p, all_tags_set, emit_progress)
                                continue
                            entry = {
                                "name": p.name,
                                "path": entry_path,
                                "is_dir": p.is_dir(),
                                "tags": explicit,
                                "tags_inherited": inherited,
                                "tags_null": nulls,
                            }
                            if emit_progress:
                                yield ("entry", entry)
                            else:
                                yield entry
                            if p.is_dir():
                                yield from walk(p, all_tags_set, emit_progress)
                        except OSError:
                            continue
                except OSError:
                    pass

            if mode == "contains":
                matches = list(walk(scope, set(), emit_progress=False))  # don't collect tags from full hierarchy
                scope_str = str(scope.resolve())
                dirs_to_show = set()
                dirs_direct = set()  # folders that have at least one match as a direct child
                for entry in matches:
                    path_str = entry["path"]
                    is_dir = entry["is_dir"]
                    direct_container = path_str if is_dir else str(Path(path_str).parent)
                    dirs_direct.add(direct_container)
                    d = direct_container
                    while d == scope_str or d.startswith(scope_str + os.sep):
                        dirs_to_show.add(d)
                        if d == scope_str:
                            break
                        parent = Path(d).parent
                        d_str = str(parent)
                        if d_str == d:
                            break
                        d = d_str
                dir_entries = []
                all_tags_from_dirs = set()  # top tier: only tags from the folder results (current view)
                for d in sorted(dirs_to_show, key=str.lower):
                    p = Path(d)
                    if not p.exists() or not p.is_dir():
                        continue
                    explicit = get_tags(_meta_db, d)
                    from_rules = get_tags_from_rules(_meta_db, d)
                    from_ancestors = get_ancestor_tags(_meta_db, d)
                    inherited = list(dict.fromkeys(from_rules + from_ancestors))
                    nulls = get_tag_nulls(_meta_db, d)
                    effective = set(explicit) | set(inherited) - set(nulls)
                    if report_all_tags:
                        all_tags_from_dirs |= effective
                    dir_entries.append({
                        "name": p.name,
                        "path": d,
                        "is_dir": True,
                        "tags": explicit,
                        "tags_inherited": inherited,
                        "tags_null": nulls,
                        "has_direct_match": d in dirs_direct,
                    })
                out = {"tag": tag, "path": raw_scope, "entries": dir_entries, "mode": "contains"}
                if report_all_tags:
                    out["all_tags_in_scope"] = list(all_tags_from_dirs)
                return jsonify(out)

            if stream_mode:
                def generate():
                    all_tags = set()
                    for item in walk(scope, all_tags, emit_progress=True):
                        if isinstance(item, tuple) and item[0] == "progress":
                            payload = {"type": "progress", "path": item[1]}
                            if len(item) >= 3 and item[2] is not None:
                                payload["children"] = item[2]
                            yield (json.dumps(payload) + "\n").encode("utf-8")
                        else:
                            entry = item[1] if isinstance(item, tuple) else item
                            if report_all_tags and entry:
                                pass  # entry is the dict; all_tags updated in walk
                            yield (json.dumps({"type": "entry", "entry": entry}) + "\n").encode("utf-8")
                    if report_all_tags:
                        yield (json.dumps({"type": "all_tags_in_scope", "tags": list(all_tags)}) + "\n").encode("utf-8")
                    yield (json.dumps({"type": "done"}) + "\n").encode("utf-8")

                return Response(
                    stream_with_context(generate()),
                    mimetype="application/x-ndjson",
                )

            all_tags = set()
            entries = list(walk(scope, all_tags, emit_progress=False))
            out = {"tag": tag, "path": raw_scope, "entries": entries}
            if report_all_tags:
                out["all_tags_in_scope"] = list(all_tags)
            return jsonify(out)

        @app.route("/api/tags", methods=["POST"])
        def api_add_tag():
            data = request.get_json() or {}
            raw = (data.get("path") or "").strip()
            tag = (data.get("tag") or "").strip()
            if not raw or not tag:
                return jsonify({"error": "path and tag required"}), 400
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            add_tag(_meta_db, raw, tag)
            return jsonify({"path": raw, "tags": get_tags(_meta_db, raw)})

        @app.route("/api/tags", methods=["DELETE"])
        def api_remove_tag():
            raw = (request.args.get("path") or "").strip()
            tag = (request.args.get("tag") or "").strip()
            if not raw or not tag:
                return jsonify({"error": "path and tag required"}), 400
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            remove_tag(_meta_db, raw, tag)
            return jsonify({"path": raw, "tags": get_tags(_meta_db, raw)})

        @app.route("/api/tags/batch", methods=["POST"])
        def api_add_tag_batch():
            data = request.get_json() or {}
            paths = data.get("paths") or []
            tag = (data.get("tag") or "").strip()
            if not tag:
                return jsonify({"error": "tag required"}), 400
            if not isinstance(paths, list):
                return jsonify({"error": "paths must be a list"}), 400
            added = 0
            for raw in paths:
                path_str = str(Path(raw).resolve()) if raw else ""
                if not path_str:
                    continue
                path_obj = Path(path_str)
                if not is_path_allowed(path_obj, roots):
                    continue
                try:
                    add_tag(_meta_db, path_str, tag)
                    added += 1
                except Exception:
                    pass
            return jsonify({"tag": tag, "added": added})

        @app.route("/api/rules")
        def api_rules_list():
            rules = get_all_rules(_meta_db)
            return jsonify({"rules": rules})

        @app.route("/api/rules", methods=["POST"])
        def api_rules_add():
            data = request.get_json() or {}
            pattern = (data.get("pattern") or "").strip()
            tag = (data.get("tag") or "").strip()
            if not pattern or not tag:
                return jsonify({"error": "pattern and tag required"}), 400
            add_rule_tag(_meta_db, pattern, tag)
            return jsonify({"pattern": pattern, "tag": tag, "rules": get_all_rules(_meta_db)})

        @app.route("/api/rules", methods=["DELETE"])
        def api_rules_remove():
            pattern = (request.args.get("pattern") or "").strip()
            tag = (request.args.get("tag") or "").strip()
            if not pattern:
                return jsonify({"error": "pattern required"}), 400
            if tag:
                remove_rule_tag(_meta_db, pattern, tag)
            else:
                remove_rule_pattern(_meta_db, pattern)
            return jsonify({"pattern": pattern, "tag": tag or None, "rules": get_all_rules(_meta_db)})

        @app.route("/api/rules", methods=["PATCH"])
        def api_rules_update_pattern():
            data = request.get_json() or {}
            old_pattern = (data.get("old_pattern") or data.get("pattern") or "").strip()
            new_pattern = (data.get("new_pattern") or "").strip()
            if not old_pattern or not new_pattern:
                return jsonify({"error": "old_pattern and new_pattern required"}), 400
            if old_pattern == new_pattern:
                return jsonify({"rules": get_all_rules(_meta_db)})
            update_rule_pattern(_meta_db, old_pattern, new_pattern)
            return jsonify({"old_pattern": old_pattern, "new_pattern": new_pattern, "rules": get_all_rules(_meta_db)})

        @app.route("/api/tag-nulls", methods=["POST"])
        def api_add_tag_null():
            data = request.get_json() or {}
            raw = (data.get("path") or "").strip()
            tag = (data.get("tag") or "").strip()
            if not raw or not tag:
                return jsonify({"error": "path and tag required"}), 400
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            add_tag_null(_meta_db, raw, tag)
            return jsonify({
                "path": raw,
                "tags": get_tags(_meta_db, raw),
                "tags_null": get_tag_nulls(_meta_db, raw),
            })

        @app.route("/api/tag-nulls", methods=["DELETE"])
        def api_remove_tag_null():
            raw = (request.args.get("path") or "").strip()
            tag = (request.args.get("tag") or "").strip()
            if not raw or not tag:
                return jsonify({"error": "path and tag required"}), 400
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            remove_tag_null(_meta_db, raw, tag)
            return jsonify({
                "path": raw,
                "tags": get_tags(_meta_db, raw),
                "tags_null": get_tag_nulls(_meta_db, raw),
            })

        @app.route("/api/hidden-tags")
        def api_get_hidden_tags():
            tags = get_hidden_tags(_meta_db)
            return jsonify({"hidden_tags": list(tags)})

        @app.route("/api/hidden-tags", methods=["POST"])
        def api_add_hidden_tag():
            data = request.get_json() or {}
            tag = (data.get("tag") or request.args.get("tag") or "").strip()
            if not tag:
                return jsonify({"error": "tag required"}), 400
            add_hidden_tag(_meta_db, tag)
            return jsonify({"tag": tag, "hidden_tags": list(get_hidden_tags(_meta_db))})

        @app.route("/api/hidden-tags", methods=["DELETE"])
        def api_remove_hidden_tag():
            tag = (request.args.get("tag") or "").strip()
            if not tag:
                return jsonify({"error": "tag required"}), 400
            remove_hidden_tag(_meta_db, tag)
            return jsonify({"tag": tag, "hidden_tags": list(get_hidden_tags(_meta_db))})

        @app.route("/api/new-folder", methods=["POST"])
        def api_new_folder():
            data = request.get_json() or {}
            parent_raw = (data.get("path") or "").strip()
            name = (data.get("name") or "").strip()
            if not parent_raw or not name:
                return jsonify({"error": "path and name required"}), 400
            parent = Path(parent_raw).resolve()
            if not is_path_allowed(parent, roots):
                return jsonify({"error": "path not allowed"}), 403
            # Allow real directory or virtual folder (meta row with no inode) as parent
            if parent.is_dir():
                pass
            elif _meta_db and _meta_db.exists():
                from file_triage.meta import get_path_meta, get_meta_by_vpath
                meta = get_path_meta(_meta_db, parent_raw) or get_meta_by_vpath(_meta_db, parent_raw)
                if meta is None or meta.get("inode") is not None:
                    return jsonify({"error": "path is not a directory"}), 400
            else:
                return jsonify({"error": "path is not a directory"}), 400
            # Disallow path segments in name
            if "/" in name or name in ("", ".", ".."):
                return jsonify({"error": "invalid folder name"}), 400
            new_path = parent / name
            new_path_str = str(new_path.resolve())
            if not is_path_allowed(new_path, roots):
                return jsonify({"error": "path not allowed"}), 403
            try:
                meta_path = add_virtual_folder(_meta_db, new_path_str)
            except ValueError as e:
                return jsonify({"error": str(e)}), 409
            return jsonify({"path": meta_path, "vpath": new_path_str}), 201

        @app.route("/api/move", methods=["POST"])
        def api_move():
            """Set vpath (display location) for a path. No filesystem change."""
            data = request.get_json() or {}
            path_raw = (data.get("path") or "").strip()
            vpath_raw = (data.get("vpath") or "").strip()
            if not path_raw:
                return jsonify({"error": "path required"}), 400
            path_obj = Path(path_raw).resolve()
            if not is_path_allowed(path_obj, roots):
                return jsonify({"error": "path not allowed"}), 403
            # Keep vpath as-is (do not resolve): __VTRASH/... must stay literal, not become cwd-relative
            vpath_str = vpath_raw if vpath_raw else None
            if vpath_str and not vpath_str.startswith("__VTRASH/"):
                if not is_path_allowed(Path(vpath_str), roots):
                    return jsonify({"error": "vpath not allowed"}), 403
            try:
                set_vpath(_meta_db, path_raw, vpath_str)
            except ValueError as e:
                return jsonify({"error": str(e)}), 409
            return jsonify({"path": path_raw, "vpath": vpath_str}), 200

        @app.route("/api/changes")
        def api_changes():
            """Return moved items (path, vpath) where path or vpath is under scope_left or scope_right."""
            scope_left = (request.args.get("scope_left") or "").strip() or None
            scope_right = (request.args.get("scope_right") or "").strip() or None
            rows = get_moved_in_scopes(_meta_db, scope_left, scope_right)
            return jsonify({"changes": rows})

    # Debug routes: always registered so they return JSON
    @app.route("/api/debug/ping")
    def api_debug_ping():
        """Minimal response to verify debug routes work."""
        return jsonify({"pong": True})

    @app.route("/api/debug/meta")
    def api_debug_meta():
        """Return path, vpath, inode for all meta rows (for debugging)."""
        try:
            if not _meta_db:
                return jsonify({"meta": [], "error": "No meta DB configured"})
            from file_triage.meta import get_all_meta_for_debug
            rows = get_all_meta_for_debug(_meta_db)
            return jsonify({
                "meta": rows,
                "meta_db": str(_meta_db),
                "meta_db_exists": _meta_db.exists(),
            })
        except Exception as e:
            return jsonify({"meta": [], "error": str(e)}), 500

    return app
