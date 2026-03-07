# File Triage — Backlog (spec alignment and consolidation)

Gap analysis between **current implementation** and **specification documents** (PSEUDO_LOGIC.md, FUNCTIONAL_SPECIFICATION.md, FUNCTIONAL_CHEATSHEET.md, EXPLORER_RULES.md) is used to derive iterations that bring implementation into alignment, consolidate for reuse, and keep code minimal (no overload: one way per concept, one name per concept).

**Ordering principle:** High impact from a design/maintenance perspective, **low blast radius** first. Ease into meaningful change; avoid high-risk destabilizing changes at the top.

**Deployment before development:** Deployment strategy and end-to-end CI/CD are prerequisites for development (../core-documentation/CODING_STANDARDS § Deployment and CI/CD). No development iteration (beyond the current one) may start until the deployment pipeline is in place and a hello-world MVP has been run through it. **If you are midstream on an iteration,** complete that iteration first; then satisfy the deployment prerequisite before advancing to the next development iteration. See § Deployment iteration below.

**Relationship to ../core-documentation/CODING_STANDARDS.md:** BACKLOG defines **what** (outcomes, deliverables, iteration scope). ../core-documentation/CODING_STANDARDS.md defines **how** (implementation approach). The two are orthogonal: apply coding standards when implementing backlog items; do not embed coding strategy inside backlog tasks.

**Per-iteration workflow:** For each iteration: (1) update version in package.json, (2) merge, (3) commit, (4) push. CI creates a Git tag from the version; bumping ensures the tag does not already exist.

---

## Gap summary (implementation vs spec)

| Area | Spec | Current implementation | Gap |
|------|------|------------------------|-----|
| **Path / vpath** | effective_path = vpath ?? path; set_vpath normalizes and persists; move/rename/delete/restore = set_vpath only | set_vpath in meta/db.py with normalize; move/rename/trash/restore call it | Aligned. Naming in code comments could say "set_vpath" / "set location". |
| **Tags** | (Hard ∪ Soft) ∖ Negation; soft from **parent only** + rules; four states: soft, hard, negation, absent | effective_tags; get_parent_effective_tags; tags_negation in API; tag_nulls stores negation | Aligned. |
| **Entry building** | Single logical path for entry + tags + empty | Duplicated "get_tags, get_tag_nulls, get_tags_from_rules, get_ancestor_tags → build" in listing, tagged, tag-search | Consolidate to one path (see REFACTOR_ITERATION_PLAN Iteration 4). |
| **Empty** | folder_empty and file_empty depend on show_trashed; child-by-path only when vpath null or show_trashed | compute_empty is model-level (no show_trashed); frontend uses entry.empty | Align: document model vs view empty; frontend "empty" = no visible children after filter; file empty = size==0 or (vpath && !showTrashed). |
| **Visibility** | Render-time only; backend returns full data | Backend passes hide_tags=set(); show_null_tagged=True always | Aligned. |
| **TS / SRS** | Tag matches/containers in TS; contains mode → move_in no-op. SRS = other search types (e.g. regex_path). | Tag search is separate route; drop on tag scope always adds tag; no regex search | Contains-mode no-op missing. SRS regex_path not implemented. |
| **Controls** | Scope-local toggles (e.g. show_negation) in pane; global (show_trashed, hidden_tag_set) in shared UI | show_trashed and show_null in header | Optional: move show_negation into pane for TS/SRS (later). |
| **Terminology** | pane, scope, negation, effective path, set_vpath | view, left/right pane, tags_negation | Aligned (Iteration 6). |

---

## Iteration 1 — Docs and API naming (zero behavior change)

**Goal:** Align documentation and public API naming with spec. No logic or UI behavior change. Lowest blast radius.

- [x] Contract doc has a "Terms (spec-aligned)" section: effective path, set_vpath, negation (tag state), scope (FS/TS/SRS), pane; API keys mapped to spec (e.g. tags_null ↔ negation).
- [x] API contract and responses consistently expose or document negation (e.g. tags_negation alias or tags_null documented as negation set). Frontend may continue using existing key until a later iteration.
- [x] Contract and in-code comments use "pane" where spec means container; "view" reserved for data-view context.
- [x] Move/rename/trash/restore primitive referred to as set_vpath or set location in contract and relevant docstrings.
- [x] EXPLORER_RULES, FUNCTIONAL_SPECIFICATION, FUNCTIONAL_CHEATSHEET, PSEUDO_LOGIC are the single source of truth; other docs (e.g. REFACTOR_ITERATION_PLAN) reference these rather than duplicating spec wording.

