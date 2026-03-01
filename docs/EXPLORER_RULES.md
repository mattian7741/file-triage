# File Triage Explorer — Rules (Mechanics)

This document states the **rules** that govern behavior: tags, path/vpath, rename, move, search, scopes, visibility, empty, and scope-mode changes. It is intended to be corrected and refined before implementation. Terms are used consistently; where a rule is ambiguous or wrong, correct it here first.

---

## 1. Terminology

- **path** — Canonical filesystem path of an item. Never changed by the app; read-only from disk. Used only for tracking original state.
- **vpath** — Optional virtual path (metadata). When set, the item is "moved", "trashed", or "renamed"; it appears under the vpath hierarchy (blue), not at its path.
- **effective path** — For display, sorting, and "where it lives": `vpath if set, else path`.
- **FS** — Folder scope: a cross section of the data view along the current level in a hierarchy.
- **TS** — Tag scope: a cross section along a common tag (items that have that tag in their effective tag set).
- **SRS** — Search results scope: a cross section along matched criteria (results of a search). Results of any kind of search; currently two tag-based search types (matches, contains); more search types will be added.
- **Panes** — UI containers. FS, TS, and SRS are concepts independent of which physical pane they appear in. In the current implementation, volume selection (VOLUMES), tag selection (TAGS), and search (SEARCH) are bound to the main left pane—as a necessity for now, not a design requirement.
- **Scope tag** — In TS, the tag that defines the scope (the selected tag). In SRS, the tag used in the search (no "scope tag" for add/remove; search is read-only for "into").

---

## 2. Tags

### 2.1 Tag types (row-level)

- **Hard tag (black)** — Explicitly attached to the path by the user. Item "is tagged with" this tag.
- **Soft tag (grey)** — Tag derived at runtime: (a) inheritance — if a parent has the tag (hard or soft), the child has that tag as soft; (b) tagging rules — regex/pattern on the path maps to a tag. Rules define an explicit pattern that should be tagged with a specific tag. Item "is tagged with" this tag (derived).
- **Negation tag (red)** — Explicit "is not tagged with" this tag. Removes that tag from the effective set. User does not add negation tags independently of hard/soft; they are one state in the tag cycle (see below).
- **Absent** — Item does not have this tag (not hard, not soft, not negation). For display: "no tag X."

### 2.2 Four mutually exclusive states per tag name

For a given tag name, an item is in exactly one state: **soft**, **hard**, **negation**, or **absent**.

- **Soft** and **absent**: initial states—item either has soft tag X (from inheritance/rules) or has no tag X.
- **User cycle** (no separate "x" to remove): each click advances one step.
  - From **soft** or **absent**: click (or + and type tag) → **hard**.
  - From **hard**: click → **negation**.
  - From **negation**: click → back to **soft** or **absent** (depending on ancestors and rules).
- Simplified: initial state = soft tag X or no tag X, and + to add a new tag. Clicking the soft tag or using + and typing the tag creates a hard tag. Click again → negation. Click again → soft/absent.

### 2.3 Effective tag set

- **Effective tags = (Hard ∪ Soft) ∖ Negation**
- (Negation removes that tag from the set; absent means the tag was never in the set.)
- Used for: visibility (hidden-tag filter), tag scope membership, search matching, display of pills.

---

## 3. Path and vpath

- **path** = canonical path on disk; read-only; used only for tracking original state. When vpath is set, path is shown in red/strikethrough; when vpath is unset, path is shown in black.
- **vpath** = where the item appears (blue). Any mutation to an item's location or name is a change to **vpath** only. No separate rules for "rename" vs "move"—both set vpath.
- **effective path** = vpath if set, else path. Used for display, sorting, and move target.

### 3.1 Invariants

- Every item has exactly one **path** (physical). It may have zero or one **vpath** (metadata).
- **Move** = set vpath to a new value (target folder’s effective path + item name). Path on disk is unchanged.
- **Restore** = clear vpath (set to empty). Item then appears at its path again.
- **Trash** = set vpath to a special prefix (e.g. `__VTRASH/…`). Restore clears it as above.

### 3.2 Effective path

- **Effective path = vpath if vpath is set, else path.**
- Used for: which folder the item appears under, sort order, display name in that folder, and **the target of a move** (see Move rules).

### 3.3 Move API

- Move is always expressed as **(path, vpath)**:
  - **path** = the item’s canonical path on disk (the row’s `path`). Never use the item’s current vpath as the “path” in the move request.
  - **vpath** = the new virtual path (e.g. target folder’s effective path + "/" + item name). Empty string means “restore” (clear vpath).

### 3.4 Drop target for move

