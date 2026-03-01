# PSEUDO_LOGIC — Logical specification grammar

// Grammar: = ? : ?? case | end → ∧ ∨ ¬ ∈ ∖ ∪ ∃ ∀.
// Layering: (1) Governing principles (2) Functional controls (3) UI discipline + layout & panes (4) Bind to layout.

// UI discipline — All actions, interactions, and state changes are defined and executed at the logical/functional level, isolated from UI concerns. The UI only binds to logical controls and displays their state; it does not define behavior. A toggle that controls a scope must be bundled with that scope's pane (local) unless it applies to any scope (global). Both local and global are valid iff logically valid.

---

# PART I — Governing principles (files and folders)

## 1. Location: path, vpath, effective path

path(item)     = read_only(item.path)           // original disk
vpath(item)    = item.vpath                      // override; intended future path
effective_path(item) = item.vpath ?? item.path   // only path used for all app logic

// path and vpath used only for rendering (black / red_strikethrough / blue)
render_path(item) = case
  | item.vpath == null → item.path black
  | item.vpath != null → item.path red_strikethrough; item.vpath blue
  end

---

## 2. Set vpath (single mutation primitive)

// All location mutation reduces to set_vpath. Normalize incorporated; apply after every assign.
set_vpath(item, vpath) =
  item.vpath = (vpath == item.path) ? null : vpath;   // normalize inline
  write(item.path, item.vpath)                         // persist; first arg always item.path

// Intended vpath by interaction (before set_vpath)
intended_vpath(item, action) = case action
  | move   → target.effective_path + "/" + basename(item.path)
  | rename → parent.effective_path + "/" + new_name
  | delete → TRASH_PREFIX + effective_path(item)
  | restore → null
  end

mutate_location(item, action) = set_vpath(item, intended_vpath(item, action))

---

## 3. Tags — state, effective set, inheritance

tag_state(item, tag) ∈ { soft, hard, negation, absent }
effective_tags(item) = (hard(item) ∪ soft(item)) ∖ negation(item)

// Soft from parent ONLY ∪ rules. Parent negation → child absent (not negation).
soft(item) = effective_tags(parent(item)) ∪ rule_matched_tags(item)

next_tag_state(item, tag) = case tag_state(item, tag)
  | soft, absent → hard
  | hard         → negation
  | negation     → soft | absent
  end

---

## 4. Scope (data cross-section) and membership

// Scope = logical concept; independent of where it appears on screen.
scope ∈ { FS, TS, SRS }

in_scope(item, scope) = case scope
  | FS  → is_direct_child(item, current_folder)   // by effective_path
  | TS  → scope_tag ∈ effective_tags(item)
  | SRS → search_matches(item, query)
  end

---

## 5. Search (result set = model; display filtered by view opts later)

search_matches(item, query) = case query.search_type
  | regex_path → regex_match(query.pattern, item.path) ∨ regex_match(query.pattern, item.vpath ?? item.path)
  | _ → false
  end
// Path matches with vpath != null always in result set; show_trashed controls display only.

---

## 6. Empty (depends on control state)

is_child_by_vpath(parent, item) = parent_of(item.vpath) == parent
is_child_by_path(parent, item)  = parent_of(item.path) == parent ∧ (item.vpath == null ∨ ctrl.show_trashed)

folder_empty(parent, ctrl) = ¬ ∃ item : is_child_by_path(parent, item) ∨ is_child_by_vpath(parent, item)
file_empty(item, ctrl)    = (item.size == 0) ∨ (item.vpath != null ∧ ¬ ctrl.show_trashed)

---

# PART II — Logical controls (function only, no layout)

// Controls defined by function. Scope-local = tied to one scope, must live in that scope's pane. Global = applies to any scope, can live in shared UI.

## 7. Control catalog

// Scope selector — which data cross-section the pane shows. Bound to e.g. volume tree, tag list, search box.
scope_selector ∈ { FS, TS, SRS }

// Toggles — global (apply to any scope) vs local (scope-specific, bundled with that pane)
ctrl.show_trashed      : bool   // global
ctrl.hidden_tag_set    : set    // global — tags in set hide item if effective_tags(item) ∩ set ≠ ∅
ctrl.show_negation     : bool   // local(TS), local(SRS) — when on show items with scope_tag = negation
ctrl.include_soft_tags : bool   // local(TS) — when on stream soft-tag matches (hard tags loaded first)
ctrl.contains_mode     : bool   // local(TS) — when on show containers of tag (move_in → no_op)

