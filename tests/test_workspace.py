import tempfile
import unittest
from pathlib import Path

from workspace import WorkspaceError, WorkspaceStore


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = WorkspaceStore(Path(self.temp_dir.name) / "appdata")
        self.project_id = self.store.list_projects()[0]["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_project_and_file_are_created(self):
        self.assertIn("main.py", self.store.list_files(self.project_id))
        self.assertIn("Hello", self.store.read_file(self.project_id, "main.py"))

    def test_file_changes_survive_new_store_instance(self):
        self.store.write_file(self.project_id, "main.py", "print(123)\n")
        reopened = WorkspaceStore(Path(self.temp_dir.name) / "appdata")
        self.assertEqual(reopened.read_file(self.project_id, "main.py"), "print(123)\n")

    def test_create_and_switch_project(self):
        new_id = self.store.create_project("Demo Project")
        self.assertNotEqual(new_id, self.project_id)
        self.assertEqual(self.store.list_files(new_id), ["main.py"])

    def test_duplicate_project_name_gets_unique_id(self):
        first = self.store.create_project("Practice")
        second = self.store.create_project("Practice")
        self.assertNotEqual(first, second)

    def test_supports_arabic_project_display_name(self):
        project_id = self.store.create_project("مشروعي الجديد")
        project = next(item for item in self.store.list_projects() if item["id"] == project_id)
        self.assertEqual(project["name"], "مشروعي الجديد")

    def test_reject_path_traversal_file_name(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, "../outside.py")

    def test_reject_non_python_file(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, "notes.txt")

    def test_prevent_deleting_last_file(self):
        with self.assertRaises(WorkspaceError):
            self.store.delete_file(self.project_id, "main.py")

    def test_delete_and_rename_file(self):
        self.store.create_file(self.project_id, "helper.py")
        renamed = self.store.rename_file(self.project_id, "helper.py", "utils.py")
        self.assertEqual(renamed, "utils.py")
        self.assertIn("utils.py", self.store.list_files(self.project_id))
        self.store.delete_file(self.project_id, "utils.py")
        self.assertNotIn("utils.py", self.store.list_files(self.project_id))

    def test_reject_oversized_file(self):
        with self.assertRaises(WorkspaceError):
            self.store.write_file(self.project_id, "main.py", "x" * (512 * 1024 + 1))

    def test_remember_active_project_and_file(self):
        self.store.create_file(self.project_id, "tools.py")
        self.store.save_settings(self.project_id, "tools.py")
        reopened = WorkspaceStore(Path(self.temp_dir.name) / "appdata")
        self.assertEqual(
            reopened.load_settings(),
            {"active_project": self.project_id, "active_file": "tools.py"},
        )


if __name__ == "__main__":
    unittest.main()
