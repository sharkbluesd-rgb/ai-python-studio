"""Editor tab state management."""

from __future__ import annotations


class OpenFileTabs:
    """Manage open files and the active editor tab."""

    def __init__(
        self,
        initial_file: str | None = None,
        *,
        max_tabs: int = 12,
    ) -> None:
        if max_tabs < 1:
            raise ValueError("max_tabs must be at least 1")

        self.max_tabs = max_tabs
        self._files: list[str] = []
        self._active_file: str | None = None

        if initial_file:
            self.open(initial_file)

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(self._files)

    @property
    def active_file(self) -> str | None:
        return self._active_file

    def open(self, file_path: str) -> str:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("Invalid file path")

        if file_path in self._files:
            self._active_file = file_path
            return file_path

        if len(self._files) >= self.max_tabs:
            inactive = next(
                (p for p in self._files if p != self._active_file),
                None,
            )
            if inactive is None:
                raise RuntimeError("No inactive tab available")
            self.close(inactive)

        self._files.append(file_path)
        self._active_file = file_path
        return file_path

    def close(self, file_path: str) -> str | None:
        if file_path not in self._files:
            return self._active_file

        index = self._files.index(file_path)
        was_active = self._active_file == file_path
        self._files.pop(index)

        if was_active:
            if self._files:
                self._active_file = self._files[
                    min(index, len(self._files) - 1)
                ]
            else:
                self._active_file = None

        return self._active_file

    def rename(self, old_path: str, new_path: str) -> bool:
        if not isinstance(new_path, str) or not new_path.strip():
            raise ValueError("Invalid new path")

        if old_path not in self._files:
            return False

        if new_path != old_path and new_path in self._files:
            raise ValueError("Target tab already exists")

        index = self._files.index(old_path)
        self._files[index] = new_path

        if self._active_file == old_path:
            self._active_file = new_path

        return True

    def reset(self, file_path: str) -> str:
        self._files.clear()
        self._active_file = None
        return self.open(file_path)