// Search (when scope = SRS) — local(SRS)
ctrl.search_type      : regex_path | ...
ctrl.search_pattern   : string

// Buttons (impulse)
action ∈ { move, rename, delete, restore }

// Pane = logical container: one scope_selector, one listing, receives actions. Scope-local toggles live in this pane; global toggles may live elsewhere.

// Placement rule: control is valid in a pane iff (control is global) ∨ (control is local(scope) ∧ pane.scope = scope).

---

## 8. How controls govern visibility

hidden(item, ctrl) = (effective_tags(item) ∩ ctrl.hidden_tag_set) ≠ ∅
scope_visible_negation(item, scope, ctrl) = scope ∉ {TS, SRS} ∨ ctrl.show_negation ∨ tag_state(item, scope_tag) ≠ negation

visible_in_listing(item, scope, ctrl) =
  ¬ hidden(item, ctrl)
  ∧ (ctrl.show_trashed ∨ item.vpath == null ∨ show_under_vpath_parent(ctrl, item))
  ∧ scope_visible_negation(item, scope, ctrl)

---

## 9. How controls govern mutation (scope + action)

// Non-navigation actions keep pane state (e.g. scroll) unchanged.
scope_side_effect(item, scope, action, ctrl) = case (scope, action)
  | (_, move_in) when ctrl.contains_mode → no_op
  | (TS, move_in)   → add_hard_tag(item, scope_tag)
  | (TS, move_out)  → mutate_location(item, move); remove_scope_tag(item)
  | (SRS, move_in)  → no_op
  | (SRS, move_out) → mutate_location(item, move)
  | (_, rename)    → mutate_location(item, rename); if TS|SRS ∧ ¬in_scope(item, scope) → remove_from_pane(item)
  | (_, delete)    → mutate_location(item, delete)
  | (_, restore)   → mutate_location(item, restore)
  | (FS, move_in), (FS, move_out) → mutate_location(item, move)
  end

---

## 10. How controls govern scope transition

// Only these control events change scope; all other actions refresh content only.
scope_transition(control_event) = case control_event
  | scope_selector → FS | TS | SRS   // e.g. select volume → FS; select tag → TS; run search → SRS
  | up, clear_scope → FS
  | move, rename, delete, restore, tag_click, select, preview → no_change
  end

---

# PART III — UI discipline: layouts and panes

// All behavior is defined in Part I–II. UI only binds to logical controls and displays state. Layout and panes organize where controls appear.

// Layout — Rules by which panes are arranged (e.g. snapping, tiling, floating, docking). Layout constrains position/size of panes; it does not define contents. (Industry: same; sometimes "layout manager" or "window management.")

// Pane — A control that is a portable container: positioned by the layout, isolates the layout from its internals. Layout operates on panes; panes host other controls and display one scope (FS | TS | SRS). Scope-local toggles are bundled inside the pane whose scope they affect; global toggles may live in a shared area (toolbar, app bar). (Industry: "panel" or "pane" common; here "pane" = container.)

// Control — Active or passive element inside a pane or layout. (Industry: same; some use "widget" or "component.")

// Scope — Domain concept: data perspective (nodes sharing attributes). Scope is what a pane displays; not a UI element. Parameters: e.g. containing path, matches_tag, contains_tag, search criteria.

// Toggle — Boolean control (step function). Implementation: checkbox, switch, etc. If it affects one scope → bundle with that pane. If it affects all scopes → global, may be elsewhere.

// Button — Action control (impulse function). No state.

// Organization: Layout contains panes. Each pane has one scope_selector and shows one listing; pane hosts scope-local toggles for that scope. Global toggles (show_trashed, hidden_tag_set) live in shared UI. Actions (move, rename, delete, restore) are available in the pane according to scope_side_effect.

---

# PART IV — Binding (reference)

// Bind logical controls to UI: which toggle in which pane (local) or in shared area (global), which button, which pane, which layout. Placement and chrome are implementation.
// bind(control, element) — e.g. bind(scope_selector, tree), bind(ctrl.show_trashed, toolbar_toggle), bind(ctrl.show_negation, pane_toggle), bind(action.restore, button).
