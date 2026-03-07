# File Triage

Desktop file triage — analyse and organise chaotic file collections across disks. Explorer UI (tagging, virtual paths, rules) runs in the browser; this repo also wraps it in Electron for a desktop app.

## Docs

- **Documentation** — Project docs live in `docs/`. Start with **docs/EXECUTIVE_SUMMARY.md** for a one-page overview; then **../core-documentation/DEVELOPMENT_GUIDE.md** for the full document map and how to run iterations.
- **docs/BACKLOG.md** — Spec-alignment iterations; Deployment iteration (Electron + Homebrew Cask) is the gate before Iteration 2+.
- **docs/explorer_api_contract.md** — API and terminology (effective path, negation, pane, etc.).

## Run Explorer (CLI)

```bash
pip install -e .
file-triage explorer --port 5001
# Open http://127.0.0.1:5001/
```

With meta DB (tagging):

```bash
file-triage meta init
file-triage explorer --meta-db ~/.file-triage/meta.db
```

## Run desktop app (Electron)

Prerequisites: Node 18+, Python 3.10+, and `pip install -e .` so `file_triage` is on the module path.

```bash
npm install
npm start
```

Electron starts the Flask backend on port 5001 and opens a window to it. To use a different Python: `PYTHON_PATH=/path/to/python3 npm start`.

## Build macOS artifact

```bash
npm run build
```

Produces `dist/File Triage-0.1.0.dmg` and `.zip`. The app bundles the Python source in `resources/app` and runs `python3 -m file_triage.cli explorer` at launch (so a system Python 3 with dependencies is required unless you add a bundled Python later).

## Deployment (CI/CD and Cask)

- **Canonical strategy:** Build → publish to stable URL (e.g. GitHub Releases) → distribute via Homebrew Cask. See ../core-documentation/CODING_STANDARDS § Canonical deployment strategy and docs/BACKLOG § Deployment iteration.
- **Pipeline:** `.github/workflows/build-release.yml` builds the macOS app on release; attach the DMG/zip to the release for the Cask URL.
- **Cask:** Tap repo at `mattian7741/homebrew-tap`. Install with `brew tap mattian7741/tap` then `brew install --cask file-triage`. Update the Cask (version, sha256) in the tap repo when releasing. See docs/DETAILED_DESIGN § Deployment.
- **Verify the built app (prerequisite):** Before starting Iteration 2+, run through the hello-world MVP verification once: download the DMG from a release, install, launch, and confirm the Electron window loads the Explorer UI and the backend listens on port 5001. Full steps: docs/DETAILED_DESIGN.md § Deployment → How to verify the hello-world MVP.
