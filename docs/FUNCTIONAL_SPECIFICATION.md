# File Triage Explorer — Functional Specification

This document describes the intended behavior of the File Triage Explorer application from a user and system-behavior perspective only. It does not describe implementation, architecture, or technology choices.

---

## 1. Purpose and Scope

The Explorer is a file-management interface that allows users to:

- Navigate a configurable set of filesystem roots (e.g. volumes, drives).
- Attach **tags** to paths and use tags to filter, search, and organize content.
- **Move** items to virtual locations without changing their physical path on disk, and optionally **trash** them to a virtual trash area.
- View content in three kinds of **scopes**: folder hierarchy, tag-based list, and search results.

All behavior is defined in terms of **path** (original location on disk), **vpath** (override / intended future path), **effective path** (the only path used for all app actions and interactions), **tags** (labels with inheritance and negation rules), and **visibility** (which items appear where and when).

---

## 2. Path and Virtual Path (vpath)

### 2.1 Definitions

- **Path**  
  The canonical filesystem path of a file or directory. Read-only; never changed by the app. The **original** location on disk.

- **Virtual path (vpath)**  
  An optional override to path. User-assigned. When set, it represents the “intended future path.” When null, the item is considered to live at its path. At most one vpath per path; stored as metadata; filesystem is not modified.

- **Effective path**  
  The **only** path used by the application for all actions and interactions. It is the blended resultant: **effective path = vpath if vpath is set, else path.** Listing, sorting, hierarchy parent, move target, and all other logic use effective path only. **path** and **vpath** are used **only for rendering**: path is shown in black when vpath is null, in red/strikethrough when vpath is set; vpath is shown in blue. The item appears in both locations (at path and at vpath when set); the pane renders them differently.

### 2.2 Path–vpath relationship and listing

- When listing the contents of a folder by **path**, direct children are: items whose path is a direct child of that path, plus items whose vpath is a direct child of that path (“moved here”).
- When listing by **vpath**, direct children are items whose vpath is a direct child of that vpath. Physical path is irrelevant for that listing.
- **Empty directory**: No direct children under the rule: by vpath always; by path only when the item has no vpath or “show trashed” is on. So when “show trashed” is off, items with a vpath do not count as children of their path parent.
- **Invariant:** If vpath and path ever match, vpath must be nullified: set vpath to null when vpath equals path.

### 2.3 Move, rename, delete (trash), and restore — unified

All four actions are the same operation: set vpath (or clear it). Path on disk is never modified. Only the interaction and the resulting vpath differ:

| Action | Interaction | Resulting vpath |
|--------|-------------|-----------------|
| **Move** | Drag and drop onto target folder | target effective path + "/" + basename(path) |
| **Rename** | Click + edit text box | parent effective path + "/" + new name |
| **Delete (trash)** | Trash can click or Backspace | special prefix (e.g. `__VTRASH/`) + effective path |
| **Restore** | Restore button or Backspace | null (clear vpath) |

After any of these, apply the invariant: `vpath = (vpath == path) ? null : vpath`. The system always persists **(path, vpath)**; the first argument is the item’s path (disk), never its current vpath. Whether trashed/original items are shown in listings is governed by visibility (see Visibility).

---

## 3. Tagging — Logical Rules

This section defines how tags are associated with paths and how that association is interpreted. No storage or API details are specified.

### 3.1 Tag Sources

Tags can come from three sources:

1. **Hard tags (explicit tags)**  
   Directly attached to a path by the user. User can cycle tag state (soft → hard → negation → soft/absent) per path.

2. **Soft tags (derived)**  
   Tags a path is considered to have, derived at runtime from **parent only** and from rules:
   - **From parent**: If the parent has a tag (hard or soft) in its effective set, the child has that tag as soft. If the parent has a **negation** tag for T, the child has **absent** T (omitted), not negation—inherited negation is absence.
   - **From rules**: Rules map a pattern (e.g. path or name pattern) to a tag. If a path matches a rule, that tag is added to the soft set for that path.

3. **Negation tags**  
   A path can have a **negation** tag for a tag name, meaning “this path explicitly does not have this tag.” It removes that tag from the effective set. Used to opt out of an otherwise soft (inherited or rule) tag.

4. **Absent**  
   The path has no tag (not hard, not soft, not negation). Four states per tag name are mutually exclusive: soft | hard | negation | absent.

### 3.2 Effective Tag Set

For any path, the **effective tag set** is the set of tags used for matching, filtering, search, and display. It is defined as:

- **Effective tags = (Hard ∪ Soft) ∖ Negation**

In other words:

- Include every hard tag for the path.
- Include every soft tag (from parent and from rules) for the path.
- Remove any tag that is negation for this path.

Duplicate tags from multiple sources are treated as one. Order: union hard and soft, then subtract negation. The result is a set.

### 3.3 Semantics of Tag Types