**Deliverables:** Updated contract doc; consistent terminology; no request/response behavior change.

---

## Deployment iteration — Pipeline and hello-world MVP (prerequisite gate)

**Goal:** Satisfy the deployment/CI/CD prerequisite before advancing with further development work. This project uses the **canonical** approach for desktop apps (Electron + Homebrew Cask); see ../core-documentation/CODING_STANDARDS § Canonical deployment strategy and DETAILED_DESIGN § Deployment.

- [x] **Deployment approach:** Canonical (Electron + brew cask) chosen and documented in DETAILED_DESIGN § Deployment.
- [x] **Electron shell:** App runs inside Electron (wrap existing backend + frontend). Minimal window, load the Explorer UI; backend (Flask or equivalent) runs locally inside the app or is served by the same process.
- [x] **Build:** macOS artifact (`.app` in `.dmg` or `.zip`) produced via standard tool (e.g. `electron-builder`). Build is repeatable (e.g. from `npm run build` or CI script).
- [x] **Publish:** Artifact hosted at a stable, versioned URL (e.g. GitHub Releases). Pipeline creates the release and uploads the artifact.
- [x] **Cask:** A Homebrew Cask exists that points at the release URL (either in a dedicated tap repo or prepared for submission to homebrew-cask). Cask includes `version`, `sha256`, `url`, `name`, `desc`, `homepage`, `app`.
- [x] **CI/CD pipeline:** End-to-end workflow runs on push/tag (e.g. GitHub Actions): build Electron app → run tests → create release + upload artifact → (if using a tap) update cask and push. Pipeline is documented (e.g. in README or `.github/workflows`).
- [x] **Hello-world MVP:** Full run through the pipeline; install the app via `brew install --cask <cask>` (or run the built `.app`/`.dmg`) and **verify it launches** (see DETAILED_DESIGN § Deployment → How to verify the hello-world MVP). Prerequisite satisfied; development unblocked for Iteration 2+.
- [x] No further development iterations (e.g. Iteration 2+) are started until this gate is satisfied. If midstream on an iteration (e.g. Iteration 1), complete it first, then complete this deployment iteration.

**Deliverables:** Electron app builds and runs; artifact published at stable URL; cask available; CI/CD pipeline in place and exercised; **hello-world MVP verified** (run the steps in DETAILED_DESIGN § Deployment → How to verify the hello-world MVP at least once). Development unblocked for next backlog iteration.

---

## Iteration 2 — Single entry-build path (consolidation)

**Goal:** One code path for building a listing entry (tags, soft, negation, effective, empty, hide filter). Removes duplication and overload.

- [x] A single entry-build path exists: given path, tag/vpath data (or accessor), and hide_tags, returns full listing entry or exclude. All listing, tagged, and tag-search responses use it.
- [x] A single tag-resolution path exists: given path and accessor, returns (hard, soft, negation). Soft uses current parent-chain semantics (inheritance unchanged in this iteration).
- [x] All duplicated tag-resolution and entry-building blocks in listing, tagged, and tag-search routes are removed; routes call the single path.
- [x] A single empty-computation path exists and is the only place empty is set for entries; duplicate compute_empty call sites removed.
- [x] Single entry-build path is covered by tests.

**Deliverables:** No duplicate tag-resolution or entry-shape logic; routes are thin (parse → single build path → response).

---

## Iteration 3 — Empty: model vs view and file empty

**Goal:** Align empty semantics with spec: folder empty and file empty depend on show_trashed where specified; view-level empty = after visibility filter.

- [x] Contract or EXPLORER_RULES documents **model empty** (what API returns) vs **view empty** (after visibility): folder has no visible children; file empty = size 0 or (has vpath and show_trashed is off).
- [x] Backend continues to return one consistent model-level `empty` per entry (no show_trashed in API for this iteration unless required).
- [x] Frontend empty display: folder = no visible children after visibility filter (or entry.empty when no children loaded); file = (size === 0) or (entry.vpath && !showTrashed). Applied wherever row-empty or empty state is shown.
- [x] If "empty in view" is later exposed by API (e.g. with show_trashed param), document as future option; do not change default response shape in this iteration.

**Deliverables:** Spec-aligned empty semantics documented; frontend empty display uses view-level rule for file and folder.

---

