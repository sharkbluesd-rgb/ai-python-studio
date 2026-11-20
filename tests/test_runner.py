import tempfile
import unittest
from pathlib import Path
import sys

from runner import execute_python


class RunnerTests(unittest.TestCase):
    def test_captures_printed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "main.py"
            result, success = execute_python("print('hello runner')", str(script))
        self.assertTrue(success)
        self.assertEqual(result.strip(), "hello runner")

    def test_returns_traceback_for_invalid_code(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "main.py"
            result, success = execute_python("raise ValueError('broken')", str(script))
        self.assertFalse(success)
        self.assertIn("ValueError: broken", result)

    def test_imports_modules_from_project_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "helper.py").write_text("VALUE = 42\n", encoding="utf-8")
            script = project / "main.py"
            result, success = execute_python("import helper\nprint(helper.VALUE)", str(script))
        self.assertTrue(success)
        self.assertEqual(result.strip(), "42")

    def test_restores_sys_path(self):
        with tempfile.TemporaryDirectory() as directory:
            before = list(sys.path)
            execute_python("pass", str(Path(directory) / "main.py"))
            self.assertEqual(sys.path, before)


if __name__ == "__main__":
    unittest.main()
