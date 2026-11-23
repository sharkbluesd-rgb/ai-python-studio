import unittest

from web_preview import validate_python_source


class WebPreviewValidationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
