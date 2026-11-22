# Changelog

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
