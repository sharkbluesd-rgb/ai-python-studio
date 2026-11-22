# Security policy

## Running Python code

AI Python Studio currently runs user code with Python `exec()` in the same process as the Flet application. This is not a sandbox. A script may read or modify files available to the app, consume CPU or memory, alter process-global state, or interfere with the application. The current runner is for trusted personal code only.

Do not run untrusted scripts. Do not treat the UI warning, syntax checker, thread offloading, or output truncation as a security boundary.

## Project archives

ZIP import validates relative paths, rejects traversal and symbolic links, limits compressed archives to 12 MiB, limits each extracted member to 512 KiB and the project payload to 24 MiB, caps archive entries and supported project files, ignores common cache/build folders, bounds decompression reads, and only imports allowlisted file types. These checks reduce archive extraction risks but are not a substitute for platform-level sandboxing.

## Reporting

Report security issues privately to the repository maintainer. Do not publish secrets, API keys, signing keys, or personal project archives in public issues.


## GitHub integration

- Authentication uses GitHub OAuth Device Flow. Device Flow must be enabled in the OAuth App settings.
- The app requests repo and workflow scopes. These are broad scopes that can grant access to private repositories and workflow files; users must review and approve this access in GitHub.
- OAuth tokens are not written to project files, settings, logs, or environment variables. The client holds a token reference in memory while connected. Python cannot guarantee secure zeroization of immutable strings.
- Because project scripts and package build backends execute in the same application process or under the same app identity, the GitHub session is automatically disconnected before executing scripts, tests, and package installations. This reduces exposure but does not create a sandbox.
- Never run untrusted scripts or install untrusted packages. Do not treat session disconnection or cooperative timeouts as a security boundary.
- Project uploads reject traversal, links and special files, environment files, duplicate paths, encrypted entries, oversized files, and oversized projects. Artifact redirects are followed without forwarding the OAuth Authorization header to the storage host.
- APK installation has not been tested on every Android device. Verify artifacts on a trusted device before distribution.

- Before upload, a heuristic scanner blocks common GitHub/AWS token patterns, private-key headers, and long literal assignments to secret-like variable names. This is a safety net, not a complete secret scanner; manually review every project before upload.
