"""Persistent, app-private project and file storage for AI Python Studio."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_NAME = "My First Project"
DEFAULT_FILE_NAME = "main.py"
DEFAULT_CODE = 'print("Hello from AI Python Studio!")\n'
MAX_PROJECTS = 30
MAX_FILES_PER_PROJECT = 100
MAX_FILE_BYTES = 512 * 1024
PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
FILE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,47}\.py$")


class WorkspaceError(ValueError):
    """Raised when a workspace operation is invalid or cannot be completed."""


class WorkspaceStore:
    """Store projects as ordinary .py files under Flet's durable app directory.

    On Android, Flet sets FLET_APP_STORAGE_DATA to an app-private directory that
    survives app updates. An optional root is accepted for tests and development.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        if root is not None:
            base = Path(root).expanduser()
        elif os.getenv("FLET_APP_STORAGE_DATA"):
            base = Path(os.environ["FLET_APP_STORAGE_DATA"]) / "ai_python_studio"
        else:
            base = Path.home() / ".local" / "share" / "ai_python_studio"

        self.root = base.resolve()
        self.projects_root = self.root / "projects"
        self.settings_path = self.root / "workspace.json"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self._ensure_default_project()

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_-").lower()
        slug = slug[:40].strip("_-")
        if not slug:
            slug = "project"
        if not slug[0].isalnum():
            slug = f"project_{slug}"
        return slug

    @staticmethod
    def _validate_project_id(project_id: str) -> str:
        if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
            raise WorkspaceError("معرّف المشروع غير صالح.")
        return project_id

    @staticmethod
    def validate_file_name(file_name: str) -> str:
        name = (file_name or "").strip()
        if not name:
            raise WorkspaceError("اكتب اسم الملف أولًا.")
        if not name.lower().endswith(".py"):
            name += ".py"
        if not FILE_NAME_RE.fullmatch(name):
            raise WorkspaceError("اسم الملف غير صالح. استخدم الحروف والأرقام و _ أو - وامتداد .py فقط.")
        return name

    def _project_dir(self, project_id: str) -> Path:
        project_id = self._validate_project_id(project_id)
        path = (self.projects_root / project_id).resolve()
        if path.parent != self.projects_root.resolve():
            raise WorkspaceError("مسار المشروع غير صالح.")
        return path

    def _project_meta_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / ".project.json"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temp_name = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if temp_name and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    @staticmethod
    def _read_json(path: Path, fallback: Any) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return fallback

    def _ensure_default_project(self) -> None:
        if self.list_projects():
            return
        self.create_project(DEFAULT_PROJECT_NAME)

    def list_projects(self) -> list[dict[str, str]]:
        projects: list[dict[str, str]] = []
        if not self.projects_root.exists():
            return projects
        for directory in self.projects_root.iterdir():
            if not directory.is_dir() or not PROJECT_ID_RE.fullmatch(directory.name):
                continue
            metadata = self._read_json(directory / ".project.json", {})
            display_name = metadata.get("display_name") if isinstance(metadata, dict) else None
            projects.append({
                "id": directory.name,
                "name": display_name if isinstance(display_name, str) else directory.name,
            })
        return sorted(projects, key=lambda item: item["name"].casefold())

    def create_project(self, display_name: str) -> str:
        clean_name = (display_name or "").strip()
        if not clean_name or len(clean_name) > 48:
            raise WorkspaceError("اسم المشروع مطلوب، وبحد أقصى 48 حرفًا.")
        projects = self.list_projects()
        if len(projects) >= MAX_PROJECTS:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للمشاريع ({MAX_PROJECTS}).")

        base_id = self._slug(clean_name)
        project_id = base_id
        suffix = 2
        while self._project_dir(project_id).exists():
            project_id = f"{base_id[:40]}_{suffix}"
            suffix += 1

        project_dir = self._project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=False)
        self._atomic_write(
            project_dir / ".project.json",
            json.dumps({"display_name": clean_name}, ensure_ascii=False, indent=2),
        )
        self._atomic_write(project_dir / DEFAULT_FILE_NAME, DEFAULT_CODE)
        return project_id

    def list_files(self, project_id: str) -> list[str]:
        directory = self._project_dir(project_id)
        if not directory.exists():
            raise WorkspaceError("المشروع غير موجود.")
        return sorted(
            (item.name for item in directory.iterdir()
             if item.is_file() and FILE_NAME_RE.fullmatch(item.name)),
            key=str.casefold,
        )

    def _file_path(self, project_id: str, file_name: str) -> Path:
        safe_name = self.validate_file_name(file_name)
        directory = self._project_dir(project_id)
        path = (directory / safe_name).resolve()
        if path.parent != directory.resolve():
            raise WorkspaceError("مسار الملف غير صالح.")
        return path

    def read_file(self, project_id: str, file_name: str) -> str:
        path = self._file_path(project_id, file_name)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise WorkspaceError("الملف غير موجود.") from exc
        except UnicodeDecodeError as exc:
            raise WorkspaceError("تعذر قراءة الملف كنص UTF-8.") from exc

    def write_file(self, project_id: str, file_name: str, content: str) -> None:
        if not isinstance(content, str):
            raise WorkspaceError("محتوى الملف يجب أن يكون نصًا.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError("حجم الملف أكبر من 512 كيلوبايت.")
        path = self._file_path(project_id, file_name)
        if not self._project_dir(project_id).is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        self._atomic_write(path, content)

    def create_file(self, project_id: str, file_name: str) -> str:
        name = self.validate_file_name(file_name)
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        if len(self.list_files(project_id)) >= MAX_FILES_PER_PROJECT:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للملفات ({MAX_FILES_PER_PROJECT}).")
        path = self._file_path(project_id, name)
        if path.exists():
            raise WorkspaceError("يوجد ملف بهذا الاسم بالفعل.")
        self._atomic_write(path, "# اكتب كود Python هنا\n")
        return name

    def delete_file(self, project_id: str, file_name: str) -> None:
        files = self.list_files(project_id)
        name = self.validate_file_name(file_name)
        if name not in files:
            raise WorkspaceError("الملف غير موجود.")
        if len(files) <= 1:
            raise WorkspaceError("لا يمكن حذف آخر ملف في المشروع.")
        self._file_path(project_id, name).unlink()

    def rename_file(self, project_id: str, old_name: str, new_name: str) -> str:
        old_safe = self.validate_file_name(old_name)
        new_safe = self.validate_file_name(new_name)
        old_path = self._file_path(project_id, old_safe)
        new_path = self._file_path(project_id, new_safe)
        if not old_path.is_file():
            raise WorkspaceError("الملف الأصلي غير موجود.")
        if new_path.exists():
            raise WorkspaceError("يوجد ملف بالاسم الجديد بالفعل.")
        old_path.replace(new_path)
        return new_safe

    def load_settings(self) -> dict[str, str]:
        value = self._read_json(self.settings_path, {})
        if not isinstance(value, dict):
            return {}
        return {
            key: item for key, item in value.items()
            if key in {"active_project", "active_file"} and isinstance(item, str)
        }

    def save_settings(self, active_project: str, active_file: str) -> None:
        self._project_dir(active_project)
        safe_file = self.validate_file_name(active_file)
        if safe_file not in self.list_files(active_project):
            raise WorkspaceError("لا يمكن حفظ إعدادات ملف غير موجود.")
        self._atomic_write(
            self.settings_path,
            json.dumps(
                {"active_project": active_project, "active_file": safe_file},
                ensure_ascii=False, indent=2,
            ),
        )