- When the user drops on a **folder row**, the move target is that row’s effective path. **New vpath for the moved item** = target effective path + "/" + **item name** (display name / basename of the item being moved).
- When the **dropped item** has a vpath (blue row): the move request still uses that item’s **path** (not vpath) as the first argument, and the new vpath as above.

---

## 4. Rename

- Rename = set the item's **vpath** to **(parent effective path) + "/" + (new name)**. Path on disk is unchanged. No separate rules—same as any vpath mutation.
- In **TS** or **SRS**: after setting vpath, if the row no longer matches the scope criteria, remove it from the view.

---

## 5. Move

- Move = set the item's **vpath** to the target (target effective path + "/" + item name). Path unchanged. No tag change except in scope edge cases below.

**Edge cases (TS and SRS):**

- **TS — Move into TS**: Add the scope tag (hard) to the item. Do not change path or vpath.
- **TS — Move out of TS**: Set vpath to the target and remove the scope tag from the item.
- **TS — Rename in TS**: Set vpath; if the row no longer matches the scope (effective tag set), remove it from the view.

- **SRS — Move into SRS**: Undefined / no action (search is read-only for "into").
- **SRS — Move out of SRS**: Set vpath to the target. No tag change.
- **SRS — Rename in SRS**: Set vpath; if the row no longer matches the search criteria, remove it from the view.

### 5.1 Move in FS (folder to folder)

- **Source**: item identified by path (and optionally current vpath for display).
- **Target**: folder row or dropzone; target effective path = that folder’s vpath if set, else path.
- **Action**: Set item’s vpath to `target_effective_path + "/" + item_name`. Path unchanged.
- **Tag**: No tag change.

### 5.2 Move into TS (drop on left dropzone when left pane is in TS)

- **Action**: Add the **scope tag** as a **hard tag** to the dropped item’s path. **Do not** change the item’s path or vpath.
- **Intent**: “This item is now in this tag scope” = it has the tag.

### 5.3 Move out of TS (drag from left pane when in TS; drop on folder or right dropzone)

- **Intent**: User is moving the item to another location **and** expressing that it should no longer have the scope tag.
- **Actions** (both must happen):
  1. **Move**: Set the item’s vpath to the drop target (same rule as 5.1: target effective path + "/" + item name). Use the item’s **path** in the move API, and the computed new vpath. Path on disk unchanged.
  2. **Remove scope tag**: Remove the TS scope tag (current tag) from that item’s path (hard tag or negation, as applicable — typically remove hard tag). This must happen **whenever** the move is “out of TS,” regardless of whether the new vpath is the same as the item’s current location (e.g. “move back to original” with vpath cleared) or a new location.
- **Rule**: Moving an item out of TS **always** removes the scope tag from that item. The move (vpath update) is independent: it can be “to same place” (e.g. vpath → same or vpath → empty) or to a new place; in all cases the scope tag is removed.

### 5.4 Move in SRS (not supported)

- Drop onto the search-results pane does nothing (read-only).

### 5.5 Move out of SRS (drag from left when in SRS; drop on folder or right dropzone)

- **Action**: Same as move in FS: set item’s vpath to target. No tag change (search has no “scope tag” to add/remove).
- Path on disk unchanged.

### 5.6 Move and source item has vpath (blue)

- The **move API** must receive the item’s **path** (canonical path on disk), not its current vpath.
- The **new vpath** must be computed from the **drop target** only: target folder’s effective path + "/" + **item name**. The item name should be the basename of the item’s path (or the name part of its current effective path — to be specified consistently so that “blue” items don’t end up at root). Rule to lock in: **item name = basename of path** (so that move target is always `target_effective_path + "/" + basename(path)`).

---

## 6. Trash and Restore

- **Trash**: Set item’s vpath to `__VTRASH/` + (effective path of item, or path if vpath empty). Path unchanged.
- **Restore**: Clear vpath (set to empty). Path unchanged.
- Trash/restore do **not** change scope mode; they only refresh the current view.

---

## 7. Search (SRS)

- **Tag search** under a scope path: **matches** = paths with tag in effective set; **contains** = folders that contain (recursively) at least one such path.
- Data for search is **not** filtered by hidden tags or “show trashed” at fetch time; visibility is applied at render time only.
- Move into SRS: not supported. Move out of SRS: same as move in FS (set vpath to target; no tag change).

---

## 8. Scopes (FS, TS, SRS)

### 8.1 Which pane drives which

- **Left pane**: Driven by volume selection (tree), tag selection (TAGS), or search (SEARCH). So left can be FS, TS, or SRS.
- **Right pane**: Always FS (hierarchy only). Not driven by tag or search.

