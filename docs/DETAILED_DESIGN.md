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

---

## (Further sections by topology/feature as iterations are designed)
