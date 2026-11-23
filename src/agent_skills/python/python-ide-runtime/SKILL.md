---
name: python-ide-runtime
description: Design and troubleshoot Python execution inside a mobile IDE, including project isolation, interpreter selection, package installation, subprocess lifecycle, cancellation, filesystem boundaries and safe output.
---
# Python IDE Runtime Engineering

1. Map interpreter, working directory, project root, environment, package manager and process ownership before changing runtime code.
2. Separate editor UI, execution service, package manager, project storage and platform adapters.
3. Never call unrestricted exec() in the main app process a sandbox. Prefer a separate process with timeouts, resource limits and restricted filesystem/network access where supported.
4. Treat cooperative cancellation as best effort; blocking native calls and subprocess descendants need explicit termination and cleanup.
5. Resolve paths against an approved project root; reject traversal, unsafe symlinks and writes outside allowed directories.
6. Run package installation in controlled subprocesses with timeouts, bounded logs and progress feedback.
7. Validate Android wheel and ABI compatibility separately from desktop installation.
8. Return structured results: exit code, stdout, stderr, duration, cancellation and timeout state.
9. Test syntax errors, runtime exceptions, infinite-loop timeout, cancellation, large output, invalid paths and missing dependencies.
10. Document platform limitations honestly; a terminal-like UI is not automatically a full interactive shell.
