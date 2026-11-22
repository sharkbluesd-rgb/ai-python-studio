import unittest

from src.file_tree import build_tree_entries


class FileTreeTests(unittest.TestCase):
    def test_root_files_are_visible(self):
        result = build_tree_entries(
            ["main.py", "README.md"], [], set()
        )
        self.assertEqual(
            result,
            [("file", "main.py", 0), ("file", "README.md", 0)],
        )

    def test_collapsed_folder_hides_children(self):
        result = build_tree_entries(
            ["src/main.py"], ["src"], set()
        )
        self.assertEqual(result, [("folder", "src", 0)])

    def test_expanded_folder_shows_children(self):
        result = build_tree_entries(
            ["src/main.py"], ["src"], {"src"}
        )
        self.assertEqual(
            result,
            [
                ("folder", "src", 0),
                ("file", "src/main.py", 1),
            ],
        )

    def test_nested_folders(self):
        result = build_tree_entries(
            ["src/core/app.py"],
            ["src", "src/core"],
            {"src", "src/core"},
        )
        self.assertEqual(
            result,
            [
                ("folder", "src", 0),
                ("folder", "src/core", 1),
                ("file", "src/core/app.py", 2),
            ],
        )

    def test_implicit_parent_is_created(self):
        result = build_tree_entries(
            ["tests/unit/test_app.py"], [], {"tests", "tests/unit"}
        )
        self.assertEqual(
            result,
            [
                ("folder", "tests", 0),
                ("folder", "tests/unit", 1),
                ("file", "tests/unit/test_app.py", 2),
            ],
        )

    def test_files_are_sorted(self):
        result = build_tree_entries(
            ["z.py", "a.py"], [], set()
        )
        self.assertEqual(
            [entry[1] for entry in result], ["a.py", "z.py"]
        )


if __name__ == "__main__":
    unittest.main()
