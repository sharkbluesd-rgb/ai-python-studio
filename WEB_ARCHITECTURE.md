# Flet APK Studio 2.0 — Web Architecture

## Current implementation baseline

- Branch: `feature/studio-2.0`
- The existing Flet client already contains project validation, Android metadata configuration, GitHub Device Flow, repository operations, workflow dispatch, run monitoring, and APK artifact extraction.
- The GitHub Pages site is a static design preview. It does not execute these operations.
- The web release will use a same-origin FastAPI service that serves the web assets and owns GitHub credentials.

## Target request flow

`Mobile/Desktop Browser → FastAPI (same origin) → GitHub REST API → GitHub Actions → APK artifact → FastAPI download`

## Security boundaries

- OAuth Device Flow is performed server-side. Device codes and access tokens never enter browser JavaScript.
- The browser receives an HttpOnly, signed, short-lived session cookie and a separate CSRF token.
- Session state and OAuth tokens are held in server memory only.
- ZIP upload is bounded and extracted through the existing guarded WorkspaceStore.
- The existing GitHub upload path rejects common secret patterns and unsafe archive entries.
- The backend must run as one worker/instance for this in-memory MVP. Do not scale horizontally or add workers until session/job state moves to a shared store.
- Configure `FLET_APK_STUDIO_SESSION_SECRET` with a stable random secret in production. Never commit it.
- Use HTTPS and `COOKIE_SECURE=true`.

## Deployment

The included Render blueprint deploys the FastAPI service from `feature/studio-2.0`. The service serves `web-preview-static/index.html`, `style.css`, and `app.js` on the same origin as `/api/*`.

The first deployment uses ephemeral storage and in-memory sessions. A restart clears active sessions and temporary projects. This is deliberate for the first working web milestone; durable projects, Redis-backed sessions, background jobs, and multi-instance scaling are follow-up production-hardening tasks.

## API milestones

1. Session bootstrap, signed HttpOnly cookie, CSRF validation, health endpoint.
2. GitHub Device Flow, user/repository listing and repository creation.
3. ZIP import, Flet validation and Android configuration.
4. GitHub commit/upload and workflow dispatch.
5. Build status, job steps, and verified APK download.
