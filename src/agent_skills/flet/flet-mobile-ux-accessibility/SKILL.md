---
name: flet-mobile-ux-accessibility
description: Design and review responsive, accessible Flet interfaces for Android phones, including RTL, touch interaction, keyboard behavior, loading states, and narrow screens.
---

# Flet Mobile UX and Accessibility

Use this skill when designing or reviewing Flet screens intended primarily for Android phones.

## Design workflow

1. Start with the smallest supported phone viewport and define a clear single-column layout. Add wider layouts only when space permits.
2. Establish consistent spacing, typography, color, and component rules. Avoid arbitrary per-screen styling.
3. Use responsive layout primitives and allow content to scroll; avoid fixed heights that clip content on short screens.
4. Respect system insets and ensure bottom navigation and primary actions are not hidden behind Android system bars or the keyboard.
5. Make touch controls large and clearly separated. Provide labels and visible states; do not communicate status through color alone.
6. Support RTL explicitly for Arabic screens while keeping code, paths, logs, and technical identifiers readable in their natural direction.
7. Design loading, empty, success, error, offline, and retry states for every important asynchronous workflow.
8. Preserve editor usability: readable monospace font, horizontal code scrolling where appropriate, clear active-file state, and safe keyboard handling.
9. Use semantic labels for icon-only controls. Ensure sufficient contrast and support text scaling.
10. Test at multiple screen widths, font scales, and orientations on a real device where possible.

## Review checklist

- [ ] No clipped content or accidental horizontal page scrolling.
- [ ] Primary actions are reachable with one hand where practical.
- [ ] Bottom controls account for system navigation insets.
- [ ] Dialogs fit short screens and can be dismissed accessibly.
- [ ] Arabic RTL labels, mixed text, code, and file paths render correctly.
- [ ] Buttons have meaningful labels and disabled/loading states.
- [ ] Errors explain what happened and what the user can do next.
- [ ] Focus order and keyboard navigation are sensible.
- [ ] Contrast and text scaling remain usable.

Do not redesign unrelated screens when fixing a focused usability bug. Keep behavior stable and verify with screenshots or device tests.
