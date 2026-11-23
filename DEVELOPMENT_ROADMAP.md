# AI Python Studio — Two-Part Delivery Plan

Target branch: `feature/studio-2.0`  
Rule: finish Part 1 and stabilize it before changing the main editor screen for Part 2.

This plan deliberately separates the work by delivery priority, not by splitting the repository into two unrelated applications. Both parts remain in the same project and branch.

## Part 1 — Core mobile Python editor

**Priority: first. Goal: make the editor comfortable and reliable to use every day.**

### Included
- Mobile-first, responsive editor screen with the code area taking most of the available space.
- Arabic RTL application chrome, with source code, filenames, and paths kept LTR.
- Collapsible file explorer, hidden by default.
- Reliable tabs: open, switch, close, active-file indication, and safe save behavior.
- Small primary toolbar: Save, Run, Stop, Files, and More.
- Collapsible output / diagnostics panel.
- Preserve the installed editor extension features: Python highlighting, line numbers, folding, and autocomplete.
- Focused regression tests for editing, file navigation, persistence, and running scripts.

### Acceptance checklist
- [ ] Usable on a narrow Android screen without horizontal overflow.
- [ ] The editor remains the main visible surface; secondary panels open only when requested.
- [ ] Opening, switching, and closing tabs never silently loses saved content.
- [ ] Save, Run, Stop, and output/error states work and provide feedback.
- [ ] Existing project files and capabilities are preserved.
- [ ] Unit tests, static checks, and the Android build workflow pass.

### Main code areas
`src/main.py`, `src/editor_tabs.py`, related editor/workspace tests.

## Part 2 — Advanced tools, integrations, and release validation

**Priority: second. Start after Part 1's screen and navigation are stable.**

### Included
- Move secondary actions into a compact Tools / More area instead of crowding the editor.
- Verify and repair project search/replace, templates, ZIP import/export, project diagnostics, and package management.
- Verify GitHub Device Flow, repository operations, Actions dispatch/status/logs, and APK artifact validation.
- Verify the bundled Skills Library remains searchable and treats imported skill content as untrusted reference text.
- Keep AI provider setup optional and explicit. Do not advertise AI chat as operational until a real end-to-end provider test passes.
- Check actual Flet 1.1.2 and editor-extension web compatibility before attempting web deployment.
- Update documentation and release notes to reflect only tested behavior and known limitations.

### Acceptance checklist
- [ ] Every visible advanced action works and has clear success/error feedback.
- [ ] Search, import/export, diagnostics, package, and GitHub workflows have regression tests.
- [ ] Security checks and the full CI workflow pass.
- [ ] Android and web compatibility statements are backed by successful builds/tests.
- [ ] Known limitations are stated accurately: local `exec()` is not a sandbox; no native shell or full interactive debugger is included unless later implemented and tested.

### Main code areas
Existing project-tool, package, GitHub, skills, AI, test, and deployment modules. Avoid competing edits to the main editor layout while Part 1 is in progress.

## Working rules
1. Work only on `feature/studio-2.0`; do not modify `main`.
2. Finish Part 1 before broad Part 2 UI changes.
3. Inspect current code before adding a feature; prefer fixing and testing existing functionality over duplicating it.
4. Do not add dummy controls, fake data, or placeholder success messages.
5. Run targeted tests after each change, then the full CI workflow before calling a part complete.
6. A successful APK build alone does not prove that the web version is deployed or functional.

## GitHub work items
- Part 1: [Finish the mobile-first Python editor core](https://github.com/sharkbluesd-rgb/ai-python-studio/issues/1)
- Part 2: [Complete advanced tools, integrations, and release validation](https://github.com/sharkbluesd-rgb/ai-python-studio/issues/2)
