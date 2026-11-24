"""Regression checks for the live browser app shell."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-preview-static"


class BuilderPreviewTests(unittest.TestCase):
    def test_web_ui_is_connected_to_real_api_routes(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        script = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="project-zip"', html)
        self.assertIn('id="oauth-client-id"', html)
        self.assertIn("/api/projects/import", script)
        self.assertIn("/api/auth/github/device/start", script)
        self.assertIn("/api/build/start", script)
        self.assertIn("/api/build/status", script)
        self.assertIn("/api/build/download", script)
        self.assertNotIn("معاينة تصميم فقط", html)
        self.assertNotIn("لم يبدأ أي بناء", script)

    def test_web_ui_keeps_secret_out_of_browser_storage(self):
        script = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("credentials: \"same-origin\"", script)
        self.assertIn("X-CSRF-Token", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)

    def test_preview_has_mobile_layout_rules(self):
        css = (WEB / "style.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:650px)", css)
        self.assertIn("grid-template-columns:1fr", css)


if __name__ == "__main__":
    unittest.main()
