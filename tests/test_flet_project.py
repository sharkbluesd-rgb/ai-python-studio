import tempfile
import unittest
from pathlib import Path

from flet_project import configure_flet_project, validate_application_id, validate_flet_project


class FletProjectConfigurationTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        (root / "src").mkdir()
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / "src" / "main.py").write_text("import flet as ft\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n'
            '[tool.flet]\nproduct = "Demo"\norg = "com.example.demo"\n'
            '[tool.flet.app]\npath = "src"\n',
            encoding="utf-8",
        )
        (root / ".github" / "workflows" / "build-apk.yml").write_text(
            "on:\n  workflow_dispatch:\nsteps:\n  - name: Build APK\n    with:\n"
            "      target: apk\n      build-version: '0.1.0'\n      build-number: 1\n"
            "      uses: flet-dev/flet-build-action@v1\n"
            "  - uses: actions/upload-artifact@v4\n",
            encoding="utf-8",
        )
        return root

    def test_validates_android_application_id(self):
        self.assertEqual(validate_application_id("com.example"), "com.example")
        self.assertEqual(validate_application_id("com.example.my_app"), "com.example.my_app")

    def test_rejects_invalid_application_ids(self):
        for value in ("Com.example.app", "com..app", "com.example-app", "com.1app"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_application_id(value)

    def test_configures_project_and_build_workflow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            configure_flet_project(
                root, app_name="تطبيقي", application_id="org.demo.mobile",
                version="2.3.1", build_number="42",
            )
            config = (root / "pyproject.toml").read_text(encoding="utf-8")
            workflow = (root / ".github" / "workflows" / "build-apk.yml").read_text(encoding="utf-8")
            self.assertIn('version = "2.3.1"', config)
            self.assertIn('product = "تطبيقي"', config)
            self.assertIn('org = "org.demo.mobile"', config)
            self.assertIn("build-version: '2.3.1'", workflow)
            self.assertIn("build-number: 42", workflow)
            self.assertEqual(validate_flet_project(root), [])

    def test_rejects_invalid_values_without_changing_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            original = (root / "pyproject.toml").read_text(encoding="utf-8")
            with self.assertRaises(ValueError):
                configure_flet_project(
                    root, app_name="Demo", application_id="Bad.ID",
                    version="latest", build_number="0",
                )
            self.assertEqual((root / "pyproject.toml").read_text(encoding="utf-8"), original)

    def test_prebuild_requires_manual_dispatch_and_apk_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            workflow_path = root / ".github" / "workflows" / "build-apk.yml"
            original = workflow_path.read_text(encoding="utf-8")
            workflow_path.write_text(original.replace("  workflow_dispatch:\\n", ""), encoding="utf-8")
            issues = validate_flet_project(root)
            self.assertTrue(any("workflow_dispatch" in issue for issue in issues))

    def test_prebuild_validation_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertGreaterEqual(len(validate_flet_project(root)), 1)


if __name__ == "__main__":
    unittest.main()
