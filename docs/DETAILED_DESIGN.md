# Detailed Design

Technical approach and implementation strategy for iterations. Driven by BACKLOG (requirements), ../core-documentation/CODING_STANDARDS (constraints), and the existing codebase. Written just-in-time before implementation; add as you go.

**Scope:** App-specific strategy only. Generally applicable strategy belongs in ../core-documentation/CODING_STANDARDS (see ../core-documentation/DEVELOPMENT_GUIDE § Where to capture strategy decisions). Do not repeat or relitigate coding standards here.

**Structure:** Organize by **application topology and features**, not by the sequence in which work was done. When adding or amending, place content under the relevant area (e.g. meta layer, explorer API, tag resolution, frontend panes). This document is a partially completed technical map that fills out as areas are touched and improved.

---

## Iteration 1 — Docs and API naming (BACKLOG Iteration 1)

**Scope:** Documentation and contract only. No request/response behavior change; no logic changes.

**Artifacts to touch:**

| Area | Action |
|------|--------|
| **explorer_api_contract.md** | Add § "Terms (spec-aligned)": effective path, set_vpath, negation (tag state), scope (FS/TS/SRS), pane. Map API keys to spec (e.g. `tags_null` ↔ negation). Document move/rename/trash/restore as set_vpath / set location. Use "pane" for spec container; reserve "view" for data-view context. Ensure listing entry shape and endpoint tables reference negation (alias or documented as negation set). |
| **In-code comments / docstrings** | set_vpath or set location for move/rename/trash/restore; "pane" where spec means container. |
| **REFACTOR_ITERATION_PLAN.md** (and any other non-spec docs) | Reference PSEUDO_LOGIC, FUNCTIONAL_SPECIFICATION, FUNCTIONAL_CHEATSHEET, EXPLORER_RULES as source of truth; avoid duplicating spec wording. |

**Single source of truth:** EXPLORER_RULES, FUNCTIONAL_SPECIFICATION, FUNCTIONAL_CHEATSHEET, PSEUDO_LOGIC. Contract and other docs point to these; no spec duplication elsewhere.

**State-based API (../core-documentation/CODING_STANDARDS):** Location is expressed as **state**, not action. The contract uses **PUT `/api/vpath`** (or PUT `/api/location`) to set the entity’s location state; no separate /move, /delete, /rename. Implementation may still expose a legacy `/api/move` route that delegates to the same state update until clients migrate.

**Payload schemata:** All contract payloads will follow the global-superset principle (../core-documentation/CODING_STANDARDS)—subset of a consistent superset, implicit mask per consumer, commutable to messaging. Full application across the API will be litigated as we evolve endpoints.

---

## Deployment (canonical: Electron + Homebrew Cask)

This project is a desktop app that runs inside Electron. We use the **canonical deployment strategy** for desktop apps (../core-documentation/CODING_STANDARDS § Canonical deployment strategy): build the Electron app to a macOS artifact, publish to a stable URL, distribute via Homebrew Cask. No custom or no-deployment justification; DETAILED_DESIGN and BACKLOG § Deployment iteration capture the concrete tasks to implement the pipeline and hello-world MVP.

**Implemented (Deployment iteration):**
- **Electron shell:** `electron/main.js` spawns the Flask backend (`python3 -m file_triage.cli explorer --port 5001`), waits for server ready, opens `BrowserWindow` to `http://127.0.0.1:5001`. On window close, backend process is killed. Dev: `npm start`; PYTHONPATH set to project `src` when not packaged.
- **Build:** `package.json` + `electron-builder`; `npm run build` produces macOS `.dmg` and `.zip`. Python app is copied into app via `extraResources` (src → resources/app/src, pyproject.toml → resources/app) so the packaged app can run `python3 -m file_triage.cli` from the bundle (system Python required unless a bundled Python is added later).
- **CI/CD:** `.github/workflows/build-release.yml` runs on release publish: checkout, setup Python + Node, `pip install -e .`, `npm ci`, `npm run build`, upload `dist/*.dmg` and `dist/*.zip` to the GitHub Release. Release URL is the stable URL for the Cask.
- **Cask:** Separate tap repo `mattian7741/homebrew-tap`. Install with `brew tap mattian7741/tap` then `brew install --cask file-triage`. Update the Cask (version, sha256) in the tap repo when releasing.

**How to verify the hello-world MVP (prerequisite gate)**

You must run through this verification at least once before starting Iteration 2 (or any later development iteration). If the pipeline has already produced a release but you never verified the built app, do this now to satisfy the deployment prerequisite.

1. **Open the release page** — GitHub repo → Releases → select the release that contains the built artifacts (e.g. v0.1.0).
2. **Download the DMG** — Download `File.Triage-<version>-arm64.dmg` (Apple Silicon) or `File.Triage-<version>-x64.dmg` (Intel) from the release assets.
3. **Install and launch** — Open the DMG, drag **File Triage** to Applications (or run it from the DMG). Launch **File Triage**.
4. **Verify behavior** — An Electron window should open and load the Explorer UI. The backend starts automatically and listens on port 5001. You should see the file-explorer interface (panes, folder tree or listing). Closing the window stops the backend.
5. **Install via Homebrew (tap):** `brew tap mattian7741/tap` then `brew install --cask file-triage`. Launch the app and confirm the same behavior. If the Cask fails (wrong sha256), update the Cask in the tap repo (`mattian7741/homebrew-tap`) with the correct `version` and `sha256`, push, and retry.

**Outcome:** Once this verification succeeds, the deployment prerequisite is satisfied. You can start Iteration 2 (single entry-build path) on a new branch from `main` when ready. See BACKLOG § Deployment iteration and § Suggested order.

---

## Iteration 2 — Single entry-build path (BACKLOG Iteration 2)

**Scope:** Consolidate tag resolution, empty computation, and entry building into a single path. All listing, tagged, and tag-search routes use it. Inheritance remains parent-chain (unchanged this iteration).

**Artifacts to touch:**

| Area | Action |
|------|--------|
| **listing_helpers.py** | Add `resolve_tags(meta_accessor, path_str, scope_for_rules)` → (tags, inherited, nulls). Extend `build_listing_entry_from_meta` to accept `path_obj` and `scope_for_vpath_children`, compute `empty` internally (remove `empty` param). Extend `compute_empty` to handle non-existent paths. |
| **app.py** | All `build_listing_entry_from_meta` call sites pass `path_obj` and `scope_for_vpath_children` where applicable; remove inline `empty = size == 0` and duplicate `compute_empty` patterns. Routes become thin: gather path info → call single build path → append. |
| **tests/** | Add tests for `resolve_tags`, `compute_empty`, `build_listing_entry_from_meta` (and domain `build_listing_entry`). |

**Single path flow:** `resolve_tags` → `compute_empty` (when path_obj given) → `build_listing_entry`. `build_listing_entry_from_meta` orchestrates; routes only call it.

---

## (Further sections by topology/feature as iterations are designed)
