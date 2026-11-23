---
name: frontend-ui-engineering
description: Use when building or fixing polished, accessible, responsive Flet interfaces, especially Android-first layouts, Arabic RTL screens, navigation, forms, editor panels, and web preview UI.
---

# Frontend UI Engineering for Flet

Build interfaces that are clear, consistent, accessible, and practical on small Android screens. Follow the repository's pinned Flet version and existing visual language; never assume APIs from a different Flet release.

## Before editing

1. Inspect nearby screens and shared components.
2. Read the pinned dependency version and official documentation for the exact API.
3. Identify the target device sizes, navigation flow, loading/error/empty states, and keyboard behavior.
4. Preserve working interactions and avoid replacing real functionality with decorative mock controls.

## Mobile-first layout

- Design for narrow portrait screens first, then adapt to tablets and desktop.
- Keep primary actions reachable, touch targets comfortable, and important content visible without excessive scrolling.
- Use responsive layout primitives and avoid fixed widths that overflow on small devices.
- Handle Android keyboard appearance, safe areas, orientation changes, and long text.
- Provide loading, empty, success, and recoverable error states.

## Arabic and RTL

- Set RTL at the page or screen level where appropriate.
- Right-align Arabic labels, helper text, and prose.
- Keep code editors, paths, tokens, URLs, terminal output, and technical identifiers left-to-right.
- Test mixed Arabic/English strings, punctuation, numbers, and cursor movement.
- Use a legible Arabic font with a reliable loading fallback; do not make the interface unusable when the remote font is unavailable.
- Verify both light and dark themes.

## Accessibility and interaction

- Give every interactive control a clear label and visible state.
- Preserve keyboard navigation and focus behavior where supported.
- Do not communicate status through color alone.
- Disable or guard actions while operations are running; show progress and actionable errors.
- Ensure every visible button performs its advertised action.
- Use confirmation for destructive actions and preserve user data on recoverable failures.

## Flet compatibility and verification

- Check the installed Flet version before using a property, event, or control.
- Do not copy Flutter or web-only APIs into Flet without verifying support.
- Add focused tests for layout configuration and callback behavior where testable.
- Run the repository test suite and compile checks.
- For web changes, test the actual deployed preview in a mobile browser; for Android changes, verify a real APK build and device behavior.
- Capture screenshots or logs when visual behavior cannot be asserted automatically.

Do not claim visual quality or accessibility compliance based only on source inspection.
