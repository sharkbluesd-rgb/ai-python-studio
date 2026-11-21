# Changelog

## 1.1.0 - 2026-11-21

- Added whole-project exact text replacement with a preview-before-apply workflow.
- Added offline project analysis with Python syntax diagnostics, file/line/function/class metrics, TODO counts and heuristic security warnings.
- Added starter templates for CLI tools, Flet apps and unittest projects.
- Added a requirements.txt editor entry point for maintaining dependency manifests.
- Expanded automated tests for static analysis and safe project-wide replacement.

## 1.0.0 - 2026-11-21

- Replaced the plain multiline text field with the Flet CodeEditor extension (Flet 1.1.2 / flet-code-editor 1.1.2).
- Added Python syntax highlighting, autocomplete, line numbers and code folding.
- Added multi-file and nested-folder project support.
- Added source-file creation, rename, duplicate and delete operations.
- Added project-wide text search and active-file replace-all.
- Added built-in multi-file Python and automation templates.
- Added ZIP import/export for project backup and migration.
- Added archive path traversal, symbolic-link, file-count and size validation.
- Added bounded ZIP decompression and safe support for `.github` workflow folders.
- Added validation against symlinked folder parents and safer project templates.
- Added Python syntax checking without executing code.
- Improved local runner project import-path support and restoration of process arguments/path.
- Expanded automated tests and enabled CI builds on `feature/**` branches.
- Documented the local execution security limitation.

## Known limitations

- This release uses Flet CodeEditor; it is not CodeMirror 6.
- The code runner still executes trusted scripts in the app process and is not a sandbox.
- No embedded independent Python distribution, general Android pip manager, AI provider, Git remote integration or in-app remote build manager is shipped yet.
