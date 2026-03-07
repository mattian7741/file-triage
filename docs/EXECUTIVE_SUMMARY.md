# Executive Summary

One-page overview of the File Triage product for stakeholders, new contributors, and decision-makers. For detailed behavior see FUNCTIONAL_SPECIFICATION.md and FUNCTIONAL_CHEATSHEET.md; for development flow see ../core-documentation/DEVELOPMENT_GUIDE.md and BACKLOG.md.

---

## Product

**File Triage** is a desktop application for analyzing and organizing chaotic file collections across disks. Users browse and manage files in an **Explorer** UI that supports tagging, virtual paths (intended locations), and rules. The Explorer runs in the browser; the same codebase is wrapped in **Electron** for a standalone desktop app. The app never modifies on-disk paths directly—all move, rename, trash, and restore actions update a **virtual path** (vpath) overlay; the **effective path** used everywhere is `vpath ?? path`.

---

## Key capabilities

- **Path and vpath** — Original path (read-only) plus optional vpath override. Move, rename, trash, and restore are a single operation: set or clear vpath. Effective path = vpath ?? path for all logic and display.
- **Tags** — Four states per tag: soft (inherited or from rules), hard (user-set), negation (user-set “does not have”), absent. Effective tags = (Hard ∪ Soft) ∖ Negation. Cycle control: soft/absent → hard → negation → soft/absent.
- **Scopes** — **FS** (folder tree), **TS** (by tag; tag matches or containers), **SRS** (by search, e.g. regex on path). Move/rename semantics depend on scope (e.g. move-in in tag-containers mode is no-op).
- **Visibility** — Render-time filtering: hidden tags, show trashed, show negation tags (TS/SRS). Backend returns full data; filters applied when building the list.
- **Deployment** — Electron app builds to macOS `.dmg`/`.zip`; published to GitHub Releases; distributable via Homebrew Cask. CI/CD pipeline runs on release.

---

## Current status

- **Iteration 1 (docs and API naming)** and **Deployment iteration** are complete: terminology aligned with spec (effective path, set_vpath, negation, pane, scope); Electron shell, build, GitHub Actions release workflow, and Cask in place; hello-world MVP verified.
- **Next:** Spec-alignment iterations 2–10 in BACKLOG (single entry-build path, empty semantics, contains-mode no-op, parent-only tag inheritance, negation naming, regex search, testing, optional toggle placement and module organization). Development is unblocked for Iteration 2+.

---

## Roadmap

See **BACKLOG.md** § Suggested order and dependencies. Minimum path to spec alignment: Iterations 2 → 3 → 4 → 5 → 6, then 9 (testing).
