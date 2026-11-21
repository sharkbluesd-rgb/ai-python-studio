# Security policy

## Running Python code

AI Python Studio currently runs user code with Python `exec()` in the same process as the Flet application. This is not a sandbox. A script may read or modify files available to the app, consume CPU or memory, alter process-global state, or interfere with the application. The current runner is for trusted personal code only.

Do not run untrusted scripts. Do not treat the UI warning, syntax checker, thread offloading, or output truncation as a security boundary.

## Project archives

ZIP import validates relative paths, rejects traversal and symbolic links, limits compressed archives to 12 MiB, limits each extracted member to 512 KiB and the project payload to 24 MiB, caps archive entries and supported project files, ignores common cache/build folders, bounds decompression reads, and only imports allowlisted file types. These checks reduce archive extraction risks but are not a substitute for platform-level sandboxing.

## Reporting

Report security issues privately to the repository maintainer. Do not publish secrets, API keys, signing keys, or personal project archives in public issues.
