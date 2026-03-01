# CODING_STANDARDS

Lean overlay. Use with BACKLOG.md to drive implementation: BACKLOG defines **what** (outcomes, iterations); this document defines **how** (modifier subset that overrides default approach). Not exhaustive.

**Scope:** Generally applicable strategy only (any application). App-specific strategy belongs in DETAILED_DESIGN (see DEVELOPMENT_GUIDE § Where to capture strategy decisions).

---

**Git management (first-class concern)**

- Before any development work: confirm a git project is active. If not, create one or clone/pull the repository. No work without an active git project.
- No work with unresolved unstaged changes. Resolve by committing, stashing, or discarding; then push or sync as appropriate before starting.
- No iteration on the default branch (e.g. master/main). Each iteration is done in a new branch.
- Iteration is complete when the branch is merged into the default branch, committed, and pushed.

---

- **No ORMs.** Use explicit data access only.

- **OOP for structure:** Organization, isolation, abstraction, interfaces, inheritance. Use object orientation for these; not for one-off scripts.

- **AOP where it helps reuse.** Use aspect-oriented patterns for cross-cutting, stock behaviors (e.g. logging, validation) so they are not duplicated.

- **Pure functions for implementation.** Use pure functions for logic. Use I/O and injected behavior only at boundaries (entry points, interfaces).

- **Config / business-rule driven.** Prefer configuration and business rules over environment variables and hard-coded branching. Drive behavior from data where possible.

- **Logic via algebra and routers.** Evaluate conditionals with proper logical algebra. Prefer routers (e.g. case/dispatch) over long if/then/else chains.

- **Contractions over long form.** Prefer lambda, ternary, comprehensions where they improve readability. Forbid cryptic contractions (e.g. Perl-style symbols, C++ #define macros).

- **Comments rare and short.** Avoid comments, or keep them very brief. Use only to annotate confusing lines or a one-line description at the top of a method.

- **One file per class (Python).** In Python, one class per file (Java-style). In Web/JS, multiple classes/functions per file is acceptable; still prefer multiple files to separate concerns.

- **Variable names by context.** For simple arithmetic/math-style functions use short names: x, y, a, b (e.g. `def sum(a, b): return a + b`). For procedural code use meaningful names.

- **Avoid ad-hoc helpers.** Helpers are not banned, but many are a smell. Prefer: implement as a first-class, generic function (or library), then consume it. Single-purpose helpers: prefer inline (e.g. lambda) inside the caller. If it is truly single-purpose, keep it local and compact.

- **Convergence points for code paths.** Drive code paths through single points: routers, shared functions, polymorphism. Avoid many parallel branches that do the same thing.

- **Event-loop style where useful.** Use an event loop where applicable. Where there is no real event loop, consider patterns that resemble one for modeling behavior.

- **Async at entry points.** Where applicable, wrap entry points in an async wrapper so async can be used internally without forcing callers to be async.

- **Standard logger + AOP for call-stack logging.** Use a standard logger. Use AOP to attach default call-stack logging (configurable or off in production).

- **Interfaces for contracts.** Wrap homegrown and third-party code behind interfaces. Isolate concerns; use inheritance for variation.

- **Change in broad context.** Never make a change only to get a local result. Evaluate the requirement in the broadest relevant context; see if it applies elsewhere. Absorb the requirement in a general way (infrastructure, shared behavior), then implement that once and use it for the specific case.
