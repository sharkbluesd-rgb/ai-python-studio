# PYTHON STUDIO MOBILE — development roadmap

Target branch: `feature/studio-2.0`

## Product goal

Build a professional, mobile-first Python IDE with a real code editor, local project storage and a Python runtime. The browser is the first test and delivery target. The Android application is the second target and must replace only the runtime/storage adapters where native integration is required.

## Phase 1 — Browser IDE

- [x] CodeMirror 6 Python editor foundation and mobile layout.
- [x] Line numbers, folding, bracket matching, indentation, search, undo/redo and language autocomplete foundation.
- [x] IndexedDB project storage, tabs and autosave.
- [x] File/project create, rename, duplicate, delete and ZIP import/export.
- [x] Pyodide Web Worker runtime foundation.
- [x] Worker output, errors, package install/list and runtime adapter.
- [x] Stop fallback by terminating the Worker.
- [x] COOP/COEP hosting headers and SharedArrayBuffer path for input/interrupt.
- [x] Service-worker cache for application/runtime and downloaded Pyodide package resources.
- [ ] Verify production Vite build and GitHub Pages deployment.
- [ ] Browser-level checks on Android Chrome (portrait and landscape).
- [ ] Verify input(), interrupt, package installation and offline restart on a COOP/COEP host.

## Phase 2 — Android application

- [ ] Connect Flet Android UI to the same project model and editor interaction contract.
- [ ] Implement native Android Python runtime adapter; do not use Pyodide as a substitute for native Python.
- [ ] Add Android document picker, scoped storage and project import/export.
- [ ] Implement native package manager with Android ABI/wheel compatibility checks.
- [ ] Validate execution cancellation, filesystem access and performance on physical devices.
- [ ] Build, install and test signed/unsigned APK variants.

## Acceptance criteria

A feature is not complete merely because a control is visible. It must be connected to a real operation and tested. Browser Python execution must occur in a Worker, project persistence must survive reloads through IndexedDB, and the Android runtime must be verified separately from Pyodide.

## Technical constraints

- Pyodide runs Python compiled to WebAssembly. It does not provide general Linux shell commands, native Android APIs, unrestricted native sockets/processes or universal PyPI compatibility.
- Interactive stdin and cooperative interrupts require cross-origin isolation (COOP/COEP) and SharedArrayBuffer. Hosts without those headers use Worker termination as Stop fallback; the UI must not claim that interactive stdin is available.
- Web Workers keep long-running code off the UI thread but are not a security sandbox. The browser executes code locally for the user.
- Package wheels are loaded from the matching Pyodide distribution or compatible pure-Python PyPI wheels through micropip.

## Working rules

1. Work only on `feature/studio-2.0`.
2. Prefer small changes, real tests and root-cause fixes.
3. Do not add a remote code-execution backend for the browser IDE.
4. Do not claim browser support for native Python capabilities.
5. Keep the existing Android packaging pipeline separate until it is integrated and verified.
