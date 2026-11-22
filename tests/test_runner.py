import tempfile
import threading
import unittest
from pathlib import Path
import sys

from runner import (
    MAX_CAPTURE_CHARS,
    ExecutionControl,
    check_python,
    execute_python,
)


class RunnerTests(unittest.TestCase):

    def test_relative_file_io_uses_project_root_and_restores_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            (project / "src").mkdir(parents=True)
            (project / "notes.txt").write_text("project data", encoding="utf-8")
            script = project / "src" / "main.py"
            original_cwd = Path.cwd()
            result, success = execute_python(
                "with open('notes.txt', encoding='utf-8') as stream:\n"
                "    print(stream.read())\n",
                str(script),
                str(project),
            )
            self.assertEqual(Path.cwd(), original_cwd)
        self.assertTrue(success)
        self.assertEqual(result.strip(), "project data")

    def test_working_directory_is_restored_after_script_error(self):
        with tempfile.TemporaryDirectory() as directory:
            original_cwd = Path.cwd()
            result, success = execute_python(
                "raise RuntimeError('failure')",
                str(Path(directory) / "main.py"),
                directory,
            )
            self.assertEqual(Path.cwd(), original_cwd)
        self.assertFalse(success)
        self.assertIn("RuntimeError: failure", result)


    def test_runs_unittest_discovery_from_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            test_dir = project / "tests"
            test_dir.mkdir()
            (test_dir / "test_sample.py").write_text(
                "import unittest\n"
                "class SampleTests(unittest.TestCase):\n"
                "    def test_success(self):\n"
                "        self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )
            from runner import execute_unittest_discovery
            output, success = execute_unittest_discovery(str(project))
        self.assertTrue(success)
        self.assertIn("test_success", output)
        self.assertIn("النتيجة: 1 اختبار", output)

    def test_rejects_test_directory_traversal(self):
        from runner import execute_unittest_discovery
        output, success = execute_unittest_discovery(".", "../outside")
        self.assertFalse(success)
        self.assertIn("غير صالح", output)

    def test_reports_missing_test_directory(self):
        from runner import execute_unittest_discovery
        with tempfile.TemporaryDirectory() as directory:
            output, success = execute_unittest_discovery(directory)
        self.assertFalse(success)
        self.assertIn("لم يتم العثور", output)

    def test_rejects_windows_test_directory_path(self):
        from runner import execute_unittest_discovery
        output, success = execute_unittest_discovery(".", r"..\\outside")
        self.assertFalse(success)
        self.assertIn("غير صالح", output)

    def test_failing_unittest_suite_returns_failure(self):
        from runner import execute_unittest_discovery
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            test_dir = project / "tests"
            test_dir.mkdir()
            (test_dir / "test_failure.py").write_text(
                "import unittest\n"
                "class FailingTests(unittest.TestCase):\n"
                "    def test_failure(self):\n"
                "        self.assertEqual(1, 2)\n",
                encoding="utf-8",
            )
            output, success = execute_unittest_discovery(str(project))
        self.assertFalse(success)
        self.assertIn("FAILED", output)
        self.assertIn("test_failure", output)

    def test_passes_script_arguments_and_restores_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            before = list(sys.argv)
            script = Path(directory) / "main.py"
            result, success = execute_python(
                "import sys\nprint('|'.join(sys.argv[1:]))",
                str(script),
                script_args=["input.csv", "--verbose", "two words"],
            )
            self.assertEqual(sys.argv, before)
        self.assertTrue(success)
        self.assertEqual(result.strip(), "input.csv|--verbose|two words")

    def test_captures_printed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "main.py"
            result, success = execute_python("print('hello runner')", str(script))
        self.assertTrue(success)
        self.assertEqual(result.strip(), "hello runner")

    def test_output_capture_is_bounded(self):
        chunks = []
        with tempfile.TemporaryDirectory() as directory:
            result, success = execute_python(
                f"print('x' * {MAX_CAPTURE_CHARS + 100})",
                str(Path(directory) / "large_output.py"),
                output_callback=chunks.append,
            )
        self.assertTrue(success)
        self.assertIn("تم اختصار الإخراج", result)
        self.assertIn("تم اختصار الإخراج", "".join(chunks))
        self.assertLessEqual(
            len("".join(chunks)),
            MAX_CAPTURE_CHARS + len("\n[تم اختصار الإخراج بعد بلوغ الحد الآمن]"),
        )

    def test_returns_traceback_for_invalid_runtime_code(self):
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

    def test_imports_modules_from_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "utils.py").write_text("VALUE = 'root'\n", encoding="utf-8")
            script = project / "src" / "main.py"
            script.parent.mkdir()
            result, success = execute_python(
                "import utils\nprint(utils.VALUE)", str(script), str(project)
            )
        self.assertTrue(success)
        self.assertEqual(result.strip(), "root")

    def test_restores_sys_path_and_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            before_path = list(sys.path)
            before_argv = list(sys.argv)
            execute_python("import sys\nsys.argv.append('changed')", str(Path(directory) / "main.py"))
            self.assertEqual(sys.path, before_path)
            self.assertEqual(sys.argv, before_argv)

    def test_syntax_error_callback_ends_with_real_newline(self):
        chunks = []
        with tempfile.TemporaryDirectory() as directory:
            result, success = execute_python(
                "def broken(:",
                str(Path(directory) / "broken.py"),
                output_callback=chunks.append,
            )
        self.assertFalse(success)
        self.assertEqual(chunks, [result + "\n"])
        self.assertFalse(chunks[0].endswith("\\n"))

    def test_syntax_checker_accepts_valid_source(self):
        valid, message = check_python("print('ok')", "main.py")
        self.assertTrue(valid)
        self.assertIn("لا توجد أخطاء", message)

    def test_syntax_checker_reports_line_number(self):
        valid, message = check_python("def broken(:\n    pass", "broken.py")
        self.assertFalse(valid)
        self.assertIn("السطر 1", message)


