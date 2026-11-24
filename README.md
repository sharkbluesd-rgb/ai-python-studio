# PYTHON STUDIO MOBILE

**Python Studio Mobile** is a mobile-first Python IDE. The first delivery target is a real browser IDE that can be tested from an Android phone; the second target is an Android application with a native local Python runtime.

## Browser IDE (phase 1)

- CodeMirror 6 editor with Python language support, line numbers, bracket matching, auto-indentation, folding, search, undo/redo and autocomplete.
- Pyodide Python runtime in a dedicated Web Worker. Python code does not execute on FastAPI or another public server.
- IndexedDB project storage with file tabs, local autosave and project restoration.
- Project/file creation, rename, duplicate, delete, multi-file import, ZIP import/export.
- Output and error panes, a clearly labelled editor command terminal, and a micropip-based package manager.
- Responsive mobile-first UI and a service worker for app/runtime cache.

The WebAssembly runtime is Python compiled for the browser, not a native Android/Linux Python interpreter. The package manager only supports pure-Python wheels and packages built for Pyodide/WebAssembly. See [web-ide/README.md](web-ide/README.md) for runtime limits, COOP/COEP requirements and offline behavior.

## Run the browser IDE locally

Requirements: Node.js 22.12 or newer.

```sh
cd web-ide
npm install
npm run dev
```

To run tests and build:

```sh
npm test
npm run build
npm run preview
```

The GitHub Actions workflow builds and publishes the web IDE from `feature/studio-2.0`. The source tree for the browser product is `web-ide/`.

## Android phase (phase 2)

The native Flet shell and local Python workspace remain in `src/`. The runtime is separated behind `PyodideRuntimeAdapter` on the web side so that the native app can later provide a compatible Android runtime adapter without replacing the CodeMirror-oriented web editor or project model. Android filesystem permissions, native package installation and native Python compatibility must be implemented and tested on a physical Android device; browser runtime capabilities must not be represented as native Android capabilities.

## Existing server code

The repository still contains the earlier FastAPI cloud-build integration and its regression tests. The browser IDE does not use it to execute Python. Keep that service separate from the local browser runtime; it may be retained as an optional future APK-build service until its integration is redesigned.

## Working branch

All development for this product remains on `feature/studio-2.0`. Do not modify `main` without an explicit request.
