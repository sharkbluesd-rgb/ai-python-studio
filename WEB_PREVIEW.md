# AI Python Studio — Browser Previews

The GitHub Pages site contains two clearly separated browser experiences.

## 1. Responsive UI preview

The root page is a static HTML/CSS/JavaScript preview. It is useful for checking the responsive layout, navigation, basic editor interactions and bundled Skills Library from a phone.

It does not run the full Flet application in `src/main.py`.

## 2. Flet CodeEditor compatibility test

Open **Flet CodeEditor browser test** from the footer of the root page, or visit:

`https://sharkbluesd-rgb.github.io/ai-python-studio/flet-editor/`

This is a small isolated Flet app built with the pinned `flet==1.1.2` and `flet-code-editor==1.1.2` packages. It exists to verify that the actual Flet CodeEditor control can be packaged and rendered in a browser using a custom web client.

It supports:
- Switching between two in-memory Python files.
- Editing with the real Flet CodeEditor control.
- Saving changes for the current browser session.
- Python syntax validation without executing code.

The session save is temporary and is not browser persistence or a device filesystem.

## Build and deployment

The workflow `.github/workflows/web-preview.yml` builds the static root preview, builds the isolated Flet CodeEditor app into `build/web/flet-editor`, verifies both outputs, then publishes them together to GitHub Pages.

Expected addresses:

- Root UI preview: `https://sharkbluesd-rgb.github.io/ai-python-studio/`
- Flet CodeEditor test: `https://sharkbluesd-rgb.github.io/ai-python-studio/flet-editor/`

Open the Actions tab and inspect **Build and deploy AI Python Studio Web Preview**. The addresses are current only after the latest deployment job reports success.

## What remains outside the browser tests

Neither preview is the complete Android IDE. They do not provide:
- Native phone filesystem access or permanent project storage.
- General-purpose pip installation or native Android wheels.
- A local shell terminal.
- APK building or the GitHub OAuth upload/build workflow.
- Safe execution of arbitrary Python scripts.

The full Flet application uses filesystem operations, subprocesses, threading and Android-oriented workflows. These require separate adaptation and end-to-end testing before the full app can be described as web-compatible.

**Status:** the root preview and the isolated CodeEditor test are separate deliverables. A successful CodeEditor web build proves only that the control can be packaged and rendered; it does not prove that every feature in `src/main.py` works in a browser.
