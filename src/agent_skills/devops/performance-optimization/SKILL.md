---
name: performance-optimization
description: Use when diagnosing slow Flet startup, web preview loading, APK size, Python runtime responsiveness, memory use, or inefficient application workflows. Measure before optimizing.
---

# Performance Optimization for AI Python Studio

Measure first. Do not add caching, concurrency, or complexity based on guesses.

## Establish a baseline

Record the device, OS, Python/Flet versions, build mode, network conditions, test input, and measurement method. Compare the same scenario before and after a change.

Useful signals include:
- App startup and first interactive screen time
- Web preview download size and time to first usable screen
- APK size and build duration
- UI frame drops and long-running callbacks
- Python process memory and CPU
- Package installation time and dependency count
- AI request latency, response size, and timeout frequency

## Diagnose by layer

### Flet UI
- Keep event handlers short; move expensive work off the UI event path using supported async/background patterns.
- Avoid rebuilding large control trees unnecessarily.
- Paginate or virtualize long file, package, and skill lists when supported.
- Provide progress and cancellation for long tasks.
- Test on a real low-to-mid-range Android device, not only desktop.

### Web preview
- Inspect network waterfalls and browser console before changing assets.
- Avoid duplicate large assets and unnecessary fonts.
- Load non-critical content lazily when compatible with Flet's runtime.
- Test cold-cache and warm-cache loads separately.
- Verify the deployed base path and static assets before attributing failures to performance.

### Python runtime and packages
- Profile the actual workload before changing algorithms.
- Avoid loading optional heavy modules until their feature is used.
- Bound output buffers, file scans, subprocess duration, and concurrent jobs.
- Prefer compatible wheels and the project's supported dependency set; do not upgrade packages blindly.

### Build pipeline
- Cache only deterministic dependencies with correct cache keys.
- Keep build artifacts separate from source and do not commit generated APKs unless requested.
- Compare clean and cached builds to detect stale-cache problems.

## Verify improvements

1. Repeat the baseline measurement under the same conditions.
2. Run focused tests and the full relevant test suite.
3. Check memory, responsiveness, and correctness for regressions.
4. Record measured before/after values and remaining limitations.

Never invent benchmark numbers or promise a speedup that was not measured.