- **Hard tag**: “This path has this tag.” User-set. Removing or changing it is a direct user action (cycle to negation or soft/absent).
- **Soft tag**: “This path is considered to have this tag (derived from parent or rules).” If the same tag is negation for this path, the path does **not** have that tag in the effective set (negation wins).
- **Negation tag**: “This path does not have this tag.” User-set. It only removes that tag from the effective set. Parent’s negation gives child **absent**, not negation.
- **Absent**: Path has no tag for that name.

### 3.4 Rule-Based Inference

- **Rules** are pairs (pattern, tag). A pattern is matched against paths (or path components) in a defined way (e.g. regex or glob). When a path matches a pattern, the corresponding tag is added to the soft set for that path.
- Rule-inferred tags are combined with parent-derived soft tags; the combined set is then subject to negation removal when computing the effective tag set.
- Rules are global (not per-path). The same rule can cause many paths to have the same soft tag.

### 3.5 Tag Scope and Search

- **Tag scope (TS)** shows all paths that have the selected tag in their effective set. TS can offer a “matches” vs “containers” toggle: matches = tagged items; containers = folders that contain (recursively) at least one tagged item. When in containers mode, “move in” (drop) has no effect. Tag search is thus part of TS.
- **Search results scope (SRS)** shows results of other search types (e.g. regex on path matching path and vpath). Move in to SRS is not supported (read-only). Visibility (hidden tags, show trashed, show negation) is applied at render time; result set is model-level.
- Paths that have the scope tag as **negation** can be shown or hidden via a “show negation tags” toggle (TS and SRS). When off, those items are hidden from the listing.

---

## 4. Visibility

Visibility determines whether an item appears in a given listing or view. Visibility is applied after the set of candidates (e.g. folder contents, tag list, or search results) is determined.

### 4.1 Hidden Tags

- The user can mark specific tags as **hidden**. The set of hidden tags is global.
- **Rule**: An item is **hidden** (excluded from all listings and views) if its **effective tag set** has a non-empty intersection with the hidden-tag set.
- **Implications**:
  - If an item has a hard or soft tag T and T is hidden, the item is hidden everywhere (folder scope, tag scope, search scope).
  - If an item has a negation tag T, T is not in the effective set, so hiding T does **not** hide that item (the item does not “have” T).
  - If an item has hard tag XYZ and negation tag ABC, hiding XYZ hides the item; hiding ABC does not.

Hidden-tag visibility is applied consistently in folder listings, tag-scope listings, and search results.

### 4.2 Trashed / Moved Visibility

- Items that have a non-empty vpath (moved or trashed) can be shown or hidden via a **show trashed** (or equivalent) toggle.
- When “show trashed” is off:
  - An item whose vpath is set (moved/trashed) is **hidden** from its **path**-based listing (its original folder). It does not appear as a child of its physical parent.
  - It **is shown** in the listing of the folder that corresponds to its vpath parent (the “moved here” location), so the user can see and restore it.
  - Optionally, “original” placeholders (e.g. “Item X was moved to …”) can be hidden when “show trashed” is off, so that the path-based view shows only current physical contents and moved items only in their vpath location.
- When “show trashed” is on, moved/trashed items can be shown in both path-based and vpath-based listings as defined by the product (e.g. show in both, or show “original” markers).

The exact behavior of “original” vs “moved here” display is a product choice; the invariant is that visibility of moved items is consistent and controlled by the show-trashed setting.

### 4.3 Scope-Specific Visibility

- **Folder scope**: Visibility is determined by path/vpath hierarchy, hidden tags, and trashed/moved rules above. Only items under the selected root(s) and allowed paths are considered.
- **Tag scope**: The list is “all paths that have this tag in their effective set.” Then hidden-tag and (if applicable) trashed rules are applied. No extra scope filter beyond “has the tag” and global visibility.
- **Search scope**: The list is “all paths under scope that match the search (e.g. tag matches/contains).” Same hidden-tag and trashed rules apply.

Allowed paths are defined by **roots**: only paths under the configured roots are listable or searchable. Paths outside roots are out of scope and never appear.

---

## 5. Scopes and panes

The application presents content in three logical scopes. Each scope is shown in a pane; each pane has a consistent set of actions (select, preview, rename, move, tag, trash/restore) where applicable.

### 5.1 Folder Scope (FS)

- The user navigates a hierarchy of folders. The hierarchy can be path-based (directories on disk) or vpath-based (virtual folders created by move).
- Listing shows direct children of the current folder (by path or by vpath as described in Path and vpath).
- **Rename** means set vpath to parent effective path + new name (same as move to same parent with new name).
- **Move** (drag to another folder or drop zone) sets vpath to target effective path + item name. **Trash** sets vpath to the special trash prefix. **Restore** clears vpath. All four (move, rename, trash, restore) share the same vpath semantics; see §2.3.
- Selection, keyboard navigation, and preview do not change the current scope; only explicit navigation (e.g. open folder, “up,” or breadcrumb) changes the folder scope.

### 5.2 Tag Scope (TS)

