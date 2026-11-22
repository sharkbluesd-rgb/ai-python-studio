# AI Python Studio 1.1.0

A mobile-first Python development workspace built with Flet for Android.

## Current features

- Native Flet code editor extension with Python syntax highlighting, line numbers, folding and autocomplete.
- Persistent, app-private projects and nested source folders.
- Multi-file Python project structure and supported text/config files.
- Create nested folders; create, rename, duplicate and delete source files.
- Search across project text files, replace in the current file, and preview/apply exact replacements across the whole project.
- Offline templates for Python, automation, CLI tools, Flet apps and unit-test projects.
- Dedicated Flet Android App template with a complete project manifest and GitHub Actions APK workflow.
- ZIP project import/export with path traversal, symlink and size checks; common image assets are retained.
- Python syntax checking without executing the script.
- Offline project analysis: code metrics, severity totals and an indicative quality score.
- Static diagnostics for hard-coded-secret patterns, dynamic execution, shell usage, pickle/YAML hazards, mutable defaults, ignored exceptions, wildcard imports, HTTP calls without timeouts and TODO markers.
- Project report displayed in the diagnostics panel; static analysis never imports or executes project code.
- Run, search, syntax, package and analysis actions navigate to the results screen automatically.
- Python package manager with individual package installation, requirements installation and installed-package listing; compatibility depends on Android wheels.
- Local trusted-code execution with captured output and tracebacks; relative file access starts at the active project root and the app working directory is restored afterwards. Optional command-line arguments are supported.
- In-app unittest discovery for the active project's tests folder, including a 180-second cooperative execution limit.
- GitHub Actions tests and Android APK builds on `main` and `feature/**` branches.

## Development

Python 3.10+ is required.

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

To run the Flet application locally:

```bash
flet run
```

## Android APK

Push to `main` or a `feature/**` branch, or start the `Build AI Python Studio APK` workflow manually from GitHub Actions. The workflow builds version `1.1.0`. The official Flet build action creates `flet-apk.zip`; GitHub Actions uploads that archive as a downloadable artifact.

## Important execution warning

The current local runner executes code with exec() inside the app process. It is intended only for code the device owner trusts. It is not a security sandbox. Cancellation checks Python line events but cannot reliably interrupt native extensions, blocking I/O, or every third-party call. Do not use it to run unknown code from other people.

## Deliberate limitations in this release

The project does not yet bundle a separate Python distribution or a general-purpose `pip` environment for Android. The `requirements.txt` tool edits the manifest only; it does not install packages. Package installation depends on Android-compatible wheels and is not exposed as a one-tap feature. AI providers, Git remote operations, a real terminal, interactive debugger, and remote build orchestration are not yet connected in the app; APK building is currently handled by this repository's GitHub Actions workflow.
