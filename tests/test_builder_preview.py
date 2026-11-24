"""Regression checks for the browser-first Python Studio Mobile IDE."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-ide"


class PythonStudioWebTests(unittest.TestCase):
    def test_web_shell_exposes_real_ide_controls(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        for marker in ('id="editor"', 'id="run-button"', 'id="stop-button"',
                       'id="file-list"', 'id="editor-tabs"', 'id="package-install-button"',
                       'id="terminal-form"', 'id="programmer-keyboard"'):
            self.assertIn(marker, html)
        self.assertIn("PYTHON STUDIO MOBILE", html)
        self.assertNotIn("Flet APK Studio", html)

    def test_code_editor_is_codemirror_with_python_language_support(self):
        script = (WEB / "src/main.js").read_text(encoding="utf-8")
        self.assertIn('from "codemirror"', script)
        self.assertIn('from "@codemirror/lang-python"', script)
        self.assertIn("basicSetup", script)
        self.assertIn("globalCompletion", script)
        self.assertIn("openSearchPanel", script)

    def test_pyodide_runs_in_a_dedicated_worker(self):
        worker = (WEB / "src/python.worker.js").read_text(encoding="utf-8")
        adapter = (WEB / "src/runtime-adapter.js").read_text(encoding="utf-8")
        self.assertIn("loadPyodide", worker)
        self.assertIn("runPythonAsync", worker)
        self.assertIn('new Worker(new URL("./python.worker.js"', adapter)
        self.assertIn("terminate()", adapter)
        self.assertIn("setInterruptBuffer", worker)
        self.assertIn("setStdin", worker)

    def test_projects_are_persisted_in_indexeddb_and_paths_are_guarded(self):
        storage = (WEB / "src/storage.js").read_text(encoding="utf-8")
        self.assertIn("indexedDB.open", storage)
        self.assertIn("normalizeProjectPath", storage)
        self.assertIn("MAX_PROJECT_FILES", storage)
        self.assertIn("MAX_FILE_BYTES", storage)

    def test_mobile_layout_and_programmer_keyboard_exist(self):
        css = (WEB / "src/style.css").read_text(encoding="utf-8")
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("@media(orientation:landscape)", css)
        self.assertIn('data-key="TAB"', html)
        self.assertIn('data-key="ARROWLEFT"', html)

    def test_offline_cache_and_cross_origin_isolation_configuration(self):
        worker = (WEB / "public/sw.js").read_text(encoding="utf-8")
        headers = (WEB / "public/_headers").read_text(encoding="utf-8")
        self.assertIn("caches.open", worker)
        self.assertIn("cdn.jsdelivr.net", worker)
        self.assertIn("Cross-Origin-Opener-Policy", headers)
        self.assertIn("Cross-Origin-Embedder-Policy", headers)


if __name__ == "__main__":
    unittest.main()
