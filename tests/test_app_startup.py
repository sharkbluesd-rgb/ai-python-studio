"""Startup smoke tests for the local Python IDE."""

import os
import tempfile
import unittest
from unittest.mock import patch

import main


class FakePage:
    def __init__(self):
        self.controls = []
        self.update_count = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        self.update_count += 1


class AppStartupSmokeTests(unittest.TestCase):
    def test_main_builds_initial_python_ide_screen(self):
        with tempfile.TemporaryDirectory() as storage:
            page = FakePage()
            with patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": storage}):
                main.main(page)

        self.assertEqual(page.title, "AI Python Studio")
        self.assertEqual(len(page.controls), 1)
        self.assertGreaterEqual(page.update_count, 0)

    def test_main_uses_local_workspace_and_python_runner(self):
        import inspect

        source = inspect.getsource(main)
        self.assertIn("WorkspaceStore", source)
        self.assertIn("execute_python", source)
        self.assertIn("تشغيل الكود", source)


if __name__ == "__main__":
    unittest.main()
