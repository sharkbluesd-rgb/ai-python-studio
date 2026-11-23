---
name: python-debugging
description: >-
  Methodical Python debugging for startup failures, exceptions, UI freezes,
  import errors, Android runtime issues, path problems, async bugs and API
  failures. Reproduce first, isolate the cause, collect useful diagnostics,
  fix with regression tests and verify on the target runtime.
version: 1.0.0
author: AI Python Studio
license: MIT
tags: [python, debugging, traceback, errors, android, async, diagnostics]
---

# Python Debugging

## Diagnostic workflow

1. Capture the exact error, full traceback, command, working directory, Python version, OS/runtime and dependency versions.
2. Reproduce the failure with the smallest reliable example. Distinguish startup, import, UI rendering, network, filesystem and platform-specific failures.
3. Read the complete function and its callers before changing it. Trace input, state transitions, exception handling and side effects.
4. Form one testable hypothesis at a time. Use focused logs and a small experiment; do not change several unrelated things together.
5. Add a regression test that fails before the fix whenever the bug is reproducible in a unit/integration test.
6. Implement the smallest correction, then run the focused test, complete test suite, compile check, linter and applicable security scanner.
7. Verify on the actual target runtime. Desktop success does not prove Android success; Python web preview success does not prove native plugin success.
8. Report what was tested, what passed, what remains unverified and the exact next action.

## Evidence rules

- Never diagnose a root cause from a screenshot alone when runtime logs or console output can distinguish alternatives.
- Never claim a bug is fixed because code compiles. Compilation does not prove rendering, package compatibility, permissions or network behavior.
- Separate a confirmed defect from a plausible hypothesis.
- Keep secrets, access tokens, personal data and private file contents out of logs and reports.
- Do not use broad exception suppression as a quick fix. Preserve useful error context and render actionable diagnostics.

## Python-specific checks

- Imports: interpreter, virtual environment, package name versus import name, version conflicts and platform wheel availability.
- Filesystem: current working directory, app-private data paths, relative paths, permissions, symlinks and case sensitivity.
- Async: event-loop ownership, blocking calls, task cancellation, timeouts and exceptions raised by background tasks.
- UI: control lifecycle, parent/container sizing, expand/scroll constraints, event callback wiring and client/server compatibility.
- Android: native library ABI, Android permissions, bundled assets, package extraction rules, logcat output and physical-device reproduction.

## Definition of done

- [ ] A reproducible failure or a precise reason why reproduction was not possible.
- [ ] Root cause supported by code or runtime evidence.
- [ ] Regression test added where practical.
- [ ] Focused and full checks passed.
- [ ] Target platform tested or explicitly listed as unverified.
- [ ] No secrets or private data exposed in diagnostics.
