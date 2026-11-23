# Flet APK Studio 2.0

**Flet APK Studio** is a focused mobile-first tool for turning an existing Python/Flet project into an Android APK. It is not a Python IDE and does not contain a code editor.

## Build flow

1. Create the included Flet Android starter or import a project ZIP from your device.
2. Set the Android app name, package ID, version and build number.
3. Connect a GitHub account using OAuth Device Flow.
4. Select an existing repository or create a new private repository.
5. Upload the project, dispatch \`.github/workflows/build-apk.yml\`, and follow the GitHub Actions run.
6. Download the APK only after the selected run completes successfully.

The actual APK is built by GitHub Actions using the official Flet build action. The phone does not need the Android SDK or Gradle installed.

## Required project structure

An imported project must include:

- \`pyproject.toml\` with \`[project]\`, \`[tool.flet]\` and \`[tool.flet.app]\`.
- \`src/main.py\` as the Flet application entry point.
- \`.github/workflows/build-apk.yml\` with \`workflow_dispatch\`, APK build and artifact upload.

Use the in-app **Flet Android App** starter to create a project with this structure. Python dependencies must support the Python/Android ABI selected by the build workflow. A package that installs on desktop or Termux is not automatically compatible with Android.

## GitHub setup

1. Create a GitHub OAuth App and enable Device Flow.
2. Enter its Client ID in the app. Never enter a password, Client Secret or personal access token.
3. Approve the displayed device code at GitHub, then verify the connection in the app.
4. Select/create a repository and start the build.

GitHub authorization requests \`repo\` and \`workflow\` scopes. These are broad permissions. The OAuth token is held in memory only and is cleared when disconnected or the app process ends. Review your project and every GitHub Actions workflow before uploading/building. Do not include \`.env\` files, passwords, API keys, signing keys or other secrets in the project.

## Development and tests

Python 3.10+ is required.

\`\`\`bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests tools
flet run
\`\`\`

The project pins \`flet==1.1.2\`. The former \`flet-code-editor\` dependency and editor screens have been removed.

## Web preview

The GitHub Pages root is a responsive **UI preview** of the APK builder. It can display a selected ZIP filename and demonstrate the layout, but it does not upload files, connect to GitHub or build/download an APK. Real build operations are available in the Flet application after GitHub is connected.

Preview: https://sharkbluesd-rgb.github.io/ai-python-studio/

## Limitations

- Builds run on GitHub Actions, not locally on the phone.
- Build time and availability depend on GitHub Actions quotas and the project's dependencies.
- APK download requires a successful Actions run and an artifact containing one APK.
- Successful cloud build does not replace installation and launch testing on a physical Android device.
