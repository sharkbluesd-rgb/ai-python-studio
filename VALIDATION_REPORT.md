# AI Python Studio 1.1.0 — validation report

Date: 2026-11-21

## Source archive inspected

The uploaded archive contained a Flet `TextField` editor and the `flet-webview==1.1.2` dependency; the WebView was not used by `src/main.py`. This release replaces that unused dependency with `flet-code-editor==1.1.2` and pins Flet to `1.1.2`.

## 1.1.0 additions

- Project-wide exact replacement preview does not modify files; apply operation updates matches across text files.
- Replacement tests cover preview-only behaviour, multi-file changes, and empty-query rejection.
- Static project analysis parses Python AST without importing or executing project files.
- Heuristic checks include syntax errors, dynamic execution, shell invocation patterns, unsafe pickle loading, weak YAML loader use, and potential hard-coded secrets.
- Additional CLI, Flet and unittest project templates compile.
- Requirements editor opens or creates `requirements.txt`; it does not install packages.

## Checks run in the build workspace

- Python unit tests: 46/46 passed for the 1.1.0 source in this workspace.
- `python -m compileall -q src tests`: passed.
- ZIP export/import round-trip: passed in unit tests.
- GitHub-style wrapper folder ZIP import: passed in unit tests.
- ZIP path traversal rejection: passed in unit tests.
- ZIP symlink rejection: passed in unit tests.
- Bounded ZIP member decompression: implemented; oversized entries rejected before full extraction.
- Hidden GitHub workflow folders (`.github`) supported; sensitive `.git` and `.env` paths rejected.
- Symlink parent folders are rejected during folder creation.
- Control characters and excessively long paths are rejected.
- `.github/workflows` project folders and project folder listing are supported.
- Nested folders and file create/read/search: passed in unit tests.
- Python syntax validation: passed in unit tests.
- Project analysis and multi-file replace: passed in unit tests.

## Not verified here

- Flet app launch: Flet packages were not installed in this local build workspace; the Android UI has not been launched here.
- Android APK build: not executed in this workspace; GitHub Actions must perform this step.
- Android device test: not executed.
- FilePicker Android behaviour: API was checked against current Flet documentation; selected ZIP size is checked before processing and save uses `src_bytes`; on-device testing is still required.
- `flet-code-editor` Android native rendering: requires GitHub Actions APK build and device testing.
- GitHub workflow uses the official Flet build action and the current GitHub Actions checkout, Python setup and artifact actions.

A green GitHub Actions build and an install/open test on the Android device are still required before treating this update as a verified release.

## Safety note

The runner uses `exec()` in the app process. This project is not suitable for safely executing untrusted code. It has no reliable hard timeout or memory sandbox.
