# Flet APK Studio — focused delivery plan

Target branch: \`feature/studio-2.0\`

## Product scope

The application has one job: package a Python/Flet project as an Android APK through GitHub Actions. The in-app code editor, IDE navigation, local Python runner and unrelated development panels are out of scope.

## Main workflow

1. Project intake: create the included Flet Android starter or import a ZIP.
2. Project validation: check the Flet manifest, \`src/main.py\` and APK workflow.
3. Android configuration: update app name, package ID, version and build number.
4. GitHub connection: OAuth Device Flow, repository selection/creation.
5. Cloud build: upload project, dispatch the workflow and identify only the newly dispatched run.
6. Release: show job/step status, fetch failure logs, and download the APK only from a successful run.

## Acceptance checklist

- [ ] No CodeEditor dependency or editor screen remains.
- [ ] Import ZIP preserves valid source files and assets while enforcing archive/path limits.
- [ ] The Flet starter contains the correct entry point, manifest and manual APK workflow.
- [ ] Package ID, version and build number are validated before changing project files.
- [ ] GitHub credentials remain session-only and are never written into project files.
- [ ] Upload rejects common secret patterns and unsafe paths.
- [ ] A build request is matched to a newly dispatched run, not an older successful run.
- [ ] Build logs are visible when a job fails.
- [ ] APK download is enabled only after a successful run and the APK archive is structurally validated.
- [ ] Responsive phone UI, unit tests, static checks and GitHub Actions pass.
- [ ] Physical Android installation and first-launch testing are recorded separately from CI.

## Security notes

GitHub \`repo\` and \`workflow\` scopes are broad. Users must inspect imported source and workflow files before triggering Actions. Never place credentials, signing keys or API secrets in an imported project. Cloud build success is not proof that arbitrary third-party dependencies are safe or Android-compatible.

## Working rules

1. Work only on \`feature/studio-2.0\`; do not modify \`main\`.
2. Prefer small changes with focused tests.
3. Do not add fake build success states or sample APK artifacts.
4. Report web-preview, cloud-build and physical-device validation as separate results.
