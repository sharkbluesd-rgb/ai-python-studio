import tempfile
import unittest

from editor_tabs import OpenFileTabs
from workspace import WorkspaceStore


class EditorWorkflowPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.store = WorkspaceStore(self.root)
        self.project_id = self.store.list_projects()[0]["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_switching_tabs_preserves_saved_content_across_reopen(self):
        self.store.write_file(self.project_id, "main.py", "print('main saved')\n")
        self.store.create_file(self.project_id, "helper.py")
        self.store.write_file(self.project_id, "helper.py", "VALUE = 42\n")

        tabs = OpenFileTabs("main.py")
        tabs.open("helper.py")
        self.store.save_settings(self.project_id, tabs.active_file)

        # A change made in the active tab is persisted before switching away.
        self.store.write_file(self.project_id, "helper.py", "VALUE = 99\n")
        tabs.open("main.py")
        self.store.save_settings(self.project_id, tabs.active_file)

        reopened = WorkspaceStore(self.root)
        self.assertEqual(reopened.read_file(self.project_id, "main.py"), "print('main saved')\n")
        self.assertEqual(reopened.read_file(self.project_id, "helper.py"), "VALUE = 99\n")
        self.assertEqual(reopened.load_settings()["active_file"], "main.py")
        self.assertEqual(tabs.files, ("main.py", "helper.py"))

    def test_closing_active_tab_selects_neighbor_without_deleting_file(self):
        self.store.create_file(self.project_id, "helper.py")
        self.store.write_file(self.project_id, "main.py", "MAIN = True\n")
        self.store.write_file(self.project_id, "helper.py", "HELPER = True\n")

        tabs = OpenFileTabs("main.py")
        tabs.open("helper.py")
        next_active = tabs.close("helper.py")

        self.assertEqual(next_active, "main.py")
        self.assertEqual(tabs.active_file, "main.py")
        reopened = WorkspaceStore(self.root)
        self.assertEqual(reopened.read_file(self.project_id, "helper.py"), "HELPER = True\n")
        self.assertEqual(reopened.read_file(self.project_id, "main.py"), "MAIN = True\n")


if __name__ == "__main__":
    unittest.main()
