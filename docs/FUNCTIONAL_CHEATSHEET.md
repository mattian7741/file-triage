# File Triage Explorer — Functional Cheatsheet

Minimal logical definition of how the application works. Lean reference only.

---

## Path and vpath

- **path** — Original path on disk. Read-only. Never changed by the app.
- **vpath** — Override to path; optional. “Intended future path.” When set, path is overridden for all app logic.
- **effective path** — The only path used in the app for all actions and interactions. Blended resultant: `vpath ?? path`. path and vpath are used **only for rendering**: black (path when vpath null), red-strikethrough (path when vpath not null), blue (vpath). The item appears in both path and vpath (if set) locations; rendering differs by view.

**Move, rename, delete (trash), and restore are the same operation:** set vpath (or clear it). Only the interaction differs:

| Interaction | Trigger | Resulting vpath |
|-------------|---------|-----------------|
| **Move** | Drag and drop onto target | target_effective_path + "/" + basename(path) |
| **Rename** | Click + edit text box | parent_effective_path + "/" + new_name |
| **Delete (trash)** | Trash click or Backspace | `__VTRASH/` + effective_path |
| **Restore** | Restore click or Backspace | null (clear vpath) |

**Invariant:** If vpath and path ever match, vpath must be nullified: `vpath = (vpath == path) ? null : vpath`. Path on disk is never modified. Move API always `(path, vpath)`; first argument is the item’s **path** (disk), not current vpath.

---

## Tags

**Four mutually exclusive states per tag name:** soft | hard | negation | absent.

- **Effective tags** = (Hard ∪ Soft) ∖ Negation
- **Soft** — Derived: (a) from **parent only** (parent has tag → child has soft); parent’s negation → child absent, not negation. (b) Rules (pattern → tag).
- **Hard** — User-set. “Has this tag.”
- **Negation** — User-set. “Does not have this tag.” Removes from effective set.
- **Absent** — No tag. Not in set.
- **Cycle** (one control, no separate remove): soft/absent → click → hard → click → negation → click → soft/absent. “+” + type = add hard.

---

## Scopes (data cross-sections)

- **FS** — Cut by hierarchy level (folder tree).
- **TS** — Cut by tag (items that have that tag in effective set). Tag matches/containers live in TS; “containers” mode → move in = no-op.
- **SRS** — Cut by search (e.g. regex on path). Other search types; not tag search. Move in = no-op.

Panes are UI containers. Scope type is independent of which pane shows it.

---

## Move / rename by scope

| Scope | Move in | Move out | Rename |
|-------|---------|----------|--------|
| **FS** | Set vpath to target | Set vpath to target | Set vpath |
| **TS** | Add scope tag (hard); no vpath change | Set vpath to target **and** remove scope tag | Set vpath; remove from pane if no longer matches |
| **SRS** | No action (read-only) | Set vpath to target | Set vpath; remove from pane if no longer matches |

Rename: set vpath. In TS/SRS only, if the row no longer matches scope after vpath change, remove it from the pane.

When TS is in “containers” mode (showing folders that contain the tag), move in = no-op.

---

## Visibility (render-time only)

- **Hidden tags** — Hide item if effective tag set ∩ hidden-tag set ≠ ∅. Negation tag is not in effective set, so hiding that tag doesn’t hide the item.
- **Show trashed** — When off: hide vpath items from path-based listing; show only under vpath parent. When on: show in both (or with markers).
- **Show negation tags** (TS/SRS) — When on: show items with scope/search tag as negation. When off: hide them. Pane/local toggle.

Model (API) returns full data; filters applied when building the list.

---

## Scope mode changes

**Only these change scope:** Select tag → TS. Run search → SRS. Select volume/folder, Up, or clear tag/search → FS.

Move, rename, trash, restore, tag, selection, preview do **not** change scope; they only refresh content. Up in TS/SRS exits back to FS.

---

## Other

- **Empty folder** — No direct children by path or vpath under the rule: by vpath always; by path only when item has no vpath or “show trashed” is on. Items with vpath do not count as children of path parent when “show trashed” is off.
- **File empty** — 0 bytes, or deleted (has vpath) and “show trashed” is off.
- **Search** — TS: tag matches/containers. SRS: e.g. regex path. Visibility applied at render time.
- **Scope tag** — In TS, the selected tag. In SRS, search is read-only for move in.
