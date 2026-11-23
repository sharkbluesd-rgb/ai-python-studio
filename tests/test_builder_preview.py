"""Regression checks for the static Flet APK Studio preview."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "web-preview-static"


class BuilderPreviewTests(unittest.TestCase):
    def test_preview_presents_apk_builder_not_an_ide(self):
        html = (PREVIEW / "index.html").read_text(encoding="utf-8")
        script = (PREVIEW / "app.js").read_text(encoding="utf-8")
        self.assertIn("Flet APK Studio", html)
        self.assertIn("رفع المشروع وبدء بناء APK", html)
        self.assertIn('id="project-zip"', html)
        self.assertIn("GitHub Actions", html)
        self.assertNotIn("CodeEditor", html + script)
        self.assertNotIn('id="source-editor"', html)

    def test_preview_discloses_that_build_is_not_live(self):
        html = (PREVIEW / "index.html").read_text(encoding="utf-8")
        script = (PREVIEW / "app.js").read_text(encoding="utf-8")
        self.assertIn("معاينة تصميم فقط", html)
        self.assertIn("لم يبدأ أي بناء", script)

    def test_preview_has_mobile_layout_rules(self):
        css = (PREVIEW / "style.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:650px)", css)
        self.assertIn("grid-template-columns:1fr", css)


if __name__ == "__main__":
    unittest.main()