## Iteration 4 — Contains mode: move_in no-op

**Goal:** When tag scope is in "containers" mode (showing folders that contain the tag), dropping an item onto the tag pane is a no-op (spec: move_in when contains_mode → no_op).

- [x] Current scope and mode (e.g. tag scope + containers) are known when handling drop.
- [x] Drop onto the tag pane when in tag scope and containers mode: no add-tag call, no vpath change. Optional: brief message that move-in is not available in containers mode.
- [x] Verification: tag search in contains mode, drag item to tag pane → no tag added, no move.

**Deliverables:** Contains-mode drop = no-op; no backend change required.

---

## Iteration 5 — Inheritance: parent only

**Goal:** Soft tags from **parent only** (spec). Parent's negation → child has absent, not negation. Medium blast radius (behavior change for deep hierarchies).

- [x] Parent-only tag source exists: soft for a path = effective set of parent ∪ rule-matched tags. No ancestor chain.
- [x] Tag-resolution path (Iteration 2) uses parent-only semantics; parent's negation implies child has absent for that tag (parent effective set excludes it).
- [x] Former ancestor-chain call sites removed or switched to parent-only path.
- [x] Tests: parent has tag T → child has soft T; parent has negation T → child absent for T; grandparent has T, parent has negation T → child absent for T.

**Deliverables:** Inheritance is parent-only and spec-aligned; no ancestor-chain usage.

---

## Iteration 6 — Naming: null → negation in API and types

**Goal:** Public API and domain types use "negation" where the spec says negation; DB table name can remain for migration simplicity.

- [x] Domain/API entry shape exposes negation under a spec-aligned name (e.g. tags_negation); backward-compat alias or full rename chosen and applied consistently.
- [x] API contract and route docstrings use "negation tag" (not "null tag") for the concept.
- [x] Internal storage (e.g. tag_nulls table and its accessors) either unchanged and documented as "stores negation tags," or renamed in a separate migration.

**Deliverables:** Public surface (API, types, docs) uses "negation"; storage naming documented or migrated.

---

## Iteration 7 — Apply: generate filesystem commands (no execution)

**Goal:** The app is a pure overlay—vpath changes do not mutate the filesystem. Add the ability to **generate** (not execute) a list of filesystem commands that would materialize pending changes. Commands should be as transactional and reversible as possible. Trash is already covered; focus on moves/copies that could leave the filesystem in a partial state if interrupted.

**Initial scope:** Generate the instruction list only. No execution. User can review commands before a future iteration adds execution.

- [ ] **job_id:** Add `job_id` column to meta table (nullable; discriminator for grouping changes). New vpath writes can be associated with a job. Jobs can be applied one at a time.
- [ ] **Generate commands:** API or module that, given a job_id (or "all pending"), produces an ordered list of filesystem instructions (e.g. `mv`, `cp`, `rsync`—choose the most stable/transactional option). Instructions are idempotent where possible; partial completion should leave a recoverable state.
- [ ] **Contract:** Document the generated-command format (e.g. `{ op, src, dst, job_id }`). No execution in this iteration.
- [ ] **Future options (out of scope):** Execute staged changes; generate + review + accept each command; undo/rollback. Document as follow-on iterations.

**Design note (rollback):** We may implement an entire subtree in the filesystem as a backup structure to support rollback. Design this before implementation if we use it.

**Deliverables:** job_id in meta; generate-commands API or function; contract for command shape. No UI execution.

---

## Iteration 8 — Background search jobs

**Goal:** Run search as a background process so the user can navigate away without losing context. Search jobs are persistent, trackable, and viewable (complete or partial). Stopping a search stops the action but leaves results under that job.

- [ ] Search executes as a background process; user can navigate to folders or other views without aborting the search.
- [ ] Each search is tracked as a job with a clickable entry; user can return to view results when complete or partially complete.
- [ ] Stop search: stops the search action; results remain (partial) under that job and stay viewable.
- [ ] Search jobs are persistent (survive navigation, reload, or session end—scope TBD).
- [ ] Each search job has a trash-can icon/button to delete it; deleted jobs are removed from the list.

**Deliverables:** Background search execution; job list with click-to-view results; stop leaves partial results; persistence; delete control.

---

## Iteration 9 — SRS: regex_path search type

**Goal:** One additional search type (regex on path) so SRS is not only tag-search; result set is model-level; show_trashed affects display only.

