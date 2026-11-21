import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from workspace import WorkspaceError, WorkspaceStore
from templates import TEMPLATES


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "appdata"
        self.store = WorkspaceStore(self.root)
        self.project_id = self.store.list_projects()[0]["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_project_and_file_are_created(self):
        self.assertIn("main.py", self.store.list_files(self.project_id))
        self.assertIn("Hello", self.store.read_file(self.project_id, "main.py"))

    def test_file_changes_survive_new_store_instance(self):
        self.store.write_file(self.project_id, "main.py", "print(123)\n")
        reopened = WorkspaceStore(self.root)
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

    def test_reject_windows_traversal_file_name(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, r"..\\outside.py")

    def test_reject_unsupported_file_type(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, "notes.exe")

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

    def test_duplicate_file_creates_unique_copy(self):
        self.store.write_file(self.project_id, "main.py", "print('copy me')\n")
        first = self.store.duplicate_file(self.project_id, "main.py")
        second = self.store.duplicate_file(self.project_id, "main.py")
        self.assertEqual(first, "main_copy.py")
        self.assertEqual(second, "main_copy_2.py")
        self.assertEqual(self.store.read_file(self.project_id, first), "print('copy me')\n")

    def test_preview_project_replace_does_not_modify_files(self):
        self.store.write_file(self.project_id, "main.py", "print('cat')\n")
        self.store.create_file(self.project_id, "src/helper.py")
        self.store.write_file(self.project_id, "src/helper.py", "animal = 'cat'\n")
        preview = self.store.preview_replace_project(self.project_id, "cat", "dog")
        self.assertEqual(preview["matches"], 2)
        self.assertEqual(len(preview["files"]), 2)
        self.assertIn("cat", self.store.read_file(self.project_id, "main.py"))

    def test_replace_project_updates_all_matching_files(self):
        self.store.write_file(self.project_id, "main.py", "cat cat\n")
        self.store.create_file(self.project_id, "src/helper.py")
        self.store.write_file(self.project_id, "src/helper.py", "cat\n")
        result = self.store.replace_in_project(self.project_id, "cat", "fox")
        self.assertEqual(result["matches"], 3)
        self.assertEqual(result["files_changed"], 2)
        self.assertEqual(self.store.read_file(self.project_id, "main.py"), "fox fox\n")
        self.assertEqual(self.store.read_file(self.project_id, "src/helper.py"), "fox\n")

    def test_replace_project_requires_nonempty_search(self):
        with self.assertRaises(WorkspaceError):
            self.store.preview_replace_project(self.project_id, "", "x")

    def test_reject_oversized_file(self):
        with self.assertRaises(WorkspaceError):
            self.store.write_file(self.project_id, "main.py", "x" * (512 * 1024 + 1))

    def test_remember_active_project_and_file(self):
        self.store.create_file(self.project_id, "tools.py")
        self.store.save_settings(self.project_id, "tools.py")
        reopened = WorkspaceStore(self.root)
        self.assertEqual(
            reopened.load_settings(),
            {"active_project": self.project_id, "active_file": "tools.py"},
        )

    def test_nested_files_and_folders(self):
        self.store.create_folder(self.project_id, "src")
        nested = self.store.create_file(self.project_id, "src/helpers.py")
        self.assertEqual(nested, "src/helpers.py")
        self.store.write_file(self.project_id, nested, "VALUE = 9\n")
        self.assertIn(nested, self.store.list_files(self.project_id))
        self.assertEqual(self.store.read_file(self.project_id, nested), "VALUE = 9\n")

    def test_list_folders_returns_nested_project_paths(self):
        self.store.create_folder(self.project_id, "src/utils")
        self.assertEqual(self.store.list_folders(self.project_id), ["src", "src/utils"])

    def test_create_folder_rejects_traversal(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_folder(self.project_id, "../outside")

    def test_search_project_returns_file_and_line(self):
        self.store.write_file(self.project_id, "main.py", "first\nfind_this_value = 10\n")
        results = self.store.search_project(self.project_id, "find_this")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["file"], "main.py")
        self.assertEqual(results[0]["line"], 2)

    def test_gitignore_special_text_file(self):
        self.store.create_file(self.project_id, ".gitignore")
        self.store.write_file(self.project_id, ".gitignore", "__pycache__/\n")
        self.assertIn(".gitignore", self.store.list_files(self.project_id))

    def test_github_workflow_files_are_supported(self):
        path = self.store.create_file(self.project_id, ".github/workflows/build.yml")
        self.store.write_file(self.project_id, path, "name: Build\n")
        self.assertIn(path, self.store.list_files(self.project_id))
        self.assertEqual(self.store.read_file(self.project_id, path), "name: Build\n")

    def test_sensitive_hidden_directories_are_rejected(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, ".env/secrets.txt")
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, ".git/config")

    def test_create_github_hidden_folder(self):
        self.assertEqual(
            self.store.create_folder(self.project_id, ".github/workflows"),
            ".github/workflows",
        )

    def test_reject_control_characters_in_paths(self):
        with self.assertRaises(WorkspaceError):
            self.store.create_file(self.project_id, "bad\x00name.py")
        with self.assertRaises(WorkspaceError):
            self.store.create_folder(self.project_id, "bad\x01folder")

    def test_create_folder_rejects_symlink_parent(self):
        project_dir = self.store._project_dir(self.project_id)
        outside = self.root / "outside"
        outside.mkdir()
        link = project_dir / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable on this platform")
        with self.assertRaises(WorkspaceError):
            self.store.create_folder(self.project_id, "linked/new")
        self.assertFalse((outside / "new").exists())

    def test_all_templates_can_be_created(self):
        for name, files in TEMPLATES.items():
            project_id = self.store.create_project_from_template(name, files)
            project_files = self.store.list_files(project_id)
            self.assertIn("main.py", project_files)
            for relative in project_files:
                self.store.read_file(project_id, relative)

    def test_template_project_creation(self):
        project_id = self.store.create_project_from_template("Starter", TEMPLATES["Python Starter"])
        self.assertIn("main.py", self.store.list_files(project_id))
        self.assertIn("utils.py", self.store.list_files(project_id))
        self.assertIn("tests/test_utils.py", self.store.list_files(project_id))

    def test_all_template_python_files_compile(self):
        for template_name, files in TEMPLATES.items():
            for file_name, content in files.items():
                if file_name.endswith(".py"):
                    compile(content, f"{template_name}/{file_name}", "exec")

    def test_create_folder_rejects_existing_folder(self):
        self.store.create_folder(self.project_id, "src")
        with self.assertRaises(WorkspaceError):
            self.store.create_folder(self.project_id, "src")

    def test_zip_export_and_import_round_trip(self):
        self.store.create_file(self.project_id, "src/tools.py")
        self.store.write_file(self.project_id, "src/tools.py", "VALUE = 123\n")
        project_dir = self.store._project_dir(self.project_id)
        image_dir = project_dir / "assets"
        image_dir.mkdir()
        (image_dir / "sample.png").write_bytes(b"fake-png-content")

        archive_data = self.store.export_project_archive(self.project_id)
        imported_id = self.store.import_project_archive(archive_data, "Imported")
        self.assertIn("src/tools.py", self.store.list_files(imported_id))
        self.assertEqual(self.store.read_file(imported_id, "src/tools.py"), "VALUE = 123\n")
        self.assertIn("assets/sample.png", self.store.list_assets(imported_id))
        imported_image = self.store._project_dir(imported_id) / "assets" / "sample.png"
        self.assertEqual(imported_image.read_bytes(), b"fake-png-content")

    def test_import_github_style_zip_with_one_wrapper_folder(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("demo-repo/main.py", "print('ok')\n")
            archive.writestr("demo-repo/README.md", "# Demo\n")
        imported_id = self.store.import_project_archive(stream.getvalue(), "GitHub Import")
        self.assertEqual(self.store.read_file(imported_id, "main.py"), "print('ok')\n")
        self.assertIn("README.md", self.store.list_files(imported_id))

    def test_zip_import_rejects_path_traversal(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("safe/main.py", "print('ok')\n")
            archive.writestr("safe/../../escape.py", "bad")
        with self.assertRaises(WorkspaceError):
            self.store.import_project_archive(stream.getvalue(), "Bad Import")

    def test_zip_import_rejects_symlink(self):
        stream = io.BytesIO()
        info = zipfile.ZipInfo("project/linked.py")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("project/main.py", "print('ok')\n")
            archive.writestr(info, "../../outside.py")
        with self.assertRaises(WorkspaceError):
            self.store.import_project_archive(stream.getvalue(), "Bad Link")

    def test_zip_import_rejects_invalid_archive(self):
        with self.assertRaises(WorkspaceError):
            self.store.import_project_archive(b"not a zip", "Bad")


if __name__ == "__main__":
    unittest.main()
