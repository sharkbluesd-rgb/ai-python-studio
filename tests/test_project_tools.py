import tempfile
import unittest
from pathlib import Path

from project_tools import analyze_project, format_analysis_report, inspect_python_source
from workspace import WorkspaceStore


class ProjectToolsTests(unittest.TestCase):
    def test_inspector_detects_syntax_error(self):
        result = inspect_python_source("def broken(:\n pass", "broken.py")
        self.assertFalse(result["valid_syntax"])
        self.assertEqual(result["diagnostics"][0]["code"], "SYNTAX_ERROR")

    def test_inspector_counts_structure_and_dynamic_execution(self):
        source = """\ndef greet(name):\n    return name\n\nclass Demo:\n    pass\n\neval('1 + 1')\n"""
        result = inspect_python_source(source, "main.py")
        self.assertTrue(result["valid_syntax"])
        self.assertEqual(result["functions"], 1)
        self.assertEqual(result["classes"], 1)
        self.assertIn("DYNAMIC_EXECUTION", [item["code"] for item in result["diagnostics"]])

    def test_inspector_flags_shell_true_and_hardcoded_secret(self):
        source = "API_KEY = 'very-secret-value'\nsubprocess.run('echo hi', shell=True)\n"
        result = inspect_python_source(source, "main.py")
        codes = {item["code"] for item in result["diagnostics"]}
        self.assertIn("POSSIBLE_SECRET", codes)
        self.assertIn("SHELL_TRUE", codes)

    def test_analyze_project_returns_metrics_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(Path(directory) / "data")
            project_id = store.list_projects()[0]["id"]
            store.write_file(project_id, "main.py", "# TODO\ndef run():\n    print('ok')\n")
            report = analyze_project(store, project_id)
            self.assertEqual(report["metrics"]["python_files"], 1)
            self.assertEqual(report["metrics"]["functions"], 1)
            self.assertEqual(report["metrics"]["todos"], 1)
            rendered = format_analysis_report("Test", report)
            self.assertIn("تقرير فحص المشروع", rendered)
            self.assertIn("TODO/FIXME", rendered)


if __name__ == "__main__":
    unittest.main()
