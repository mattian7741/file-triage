# Detailed Design

Technical approach and implementation strategy for iterations. Driven by BACKLOG (requirements), CODING_STANDARDS (constraints), and the existing codebase. Written just-in-time before implementation; add as you go.

**Scope:** App-specific strategy only. Generally applicable strategy belongs in CODING_STANDARDS (see DEVELOPMENT_GUIDE § Where to capture strategy decisions). Do not repeat or relitigate coding standards here.

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

**State-based API (CODING_STANDARDS):** Location is expressed as **state**, not action. The contract uses **PUT `/api/vpath`** (or PUT `/api/location`) to set the entity’s location state; no separate /move, /delete, /rename. Implementation may still expose a legacy `/api/move` route that delegates to the same state update until clients migrate.

**Payload schemata:** All contract payloads will follow the global-superset principle (CODING_STANDARDS)—subset of a consistent superset, implicit mask per consumer, commutable to messaging. Full application across the API will be litigated as we evolve endpoints.

---

## Deployment (canonical: Electron + Homebrew Cask)

This project is a desktop app that runs inside Electron. We use the **canonical deployment strategy** for desktop apps (CODING_STANDARDS § Canonical deployment strategy): build the Electron app to a macOS artifact, publish to a stable URL, distribute via Homebrew Cask. No custom or no-deployment justification; DETAILED_DESIGN and BACKLOG § Deployment iteration capture the concrete tasks to implement the pipeline and hello-world MVP.

**Implemented (Deployment iteration):**
- **Electron shell:** `electron/main.js` spawns the Flask backend (`python3 -m file_triage.cli explorer --port 5001`), waits for server ready, opens `BrowserWindow` to `http://127.0.0.1:5001`. On window close, backend process is killed. Dev: `npm start`; PYTHONPATH set to project `src` when not packaged.
- **Build:** `package.json` + `electron-builder`; `npm run build` produces macOS `.dmg` and `.zip`. Python app is copied into app via `extraResources` (src → resources/app/src, pyproject.toml → resources/app) so the packaged app can run `python3 -m file_triage.cli` from the bundle (system Python required unless a bundled Python is added later).
- **CI/CD:** `.github/workflows/build-release.yml` runs on release publish: checkout, setup Python + Node, `pip install -e .`, `npm ci`, `npm run build`, upload `dist/*.dmg` and `dist/*.zip` to the GitHub Release. Release URL is the stable URL for the Cask.
- **Cask:** To be added (own tap or homebrew-cask); Cask points at the release asset URL. See BACKLOG § Deployment iteration.

---

## (Further sections by topology/feature as iterations are designed)
