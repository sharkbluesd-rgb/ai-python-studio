# Flet APK Studio — Web deployment

The browser application is served by the FastAPI service, not by GitHub Pages. The backend serves the HTML, CSS, JavaScript and authenticated /api/* routes from the same origin.

Deployment instructions and the Render blueprint are documented in README.md and WEB_ARCHITECTURE.md.

The old GitHub Pages URL is a historical static preview. It is not the live application and does not provide upload, GitHub authentication, cloud builds or APK downloads.

The first web deployment uses in-memory sessions and temporary files on a single worker. Restarts clear active sessions and projects. Multi-instance scaling requires shared session and job storage first.
