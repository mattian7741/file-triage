# File-Triage Refactor: Iteration Plan vs Development Standards

This plan aligns the file-triage codebase with **AA_ADDENDUM_06_DEVELOPMENT_STANDARDS.md** (core-platform-spec). Iterations are ordered so each builds on the previous; each delivers a shippable state.

**Reference:** `dev/core-platform-spec/AA_ADDENDUM_06_DEVELOPMENT_STANDARDS.md`

---

## Current Gaps (Summary)

| Standard | Current state |
|----------|----------------|
| **Contracts first** | No versioned API contract; ad-hoc JSON; no schema validation at boundaries. |
| **Functional core / imperative shell** | Domain logic (effective tags, empty, entry shape) mixed with Flask and inline meta calls in `explorer/app.py`; meta access is direct, not injected. |
| **Strong typing** | Partial typing; request/response at API boundaries unvalidated (no TypedDict/Pydantic). |
| **One primary construct per file** | `explorer/app.py` ~1150 lines, many routes + helpers; `meta/db.py` many accessors in one file. |
| **Explicit data access / no ORM** | Raw SQL in meta is fine; no clear accessor abstraction or DI. |
| **Error handling** | Broad `except Exception`; no canonical error envelope; `jsonify({"error": ...})` ad-hoc. |
| **Boundary discipline** | No input validation, no correlation IDs, no standard response envelope. |
| **Testing** | No tests. No contract tests, no pure-logic tests. |

---

## Iteration 1: API contract and error envelope (boundary discipline) ✅

**Goal:** Define a single, stable contract at the HTTP boundary and use it everywhere.

**Scope:**
- Introduce a **canonical error envelope** (e.g. `{ "error": { "code": str, "message": str, "retryable": bool } }`) and use it for all error responses from the Explorer API.
- Document **API contract** (list of routes, request/response shapes) in a single doc or schema (e.g. OpenAPI fragment or MARKDOWN table). No implementation change to request handling yet; focus on responses and errors.
- Replace broad `except Exception` at route level with **specific exception handling** and **translation** into the error envelope; log full diagnostics at the route only, never leak stack traces in responses.

**Deliverables:**
- `docs/explorer_api_contract.md` (or similar) with error envelope and list of endpoints + response shapes.
- Helper (e.g. `_error_response(code, message, retryable=False)`) used by all Explorer routes.
- All `jsonify({"error": ...})` and exception paths go through the envelope.

**Standards addressed:** §1.1 Contracts first, §2.4 Boundary discipline, §3.6 Error handling.

---

## Iteration 2: Extract domain types and pure “entry/tags” logic

**Goal:** Isolate deterministic, testable rules for “effective tags”, “empty”, and “listing entry” so they are not tied to Flask or DB.

**Scope:**
- Define **typed data structures** for the domain: e.g. `ListingEntry`, `TagSet` (explicit, inherited, nulls), and a single **effective-tags** function (pure: given explicit/inherited/nulls → effective set).
- Extract **“empty” rule** into one pure function: inputs (path type, size, has_vpath_children, recursive_empty), output bool. Call it from a single place in the Explorer that currently duplicates the empty logic.
- Extract **entry-building** into a single pure function (or small set): given path, meta row, tag sets, hide_tags → optional `ListingEntry` (or “skip”). No I/O inside; all data passed in.

**Deliverables:**
- New module(s), e.g. `file_triage.explorer.domain` or `file_triage.domain.entries`, containing only types and pure functions (no Flask, no sqlite3).
- Explorer `app.py` (or a dedicated “listing” helper) calls these functions with data fetched via meta; no duplication of effective-tags or empty logic.

**Standards addressed:** §1.2 Functional core, §3.1 Strong typing, §3.4 Functions and helpers.

---

## Iteration 3: Meta layer — accessor abstraction and DI

**Goal:** Explicit data accessors, swappable via dependency injection; no domain logic inside storage layer.

**Scope:**
- Introduce an **accessor interface** (protocol or abstract class) for “meta” operations used by the Explorer: get tags, get nulls, get path meta, get entries by vpath parent, etc. One interface, implemented by a single class that wraps current `meta.db` functions.
- **Inject** the meta accessor into the Explorer app (e.g. `create_app(meta_db_path=..., meta_accessor=None)` with a default implementation that uses `meta.db`).
- Keep **no ORM**: explicit methods, parameterized queries, row → domain mapping in the accessor. Move any “business” logic (e.g. effective tags) out of the accessor into the domain module from Iteration 2.

**Deliverables:**
- `file_triage.meta.accessor` (or similar): interface + default implementation using existing `db` module.
- Explorer creates or receives an accessor and uses it instead of importing `get_tags`, `get_path_meta`, etc. directly inside route handlers.

**Standards addressed:** §2.1 Isolation of concerns, §3.5 Data access.

---

## Iteration 4: Consolidate Explorer entry-building and tag resolution

**Goal:** Single code path for “build listing/tag-search entry” and “resolve tags for a path”.

**Scope:**
- Implement **one** function (or small pipeline) that: given path, vpath, meta row, and hide_tags, returns either a full `ListingEntry` or “exclude”. This uses the domain types and pure functions from Iteration 2 and the meta accessor from Iteration 3.
- Replace all duplicated “get_tags, get_tag_nulls, get_tags_from_rules, get_ancestor_tags → effective → build dict” blocks in `api_listing`, `api_tagged`, `api_tag_search` (and any other routes that build entries) with calls to this single path.
- Same for **“empty”**: one function that takes path info + meta (or accessor) and returns bool; used everywhere `empty` is set.

