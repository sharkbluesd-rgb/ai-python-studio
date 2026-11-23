"""Startup smoke tests for the Flet app's initial UI construction."""

import os
import tempfile
import unittest
from unittest.mock import patch

import main


class FakePage:
    def __init__(self):
        self.services = []
        self.controls = []
        self.update_count = 0
        self.clean_count = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def clean(self):
        self.clean_count += 1
        self.controls.clear()

    def update(self):
        self.update_count += 1


class AppStartupSmokeTests(unittest.TestCase):
    def test_main_builds_initial_editor_screen(self):
        with tempfile.TemporaryDirectory() as storage:
            page = FakePage()
            with patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": storage}):
                main.main(page)

        self.assertEqual(page.title, "AI Python Studio")
        self.assertEqual(len(page.controls), 1)
        self.assertGreaterEqual(page.update_count, 2)
        self.assertEqual(page.clean_count, 1)
        self.assertTrue(page.services)


if __name__ == "__main__":
    unittest.main()
