# AI Python Studio — Browser Preview

The GitHub Pages URL is a **static HTML/CSS/JavaScript preview** of the editor layout. It is useful for checking the responsive design, navigation, basic browser interactions and bundled Skills Library from a phone.

It is not the full Flet application and it does not run `src/main.py`.

## Build and deployment

The workflow `.github/workflows/web-preview.yml` copies the maintained files from `web-preview-static/` and exports the bundled skill documents to `skills.json`. It verifies the output and publishes it to GitHub Pages.

Expected address:

`https://sharkbluesd-rgb.github.io/ai-python-studio/`

Open the Actions tab and inspect **Build and deploy AI Python Studio Web Preview**. Share the address only after the deployment job reports success.

## What the current preview can verify

- Mobile and desktop layout, navigation and responsive CSS.
- Browser-side file-tab and editor interactions implemented in `web-preview-static/app.js`.
- Bundled Skills Library search.
- Basic Python syntax validation in the browser.

## What it does not verify or provide

- It does not launch the real Flet app in `src/main.py`.
- It does not bundle or render the Flet CodeEditor Flutter extension.
- It does not execute arbitrary Python code, provide a real terminal, or install packages.
- It does not access the phone filesystem, persist a native project workspace, build APKs, or authenticate to GitHub.
- Its AI demo is not a production integration; never enter a production API key into a browser-only preview.

## Full Flet web compatibility

Flet supports both static browser builds (Python runs in Pyodide/WebAssembly) and dynamic server-backed web apps. These have different package and runtime constraints. The full Studio app uses local filesystem operations, subprocesses, threading and Android-oriented workflows; those features must be tested or adapted before claiming full browser support.

The Flet CodeEditor is a third-party Flutter extension. A compatible custom web client must be built with the extension included; the standard bundled web client alone is not proof of extension support. The current Pages workflow does not perform that build.

**Status:** the static preview is published; the full Flet app and CodeEditor extension have not yet passed an end-to-end web build and browser test. Do not treat the current Pages preview as the finished web IDE.