- The user selects a tag. The pane shows all paths that have that tag in their **effective tag set**, under a chosen root or scope path.
- The pane behaves like a virtual folder: same row actions (select, rename, tag, trash, move) as in folder scope. Selection and keyboard navigation do not change scope.
- **Move out**: Set vpath to target (same as folder scope; see §2.3). Path on disk is unchanged.
- **Move in**: Dropping an item “into” the tag scope means **adding that tag as a hard tag** to the dropped path(s). vpath (and path) of the dropped items do not change.
- Hidden-tag visibility applies: items with any hidden tag are not shown in tag scope.

### 5.3 Search Results Scope (SRS)

- The user runs a search (e.g. regex on path) under a scope path. The pane shows the result set.
- Same row actions as folder and tag scope (select, rename, tag, trash, move out). Selection and keyboard navigation do not change scope.
- **Move out**: Set vpath to target (same as folder scope; see §2.3). Path on disk is unchanged.
- **Move in**: Not supported; dropping onto the search-results pane has no effect.
- Hidden-tag visibility applies.

### 5.4 Scope Consistency

- In any scope, **rename**, **trash**, and **restore** follow the unified vpath semantics (§2.3). **Move** does as well, with scope-specific additions (tag add/remove or no-op) as in §6.4.
- In any scope, **selection** and **preview** do not change the current scope; only explicit navigation or scope change (e.g. picking a different tag or running a new search) does.

---

## 6. Precedence and Layered Rules

This section summarizes how the various rules combine to produce the final result (what the user sees and what actions do).

### 6.1 Effective Tag Set (Tag Layer)

1. **Gather hard tags** for the path.
2. **Gather soft tags**: from parent (effective tags of parent) and from rules (pattern match). Parent’s negation for a tag gives child **absent** for that tag, not negation.
3. **Apply negation**: Effective = (Hard ∪ Soft) ∖ Negation.

This order is fixed. Negation always removes from the combined hard+soft set. Hard and soft are unioned; only negation removes.

### 6.2 Visibility (Filter Layer)

After a candidate set of entries is determined (e.g. folder contents, tag list, or search results):

1. **Roots / allowed paths**: Exclude any path not under the configured roots. This is applied first (entries outside roots are never considered).
2. **Hidden tags**: Exclude any entry whose effective tag set intersects the hidden-tag set. This is applied to all panes (folder, tag, search) uniformly.
3. **Trashed / moved**: Depending on the “show trashed” setting, exclude or include entries that have a vpath from path-based listings, and show or hide “original” markers. Include “moved here” entries in the vpath-parent listing as defined in Path and vpath.

Order: roots first, then hidden tags, then trashed/moved rules. No conflict between hidden-tag and trashed rules: one applies to tag set, the other to vpath and display preference.

### 6.3 Effective path (path layer)

- **effective_path = vpath ?? path** (vpath if set, else path). This is the only path used for all actions and interactions. path and vpath are used only for rendering (black / red-strikeout / blue as defined in §2.1). After any vpath update, apply: **vpath = (vpath == path) ? null : vpath**.

### 6.4 Action semantics by scope

Move, rename, trash, and restore all set (or clear) vpath as in §2.3. Scope adds only:

- **Folder scope**: No extra rule. All four actions use unified vpath semantics.
- **Tag scope**: Move **out** = set vpath to target **and** remove scope tag from item. Move **in** (drop onto tag scope) = add scope tag as hard tag; do not change vpath. When tag scope is in “containers” mode (showing folders that contain the tag), move in = no-op.
- **Search scope**: Move **out** = set vpath to target. Move **in** = no-op (read-only). Rename/trash/restore = unified vpath semantics.

Path on disk is never modified; only metadata (vpath, tags) is updated.

---

## 7. Other Behaviors (Summary)

- **Preview**: Display of file content (or placeholder for directories) for the selected item. Uses path for reading; selection does not change scope.
- **Breadcrumb / path display**: In folder scope, shows the current path or vpath. In tag scope, shows a path-like representation of the scope plus the tag (e.g. scope path and tag). In search scope, shows scope path plus search criteria. This is for user orientation only; it does not change the precedence rules above.
- **Empty directory**: No direct children (by path or by vpath) under the rules below; recursive. An item is a **child of a parent** by vpath always; by path only when the item has no vpath or “show trashed” is on. So when “show trashed” is off, items with a vpath do not count as children of their path parent. **File empty**: 0 bytes, or the file is deleted (has vpath) and “show trashed” is off.
- **Rules**: Stored as (pattern, tag). Matching contributes the tag to the soft set. Rule management is orthogonal to the effective-tag and visibility logic.

---

## 8. Document Control

- This specification describes **functional behavior** only. It does not specify APIs, data structures, or implementation strategy.
- Terms such as “path,” “vpath,” “effective path,” “effective tag set,” “soft,” “negation,” “hidden tags,” “scope,” and “visibility” are used consistently as defined in this document.
- When in doubt, the precedence order in Section 6 is authoritative for how multiple rules combine.
