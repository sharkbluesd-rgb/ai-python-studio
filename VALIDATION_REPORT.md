# AI Python Studio 1.2.0 — validation report

Updated: 2026-11-23

> Historical 1.1.0 findings are retained below for traceability. The current 1.2.0 results are recorded in the final section; do not use the older 1.1.0 test counts as current validation.

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


## GitHub cloud integration security review — 2026-11-22

The previous successful workflow run (45061148221) compiled the source, passed 96 unit tests, built the Flet Android APK, and uploaded flet-apk.zip (25,796,822 bytes). That run validates its recorded commit only; it predates the additional hardening changes currently being tested.

Additional review findings and corrections:
- OAuth device-code and token requests use URL-encoded form bodies as specified by GitHub.
- Device verification URLs are restricted to the official GitHub device page; device polling observes the server-provided interval.
- Repository owner/name and Git branch inputs are validated before being added to API paths.
- ZIP upload checks declared member sizes before reading, caps each member at 512 KiB, rejects environment files, symbolic links, special files, encrypted entries, duplicate paths, traversal, and oversized projects.
- Artifact redirects are followed without forwarding the OAuth bearer token to the redirected storage host.
- APK download is restricted to completed successful runs and the expected flet-apk.zip artifact; the nested archive is unwrapped and the APK must contain AndroidManifest.xml.
- The GitHub session is disconnected before project script execution, test execution, and third-party package installation because the current Python runner is not isolated.

Still required before calling this release fully verified:
- The post-review commit must pass CI tests, lint and security audits, and a fresh APK build.
- GitHub OAuth must be tested with a real OAuth App and user account.
- Upload, workflow dispatch, log retrieval, and APK saving must be exercised against a test repository.
- The APK must be installed and launched on a physical Android device.
- The intentionally unsandboxed local Python runner remains a known limitation.


## Current 1.2.0 validation — 2026-11-23

- Repository: `sharkbluesd-rgb/ai-python-studio`
- Branch: `feature/studio-2.0`
- Validated commit: `cfc50c87cf631593657eaa217fa4d142fa5c1f0c`
- GitHub Actions run #60: successful.
- Unit tests: 110 passed.
- Python compile check: passed.
- Ruff check across `src` and `tests`: passed.
- Bandit scan across `src` at high severity/confidence threshold: passed.
- `pip-audit -r requirements.txt`: no known vulnerabilities found.
- Android APK build: passed; output APK reported by the build action as 53.8 MB.
- Artifact: `flet-apk.zip`, 25,808,611 bytes, artifact ID `14770113247`, retention 14 days.
- SHA-256 of uploaded artifact: `8dd54238d9f5a4bc9b54b3fc5c574be9001b4b44dc052d3463ee79b5b68cb331`.
- Build warning: Flutter reports Android Gradle Plugin 8.13.2 will soon fall below its supported version and recommends AGP 9.0.1 or later. This did not fail the build.
- These CI checks do not replace a physical Android installation test, OAuth testing with a real account, or end-to-end upload/dispatch/log/download testing.

### Additional hardening after run #60

- Job-log ZIP extraction now limits the number of text entries, per-entry decompressed size and total decompressed size to reduce ZIP-bomb memory exhaustion.
- Two regression tests cover excessive log entry count and oversized uncompressed log members.
- The app version label is synchronized with the 1.2.0 package/workflow version.
