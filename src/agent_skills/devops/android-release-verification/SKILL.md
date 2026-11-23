---
name: android-release-verification
description: >-
  Build and verify Python/Flet Android APK releases using pinned dependencies,
  GitHub Actions, artifact checks, install smoke tests, version tracking and
  release evidence. Use when preparing APK builds or diagnosing failed releases.
version: 1.0.0
author: AI Python Studio
license: MIT
tags: [android, apk, release, github-actions, ci-cd, validation]
---

# Android Release Verification

## Before build

1. Confirm the branch, commit SHA, package version, build number and workflow file.
2. Run compile, unit tests, lint and security/dependency audits required by the repository.
3. Verify the manifest contains the intended Android app ID, architecture and required permissions.
4. Check package compatibility and avoid adding unpinned/unreviewed dependencies.

## CI build

- Use a reproducible workflow with least-privilege permissions and pinned Python/Flet dependencies.
- Keep build logs and artifacts associated with the exact commit SHA.
- Do not report a successful build until the workflow conclusion is `success` and the expected artifact exists.
- If a workflow is cancelled by a newer push, do not treat it as a failure or a successful release.
- Inspect the exact failed step and logs before changing build configuration.

## Artifact checks

1. Confirm the artifact name, run ID, branch and commit SHA.
2. Check archive size, checksum, expiry and that it contains the expected APK.
3. Verify the APK archive is structurally valid and contains an Android manifest.
4. Never present an expired artifact or one from a different commit as the latest build.

## Device smoke test

After installation on a physical Android device, verify:
- App starts and renders the first screen.
- Navigation works and no blank/grey control regions remain.
- Editor can load, display, edit and save code.
- File picker and app-private storage behave correctly.
- Basic Python syntax checks and trusted local scripts behave as documented.
- GitHub sign-in, upload, workflow dispatch and APK download are tested separately if enabled.

A successful CI build only verifies the build environment. It does not prove the application runs correctly on every device.

## Release report

State commit, branch, workflow run, artifact ID/name/size, test results, device model/Android version if tested, known warnings and all unverified items. Never claim “bug-free”; report evidence and residual risk.