**Deliverables:**
- One “entry builder” (or builder + tag resolver) used by listing, tagged, tag-search (matches + contains). No copy-paste of tag resolution or entry shape.
- `explorer/app.py` route handlers become thin: parse request → call accessor + domain → format response.

**Standards addressed:** §3.4 Helpers that reduce duplication, §2.1 Isolation.

---

## Iteration 5: Module and file organization

**Goal:** Align with “one primary public construct per file” and flatter structure.

**Scope:**
- Split **Explorer** by concern (not by route count alone):
  - e.g. `explorer/app.py`: only `create_app` and wiring; register blueprints or route modules.
  - e.g. `explorer/routes/listing.py`: listing + parent; `explorer/routes/tags.py`: tags, tag-nulls, tagged, tag-search; `explorer/routes/preview.py`: preview, preview-file; `explorer/routes/rules.py`: rules CRUD; etc. Each file has one clear “primary” purpose (e.g. “listing API”).
- **Meta**: consider splitting `meta/db.py` into schema + connection vs accessors (e.g. `meta/schema.py`, `meta/accessors.py` or keep single accessor file that imports from db). Avoid deep nesting; prefer flat `meta/` with explicit public surface in `meta/__init__.py`.

**Deliverables:**
- Explorer routes grouped into a small set of modules; `app.py` delegates to them.
- Meta public API remains in `__init__.py`; internal layout clearer and easier to test.

**Standards addressed:** §3.2 Module and file organization.

---

## Iteration 6: Input validation and request typing

**Goal:** Validate all inputs at the boundary; typed request/response where feasible.

**Scope:**
- For each Explorer API route: **validate** path (allowed roots, no traversal), tag (non-empty, safe chars), and other args. Reject invalid input with the canonical error envelope (Iteration 1).
- Introduce **typed request/response** at boundaries: e.g. TypedDict or dataclasses for JSON bodies and responses. Use them in the route handlers and in the contract doc.
- Ensure **no raw internal exceptions** cross the boundary; translate to error envelope and log.

**Deliverables:**
- Validation helpers (path allowed, tag format, etc.) used by every route that needs them.
- TypedDict/dataclass for key request/response shapes; contract doc updated.

**Standards addressed:** §3.1 Strong typing, §2.4 Boundary discipline.

---

## Iteration 7: Testing — contracts and pure logic

**Goal:** Test behavior and contracts; pure domain and boundary tests first.

**Scope:**
- **Pure logic tests:** Add tests for domain module from Iteration 2 (effective tags, empty rule, entry builder with mocked inputs). No I/O; exhaustive branches where practical.
- **Contract tests:** For Explorer API, add tests that check: success responses match expected shape (status, JSON structure); error responses use the canonical envelope and do not leak internals. Cover at least one route per “group” (listing, tags, preview, rules) as a baseline.
- **Idempotency:** Where applicable (e.g. add-tag, move), add tests that repeat the same request and assert idempotent behavior.

**Deliverables:**
- `tests/` (or `src/file_triage/tests/`) with pytest. Pure domain tests; API contract tests using Flask test client.
- CI or local instruction to run tests.

**Standards addressed:** §5 Testing standards.

---

## Iteration 8: Instrumentation and observability (optional / lightweight)

**Goal:** Attach logging (and optionally metrics) without changing domain logic.

**Scope:**
- Add **request correlation** (e.g. request ID in header or middleware) and ensure it is logged at entry and on errors. Do not add logging inside pure domain functions.
- Optional: lightweight metrics (e.g. request count per route, error count) via a small middleware or decorator. Instrumentation must be attachable at the shell (Flask), not in domain.

**Deliverables:**
- Middleware or before/after handlers that add correlation ID and log request/response or errors. No instrumentation inside domain or accessor logic.

**Standards addressed:** §2.5 Instrumentation as an aspect.

---

## Suggested order and dependencies

```
Iteration 1 (contract + error envelope)     ← start here
    ↓
Iteration 2 (domain types + pure logic)     ← no dependency on 3
Iteration 3 (meta accessor + DI)            ← no dependency on 2
    ↓
Iteration 4 (consolidate entry-building)    ← needs 2 and 3
    ↓
Iteration 5 (module/file organization)     ← can run in parallel with 6
Iteration 6 (input validation + typing)      ← builds on 1
    ↓
Iteration 7 (testing)                       ← after 1–4 at least; 5–6 help
    ↓
Iteration 8 (instrumentation)               ← optional, last
```

**Minimum viable refactor (if time-boxed):** 1 → 2 → 4 (with minimal 3: keep current meta imports but call domain for entry/tags/empty). Then 7 for tests. That gives contract, functional core, single entry path, and tests.

---

## Out of scope (for later)

- **Async:** Standards prefer async-native entrypoints where the runtime supports it; domain stays sync. Flask is sync; a future ASGI port would be a separate effort.
- **Eventual consistency / replay:** File-triage is single-user and local; idempotent writes (add-tag, move) are enough for now. No message/event replay in this plan.
- **Config-driven binding:** Explicit mapping from request to handler args is acceptable; full schema-driven binding can come later if needed.

---

*This plan is a living document. Update it as iterations complete or priorities change.*
