# Flet APK Studio — Web Preview

The GitHub Pages root is a static, responsive preview of the dedicated APK-builder interface:

https://sharkbluesd-rgb.github.io/ai-python-studio/

It demonstrates the mobile layout, project ZIP selection, Android metadata fields, GitHub connection section and APK build stages.

**It is a design preview only.** It does not upload the selected ZIP, perform GitHub OAuth, run GitHub Actions or produce an APK. Those actions require the Flet application, a GitHub OAuth App with Device Flow enabled, and repository permissions.

The former isolated CodeEditor browser application has been removed along with its dependency. The full Flet APK builder is validated separately through the Python startup/unit tests and Android build workflow. Browser preview validation must not be described as a successful APK build.
