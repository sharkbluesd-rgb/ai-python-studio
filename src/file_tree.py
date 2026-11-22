"""Build a visible, expandable project file tree."""
from pathlib import PurePosixPath


def build_tree_entries(files, folders, expanded):
    """Return (kind, path, depth) entries in tree display order."""
    directories = set(folders)
    file_paths = set(files)

    for item in list(directories) + list(file_paths):
        parent = PurePosixPath(item).parent
        while str(parent) not in ("", "."):
            directories.add(parent.as_posix())
            parent = parent.parent

    entries = []

    def walk(parent, depth):
        child_dirs = sorted(
            (d for d in directories
             if PurePosixPath(d).parent.as_posix() == parent),
            key=str.casefold,
        )
        child_files = sorted(
            (f for f in file_paths
             if PurePosixPath(f).parent.as_posix() == parent),
            key=str.casefold,
        )

        for folder in child_dirs:
            entries.append(("folder", folder, depth))
            if folder in expanded:
                walk(folder, depth + 1)

        for file_path in child_files:
            entries.append(("file", file_path, depth))

    walk(".", 0)
    return entries
