# Flet APK Studio 2.0

**Flet APK Studio** is a web-first tool for turning Python/Flet projects into Android APKs. It is not a Python IDE and does not include a code editor.

## Browser workflow

1. Open the deployed FastAPI web service on a phone or computer.
2. Import a Flet project ZIP or create the included Android starter.
3. Set the Android app name, package ID, version and build number.
4. Connect GitHub using OAuth Device Flow.
5. Choose an existing repository or create a private repository.
6. Upload the project, dispatch GitHub Actions, monitor the build and download the verified APK.

The browser does not need Android SDK or Gradle. APK builds run in GitHub Actions.

## Web service

FastAPI serves the browser interface and /api/* endpoints from the same origin. Run locally:

```bash
python -m pip install -r requirements.txt
COOKIE_SECURE=false PYTHONPATH=src uvicorn web_api:app --app-dir src --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Production must use HTTPS and a stable random FLET_APK_STUDIO_SESSION_SECRET.

A Render blueprint is included in render.yaml. Connect the repository to Render and deploy branch feature/studio-2.0. The blueprint creates a single-worker web service and generates the session secret.

## Security and current deployment limits

- GitHub OAuth Device Flow is handled by FastAPI. The access token stays in server memory and is never sent to browser JavaScript or written to disk.
- The browser receives a signed HttpOnly session cookie and a separate CSRF token.
- ZIP uploads are size-limited and extracted by the guarded WorkspaceStore. The upload-to-GitHub path also rejects common secret patterns and unsafe archive entries.
- The first web release uses in-memory sessions and temporary project files. It must run as one instance and one worker. Restarting or redeploying clears active sessions and temporary projects.
- Do not scale to multiple instances or workers until sessions, jobs and project state move to shared storage.
- GitHub OAuth requests repo and workflow scopes. These are broad permissions; review the approval screen and every workflow before authorizing a repository.
- Imported projects must contain pyproject.toml and src/main.py. If the build workflow is missing, the service adds the trusted Flet APK workflow. Existing workflows are not overwritten.
- Never upload .env files, passwords, API keys, signing keys or other secrets.

## Tests

Python 3.10+ is required.

```bash
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests tools
ruff check src tests --select E4,E7,E9,F
bandit -q -r src -lll
pip-audit -r requirements.txt
```

## APK verification

A successful Actions run and verified APK archive are necessary but not sufficient for release. Install and launch the APK on a trusted physical Android device before distributing it.
