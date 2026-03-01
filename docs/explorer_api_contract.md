# Explorer API Contract

Version: 1. All Explorer HTTP API responses that indicate failure use the canonical error envelope below. Success responses are described per endpoint.

---

## 1. Error envelope

Every error response has this shape:

```json
{
  "error": {
    "code": "<stable code>",
    "message": "<human-readable message>",
    "retryable": false,
    "details": {}
  }
}
```

- **code**: Stable string for client logic (e.g. `PATH_REQUIRED`, `PATH_NOT_ALLOWED`). Does not change between releases for the same condition.
- **message**: Human-readable text; may be localised or improved without changing code.
- **retryable**: `true` only if the client may retry the same request (e.g. transient server error).
- **details**: Optional object; must not contain sensitive or internal data. Omitted if empty.

No stack traces, exception names, or internal paths appear in the response. Full diagnostics are logged server-side only.

### 1.1 Error codes (stable)

| Code | HTTP | Meaning |
|------|------|--------|
| `PATH_REQUIRED` | 400 | Missing or empty `path` argument. |
| `PATH_NOT_ALLOWED` | 403 | Path is outside allowed roots. |
| `VPATH_NOT_ALLOWED` | 403 | Virtual path (vpath) is outside allowed roots. |
| `NOT_A_DIRECTORY` | 400 | Path exists but is not a directory. |
| `NOT_A_FILE` | 400 | Path exists but is not a file. |
| `TAG_REQUIRED` | 400 | Missing or empty `tag` argument. |
| `INVALID_TAG` | 400 | Tag contains invalid characters (e.g. comma, slash). |
| `PATTERN_REQUIRED` | 400 | Missing or empty `pattern` argument. |
| `OLD_AND_NEW_PATTERN_REQUIRED` | 400 | Rule update requires both old_pattern and new_pattern. |
| `PATTERN_AND_TAG_REQUIRED` | 400 | Rule requires pattern and tag. |
| `PATH_AND_TAG_REQUIRED` | 400 | Request requires path and tag. |
| `PATH_AND_NAME_REQUIRED` | 400 | New folder requires path and name. |
| `PATHS_MUST_BE_LIST` | 400 | Batch tag request body must have paths as a list. |
| `INVALID_FOLDER_NAME` | 400 | Folder name invalid (e.g. empty or contains slash). |
| `UNSUPPORTED_TYPE` | 400 | Preview or operation not supported for this file type. |
| `NO_META_DB` | 503 | Meta DB not configured or unavailable (e.g. debug endpoint). |
| `CONFLICT` | 409 | Conflict (e.g. name already exists, move conflict). |
| `NOT_FOUND` | 404 | Resource not found (e.g. path no longer exists). |
| `INTERNAL_ERROR` | 500 | Unexpected server error; retryable may be true. |

---

## 2. Endpoints

Base path: `/api` unless noted. All JSON request bodies are `application/json`; query params are as listed.

### 2.1 HTML / static

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves Explorer UI (index.html). |

### 2.2 Read-only API

| Method | Path | Query / body | Success response |
|--------|------|--------------|------------------|
| GET | `/api/roots` | — | `["/", "/Volumes/…", …]` |
| GET | `/api/preview` | `path` | `{ "kind": "none" \| "image" \| "video" \| "text" \| "unsupported", … }` |
| GET | `/api/preview-file` | `path` | Binary (image/video); error envelope on failure. |
| GET | `/api/listing` | `path`, `hide_tags?`, `report_all_tags?` | `{ "path", "entries": […], "all_tags_in_scope"? }` |
| GET | `/api/parent` | `path?` | `{ "parent": "/path" \| null }` |

**Visibility:** The `hide_tags` query parameter (and `/api/hidden-tags`) is a generic feature: the user can mark any tag as "hidden from listing". Entries whose effective tags intersect `hide_tags` are excluded. No tag name (e.g. "hide" or "trash") has special meaning; all tags are treated the same.

### 2.3 Meta (tags, rules, move) — require meta DB

| Method | Path | Query / body | Success response |
|--------|------|--------------|-------------------|
| GET | `/api/tags` | `path` | `{ "path", "tags": […] }` |
| POST | `/api/tags` | JSON `path`, `tag` | `{ "path", "tags": […] }` |
| DELETE | `/api/tags` | `path`, `tag` | `{ "path", "tags": […] }` |
| POST | `/api/tags/batch` | JSON `path`, `paths[]`, `tag` | `{ "tag", "paths": […] }` |
| GET | `/api/tag-names` | — | `{ "tags": […] }` |
| GET | `/api/tagged` | `tag`, `hide_tags?`, `report_all_tags?`, `show_null_tagged?` | `{ "tag", "entries": […], "all_tags_in_scope"? }` |
| GET | `/api/tag-search` | `tag`, `path`, `mode=matches\|contains`, `stream?`, … | JSON array (contains) or NDJSON stream (matches + stream=1). |
| POST | `/api/tag-nulls` | JSON `path`, `tag` | `{ "path", "tags", "tags_null": […] }` |
| DELETE | `/api/tag-nulls` | `path`, `tag` | `{ "path", "tags", "tags_null": […] }` |
| GET | `/api/rules` | — | `{ "rules": […] }` |
| POST | `/api/rules` | JSON `pattern`, `tag` | `{ "rules": […] }` |
| DELETE | `/api/rules` | JSON `pattern`, `tag` | `{ "rules": […] }` |
| PATCH | `/api/rules` | JSON `old_pattern`, `new_pattern`, `tag` | `{ "rules": […] }` |
| GET | `/api/hidden-tags` | — | `{ "tags": […] }` |
| POST | `/api/hidden-tags` | JSON `tag` | `{ "tags": […] }` |
| DELETE | `/api/hidden-tags` | `tag` | `{ "tags": […] }` |
| POST | `/api/new-folder` | JSON `path`, `name` | `{ "path" }` |
| POST | `/api/move` | JSON `path`, `vpath` | `{ "path", "vpath" }` |
| GET | `/api/changes` | `scope_left?`, `scope_right?` | `{ "changes": […] }` |

### 2.4 Debug

| Method | Path | Success response |
|--------|------|-------------------|
| GET | `/api/debug/ping` | `{ "pong": true }` |
| GET | `/api/debug/meta` | `{ "meta": […], "meta_db", "meta_db_exists" }` or error envelope. |

---

## 3. Listing entry shape (reference)

Each item in `entries` (listing, tagged, tag-search) has the same logical shape:

- `path`, `name`, `is_dir`, `size` (optional), `empty` (optional)
- `tags`, `tags_inherited`, `tags_null` (when meta is used)
- `vpath`, `display_style` (when moved/virtual)
- `has_direct_match` (contains mode only, optional)

Exact keys may vary by endpoint; this is the conceptual contract for “one file or folder in a list”.

---

## 4. Typed shapes (reference)

The implementation uses `file_triage.explorer.types` for TypedDict shapes: `ErrorEnvelope`, `ListingEntry`, `ListingResponse`. These align with the JSON contract above.

---

*This contract is the single source of truth for Explorer API behaviour. Implementation must not leak internal details in error responses.*
