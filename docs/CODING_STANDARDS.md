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

**Deployment and CI/CD (first-class concern)**

- Deployment strategy and end-to-end CI/CD are **prerequisites for development**. They must be determined up front. A **hello-world MVP** must be implemented to complete the deployment workflow before feature development proceeds.
- **Three approaches:**
  1. **Canonical** — Use the deployment strategy defined in this document (§ Canonical deployment strategy). This approach is shared across multiple projects unless a special case applies.
  2. **Custom** — A custom deployment strategy for special cases where there is a justified reason not to use the canonical approach. The justification must be decided and documented **up front**; good justification is the only valid substitute that satisfies the prerequisite.
  3. **No deployment** — No deployment plan required because the project is a sandbox, prototype, or there is another **justified** reason. Document the reason; “no deployment needed” without justification does not satisfy the prerequisite.
- Until one of the three is satisfied (canonical in use, custom justified and documented, or no-deployment justified and documented) and the hello-world deployment MVP is done, development work is not considered unblocked.

**Canonical deployment strategy**

- **Desktop apps (Electron).** For desktop applications that run inside Electron (and for similar GUI apps that will be distributed on macOS), the canonical approach is **build → publish to a stable URL → distribute via Homebrew Cask**.
  - **Build:** Produce a macOS artifact (`.app` in a `.dmg` or `.zip`) using a standard tool (e.g. `electron-builder`, `electron-packager`). The pipeline runs on a supported CI platform (e.g. GitHub Actions).
  - **Publish:** Host the artifact at a stable, versioned URL (e.g. GitHub Releases, internal artifact store). Each release has a deterministic URL (e.g. `https://.../releases/download/v1.0.0/App-1.0.0.dmg`).
  - **Distribute:** Provide a **Homebrew Cask** that points at that URL. Use either the public [homebrew-cask](https://github.com/Homebrew/homebrew-cask) repo (submit a cask for review) or an **organization tap** (e.g. `homebrew-tap` repo with a Caskfile); users run `brew tap org/tap` then `brew install --cask app-name`.
  - **CI/CD:** Pipeline steps: build the Electron app → run tests → create release / upload artifact → (if using a tap) update cask `version` and `sha256` and push to the tap repo. The **hello-world MVP** is: run this pipeline once and install the app via `brew install --cask <cask>` (or run the built artifact) and verify it launches.
- Other application types (e.g. web services, CLIs) may use a different canonical strategy or a justified custom approach; document in CODING_STANDARDS when added.

---

- Prefer communicating **state** over **state-change** or **delta**. Example: “the value is 28” (state) rather than “change the value to 28” (change) or “add 3 to the value” (delta).
- Entity contracts should express the **resulting state** of the entity, not the operation that got it there. Multiple action names (e.g. `/move`, `/delete`, `/rename`) that all produce the same final state overload the contract; use a single state-oriented resource (e.g. `/vpath` or `/location`) so the contract is “entity’s location state is X.”
- This is equivalent to operating in an **absolute** rather than **relative** coordinate system and reduces ambiguity across domains and verticals.

---

**Payload schemata: global superset, consistent across entities**

- All contract payload definitions should use a **subset of a global superset** of structured information. Entities can reference other entities (e.g. by ref id); a payload may contain multiple entity shapes in one structure.
- Consumers receive the same payload shape; an **implicit mask** applies—each consumer uses only the subset it needs and ignores the rest. No consumer-specific payload variants.
- This makes the same schema consumable by multiple consumers and allows API request/response schemas to **commute into a messaging layer** (e.g. event-driven service bus) without transformation. Apply for both APIs and event-driven messaging.

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
