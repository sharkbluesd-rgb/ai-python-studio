# AI Python Studio — Web Preview

This preview builds a browser client that includes the Flet CodeEditor Flutter
extension. The ordinary `flet run --web` client is not sufficient for an app
that uses a third-party Flutter extension unless it is pointed at a compatible
custom-built web client.

## Build and deployment

The workflow `.github/workflows/web-preview.yml` builds
`src/web_preview.py` with Flet 1.1.2, packages the CodeEditor extension, and
deploys the static preview to GitHub Pages from `feature/studio-2.0`.

Expected address:

`https://sharkbluesd-rgb.github.io/ai-python-studio/`

Open the Actions tab and inspect **Build and deploy AI Python Studio Web
Preview**. The address is usable only after the deployment job reports success.

The workflow always uploads a downloadable
`ai-python-studio-web-preview` artifact after a successful build. If automatic
Pages setup is denied, the artifact is still available. The repository owner
must enable **Settings → Pages → Build and deployment → Source: GitHub Actions**
once, then rerun the workflow to publish the public URL.

## What this preview verifies

- The Flutter web client can render the bundled `flet-code-editor` control.
- The sample project files can be switched.
- The editor accepts input and the syntax-check action responds.

## Preview limitations

This is an isolated browser preview, not the full Android application. It does
not access the phone filesystem, install native Python packages, launch a local
shell, build APKs, or authenticate to GitHub. Python syntax validation runs in
the browser and does not execute the submitted code. Full project operations
remain in the Android app / server-backed build workflow.