- [ ] Search API supports a type (e.g. regex_path) and pattern parameter; result set includes all matches (path and vpath); no show_trashed filtering in result set. Contract documents that visibility is applied at render time.
- [ ] Frontend can run regex-path search and display results in the same pane as tag search, with existing visibility filtering.
- [ ] Contract documents search_type=regex_path, pattern, and response shape.

**Deliverables:** Regex path search available; SRS shows non-tag results; spec search_matches extended.

---

## Iteration 10 — Toggle placement (scope-local vs global)

**Goal:** Scope-local toggles (e.g. show_negation) appear in the pane whose scope they affect; global toggles (show_trashed, hidden_tag_set) remain in shared UI. Optional / lower priority.

- [ ] Scope-local toggles (show_negation, include_soft_tags, contains_mode) are bound to the pane that shows that scope when active; not only in header.
- [ ] Global toggles remain in header or shared toolbar.
- [ ] Pane-specific toggles do not duplicate when switching scope (re-bind or re-render per scope).
- [ ] Spec docs (PSEUDO_LOGIC, EXPLORER_RULES) updated if placement is specified there.

**Deliverables:** Scope-local toggles in pane; global in shared area; placement only, no behavior change.

---

## Iteration 11 — Testing and contract stability

**Goal:** Tests lock spec-aligned behavior and prevent regression. Can run in parallel or after Iterations 1–5.

- [ ] Domain tests cover: effective_tags (hard, soft, negation); parent-only soft (after Iteration 5); entry_empty / compute_empty with and without vpath children; build_listing_entry with hide_tags.
- [ ] API contract tests: listing, tagged, tag-search, move responses match contract; error envelope used; no internal leakage. At least one test per route group.
- [ ] Spec-regression tests or scenarios cover key rules: move out of TS removes scope tag; contains mode move_in no-op; effective_path = vpath ?? path; normalize vpath when vpath == path.

**Deliverables:** tests/ with pytest; CI or run instruction; contract and spec behavior covered.

---

## Iteration 12 — Module and file organization (optional)

**Goal:** Clear module boundaries; one primary concern per file where practical; reduced overload.

- [ ] Explorer routes grouped by concern; app wiring delegates to route modules.
- [ ] Single entry point for Explorer → meta (no direct db imports in route handlers).
- [ ] Public surface documented in explorer and meta __init__ (or equivalent).

**Deliverables:** Clear boundaries; no new behavior.

---

## Suggested order and dependencies

```
Iteration 1 (docs + naming, zero behavior)     ← start
    ↓
Deployment iteration (pipeline + hello-world MVP)   ← gate: must complete before Iteration 2
    ↓
Iteration 2 (single entry-build path)           ← consolidation
    ↓
Iteration 3 (empty model vs view)               ← small frontend + doc
Iteration 4 (contains mode no-op)               ← small frontend
    ↓
Iteration 5 (parent-only inheritance)           ← behavior change, medium radius
Iteration 6 (null → negation naming)           ← API/types/docs
    ↓
Iteration 7 (Apply: generate commands)          ← new capability; after 6 to keep meta stable
Iteration 8 (background search jobs)            ← search UX: persistent jobs, click to view, stop leaves partial
Iteration 9 (regex_path search)                 ← new feature
Iteration 10 (toggle placement)                 ← UI reorg, optional
Iteration 11 (testing)                           ← can run in parallel after 2–4
Iteration 12 (module organization)               ← optional, after 2
```

**Midstream rule:** If already in progress on an iteration (e.g. Iteration 1), finish it; then do the **Deployment iteration** before starting Iteration 2.

**Minimum to align with spec (time-boxed):** Deployment → 2 → 3 → 4 → 5 → 6, then 9. That gives pipeline, terminology, single entry path, empty semantics, contains no-op, parent-only inheritance, negation naming, and tests.

---

## Reference

- **Executive summary:** EXECUTIVE_SUMMARY.md
- **Specs:** PSEUDO_LOGIC.md, FUNCTIONAL_SPECIFICATION.md, FUNCTIONAL_CHEATSHEET.md, EXPLORER_RULES.md
- **Coding standards:** ../core-documentation/CODING_STANDARDS.md (how to implement; orthogonal to this backlog)
- **Existing plan:** REFACTOR_ITERATION_PLAN.md (development standards; BACKLOG focuses on spec alignment and consolidation)
- **API:** explorer_api_contract.md

*Update checkboxes as work completes (- [ ] → - [x]).*
