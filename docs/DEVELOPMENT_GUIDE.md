# Development Guide

Entry point for development. This guide names the project’s key documents and describes how to use them together to advance the project.

**Backlog:** Evaluate, re-evaluate, and update the backlog as context about the project improves. **All other documentation:** When you find conflicts, contradictions, divergences, or strategic shifts, raise them and remediate (fix the docs or the code so they align).

**Documentation discipline:** All documents must remain under heavy scrutiny and be challenged on any frictional or inconsistent encounter. Documentation must evolve in a **convergent** way. Prioritize and claim any opportunity to reduce documentation complexity, wordiness, logical load, or redundancy.

---

## Document map

| Document | Purpose |
|----------|---------|
| **DEVELOPMENT_GUIDE.md** (this file) | Entry point. Map of documents and how they work together. |
| **PSEUDO_LOGIC.md** | Canonical logical rules in pseudo code (path, vpath, tags, scopes, visibility, controls). Single source for “what the app computes.” |
| **FUNCTIONAL_SPECIFICATION.md** | Full functional behavior from a user and system perspective. Expands and aligns with PSEUDO_LOGIC. |
| **FUNCTIONAL_CHEATSHEET.md** | Minimal summary of behavior. Quick reference; not a substitute for the spec when behavior is ambiguous. |
| **EXPLORER_RULES.md** | Mechanics and edge cases (move, rename, scope, visibility, empty). Refined rules; correct here before changing code. |
| **BACKLOG.md** | Iterations to align implementation with the spec. Outcome-focused tasks; order by impact and blast radius. |
| **ISSUES.md** | Tactical issues (docs, code, UX). Bugs/friction in current state; ordered by priority. Fix when proximal to iteration or user-raised; small numbers per iteration. |
| **CODING_STANDARDS.md** | How to implement: overlay on default approach (no ORMs, pure functions, interfaces, config-driven, etc.). Orthogonal to backlog. |
| **DETAILED_DESIGN.md** | Technical approach and implementation strategy per iteration. Just-in-time before implementation; structured by topology and features; partial map that fills out as areas are touched. |
| **REFACTOR_ITERATION_PLAN.md** | Development-standards refactor (contracts, domain extraction, testing). Complements BACKLOG; BACKLOG focuses on spec alignment. |
| **explorer_api_contract.md** | API routes, request/response shapes, errors. Contract at the HTTP boundary. |

---

## How to use them together

**1. Starting development**

- Read this guide and **FUNCTIONAL_CHEATSHEET.md** to understand what the app does.
- Use **PSEUDO_LOGIC.md** when you need the exact rule (e.g. effective path, tag cycle, scope_side_effect).
- Use **EXPLORER_RULES.md** and **FUNCTIONAL_SPECIFICATION.md** when behavior or edge cases are unclear.

**2. Choosing work**

- Work from **BACKLOG.md**. Pick an iteration (or the next unchecked task in the suggested order).
- Backlog tasks are outcomes, not implementation steps. Use the spec docs to know *what* must be true when the task is done.

**3. Detailed design (just-in-time)**

- Before implementing an iteration, **create a new branch** (do not work on the default branch). Then capture the technical approach and implementation strategy in **DETAILED_DESIGN.md**. It is driven by: the backlog (requirements for that iteration), CODING_STANDARDS (constraints), and the existing codebase. In a contracting setting, detailed design would be complete before implementation; here it is add-as-you-go and written just-in-time for each iteration.
- **Structure DETAILED_DESIGN by application topology and features**, not by the order in which work was done. When you add or change content, place it under the relevant area (e.g. meta layer, explorer routes, tag resolution, frontend panes) rather than appending at the end. The document is a partially completed technical map that fills out as areas are touched and improved.

**4. Implementing**

- Apply **CODING_STANDARDS.md** while implementing backlog items. Standards define *how* (structure, purity, interfaces, etc.); backlog defines *what*.
- At boundaries (API, DB, UI), follow **explorer_api_contract.md** for routes, payloads, and errors.
- When a rule is ambiguous, resolve it in **EXPLORER_RULES.md** or **PSEUDO_LOGIC.md** first, then change code.

**5. Completing work**

- Before considering an iteration complete: update **BACKLOG.md** checkboxes; update **DETAILED_DESIGN.md** for any touched areas (under the right topology/feature); run tests and add or update them when behavior or contract changes; merge iteration branch to default, commit, and push (see CODING_STANDARDS § Git management); remediate any doc conflicts you found.
- When implementing, consider fixing a **small number of ISSUES.md** items that have proximity to the current iteration (or that the user has raised); do not overload the iteration with issues.
- In DETAILED_DESIGN, reference the backlog iteration (e.g. “Iteration 2”) in sections you add or change so design and work stay traceable.

**6. Cross-cutting concerns**

- **New behavior or rule** → Document in PSEUDO_LOGIC and/or EXPLORER_RULES; add or adjust backlog items if implementation is needed.
- **Incidental issue** (doc, code, or UX friction) → Add to **ISSUES.md** with checkbox; order by priority. Consider including a small number in the current iteration if they have proximity to the work or the user has raised them.
- **API change** → Update explorer_api_contract.md and any spec that references the API.
- **Refactor for structure only** → REFACTOR_ITERATION_PLAN may apply; keep behavior aligned with the spec docs.

---

## Where to capture strategy decisions

When an implementation-strategy decision is made and codified, decide whether it is **generally applicable** (to any application) or **specific** (to this application). Example: “Don’t use an ORM” is generally applicable; “Negation tags are not inherited but signal tag omission in the child” is specific.

- **Generally applicable** → Capture in **CODING_STANDARDS.md**. These are constraints and approaches that apply regardless of the current app (e.g. no ORMs, pure functions at the core, interfaces for contracts).
- **Specific** → Capture in **DETAILED_DESIGN.md** (or in **FUNCTIONAL_SPECIFICATION.md** / EXPLORER_RULES if the decision forces a re-evaluation of requirements).

DETAILED_DESIGN should not relitigate standards already established in CODING_STANDARDS, and should not repeat them. It builds on those standards with app-specific technical choices.

*Note: “Coding standards” is a bit of a misnomer—the document goes beyond coding (e.g. no ORM is a philosophical/architectural standard). The name is kept for now.*

---

## Flow summary

```
Understand behavior     →  CHEATSHEET, SPEC, PSEUDO_LOGIC, EXPLORER_RULES
Choose work             →  BACKLOG
Design (JIT)            →  DETAILED_DESIGN (by topology/features)
Implement               →  CODING_STANDARDS + explorer_api_contract
Resolve ambiguity       →  EXPLORER_RULES / PSEUDO_LOGIC first, then code
Log / fix tactical      →  ISSUES (priority order; few per iteration when proximal or user-raised)
```

Start here; use the map and flow above to navigate the rest.
