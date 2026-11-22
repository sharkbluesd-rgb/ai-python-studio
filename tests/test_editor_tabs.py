import unittest

from editor_tabs import OpenFileTabs


class EditorTabsTests(unittest.TestCase):

    def test_initial_tab(self):
        tabs = OpenFileTabs("main.py")
        self.assertEqual(tabs.files, ("main.py",))
        self.assertEqual(tabs.active_file, "main.py")

    def test_open_multiple_files(self):
        tabs = OpenFileTabs("main.py")
        tabs.open("utils.py")
        tabs.open("tests.py")
        self.assertEqual(len(tabs.files), 3)
        self.assertEqual(tabs.active_file, "tests.py")

    def test_existing_file_is_not_duplicated(self):
        tabs = OpenFileTabs("main.py")
        tabs.open("utils.py")
        tabs.open("main.py")
        self.assertEqual(tabs.files, ("main.py", "utils.py"))
        self.assertEqual(tabs.active_file, "main.py")

    def test_close_active_selects_neighbor(self):
        tabs = OpenFileTabs("main.py")
        tabs.open("utils.py")
        tabs.open("tests.py")
        self.assertEqual(tabs.close("tests.py"), "utils.py")

    def test_close_last_tab(self):
        tabs = OpenFileTabs("main.py")
        self.assertIsNone(tabs.close("main.py"))
        self.assertEqual(tabs.files, ())

    def test_close_inactive_tab(self):
        tabs = OpenFileTabs("main.py")
        tabs.open("utils.py")
        tabs.close("main.py")
        self.assertEqual(tabs.active_file, "utils.py")

    def test_capacity(self):
        tabs = OpenFileTabs("main.py", max_tabs=2)
        tabs.open("utils.py")
        tabs.open("tests.py")
        self.assertEqual(tabs.files, ("utils.py", "tests.py"))

    def test_rename(self):
        tabs = OpenFileTabs("main.py")
        tabs.rename("main.py", "app.py")
        self.assertEqual(tabs.active_file, "app.py")

    def test_reset_project(self):
        tabs = OpenFileTabs("main.py")
        tabs.open("utils.py")
        tabs.reset("new/main.py")
        self.assertEqual(tabs.files, ("new/main.py",))


if __name__ == "__main__":
    unittest.main()
