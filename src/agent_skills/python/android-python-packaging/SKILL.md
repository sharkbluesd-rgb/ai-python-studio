---
name: android-python-packaging
description: Evaluate Python dependency compatibility for Android APK builds, including wheels, ABI constraints, native extensions, Flet packaging, and reproducible release checks.
---

# Android Python Packaging

Use this skill when adding Python packages to a Flet Android app or diagnosing APK build failures and runtime import errors.

## Compatibility workflow

1. Identify exact Python, Flet, Flutter, Android Gradle Plugin, build backend, and Android target versions.
2. Inventory direct and transitive dependencies. Separate runtime dependencies from development-only tools.
3. For every dependency with native code, verify a compatible Android wheel or supported build path exists for the target Python version and ABI (for example arm64-v8a). A package working in Termux or desktop Python does not prove Android compatibility.
4. Check package metadata, supported Python versions, platform tags, binary extensions, and system-library requirements. Flag packages requiring unavailable OS libraries or desktop-only APIs.
5. Prefer pure-Python packages when practical. Avoid silently replacing a requested package with an incompatible or similarly named package.
6. Pin and lock dependency versions where reproducible builds are required. Do not indiscriminately upgrade Flet, Flutter, Gradle, or native build tools.
7. Build a minimal APK after dependency changes. Inspect logs for wheel selection, compilation, linker, and manifest errors.
8. Install and launch the APK on a real Android device. Test imports and the feature that uses each new dependency.
9. Record package/version, compatibility evidence, target ABI, APK build result, device test result, and limitations.

## Common false assumptions

- A successful pip install on a computer does not prove Android support.
- A green GitHub Actions build does not prove the app launches on a phone.
- A package being available on PyPI does not mean an Android-compatible wheel exists.
- Development dependencies should not be bundled into the production APK without a clear reason.

## Release gate

Do not mark a dependency Android-supported until the APK is installed and the relevant import/feature is exercised on the target device. If device testing is unavailable, state that limitation explicitly.
