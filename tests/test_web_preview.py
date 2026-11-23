import unittest
import inspect

import web_preview

from web_preview import (
    build_skill_context,
    configure_arabic_page,
    select_skill_documents,
    validate_python_source,
)


CATALOG = [
    {
        "name": "flet-web-runtime-debugging",
        "label_ar": "تشخيص Flet Web",
        "description": "Flet browser loading splash blank page",
        "content": "تشخيص شاشة سوداء وشعار التحميل وأخطاء المتصفح",
    },
    {
        "name": "github-pages-deployment",
        "label_ar": "نشر Pages",
        "description": "GitHub Pages deployment and 404",
        "content": "base path artifact workflow deploy",
    },
    {
        "name": "python-debugging",
        "label_ar": "تصحيح Python",
        "description": "Python tracebacks runtime failures",
        "content": "تصحيح أخطاء بايثون",
    },
]


class WebPreviewValidationTests(unittest.TestCase):
    def test_browser_preview_avoids_custom_flutter_editor_extension(self):
        source = inspect.getsource(web_preview)
        self.assertNotIn("import flet_code_editor", source)
        self.assertIn("editor = ft.TextField(", source)

    def test_arabic_web_theme_loads_font_for_light_and_dark_modes(self):
        class FakePage:
            pass

        page = FakePage()
        configure_arabic_page(page)
        self.assertIn("Amiri", page.fonts)
        self.assertTrue(page.fonts["Amiri"].endswith("/Amiri-Regular.ttf"))
        self.assertEqual(page.theme.font_family, "Amiri")
        self.assertEqual(page.dark_theme.font_family, "Amiri")

    def test_valid_python_source(self):
        valid, message = validate_python_source("print('hello')\n")
        self.assertTrue(valid)
        self.assertIn("سليم", message)

    def test_invalid_python_source_reports_location(self):
        valid, message = validate_python_source("def broken(:\n    pass\n")
        self.assertFalse(valid)
        self.assertIn("السطر 1", message)

    def test_non_string_source_is_rejected(self):
        valid, message = validate_python_source(None)
        self.assertFalse(valid)
        self.assertIn("غير صالح", message)

    def test_web_runtime_skill_selected_for_blank_screen(self):
        result = select_skill_documents("Flet شاشة سوداء شعار التحميل", CATALOG)
        self.assertTrue(result)
        self.assertEqual(result[0]["name"], "flet-web-runtime-debugging")

    def test_pages_skill_selected_for_404(self):
        result = select_skill_documents("GitHub Pages deployment 404", CATALOG)
        self.assertTrue(result)
        self.assertEqual(result[0]["name"], "github-pages-deployment")

    def test_skill_context_has_untrusted_boundary_and_limit(self):
        context = build_skill_context("Flet شاشة سوداء", CATALOG, max_chars=1000)
        self.assertIn("غير موثوقة", context)
        self.assertLessEqual(len(context), 1000)
