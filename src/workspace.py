"""Persistent, guarded project storage for AI Python Studio.

Projects live in Flet's app-private data directory. Text files are editable;
common image assets are preserved by project ZIP import/export.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


DEFAULT_PROJECT_NAME = "My First Project"
DEFAULT_FILE_NAME = "main.py"
DEFAULT_CODE = 'print("Hello from AI Python Studio!")\n'
MAX_PROJECTS = 30
MAX_FILES_PER_PROJECT = 100
MAX_FILE_BYTES = 512 * 1024
MAX_ARCHIVE_BYTES = 12 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 150
MAX_PROJECT_BYTES = 24 * 1024 * 1024
PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")

TEXT_EXTENSIONS = {
    ".py", ".pyw", ".md", ".txt", ".json", ".toml", ".ini", ".cfg",
    ".yaml", ".yml", ".html", ".htm", ".css", ".js", ".mjs", ".ts",
    ".xml", ".csv", ".svg", ".sql", ".sh", ".bat", ".properties",
    ".gradle", ".kt", ".java", ".dart", ".rst", ".log", ".gitignore",
}
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
SPECIAL_TEXT_FILES = {"readme", "license", "dockerfile", "makefile", ".gitignore", ".editorconfig"}
ALLOWED_HIDDEN_DIRS = {".github", ".vscode", ".idea"}
IGNORED_ARCHIVE_PARTS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist",
    "__MACOSX",
}


class WorkspaceError(ValueError):
    """Raised when a workspace operation is invalid or cannot be completed."""


class WorkspaceStore:
    """Manage app-private projects, nested source files and safe ZIP archives."""

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
        slug = slug[:40].strip("_-") or "project"
        if not slug[0].isalnum():
            slug = f"project_{slug}"
        return slug

    @staticmethod
    def _validate_project_id(project_id: str) -> str:
        if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
            raise WorkspaceError("معرّف المشروع غير صالح.")
        return project_id

    @staticmethod
    def validate_relative_path(relative_path: str, *, allow_extensionless: bool = False) -> str:
        """Validate a portable project-relative path; never accept traversal."""
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise WorkspaceError("اكتب مسار الملف أولاً.")
        raw = relative_path.strip()
        if (
            "\\" in raw
            or raw.startswith("/")
            or re.match(r"^[A-Za-z]:", raw)
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)
            or "\x00" in raw
            or len(raw) > 240
        ):
            raise WorkspaceError("المسار غير صالح. استخدم / للفصل بين المجلدات.")
        path = PurePosixPath(raw)
        if any(len(part) > 100 for part in path.parts):
            raise WorkspaceError("اسم الملف أو المجلد طويل جداً.")
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise WorkspaceError("المسار غير صالح.")
        for index, part in enumerate(path.parts):
            if not part.startswith("."):
                continue
            is_final_special_file = index == len(path.parts) - 1 and part in {".gitignore", ".editorconfig"}
            if is_final_special_file or part in ALLOWED_HIDDEN_DIRS:
                continue
            raise WorkspaceError("هذا الاسم المخفي غير مسموح داخل المشروع.")
        name = path.name
        suffix = Path(name).suffix.lower()
        special = name.lower() in SPECIAL_TEXT_FILES
        if not suffix and not special:
            raise WorkspaceError("امتداد الملف غير مدعوم.")
        if suffix and suffix not in TEXT_EXTENSIONS and suffix not in BINARY_EXTENSIONS:
            raise WorkspaceError(f"امتداد الملف {suffix} غير مدعوم حالياً.")
        return path.as_posix()

    @staticmethod
    def _is_text_path(path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in SPECIAL_TEXT_FILES

    @staticmethod
    def _is_supported_path(path: Path) -> bool:
        return WorkspaceStore._is_text_path(path) or path.suffix.lower() in BINARY_EXTENSIONS

    def _project_dir(self, project_id: str) -> Path:
        project_id = self._validate_project_id(project_id)
        root = self.projects_root.resolve()
        path = (self.projects_root / project_id).resolve()
        if path.parent != root:
            raise WorkspaceError("مسار المشروع غير صالح.")
        return path

    def _project_file_path(self, project_id: str, relative_path: str) -> Path:
        safe = self.validate_relative_path(relative_path)
        project_dir = self._project_dir(project_id)
        candidate = project_dir.joinpath(*PurePosixPath(safe).parts)
        # Reject symlinks in every existing component, including the file itself.
        current = project_dir
        for part in PurePosixPath(safe).parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("روابط الملفات الرمزية غير مسموحة داخل المشروع.")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(project_dir):
            raise WorkspaceError("مسار الملف خارج مجلد المشروع.")
        return candidate

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.",
                suffix=".tmp", delete=False,
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

    @classmethod
    def _atomic_write(cls, path: Path, content: str) -> None:
        if not isinstance(content, str):
            raise WorkspaceError("محتوى الملف يجب أن يكون نصاً.")
        cls._atomic_write_bytes(path, content.encode("utf-8"))

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
            if directory.is_symlink() or not directory.is_dir():
                continue
            if not PROJECT_ID_RE.fullmatch(directory.name):
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
            raise WorkspaceError("اسم المشروع مطلوب، وبحد أقصى 48 حرفاً.")
        if len(self.list_projects()) >= MAX_PROJECTS:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للمشاريع ({MAX_PROJECTS}).")

        base_id = self._slug(clean_name)
        project_id = base_id
        suffix = 2
        while self._project_dir(project_id).exists():
            project_id = f"{base_id[:40]}_{suffix}"
            suffix += 1

        project_dir = self._project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=False)
        try:
            self._atomic_write(
                project_dir / ".project.json",
                json.dumps({"display_name": clean_name}, ensure_ascii=False, indent=2),
            )
            self._atomic_write(project_dir / DEFAULT_FILE_NAME, DEFAULT_CODE)
        except Exception:
            shutil.rmtree(project_dir, ignore_errors=True)
            raise
        return project_id

    def create_project_from_template(self, display_name: str, files: Mapping[str, str]) -> str:
        if not isinstance(files, Mapping) or not files:
            raise WorkspaceError("القالب لا يحتوي على ملفات.")
        if len(files) > MAX_FILES_PER_PROJECT:
            raise WorkspaceError("القالب يحتوي على ملفات أكثر من الحد المسموح.")
        project_id = self.create_project(display_name)
        project_dir = self._project_dir(project_id)
        try:
            # Replace the default starter file only if a template provides main.py.
            for relative_path, content in files.items():
                safe = self.validate_relative_path(relative_path)
                path = self._project_file_path(project_id, safe)
                if not self._is_text_path(path):
                    raise WorkspaceError("قوالب المشاريع تقبل الملفات النصية فقط.")
                encoded = content.encode("utf-8") if isinstance(content, str) else b""
                if not isinstance(content, str) or len(encoded) > MAX_FILE_BYTES:
                    raise WorkspaceError(f"محتوى الملف {safe} غير صالح أو كبير جداً.")
                self._atomic_write(path, content)
            if "main.py" not in self.list_files(project_id):
                self._atomic_write(project_dir / DEFAULT_FILE_NAME, DEFAULT_CODE)
            return project_id
        except Exception:
            shutil.rmtree(project_dir, ignore_errors=True)
            raise

    def list_files(self, project_id: str) -> list[str]:
        """Return editable text files, recursively, relative to project root."""
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        files: list[str] = []
        for item in directory.rglob("*"):
            if item.is_symlink() or not item.is_file() or item.name == ".project.json":
                continue
            try:
                relative = item.relative_to(directory).as_posix()
            except ValueError:
                continue
            if self._is_text_path(item):
                files.append(relative)
        return sorted(files, key=str.casefold)

    def list_folders(self, project_id: str) -> list[str]:
        """Return project-relative directories, excluding symbolic links."""
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        folders: list[str] = []
        for item in directory.rglob("*"):
            if item.is_symlink() or not item.is_dir():
                continue
            folders.append(item.relative_to(directory).as_posix())
        return sorted(folders, key=str.casefold)

    def list_assets(self, project_id: str) -> list[str]:
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        assets: list[str] = []
        for item in directory.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            if item.suffix.lower() in BINARY_EXTENSIONS:
                assets.append(item.relative_to(directory).as_posix())
        return sorted(assets, key=str.casefold)

    def read_file(self, project_id: str, file_name: str) -> str:
        path = self._project_file_path(project_id, file_name)
        if not self._is_text_path(path):
            raise WorkspaceError("هذا ملف أصول وليس ملفاً نصياً قابلاً للتحرير.")
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise WorkspaceError("حجم الملف أكبر من الحد المسموح.")
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise WorkspaceError("الملف غير موجود.") from exc
        except UnicodeDecodeError as exc:
            raise WorkspaceError("تعذر قراءة الملف كنص UTF-8.") from exc

    def write_file(self, project_id: str, file_name: str, content: str) -> None:
        if not isinstance(content, str):
            raise WorkspaceError("محتوى الملف يجب أن يكون نصاً.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError("حجم الملف أكبر من 512 كيلوبايت.")
        path = self._project_file_path(project_id, file_name)
        if not self._is_text_path(path):
            raise WorkspaceError("امتداد الملف غير مخصص للنصوص.")
        if not self._project_dir(project_id).is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        if not path.exists() and len(self.list_files(project_id)) >= MAX_FILES_PER_PROJECT:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للملفات ({MAX_FILES_PER_PROJECT}).")
        self._atomic_write(path, content)

    def create_file(self, project_id: str, file_name: str) -> str:
        raw = (file_name or "").strip()
        if raw and not Path(raw).suffix and Path(raw).name.lower() not in SPECIAL_TEXT_FILES:
            raw += ".py"
        name = self.validate_relative_path(raw)
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        if len(self.list_files(project_id)) >= MAX_FILES_PER_PROJECT:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للملفات ({MAX_FILES_PER_PROJECT}).")
        path = self._project_file_path(project_id, name)
        if path.exists():
            raise WorkspaceError("يوجد ملف بهذا المسار بالفعل.")
        if path.parent.exists() and not path.parent.is_dir():
            raise WorkspaceError("أحد أجزاء المسار موجود كملف وليس مجلداً.")
        if not self._is_text_path(path):
            raise WorkspaceError("أنشئ الملفات النصية فقط من المحرر.")
        self._atomic_write(path, "# اكتب هنا\n" if path.suffix == ".py" else "")
        return name

    def create_folder(self, project_id: str, folder_path: str) -> str:
        raw = (folder_path or "").strip()
        if (
            not raw
            or "\\" in raw
            or raw.startswith("/")
            or re.match(r"^[A-Za-z]:", raw)
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)
            or len(raw) > 240
        ):
            raise WorkspaceError("مسار المجلد غير صالح.")
        path = PurePosixPath(raw)
        if any(
            part in {"", ".", ".."}
            or len(part) > 100
            or (part.startswith(".") and part not in ALLOWED_HIDDEN_DIRS)
            for part in path.parts
        ):
            raise WorkspaceError("اسم المجلد غير صالح.")
        directory = self._project_dir(project_id)
        if not directory.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        target = directory.joinpath(*path.parts)
        current = directory
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("روابط المجلدات الرمزية غير مسموحة داخل المشروع.")
        try:
            target.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise WorkspaceError("المجلد موجود بالفعل أو أن أحد أجزاء المسار ملف.") from exc
        except OSError as exc:
            raise WorkspaceError(f"تعذر إنشاء المجلد: {exc}") from exc
        if not target.resolve().is_relative_to(directory.resolve()):
            shutil.rmtree(target, ignore_errors=True)
            raise WorkspaceError("مسار المجلد خارج المشروع.")
        return path.as_posix()

    def delete_file(self, project_id: str, file_name: str) -> None:
        files = self.list_files(project_id)
        name = self.validate_relative_path(file_name)
        if name not in files:
            raise WorkspaceError("الملف غير موجود.")
        if len(files) <= 1:
            raise WorkspaceError("لا يمكن حذف آخر ملف في المشروع.")
        self._project_file_path(project_id, name).unlink()

    def rename_file(self, project_id: str, old_name: str, new_name: str) -> str:
        old_safe = self.validate_relative_path(old_name)
        new_safe = self.validate_relative_path(new_name)
        old_path = self._project_file_path(project_id, old_safe)
        new_path = self._project_file_path(project_id, new_safe)
        if old_safe not in self.list_files(project_id):
            raise WorkspaceError("الملف الأصلي غير موجود.")
        if new_path.exists():
            raise WorkspaceError("يوجد ملف بالاسم الجديد بالفعل.")
        if not self._is_text_path(old_path) or not self._is_text_path(new_path):
            raise WorkspaceError("نوع الملف الجديد غير مدعوم.")
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.replace(new_path)
        except OSError as exc:
            raise WorkspaceError(f"تعذرت إعادة تسمية الملف: {exc}") from exc
        return new_safe

    def duplicate_file(self, project_id: str, file_name: str) -> str:
        source_name = self.validate_relative_path(file_name)
        files = self.list_files(project_id)
        if source_name not in files:
            raise WorkspaceError("الملف الأصلي غير موجود.")
        if len(files) >= MAX_FILES_PER_PROJECT:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للملفات ({MAX_FILES_PER_PROJECT}).")
        source = self._project_file_path(project_id, source_name)
        parent = PurePosixPath(source_name).parent
        stem = Path(source_name).stem
        suffix = Path(source_name).suffix
        candidate_name = f"{stem}_copy{suffix}"
        index = 2
        while (parent / candidate_name).as_posix() in files:
            candidate_name = f"{stem}_copy_{index}{suffix}"
            index += 1
        candidate = (parent / candidate_name).as_posix()
        self.write_file(project_id, candidate, self.read_file(project_id, source_name))
        return candidate

    def search_project(self, project_id: str, query: str, max_results: int = 100) -> list[dict[str, Any]]:
        needle = (query or "").strip().casefold()
        if not needle:
            raise WorkspaceError("اكتب عبارة للبحث عنها.")
        if max_results < 1 or max_results > 500:
            raise WorkspaceError("حد نتائج البحث غير صالح.")
        results: list[dict[str, Any]] = []
        for relative in self.list_files(project_id):
            path = self._project_file_path(project_id, relative)
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, start=1):
                if needle in line.casefold():
                    results.append({
                        "file": relative,
                        "line": line_number,
                        "snippet": line.strip()[:240],
                    })
                    if len(results) >= max_results:
                        return results
        return results

    def preview_replace_project(
        self, project_id: str, find_text: str, replacement: str, max_matches: int = 1000
    ) -> dict[str, Any]:
        """Count exact text matches across editable files without changing them."""
        if not isinstance(find_text, str) or not find_text:
            raise WorkspaceError("اكتب النص المراد البحث عنه أولاً.")
        if not isinstance(replacement, str):
            raise WorkspaceError("نص الاستبدال غير صالح.")
        if max_matches < 1 or max_matches > 10000:
            raise WorkspaceError("حد نتائج الاستبدال غير صالح.")
        files: list[dict[str, Any]] = []
        total = 0
        for relative in self.list_files(project_id):
            source = self.read_file(project_id, relative)
            count = source.count(find_text)
            if count:
                files.append({"file": relative, "matches": count})
                total += count
                if total > max_matches:
                    raise WorkspaceError(f"تجاوز عدد التطابقات الحد الآمن ({max_matches}).")
        return {"files": files, "matches": total}

    def replace_in_project(
        self, project_id: str, find_text: str, replacement: str, max_matches: int = 1000
    ) -> dict[str, Any]:
        """Replace exact text across project files, rolling back on write failure."""
        preview = self.preview_replace_project(project_id, find_text, replacement, max_matches)
        originals: dict[str, str] = {}
        changed: list[str] = []
        try:
            for item in preview["files"]:
                relative = item["file"]
                original = self.read_file(project_id, relative)
                originals[relative] = original
                self.write_file(project_id, relative, original.replace(find_text, replacement))
                changed.append(relative)
        except Exception:
            for relative in reversed(changed):
                try:
                    self.write_file(project_id, relative, originals[relative])
                except Exception:
                    pass
            raise
        return {"files_changed": len(changed), "matches": preview["matches"], "files": changed}

    def export_project_archive(self, project_id: str) -> bytes:
        project_dir = self._project_dir(project_id)
        if not project_dir.is_dir():
            raise WorkspaceError("المشروع غير موجود.")
        output = io.BytesIO()
        total = 0
        count = 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in sorted(project_dir.rglob("*")):
                if item.is_symlink() or not item.is_file() or item.name == ".project.json":
                    continue
                if not self._is_supported_path(item):
                    continue
                relative = item.relative_to(project_dir).as_posix()
                data = item.read_bytes()
                if len(data) > MAX_FILE_BYTES:
                    raise WorkspaceError(f"الملف {relative} أكبر من حد التصدير.")
                total += len(data)
                count += 1
                if total > MAX_PROJECT_BYTES or count > MAX_ARCHIVE_ENTRIES:
                    raise WorkspaceError("حجم المشروع أكبر من الحد المسموح للتصدير.")
                archive.writestr(relative, data)
        data = output.getvalue()
        if len(data) > MAX_ARCHIVE_BYTES:
            raise WorkspaceError("ملف ZIP الناتج أكبر من الحد المسموح.")
        return data

    def import_project_archive(self, archive_data: bytes, display_name: str) -> str:
        if not isinstance(archive_data, (bytes, bytearray)) or not archive_data:
            raise WorkspaceError("ملف ZIP فارغ أو غير صالح.")
        if len(archive_data) > MAX_ARCHIVE_BYTES:
            raise WorkspaceError("ملف ZIP أكبر من الحد المسموح.")
        clean_name = (display_name or "").strip()[:48] or "Imported Project"
        if len(self.list_projects()) >= MAX_PROJECTS:
            raise WorkspaceError(f"وصلت إلى الحد الأقصى للمشاريع ({MAX_PROJECTS}).")

        try:
            archive = zipfile.ZipFile(io.BytesIO(archive_data))
        except (zipfile.BadZipFile, OSError) as exc:
            raise WorkspaceError("ملف ZIP غير صالح أو تالف.") from exc

        with archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                raise WorkspaceError("عدد ملفات الأرشيف غير صالح.")
            prepared: list[tuple[str, zipfile.ZipInfo]] = []
            raw_names: list[str] = []
            for info in infos:
                name = info.filename.replace("\\", "/")
                path = PurePosixPath(name)
                if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                    raise WorkspaceError("الأرشيف يحتوي مساراً غير آمن.")
                if any(part in IGNORED_ARCHIVE_PARTS for part in path.parts):
                    continue
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise WorkspaceError("الأرشيف يحتوي روابط رمزية غير مسموحة.")
                if info.file_size > MAX_FILE_BYTES:
                    raise WorkspaceError(f"الملف {path.name} أكبر من 512 كيلوبايت.")
                raw_names.append(path.as_posix())

            # GitHub source ZIP files usually have a single wrapper directory.
            common_prefix = None
            parsed = [PurePosixPath(n) for n in raw_names]
            if parsed and all(len(p.parts) > 1 for p in parsed):
                first = parsed[0].parts[0]
                if all(p.parts[0] == first for p in parsed):
                    common_prefix = first

            total = 0
            seen: set[str] = set()
            for info in infos:
                name = info.filename.replace("\\", "/")
                path = PurePosixPath(name)
                if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                    raise WorkspaceError("الأرشيف يحتوي مساراً غير آمن.")
                if any(part in IGNORED_ARCHIVE_PARTS for part in path.parts):
                    continue
                parts = path.parts[1:] if common_prefix and path.parts[0] == common_prefix else path.parts
                if not parts:
                    continue
                relative = PurePosixPath(*parts).as_posix()
                try:
                    safe = self.validate_relative_path(relative, allow_extensionless=True)
                except WorkspaceError:
                    continue
                suffix_path = Path(safe)
                if not self._is_supported_path(suffix_path):
                    continue
                if safe in seen:
                    raise WorkspaceError(f"الأرشيف يحتوي مساراً مكرراً: {safe}")
                seen.add(safe)
                total += info.file_size
                if total > MAX_PROJECT_BYTES:
                    raise WorkspaceError("محتوى المشروع أكبر من الحد المسموح.")
                prepared.append((safe, info))

            if not prepared:
                raise WorkspaceError("لم أجد ملفات مدعومة داخل ZIP.")
            if len(prepared) > MAX_FILES_PER_PROJECT:
                raise WorkspaceError(f"الأرشيف يحتوي ملفات أكثر من الحد ({MAX_FILES_PER_PROJECT}).")

            project_id = self.create_project(clean_name)
            project_dir = self._project_dir(project_id)
            try:
                # Remove the default file only when the archive includes its own main.py.
                archive_names = {name for name, _ in prepared}
                if "main.py" in archive_names:
                    (project_dir / DEFAULT_FILE_NAME).unlink(missing_ok=True)
                for relative, info in prepared:
                    try:
                        # Bound decompression so a forged/hostile ZIP cannot expand
                        # an entry into an unbounded in-memory allocation.
                        with archive.open(info, "r") as member:
                            data = member.read(MAX_FILE_BYTES + 1)
                    except (RuntimeError, zipfile.BadZipFile, OSError, zlib.error) as exc:
                        raise WorkspaceError(f"تعذر فك الملف {relative} من الأرشيف.") from exc
                    if len(data) > MAX_FILE_BYTES:
                        raise WorkspaceError(f"الملف {relative} أكبر من 512 كيلوبايت بعد فك الضغط.")
                    if len(data) != info.file_size:
                        raise WorkspaceError(f"تعذر قراءة الملف {relative} كاملاً.")
                    target = self._project_file_path(project_id, relative)
                    self._atomic_write_bytes(target, data)
                return project_id
            except Exception:
                shutil.rmtree(project_dir, ignore_errors=True)
                raise

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
        safe_file = self.validate_relative_path(active_file)
        if safe_file not in self.list_files(active_project):
            raise WorkspaceError("لا يمكن حفظ إعدادات ملف غير موجود.")
        self._atomic_write(
            self.settings_path,
            json.dumps(
                {"active_project": active_project, "active_file": safe_file},
                ensure_ascii=False,
                indent=2,
            ),
        )
