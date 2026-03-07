"""
Flask app for Explorer: read-only file system browser API and static UI.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from flask import Flask, g, jsonify, request, Response, stream_with_context

from .roots import get_roots, is_path_allowed
from .errors import error_response
from .validation import require_path, require_path_allowed, require_tag
from .domain import effective_tags
from .listing_helpers import (
    build_listing_entry_from_meta,
    entry_effective_path,
)

# Package dir for static files
_EXPLORER_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _EXPLORER_DIR / "static"

_log = logging.getLogger(__name__)

# Header clients may send to correlate requests; we generate one if missing
REQUEST_ID_HEADER = "X-Request-ID"


def create_app(
    meta_db_path: Optional[Path] = None,
    meta_accessor: Optional[Any] = None,
) -> Flask:
    from file_triage.meta.accessor import MetaAccessor
    app = Flask(__name__, static_folder=str(_STATIC_DIR), static_url_path="")
    roots = get_roots()
    _meta = meta_accessor if meta_accessor is not None else (MetaAccessor(Path(meta_db_path).resolve()) if meta_db_path else None)
    if _meta:
        _meta.init_db()
    _meta_db = _meta.db_path if _meta else None

    @app.before_request
    def _request_id():
        """Attach a correlation ID to each request; log at entry (shell only)."""
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def _log_request(response: Response) -> Response:
        """Log request completion with correlation ID (shell only). Attach request_id to response."""
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers[REQUEST_ID_HEADER] = rid
            if request.path.startswith("/api/"):
                _log.info("request_id=%s path=%s method=%s status=%s", rid, request.path, request.method, response.status_code)
        # Prevent caching of app.js so updates are always loaded
        if request.path == "/app.js" or request.path.startswith("/app.js?"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.route("/")
    def index() -> str:
        html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
        # Cache-bust app.js so browser gets latest after updates
        app_js = _STATIC_DIR / "app.js"
        v = int(app_js.stat().st_mtime) if app_js.exists() else ""
        html = html.replace('src="/app.js"', f'src="/app.js?v={v}"')
        return html

    @app.route("/api/roots")
    def api_roots():
        return jsonify([str(r) for r in roots])

    from .routes.preview import register_preview_routes
    register_preview_routes(app, roots)

    @app.route("/api/listing")
    def api_listing():
        raw = request.args.get("path", "").strip()
        err = require_path(raw or request.args.get("path", ""))
        if err is not None:
            return err
        hide_tags_raw = request.args.get("hide_tags", "").strip()
        hide_tags = set()  # Visibility (hidden tags) applied at view layer only; model returns full data
        report_all_tags = request.args.get("report_all_tags", "") == "1"
        path = Path(raw)
        try:
            is_virtual = False
            virtual_scope_vpath = None  # when is_virtual: the vpath (scope) we're listing, for child lookups
            canonical_scope_path = None  # when is_virtual and scope is a moved physical folder: its path on disk
            if _meta_db and _meta_db.exists():
                meta = _meta.get_path_meta(raw)
                if meta is not None and meta.get("inode") is None:
                    is_virtual = True
                    virtual_scope_vpath = meta.get("vpath") or raw
                if not is_virtual:
                    meta = _meta.get_meta_by_vpath(raw)
                    if meta is not None:
                        # Any row with this vpath is listable by vpath (virtual folder or moved physical folder)
                        is_virtual = True
                        virtual_scope_vpath = meta.get("vpath") or raw
                        if meta.get("inode") is not None:
                            canonical_scope_path = meta["path"]
            if not is_virtual:
                if not is_path_allowed(path, roots):
                    return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            if not path.is_dir() and not is_virtual:
                return error_response("NOT_A_DIRECTORY", "not a directory", 400)
            entries = []
            all_tags = set()
            if is_virtual:
                # Virtual folder: hierarchy is by vpath (tier 1). All direct children of scope = parent(vpath).
                resolved_path = virtual_scope_vpath if virtual_scope_vpath else (str(path.resolve()) if path.exists() else raw)
                for moved in _meta.get_entries_by_vpath_parent(resolved_path):
                    canon_path = moved["path"]
                    vpath_val = moved["vpath"]
                    try:
                        meta = _meta.get_path_meta(canon_path)
                        if not meta:
                            continue
                        is_virtual_child = meta.get("inode") is None
                        if is_virtual_child:
                            display_path = meta.get("vpath") or canon_path
                            p = Path(display_path)
                            entry = build_listing_entry_from_meta(
                                _meta,
                                canon_path,
                                p.name,
                                True,
                                0,
                                hide_tags,
                                path_obj=None,
                                scope_for_vpath_children=vpath_val,
                                display_style="moved_here",
                                vpath=vpath_val,
                                virtual=True,
                                scope_for_rules=vpath_val,
                            )
                            if entry is None:
                                continue
                            if report_all_tags:
                                all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                            entries.append(entry)
                        else:
                            canon_p = Path(canon_path)
                            if canon_p.exists():
                                is_dir = canon_p.is_dir()
                                size = 0 if is_dir else canon_p.stat().st_size
                            else:
                                is_dir = True
                                size = 0
                            entry = build_listing_entry_from_meta(
                                _meta,
                                canon_path,
                                Path(vpath_val).name,
                                is_dir,
                                size,
                                hide_tags,
                                path_obj=canon_p if canon_p.exists() else None,
                                scope_for_vpath_children=vpath_val,
                                display_style="moved_here",
                                vpath=vpath_val,
                                scope_for_rules=vpath_val,
                            )
                            if entry is None:
                                continue
                            if report_all_tags:
                                all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                            entries.append(entry)
                    except Exception:
                        continue
                # When scope is a moved physical folder, also list its contents on disk
                if canonical_scope_path and _meta_db and _meta_db.exists():
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
                                    size = 0
                                else:
                                    try:
                                        size = p.stat().st_size
                                    except OSError:
                                        size = 0
                                meta = _meta.get_path_meta(entry_path)
                                scope_rules = (meta.get("vpath") if meta else None) or entry_path
                                scope_vpath = (meta.get("vpath") if meta else None) or entry_path
                                display_style = "original" if (meta and meta.get("vpath")) else "normal"
                                entry_vpath = meta["vpath"] if meta and meta.get("vpath") else None
                                entry = build_listing_entry_from_meta(
                                    _meta,
                                    entry_path,
                                    p.name,
                                    is_dir,
                                    size,
                                    hide_tags,
                                    path_obj=p,
                                    scope_for_vpath_children=scope_vpath,
                                    display_style=display_style,
                                    vpath=entry_vpath,
                                    scope_for_rules=scope_rules,
                                )
                                if entry is None:
                                    continue
                                if report_all_tags:
                                    all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                                entries.append(entry)
                            except OSError:
                                continue
                entries.sort(key=entry_effective_path)
                out = {"path": resolved_path, "entries": entries}
                if report_all_tags:
                    out["all_tags_in_scope"] = list(all_tags)
                return jsonify(out)
            for p in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                try:
                    is_dir = p.is_dir()
                    entry_path = str(p.resolve())
                    if is_dir:
                        size = 0
                    else:
                        try:
                            size = p.stat().st_size
                        except OSError:
                            size = 0
                    scope_rules = None
                    scope_vpath = None
                    display_style = "normal"
                    entry_vpath = None
                    if _meta:
                        meta = _meta.get_path_meta(entry_path)
                        scope_rules = (meta.get("vpath") if meta else None) or entry_path
                        scope_vpath = scope_rules
                        if meta and meta.get("vpath"):
                            display_style = "original"
                            entry_vpath = meta["vpath"]
                    entry = build_listing_entry_from_meta(
                        _meta,
                        entry_path,
                        p.name,
                        is_dir,
                        size,
                        hide_tags,
                        path_obj=p,
                        scope_for_vpath_children=scope_vpath,
                        display_style=display_style,
                        vpath=entry_vpath,
                        scope_for_rules=scope_rules,
                    )
                    if entry is None:
                        continue
                    if report_all_tags and _meta:
                        all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                    entries.append(entry)
                except OSError:
                    continue
            # Merge virtual folders (meta-only, no inode) that are direct children of this path
            if _meta_db and _meta_db.exists():
                resolved_path = str(path.resolve())
                existing_paths = {e["path"] for e in entries}
                for meta_path in _meta.get_virtual_children(resolved_path):
                    if meta_path in existing_paths:
                        continue
                    try:
                        meta = _meta.get_path_meta(meta_path)
                        if not meta:
                            continue
                        display_path = meta.get("vpath") or meta_path
                        if display_path in existing_paths:
                            continue
                        p = Path(display_path)
                        scope = meta.get("vpath") or display_path
                        entry = build_listing_entry_from_meta(
                            _meta,
                            meta_path,
                            p.name,
                            True,
                            0,
                            hide_tags,
                            path_obj=None,
                            scope_for_vpath_children=scope,
                            display_style="moved_here" if meta.get("vpath") else "normal",
                            vpath=meta.get("vpath"),
                            virtual=True,
                            scope_for_rules=meta.get("vpath") or display_path,
                        )
                        if entry is None:
                            continue
                        if report_all_tags:
                            all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                        entries.append(entry)
                    except Exception:
                        continue
                # Add "moved here" entries: meta rows where vpath is a direct child of this folder
                # Skip rows with inode IS NULL (virtual folders) — they are already added above
                for moved in _meta.get_entries_by_vpath_parent(resolved_path):
                    canon_path = moved["path"]
                    vpath_val = moved["vpath"]
                    try:
                        meta = _meta.get_path_meta(canon_path)
                        if meta is not None and meta.get("inode") is None:
                            continue  # virtual folder, already in get_virtual_children list
                        canon_p = Path(canon_path)
                        if canon_p.exists():
                            is_dir = canon_p.is_dir()
                            size = 0 if is_dir else canon_p.stat().st_size
                        else:
                            is_dir = True
                            size = 0
                        entry = build_listing_entry_from_meta(
                            _meta,
                            canon_path,
                            Path(vpath_val).name,
                            is_dir,
                            size,
                            hide_tags,
                            path_obj=canon_p if canon_p.exists() else None,
                            scope_for_vpath_children=vpath_val,
                            display_style="moved_here",
                            vpath=vpath_val,
                            scope_for_rules=vpath_val,
                        )
                        if entry is None:
                            continue
                        if report_all_tags:
                            all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                        entries.append(entry)
                    except Exception:
                        continue
                entries.sort(key=entry_effective_path)
            out = {"path": str(path.resolve()), "entries": entries}
            if report_all_tags:
                out["all_tags_in_scope"] = list(all_tags)
            return jsonify(out)
        except OSError as e:
            _log.exception("Listing failed")
            return error_response("NOT_FOUND", "Path not found or not accessible", 404)

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
            return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
        parent = path.parent
        if parent == path:
            return jsonify({"parent": None})
        if not is_path_allowed(parent, roots):
            return jsonify({"parent": None})
        return jsonify({"parent": str(parent)})

    if _meta_db:

        def _parse_hide_tags():
            raw = request.args.get("hide_tags", "").strip()
            if not raw:
                return set()
            return set(t.strip() for t in raw.split(",") if t.strip())

        @app.route("/api/tags")
        def api_get_tags():
            raw = request.args.get("path", "").strip()
            if not raw:
                return error_response("PATH_REQUIRED", "path required", 400)
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            tags = _meta.get_tags(raw)
            return jsonify({"path": raw, "tags": tags})

        @app.route("/api/tag-names")
        def api_tag_names():
            tags = _meta.get_all_tags()
            return jsonify({"tags": tags})

        @app.route("/api/tagged")
        def api_tagged():
            tag = request.args.get("tag", "").strip()
            err = require_tag(tag or request.args.get("tag", ""))
            if err is not None:
                return err
            hide_tags_raw = request.args.get("hide_tags", "").strip()
            hide_tags = set()  # Visibility applied at view layer only; model returns full data
            # Exclude entries that have any hidden tag (hard or soft); null tag = tag absent.
            hide_tags_filter = hide_tags
            report_all_tags = request.args.get("report_all_tags", "") == "1"
            show_null_tagged = True  # Always include null-tagged paths in data; view layer filters by toggle
            if not tag:
                return error_response("TAG_REQUIRED", "tag required", 400)
            paths = list(_meta.get_paths_by_tag(tag))
            paths = list(dict.fromkeys(paths + _meta.get_paths_by_tag_null(tag)))  # Always include null-tagged; view filters
            entries = []
            all_tags = set()
            for path_str in paths:
                try:
                    p = Path(path_str)
                    if p.exists():
                        is_dir = p.is_dir()
                        size = 0 if is_dir else p.stat().st_size
                    else:
                        # Include paths from tags table even if they no longer exist on disk
                        is_dir = False
                        size = 0
                    meta = _meta.get_path_meta(path_str)
                    scope_vpath = (meta.get("vpath") if meta else None) or path_str
                    entry = build_listing_entry_from_meta(
                        _meta,
                        path_str,
                        p.name if p.exists() else Path(path_str).name or path_str,
                        is_dir,
                        size,
                        hide_tags_filter,
                        path_obj=p if p.exists() else None,
                        scope_for_vpath_children=scope_vpath,
                        scope_for_rules=path_str,
                    )
                    if entry is None:
                        continue
                    if report_all_tags:
                        all_tags |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                    entries.append(entry)
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
            hide_tags = set()  # Visibility applied at view layer only; model returns full data
            if not tag:
                return error_response("TAG_REQUIRED", "tag required", 400)
            if not raw_scope:
                return error_response("PATH_REQUIRED", "path required", 400)
            scope = Path(raw_scope).resolve()
            if not scope.is_dir():
                return error_response("NOT_A_DIRECTORY", "path is not a directory", 400)
            if not is_path_allowed(scope, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            report_all_tags = request.args.get("report_all_tags", "") == "1"
            # Exclude entries that have any hidden tag (hard or soft); null tag = tag absent.
            hide_tags_filter = hide_tags
            show_null_tagged = True  # Always include null-tagged in search results; view layer filters by toggle
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
                    entries_list = list(scope_path.iterdir())
                except OSError:
                    entries_list = []
                entries_list.sort(key=lambda p: p.name.lower())
                if emit_progress:
                    dir_names = [p.name for p in entries_list if p.is_dir()]
                    yield ("progress", resolved, dir_names)
                try:
                    for p in entries_list:
                        try:
                            entry_path = str(p.resolve())
                            if not is_path_allowed(p, roots):
                                continue
                            is_dir = p.is_dir()
                            size = 0 if is_dir else p.stat().st_size
                            meta_for_scope = _meta.get_path_meta(entry_path)
                            scope_vpath = (meta_for_scope.get("vpath") if meta_for_scope else None) or entry_path
                            entry = build_listing_entry_from_meta(
                                _meta,
                                entry_path,
                                p.name,
                                is_dir,
                                size,
                                hide_tags_filter,
                                path_obj=p,
                                scope_for_vpath_children=scope_vpath,
                                scope_for_rules=entry_path,
                            )
                            if entry is None:
                                continue
                            eff = effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                            if report_all_tags:
                                all_tags_set |= eff
                            if tag not in eff and not (show_null_tagged and tag in entry["tags_negation"]):
                                if p.is_dir():
                                    yield from walk(p, all_tags_set, emit_progress)
                                continue
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
                all_tags_from_dirs = set()
                for d in sorted(dirs_to_show, key=str.lower):
                    p = Path(d)
                    if not p.exists() or not p.is_dir():
                        continue
                    meta_for_scope = _meta.get_path_meta(d)
                    scope_vpath = (meta_for_scope.get("vpath") if meta_for_scope else None) or d
                    entry = build_listing_entry_from_meta(
                        _meta,
                        d,
                        p.name,
                        True,
                        0,
                        hide_tags_filter,
                        path_obj=p,
                        scope_for_vpath_children=scope_vpath,
                        scope_for_rules=d,
                        has_direct_match=(d in dirs_direct),
                    )
                    if entry is None:
                        continue
                    if report_all_tags:
                        all_tags_from_dirs |= effective_tags(entry["tags"], entry["tags_inherited"], entry["tags_negation"])
                    dir_entries.append(entry)
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
                return error_response("PATH_AND_TAG_REQUIRED", "path and tag required", 400)
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            _meta.add_tag(raw, tag)
            return jsonify({"path": raw, "tags": _meta.get_tags(raw)})

        @app.route("/api/tags", methods=["DELETE"])
        def api_remove_tag():
            raw = (request.args.get("path") or "").strip()
            tag = (request.args.get("tag") or "").strip()
            if not raw or not tag:
                return error_response("PATH_AND_TAG_REQUIRED", "path and tag required", 400)
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            _meta.remove_tag(raw, tag)
            return jsonify({"path": raw, "tags": _meta.get_tags(raw)})

        @app.route("/api/tags/batch", methods=["POST"])
        def api_add_tag_batch():
            data = request.get_json() or {}
            paths = data.get("paths") or []
            tag = (data.get("tag") or "").strip()
            if not tag:
                return error_response("TAG_REQUIRED", "tag required", 400)
            if not isinstance(paths, list):
                return error_response("PATHS_MUST_BE_LIST", "paths must be a list", 400)
            added = 0
            for raw in paths:
                path_str = str(Path(raw).resolve()) if raw else ""
                if not path_str:
                    continue
                path_obj = Path(path_str)
                if not is_path_allowed(path_obj, roots):
                    continue
                try:
                    _meta.add_tag(path_str, tag)
                    added += 1
                except Exception:
                    pass
            return jsonify({"tag": tag, "added": added})

        from .routes.rules import register_rules_routes
        register_rules_routes(app, _meta)

        @app.route("/api/tag-nulls", methods=["POST"])
        def api_add_tag_null():
            data = request.get_json() or {}
            raw = (data.get("path") or "").strip()
            tag = (data.get("tag") or "").strip()
            if not raw or not tag:
                return error_response("PATH_AND_TAG_REQUIRED", "path and tag required", 400)
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            _meta.add_tag_null(raw, tag)
            return jsonify({
                "path": raw,
                "tags": _meta.get_tags(raw),
                "tags_negation": _meta.get_tag_nulls(raw),
            })

        @app.route("/api/tag-nulls", methods=["DELETE"])
        def api_remove_tag_null():
            raw = (request.args.get("path") or "").strip()
            tag = (request.args.get("tag") or "").strip()
            if not raw or not tag:
                return error_response("PATH_AND_TAG_REQUIRED", "path and tag required", 400)
            path_obj = Path(raw)
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            _meta.remove_tag_null(raw, tag)
            return jsonify({
                "path": raw,
                "tags": _meta.get_tags(raw),
                "tags_negation": _meta.get_tag_nulls(raw),
            })

        @app.route("/api/hidden-tags")
        def api_get_hidden_tags():
            tags = _meta.get_hidden_tags()
            return jsonify({"hidden_tags": list(tags)})

        @app.route("/api/hidden-tags", methods=["POST"])
        def api_add_hidden_tag():
            data = request.get_json() or {}
            tag = (data.get("tag") or request.args.get("tag") or "").strip()
            if not tag:
                return error_response("TAG_REQUIRED", "tag required", 400)
            _meta.add_hidden_tag(tag)
            return jsonify({"tag": tag, "hidden_tags": list(_meta.get_hidden_tags())})

        @app.route("/api/hidden-tags", methods=["DELETE"])
        def api_remove_hidden_tag():
            tag = (request.args.get("tag") or "").strip()
            if not tag:
                return error_response("TAG_REQUIRED", "tag required", 400)
            _meta.remove_hidden_tag(tag)
            return jsonify({"tag": tag, "hidden_tags": list(_meta.get_hidden_tags())})

        @app.route("/api/new-folder", methods=["POST"])
        def api_new_folder():
            data = request.get_json() or {}
            parent_raw = (data.get("path") or "").strip()
            name = (data.get("name") or "").strip()
            if not parent_raw or not name:
                return error_response("PATH_AND_NAME_REQUIRED", "path and name required", 400)
            parent = Path(parent_raw).resolve()
            if not is_path_allowed(parent, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            # Allow real directory or virtual folder (meta row with no inode) as parent
            if parent.is_dir():
                pass
            elif _meta_db and _meta_db.exists():
                meta = _meta.get_path_meta(parent_raw) or _meta.get_meta_by_vpath(parent_raw)
                if meta is None or meta.get("inode") is not None:
                    return error_response("NOT_A_DIRECTORY", "path is not a directory", 400)
            else:
                return error_response("NOT_A_DIRECTORY", "path is not a directory", 400)
            # Disallow path segments in name
            if "/" in name or name in ("", ".", ".."):
                return error_response("INVALID_FOLDER_NAME", "invalid folder name", 400)
            new_path = parent / name
            new_path_str = str(new_path.resolve())
            if not is_path_allowed(new_path, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            try:
                meta_path = _meta.add_virtual_folder(new_path_str)
            except ValueError as e:
                _log.warning("New folder conflict: %s", e)
                return error_response("CONFLICT", "Conflict (e.g. name already exists)", 409)
            return jsonify({"path": meta_path, "vpath": new_path_str}), 201

        @app.route("/api/move", methods=["POST"])
        def api_move():
            """Set location state (vpath) for the entity identified by path. Move, rename, trash, restore
            are all this single state update. Contract: PUT /api/vpath; this route kept for compatibility."""
            data = request.get_json() or {}
            path_raw = (data.get("path") or "").strip()
            vpath_raw = (data.get("vpath") or "").strip()
            if not path_raw:
                return error_response("PATH_REQUIRED", "path required", 400)
            path_obj = Path(path_raw).resolve()
            if not is_path_allowed(path_obj, roots):
                return error_response("PATH_NOT_ALLOWED", "path not allowed", 403)
            # Keep vpath as-is (do not resolve): __VTRASH/... must stay literal, not become cwd-relative
            vpath_str = vpath_raw if vpath_raw else None
            if vpath_str and not vpath_str.startswith("__VTRASH/"):
                if not is_path_allowed(Path(vpath_str), roots):
                    return error_response("VPATH_NOT_ALLOWED", "vpath not allowed", 403)
            job_id = (data.get("job_id") or "").strip() or None
            if job_id is None:
                job_id = (request.headers.get("X-Job-Id") or "").strip() or None
            if job_id is None:
                _log.warning("move request received with no job_id; path=%s (client may be using cached JS)", path_raw)
            try:
                _meta.set_vpath(path_raw, vpath_str, job_id)
            except ValueError as e:
                _log.warning("Move conflict: %s", e)
                return error_response("CONFLICT", "Conflict (e.g. destination exists)", 409)
            return jsonify({"path": path_raw, "vpath": vpath_str, "job_id": job_id}), 200

        @app.route("/api/generate-commands")
        def api_generate_commands():
            """Generate filesystem commands to materialize pending vpath changes. No execution.
            job_id: optional; if omitted or 'all', returns all pending; else only that job."""
            if not _meta_db or not _meta_db.exists():
                return error_response("NO_META_DB", "No meta DB configured", 503)
            job_id = request.args.get("job_id") or None
            if job_id == "":
                job_id = None
            commands = _meta.generate_commands(job_id)
            return jsonify({"commands": commands})

        @app.route("/api/changes")
        def api_changes():
            """Return meta rows (path, vpath) where path or vpath is under scope_left or scope_right.
            Used for the changes pane (location-state changes in either pane scope)."""
            scope_left = (request.args.get("scope_left") or "").strip() or None
            scope_right = (request.args.get("scope_right") or "").strip() or None
            rows = _meta.get_moved_in_scopes(scope_left, scope_right)
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
                return error_response("NO_META_DB", "No meta DB configured", 503)
            rows = _meta.get_all_meta_for_debug()
            return jsonify({
                "meta": rows,
                "meta_db": str(_meta.db_path),
                "meta_db_exists": _meta.db_path.exists(),
            })
        except Exception as e:
            _log.exception("Debug meta failed")
            return error_response("INTERNAL_ERROR", "An error occurred", 500, retryable=True)

    return app
