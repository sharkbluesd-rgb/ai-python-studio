"""Real-browser smoke test for the isolated Flet CodeEditor web build."""
from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


URL = os.environ.get(
    "FLET_EDITOR_URL",
    "http://127.0.0.1:8765/ai-python-studio/flet-editor/",
)
STARTUP_TIMEOUT_MS = 180_000


def main() -> int:
    page_errors: list[str] = []
    console_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.url}: {request.failure}"
            ),
        )

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        if response is None or response.status >= 400:
            status = None if response is None else response.status
            browser.close()
            raise SystemExit(
                f"Flet editor returned an invalid HTTP response: {status}"
            )

        try:
            page.wait_for_function(
                "() => document.title.endsWith('READY') "
                "|| document.title.endsWith('ERROR')",
                timeout=STARTUP_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            diagnostics = {
                "url": page.url,
                "title": page.title(),
                "page_errors": page_errors,
                "console_errors": console_errors[-30:],
                "failed_requests": failed_requests[-30:],
                "canvas_count": page.locator("canvas").count(),
                "body_text": page.locator("body").inner_text(
                    timeout=10_000
                )[:1500],
            }
            browser.close()
            raise SystemExit(
                "Flet Python app did not finish startup (the page may be "
                "stuck on the splash screen):\n"
                + json.dumps(diagnostics, ensure_ascii=False)
            )

        title = page.title()
        if not title.endswith("READY"):
            details = page.locator("body").inner_text(timeout=10_000)[:1500]
            browser.close()
            raise SystemExit(
                "Flet app reported a startup error:\n"
                + json.dumps(
                    {
                        "title": title,
                        "details": details,
                        "page_errors": page_errors,
                        "console_errors": console_errors[-30:],
                        "failed_requests": failed_requests[-30:],
                    },
                    ensure_ascii=False,
                )
            )

        if page_errors or console_errors or failed_requests:
            browser.close()
            raise SystemExit(
                "Browser errors occurred while rendering the Flet app:\n"
                + json.dumps(
                    {
                        "page_errors": page_errors,
                        "console_errors": console_errors[-30:],
                        "failed_requests": failed_requests[-30:],
                    },
                    ensure_ascii=False,
                )
            )

        result = {
            "status": "passed",
            "title": title,
            "canvas_count": page.locator("canvas").count(),
            "url": page.url,
        }
        browser.close()
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
