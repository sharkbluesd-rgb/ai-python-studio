# Changelog

## Unreleased — Part 2 hardening

### Improved
- Bounded and validated package requirements input before invoking pip.
- Limited package installation requests to 100 package specs and 64 KB requirements files.
- Clamped package installation timeouts and normalized pip startup failures.
- Added regression tests for package option/URL injection, oversized requirements, excessive package counts and timeout handling.
- Applied the shared strict GitHub owner/repository and branch validators in the editor's upload/build flow.
- Corrected web-preview documentation to distinguish the published static browser mock from the full Flet application.

### Validation status
- The GitHub Actions run for the current feature branch passed Python compilation, unit tests, Ruff, Bandit and pip-audit before entering the APK build step.
- APK build and upload are still pending final workflow completion.
- Full Flet web compatibility and physical Android interaction remain unverified.

## 1.2.0 — 2026-11-22

### Added
- GitHub OAuth Device Flow sign-in.
- Repository listing and selection, repository creation, project upload, Actions dispatch, run/job status and logs, and APK artifact retrieval.
- Pre-build Android Flet project validation.
- CI linting, Bandit security scanning, dependency vulnerability auditing, and Dependabot configuration.

### Security
- Form-encoded OAuth device requests, strict repository and branch validation, bounded ZIP processing, and safe artifact redirect handling.
- APK extraction validates nested artifact structure and Android manifest presence.
- GitHub sessions are disconnected before local code, tests, or third-party package installation.

### Known limitations
- The local Python runner is not a sandbox.
- OAuth Device Flow requires a separately configured GitHub OAuth App and user consent.
- OAuth scopes repo and workflow are broad.
- Physical Android installation and real-account OAuth integration tests remain required.
