---
name: regression-testing
description: Build regression coverage for a Python/Flet IDE using unit, integration, startup, browser smoke, Android release and security checks.
---
# Regression Testing

1. Convert each defect into reproducible steps with expected and actual behavior.
2. Add the smallest failing unit test before fixing deterministic logic defects.
3. Use integration tests for filesystem, package management, GitHub adapters and process lifecycle.
4. Add startup smoke tests for normal and error paths. A fake page test is not a browser test.
5. Add browser checks for page load, console errors, editor rendering, typing, tab switching and syntax diagnostics.
6. Add Android smoke checks for install, cold start, permissions, keyboard, navigation and recovery when a device is available.
7. Run focused tests, full suite, compile, lint, security scan and dependency audit.
8. Keep tests deterministic and independent of live network services.
9. Preserve useful failure logs without leaking tokens or private source.
10. Record target, version, commit SHA and checks performed. Mark untested targets unverified.

Do not weaken assertions to make tests pass. Skipped tests are not passed; compilation is not runtime correctness.
