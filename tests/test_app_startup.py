"""Import-level smoke tests for the Flet application entry point."""

import unittest

import main


class AppStartupSmokeTests(unittest.TestCase):
    def test_main_entrypoint_is_importable_and_callable(self):
        self.assertTrue(callable(main.main))


if __name__ == "__main__":
    unittest.main()
