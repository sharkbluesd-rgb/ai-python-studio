# AI Python Studio 1.2.0

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
- GitHub Device Flow sign-in, repository listing and selection, repository creation, project upload, Actions dispatch, job status/logs, and APK artifact download.
- GitHub sessions are held in memory only and automatically disconnected before running Python scripts, project tests, or installing third-party packages.
- Pre-build validation for Android Flet projects, including manual workflow dispatch and artifact upload; APK download is allowed only after a successful run and APK structure verification.
- Upload guard that blocks common GitHub/AWS token patterns, private-key headers, secret-like assignments, and environment files.

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

Push to `main` or a `feature/**` branch, or start the `Build AI Python Studio APK` workflow manually from GitHub Actions. The workflow builds version `1.2.0`. The official Flet build action creates `flet-apk.zip`; GitHub Actions uploads that archive as a downloadable artifact.

## Important execution warning

The current local runner executes code with exec() inside the app process. It is intended only for code the device owner trusts. It is not a security sandbox. Cancellation checks Python line events but cannot reliably interrupt native extensions, blocking I/O, or every third-party call. Do not use it to run unknown code from other people.

## Deliberate limitations in this release

The project does not yet bundle a separate Python distribution or a general-purpose `pip` environment for Android. The package manager installs requested packages into the Python interpreter used by the app; compatibility depends on Android-compatible wheels and successful native imports. Installing a package does not guarantee that its dependencies support Android. AI providers, a native shell terminal, and an interactive debugger are not included in this release. The GitHub integration requires a GitHub OAuth App with Device Flow enabled and requests repo and workflow scopes to update files and run Actions. These scopes are broad; review the permissions on GitHub before authorizing.


## GitHub setup

1. Create a GitHub OAuth App and enable Device Flow in its settings.
2. Copy its Client ID into the GitHub screen in AI Python Studio. Never enter a password, Client Secret, or personal access token.
3. Start device authorization, open the official GitHub verification URL, enter the displayed user code, and confirm from the app.
4. Select or create a repository, upload an Android Flet project, then dispatch build-apk.yml.
5. Refresh the run status. APK download is available only after a successful run with a valid APK artifact.

The app requests repo and workflow scopes. The repo scope is used for private repository access and pushing project files; workflow is required to update workflow files and run Actions. OAuth App scopes can grant broad access to repositories.
