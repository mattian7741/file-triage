# File Triage

Desktop file triage — analyse and organise chaotic file collections across disks. Explorer UI (tagging, virtual paths, rules) runs in the browser; this repo also wraps it in Electron for a desktop app.

## Docs

- **DEVELOPMENT_GUIDE.md** — Entry point: document map, prerequisites (git + deployment), how to run iterations.
- **BACKLOG.md** — Spec-alignment iterations; Deployment iteration (Electron + Homebrew Cask) is the gate before Iteration 2+.
- **explorer_api_contract.md** — API and terminology (effective path, negation, pane, etc.).

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

- **Canonical strategy:** Build → publish to stable URL (e.g. GitHub Releases) → distribute via Homebrew Cask. See CODING_STANDARDS § Canonical deployment strategy and BACKLOG § Deployment iteration.
- **Pipeline:** `.github/workflows/build-release.yml` builds the macOS app on release; attach the DMG/zip to the release for the Cask URL.