if __name__ == "__main__":
    unittest.main()


class StreamingRunnerTests(unittest.TestCase):
    def test_streams_printed_output(self):
        chunks = []
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "main.py"
            result, success = execute_python(
                "print('live output')",
                str(script),
                output_callback=chunks.append,
            )
        self.assertTrue(success)
        self.assertIn("live output", "".join(chunks))
        self.assertIn("live output", result)

    def test_streams_runtime_traceback(self):
        chunks = []
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "main.py"
            result, success = execute_python(
                "raise ValueError('streamed error')",
                str(script),
                output_callback=chunks.append,
            )
        self.assertFalse(success)
        self.assertIn("ValueError: streamed error", "".join(chunks))
        self.assertIn("ValueError: streamed error", result)


class ExecutionControlTests(unittest.TestCase):
    def test_cancels_infinite_python_loop(self):
        control = ExecutionControl(timeout_seconds=None)
        timer = threading.Timer(0.05, control.cancel)
        timer.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                result, success = execute_python(
                    "while True:\n    pass",
                    str(Path(directory) / "loop.py"),
                    control=control,
                )
        finally:
            timer.cancel()
        self.assertFalse(success)
        self.assertIn("تم إيقاف التنفيذ", result)

    def test_times_out_infinite_python_loop(self):
        control = ExecutionControl(timeout_seconds=0.05)
        with tempfile.TemporaryDirectory() as directory:
            result, success = execute_python(
                "while True:\n    pass",
                str(Path(directory) / "loop.py"),
                control=control,
            )
        self.assertFalse(success)
        self.assertIn("انتهت مهلة التنفيذ", result)
        self.assertIn("0.05 ثانية", result)

    def test_normal_execution_still_works_with_control(self):
        control = ExecutionControl(timeout_seconds=5)
        with tempfile.TemporaryDirectory() as directory:
            result, success = execute_python(
                "print('controlled')",
                str(Path(directory) / "main.py"),
                control=control,
            )
        self.assertTrue(success)
        self.assertIn("controlled", result)
