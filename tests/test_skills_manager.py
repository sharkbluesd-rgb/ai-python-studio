from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skills_manager import SkillsError, SkillsManager, parse_skill_metadata


class SkillMetadataTests(unittest.TestCase):
    def test_parses_folded_description(self):
        text = "---\nname: python-helper\ndescription: >-\n  Helps write Python.\n  Includes tests.\n---\n\nBody"
        result = parse_skill_metadata(text, "development/python-helper/SKILL.md")
        self.assertEqual(result.name, "python-helper")
        self.assertEqual(result.description, "Helps write Python. Includes tests.")
        self.assertEqual(result.category, "development")

    def test_rejects_invalid_name(self):
        text = "---\nname: ../bad\ndescription: Bad\n---\nBody"
        with self.assertRaises(SkillsError):
            parse_skill_metadata(text)


class SkillsManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = SkillsManager()

    def test_select_skills_prefers_category_diversity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {
                "security/one/SKILL.md": "---\\nname: security-one\\ndescription: security review\\n---\\nSecurity guidance",
                "security/two/SKILL.md": "---\\nname: security-two\\ndescription: security audit\\n---\\nAudit guidance",
                "testing/three/SKILL.md": "---\\nname: testing-three\\ndescription: security testing\\n---\\nTesting guidance",
            }
            for relative, text in fixtures.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            manager = SkillsManager(root)
            selected = manager.select_skills("security", max_skills=2)
            self.assertEqual(len(selected), 2)
            self.assertEqual({item.category for item in selected}, {"security", "testing"})

    def test_select_skills_rejects_invalid_limit(self):
        with self.assertRaises(SkillsError):
            self.manager.select_skills("Python", max_skills=0)

    def test_bundled_catalog_contains_core_skills(self):
        names = {item.name for item in self.manager.list_skills()}
        self.assertIn("flet-mobile-development", names)
        self.assertIn("test-driven-development", names)
        self.assertIn("code-review", names)
        self.assertGreaterEqual(len(names), 17)
        self.assertIn("flet-web-runtime-debugging", names)
        self.assertIn("github-pages-deployment", names)
        self.assertIn("android-python-packaging", names)
        self.assertIn("github-actions-ci-debugging", names)
        self.assertIn("python-ide-runtime", names)
        self.assertIn("regression-testing", names)
        self.assertIn("security-and-hardening", names)
        self.assertIn("performance-optimization", names)
        self.assertIn("frontend-ui-engineering", names)

    def test_security_search_finds_hardening_skill(self):
        matches = self.manager.search("أمان حماية مفاتيح API", limit=5)
        self.assertTrue(matches)
        self.assertEqual(matches[0].name, "security-and-hardening")

    def test_flet_ui_search_finds_rtl_skill(self):
        matches = self.manager.search("Flet واجهة عربية RTL أندرويد", limit=5)
        self.assertTrue(matches)
        self.assertIn("frontend-ui-engineering", {item.name for item in matches})

    def test_flet_search_prioritises_flet_skill(self):
        matches = self.manager.search("Flet Android APK mobile editor", limit=5)
        self.assertTrue(matches)
        self.assertEqual(matches[0].name, "flet-mobile-development")

    def test_arabic_search_finds_python_android_guides(self):
        matches = self.manager.search("تصحيح أخطاء بايثون", limit=5)
        self.assertTrue(matches)
        self.assertEqual(matches[0].name, "python-debugging")

    def test_arabic_web_debugging_search_finds_flet_runtime_skill(self):
        matches = self.manager.search("شاشة سوداء شعار تحميل Flet ويب", limit=5)
        self.assertTrue(matches)
        self.assertEqual(matches[0].name, "flet-web-runtime-debugging")

    def test_pages_search_finds_deployment_skill(self):
        matches = self.manager.search("GitHub Pages 404 نشر الموقع", limit=5)
        self.assertTrue(matches)
        self.assertEqual(matches[0].name, "github-pages-deployment")

    def test_load_skill_returns_full_content(self):
        document = self.manager.get_skill("repo-recon")
        self.assertIn("Search before assuming", document.content)
        self.assertEqual(document.summary.name, "repo-recon")

    def test_context_is_bounded_and_marks_skills_untrusted(self):
        context = self.manager.build_context("Python Flet Android", max_skills=2, max_chars=6000)
        self.assertIn("غير موثوقة", context)
        self.assertIn("<skill_reference", context)
        self.assertLessEqual(len(context), 6000)

    def test_unknown_skill_is_rejected(self):
        with self.assertRaises(SkillsError):
            self.manager.get_skill("../outside")


class SkillsPathSafetyTests(unittest.TestCase):
    def test_symlinked_skill_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            external = Path(tmp) / "external"
            (external / "fake").mkdir(parents=True)
            (external / "fake" / "SKILL.md").write_text(
                "---\nname: fake-skill\ndescription: Fake\n---\nBody",
                encoding="utf-8",
            )
            root.mkdir()
            (root / "development").mkdir()
            try:
                (root / "development" / "fake").symlink_to(external / "fake", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks are not available in this environment.")
            manager = SkillsManager(root)
            self.assertEqual(manager.list_skills(), [])


if __name__ == "__main__":
    unittest.main()