### 8.2 Scope mode changes (when does FS/TS/SRS change?)

- **Only** these actions change scope mode:
  - **To TS**: User clicks a tag in the tag list (left pane becomes tag scope).
  - **To SRS**: User runs a search (left pane becomes search results scope).
  - **To FS**: User selects a volume/folder in the tree, or uses Up to “go up” from TS/SRS (see below), or clears tag/search in a way that returns to folder view.
- **Up button** in TS or SRS: Treat current scope as a “virtual child” of the current path; going “up” exits TS/SRS and shows FS at that path. (Only the **left** pane’s Up does this; the right pane’s Up only moves the right pane up in the hierarchy.)
- **No** scope mode change: move, rename, trash, restore, add/remove tag on a row, selection, preview, keyboard navigation. These only refresh or update content in the current scope.

---

## 9. Empty (files and folders)

### 9.1 File

- **Empty** = size 0 (bytes). Display-only; no hierarchy.

### 9.2 Folder (model-level)

- A folder is **non-empty in the model** if it has at least one direct child:
  - By **path**: a child path on disk that does not have a vpath (so it still “lives” at that path).
  - By **vpath**: a child whose vpath has this folder’s (path or vpath) as parent.
- Items that have a vpath are **not** counted as children of their physical path’s parent for “empty” and “has children” in the model.

### 9.3 Folder (view-level / “empty at render time”)

- A folder can be considered **empty in the view** when, after applying visibility (hidden tags, show trashed), it has **no visible children** (and recursively those children would be empty). So: if “show trashed” is off and all children are trashed (or hidden), the folder appears empty in the view even if the model has children.
- “Empty” for display can be defined as: model-level empty **or** (after visibility filter, the folder has zero visible direct children). Exact rule can be refined (e.g. recursive) in this doc.

---

## 10. Visibility

### 10.1 When visibility is applied

- Visibility is applied **only at render time** (view layer). The **model** (data from API) includes all items; hidden-tag, show-trashed, and show-negation-tag filters are applied when building the list to display. So toggling “hidden” or “show trashed” or “show negation tags” does not require a new fetch; the same data is re-filtered.

### 10.2 Hidden tags

- User can mark tags as **hidden**. An item is **hidden** in all views (FS, TS, SRS) if its **effective tag set** intersects the hidden-tag set.
- If an item has a **negation** tag T, T is not in the effective set, so hiding T does **not** hide that item.
- Hidden-tag visibility is applied uniformly everywhere.

### 10.3 Show trashed

- When **off**: Items with a non-empty vpath are hidden from their **path**-based listing (original folder). They appear only under their vpath parent (“moved here”). Optionally, “original” placeholders are hidden.
- When **on**: Moved/trashed items can be shown in both places (or with “original” markers), as defined.

### 10.4 Show negation tags (TS and SRS)

- When **on**: In TS and SRS, show items that have the scope tag (or search tag) as **negation** (explicitly opted out).
- When **off**: In TS and SRS, hide those negation-tagged items. Visibility only; no change to model or scope.

---

## 11. Scope mode and navigation (summary)

- **Left pane**: FS ↔ TS via tag list; FS ↔ SRS via search; TS/SRS → FS via Up (or explicit “back”).
- **Right pane**: FS only; navigation by tree, breadcrumb, double-click, Up. No tag/search.
- **Move/rename/trash/restore/tag actions**: Do **not** change scope mode; only refresh content. Exception: “Up” in TS/SRS on the left exits scope mode (by design).

---

## 12. Move-out-of-TS and vpath (bugs to fix)

- **Rule (intent)**: When the user moves an item **out of** TS (drops it on a folder or the right dropzone), **always** remove the scope tag from that item, and **always** perform the move (set vpath to the drop target). Both apply whether the drop target is the item’s “current” location (e.g. restore to path = clear vpath) or a new location.
- **Move API**: Always use the item’s **path** (not its vpath) as the first argument. Always compute the new vpath as **target folder’s effective path + "/" + basename(item.path)** (or an agreed single rule so that items with an existing vpath don’t get an incorrect target and end up at root).
- **Target folder’s effective path**: When dropping on a row, use that row’s **vpath if set, else path**. When dropping on a dropzone, use the pane’s current path (or vpath of the folder being viewed, if applicable).

---

## Document control

- This is a **rules** document. Refine and correct it first; then implementation can be aligned.
- When rules conflict or are unclear, resolve them here before changing code.
- Terms (**path**, **vpath**, **effective path**, **effective tag set**, **FS**, **TS**, **SRS**, **scope tag**, **move out of TS**) are as defined above.
