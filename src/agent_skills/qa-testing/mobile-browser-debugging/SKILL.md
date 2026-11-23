---
name: mobile-browser-debugging
description: Reproduce and diagnose mobile browser and WebView failures using responsive checks, console logs, network inspection, cache controls, and interaction testing.
---

# Mobile Browser Debugging

Use this skill when a web preview works on desktop but fails on Android, remains blank, has clipped controls, or cannot be interacted with reliably.

## Workflow

1. Record device class, Android version, browser/WebView version, viewport, orientation, zoom, and network type. Do not assume all Android browsers behave identically.
2. Reproduce in a clean session. Compare normal tab, private tab, and a second supported browser to identify cache or browser-specific behavior.
3. Inspect remote debugging tools when possible. Capture console errors, failed requests, response status/MIME, and JavaScript exceptions. If DevTools are unavailable, create a minimal diagnostic panel with safe error summaries.
4. Check viewport configuration, safe-area insets, device pixel ratio, touch target size, scroll containers, keyboard resizing, and orientation changes.
5. Verify controls respond to touch and do not rely exclusively on hover or mouse-only events.
6. Check font loading, RTL layout, long Arabic labels, text scaling, and overflow at narrow widths.
7. Test slow or interrupted networks. Provide meaningful loading, retry, offline, and error states; never leave a spinner running indefinitely.
8. Compare browser and WebView behavior separately. Do not assume a WebView supports the same APIs, storage, downloads, or permissions as Chrome.
9. Fix one root cause at a time and add a regression test or documented manual test.
10. Re-test on the actual target phone after deployment.

## Mobile acceptance checklist

- [ ] First screen renders without horizontal scrolling.
- [ ] Loading either completes or exposes a useful error and retry action.
- [ ] Touch targets are comfortably tappable and spaced.
- [ ] Keyboard does not cover the active editor or primary action.
- [ ] RTL and Arabic text remain readable at system font scaling.
- [ ] Orientation and browser back navigation do not corrupt app state.
- [ ] No essential workflow depends on hover.
- [ ] Network failures are recoverable.
- [ ] No secrets or personal data appear in diagnostics.
