"""AI Python Studio — mobile-first Python workspace for Android."""

from __future__ import annotations

import asyncio
import shlex
import time
from pathlib import Path, PurePosixPath

import flet as ft
import flet_code_editor as fce

from runner import ExecutionControl, check_python, execute_python, execute_unittest_discovery
from templates import TEMPLATES
from editor_tabs import OpenFileTabs
from file_tree import build_tree_entries
from project_tools import analyze_project as inspect_project, format_analysis_report
from workspace import MAX_ARCHIVE_BYTES, WorkspaceError, WorkspaceStore
from package_manager import PackageManagerError, parse_requirements, install_packages, list_installed
from github_cloud import DeviceAuthorization, GitHubClient, GitHubError


APP_BG = "#080D16"
PANEL = "#121B2A"
EDITOR_BG = "#0A111D"
ACCENT = "#8175F5"
TEXT = "#F2F4FC"
MUTED = "#9AA8BC"
SUCCESS = "#83DDB8"
DANGER = "#FF8F9B"
OUTPUT_LIMIT = 40_000

LANGUAGE_BY_SUFFIX = {
    ".py": fce.CodeLanguage.PYTHON,
    ".pyw": fce.CodeLanguage.PYTHON,
    ".md": fce.CodeLanguage.MARKDOWN,
    ".json": fce.CodeLanguage.JSON,
    ".html": fce.CodeLanguage.XML,
    ".htm": fce.CodeLanguage.XML,
    ".css": fce.CodeLanguage.CSS,
    ".js": fce.CodeLanguage.JAVASCRIPT,
    ".mjs": fce.CodeLanguage.JAVASCRIPT,
    ".ts": fce.CodeLanguage.TYPESCRIPT,
    ".xml": fce.CodeLanguage.XML,
    ".yaml": fce.CodeLanguage.YAML,
    ".yml": fce.CodeLanguage.YAML,
    ".sql": fce.CodeLanguage.SQL,
    ".sh": fce.CodeLanguage.SHELL,
}

AUTOCOMPLETE_WORDS = [
    "print", "input", "len", "range", "enumerate", "zip", "map", "filter",
    "sum", "min", "max", "sorted", "list", "dict", "tuple", "set", "str",
    "int", "float", "bool", "open", "class", "def", "return", "async", "await",
    "import", "from", "as", "if", "elif", "else", "for", "while", "try",
    "except", "finally", "with", "lambda", "yield", "self", "True", "False",
    "None", "Path", "json", "os", "sys", "asyncio", "typing",
]


def main(page: ft.Page) -> None:
    store = WorkspaceStore()

    page.title = "AI Python Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = APP_BG
    page.padding = 0
    page.spacing = 0
    page.scroll = ft.ScrollMode.AUTO

    settings = store.load_settings()
    available_projects = store.list_projects()
    project_ids = {item["id"] for item in available_projects}
    active_project = settings.get("active_project", "")
    if active_project not in project_ids:
        active_project = available_projects[0]["id"]

    available_files = store.list_files(active_project)
    active_file = settings.get("active_file", "main.py")
    if active_file not in available_files:
        active_file = "main.py" if "main.py" in available_files else available_files[0]

    tabs = OpenFileTabs(active_file)

    editor = fce.CodeEditor(
        value=store.read_file(active_project, active_file),
        language=LANGUAGE_BY_SUFFIX.get(Path(active_file).suffix.lower(), fce.CodeLanguage.PLAINTEXT),
        code_theme=fce.CodeTheme.ATOM_ONE_DARK,
        autocomplete=True,
        autocomplete_words=AUTOCOMPLETE_WORDS,
        gutter_style=fce.GutterStyle(
            show_line_numbers=True,
            show_folding_handles=True,
            show_errors=True,
            width=52,
        ),
        text_style=ft.TextStyle(size=14, font_family="monospace"),
        padding=12,
        autofocus=False,
        expand=True,
    )

    output_text = ft.Text(
        "المخرجات ونتائج الفحص ستظهر هنا.",
        selectable=True,
        color=MUTED,
        size=13,
    )
    status_text = ft.Text("تم تحميل مساحة العمل.", size=12, color=SUCCESS)
    project_buttons = ft.Row(wrap=True, spacing=6)
    file_buttons = ft.Row(wrap=True, spacing=6)
    tab_buttons = ft.Row(wrap=True, spacing=4)
    tree_view = ft.Column(controls=[], spacing=2, scroll=ft.ScrollMode.AUTO)
    expanded_folders = set()
    active_file_label = ft.Text(active_file, size=13, color="#C7BFFF", weight=ft.FontWeight.BOLD)
    project_name_input = ft.TextField(hint_text="اسم المشروع الجديد", text_size=13, expand=True)
    file_name_input = ft.TextField(hint_text="مثال: src/utils.py", text_size=13, expand=True)
    folder_name_input = ft.TextField(hint_text="مجلد جديد: src", text_size=13, expand=True)
    rename_input = ft.TextField(hint_text="الاسم الجديد للملف", text_size=13, expand=True)
    search_input = ft.TextField(hint_text="ابحث في ملفات المشروع...", text_size=13, expand=True)
    replace_find_input = ft.TextField(hint_text="النص المراد استبداله", text_size=13, expand=True)
    replace_with_input = ft.TextField(hint_text="استبدال بـ", text_size=13, expand=True)
    project_replace_find = ft.TextField(hint_text="النص المطلوب في كل ملفات المشروع", text_size=13, expand=True)
    project_replace_with = ft.TextField(hint_text="النص البديل في المشروع", text_size=13, expand=True)
    replace_preview_state = {"find": "", "replacement": "", "matches": 0}
    replace_apply_button = ft.Button(content="تطبيق الاستبدال", disabled=True)

    package_name_input = ft.TextField(hint_text="اسم المكتبة، مثال: requests", text_size=13, expand=True)
    script_args_input = ft.TextField(
        hint_text="وسائط التشغيل (اختياري): input.csv --verbose",
        text_size=12, dense=True, expand=True,
    )
    package_state = {"busy": False}
    run_button = ft.Button(content="تشغيل Python", bgcolor="#237A55", color="white")
    test_button = ft.Button(content="اختبارات المشروع", bgcolor="#34466B", color="white")
    stop_button = ft.Button(
        content="إيقاف التنفيذ", bgcolor="#8B3038",
        color="white", disabled=True,
    )
    run_state = {"running": False, "control": None}
    autosave_state = {"revision": 0}
    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    # GitHub credentials are deliberately session-only and never written to disk.
    github_state = {"client": None, "device": None, "client_id": "", "owner": "", "repo": "", "branch": "main", "run_id": None}

    def set_status(message: str, color: str = MUTED) -> None:
        status_text.value = message
        status_text.color = color

    def current_code() -> str:
        return editor.value or ""

    def set_editor_content(content: str, file_name: str) -> None:
        editor.value = content
        editor.language = LANGUAGE_BY_SUFFIX.get(
            Path(file_name).suffix.lower(), fce.CodeLanguage.PLAINTEXT
        )
        active_file_label.value = file_name

    def active_project_name() -> str:
        for project in store.list_projects():
            if project["id"] == active_project:
                return project["name"]
        return active_project

    def save_current_file(show_status: bool = False) -> None:
        # Invalidate delayed saves scheduled for an earlier editor state.
        autosave_state["revision"] += 1
        store.write_file(active_project, active_file, current_code())
        store.save_settings(active_project, active_file)
        if show_status:
            set_status("تم حفظ الملف على الجهاز.", SUCCESS)

    def refresh_project_buttons() -> None:
        project_buttons.controls = []
        for project in store.list_projects():
            project_id = project["id"]
            is_active = project_id == active_project
            project_buttons.controls.append(
                ft.Button(
                    content=project["name"],
                    on_click=lambda e, selected=project_id: open_project(selected),
                    bgcolor=ACCENT if is_active else "#202A3A",
                    color="white",
                )
            )

    def refresh_tab_buttons() -> None:
        tab_buttons.controls = []
        for name in tabs.files:
            is_active = name == active_file
            tab_buttons.controls.append(
                ft.Row(
                    controls=[
                        ft.Button(
                            content=name,
                            on_click=lambda e, selected=name: open_file(selected),
                            bgcolor=ACCENT if is_active else "#202A3A",
                            color="white",
                        ),
                        ft.Button(
                            content="×",
                            on_click=lambda e, selected=name: close_tab(selected),
                            bgcolor="#3A2630",
                            color="white",
                        ),
                    ],
                    spacing=2,
                )
            )

    def toggle_tree_folder(folder: str) -> None:
        if folder in expanded_folders:
            expanded_folders.remove(folder)
        else:
            expanded_folders.add(folder)
        refresh_file_buttons()
        page.update()

    def refresh_file_buttons() -> None:
        file_buttons.controls = []
        tree_view.controls = []

        entries = build_tree_entries(
            store.list_files(active_project),
            store.list_folders(active_project),
            expanded_folders,
        )

        for kind, path, depth in entries:
            indent = "　" * depth
            if kind == "folder":
                opened = path in expanded_folders
                symbol = "📂" if opened else "📁"
                tree_view.controls.append(
                    ft.Button(
                        content=f"{indent}{symbol} {PurePosixPath(path).name}",
                        on_click=lambda e, selected=path: toggle_tree_folder(selected),
                        bgcolor="#202A3A",
                        color="white",
                    )
                )
            else:
                is_active = path == active_file
                tree_view.controls.append(
                    ft.Button(
                        content=f"{indent}📄 {PurePosixPath(path).name}",
                        on_click=lambda e, selected=path: open_file(selected),
                        bgcolor=ACCENT if is_active else "#172131",
                        color="white",
                    )
                )

        active_file_label.value = active_file
        refresh_tab_buttons()

    def refresh_project_summary() -> None:
        files = store.list_files(active_project)
        folders = store.list_folders(active_project)
        assets = store.list_assets(active_project)
        project_summary.value = (
            f"{len(files)} ملف · {len(folders)} مجلد · {len(assets)} أصل بصري · "
            f"{active_project_name()}"
        )

    def open_file(name: str) -> None:
        nonlocal active_file
        try:
            save_current_file()
            tabs.open(name)
            active_file = name
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تم فتح {active_file}", SUCCESS)
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def close_tab(name: str) -> None:
        nonlocal active_file
        try:
            if name == active_file:
                save_current_file()
            next_active = tabs.close(name)
            if name == active_file:
                if next_active is None:
                    tabs.open(name)
                    set_status("يجب إبقاء تبويب واحد مفتوح على الأقل.", MUTED)
                else:
                    active_file = next_active
                    set_editor_content(
                        store.read_file(active_project, active_file), active_file
                    )
                    store.save_settings(active_project, active_file)
            refresh_file_buttons()
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def open_project(project_id: str) -> None:
        nonlocal active_project, active_file
        try:
            save_current_file()
            active_project = project_id
            project_files = store.list_files(active_project)
            if not project_files:
                raise WorkspaceError("المشروع المحدد لا يحتوي على ملفات نصية.")
            active_file = "main.py" if "main.py" in project_files else project_files[0]
            tabs.reset(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_project_buttons()
            refresh_file_buttons()
            refresh_project_summary()
            set_status("تم فتح المشروع وحفظ التغييرات السابقة.", SUCCESS)
            page.update()
        except (WorkspaceError, IndexError) as exc:
            set_status(str(exc) or "تعذر فتح المشروع.", DANGER)
            page.update()

    async def save_after_typing(revision: int) -> None:
        # Rapid typing is coalesced into one disk write after a short pause.
        await asyncio.sleep(0.7)
        if revision != autosave_state["revision"]:
            return
        try:
            store.write_file(active_project, active_file, current_code())
            store.save_settings(active_project, active_file)
            if revision == autosave_state["revision"]:
                set_status("تم الحفظ تلقائياً · كل التغييرات محفوظة", SUCCESS)
                page.update()
        except WorkspaceError as exc:
            if revision == autosave_state["revision"]:
                set_status(f"فشل الحفظ التلقائي: {exc}", DANGER)
                page.update()

    def on_editor_change(e: ft.Event[fce.CodeEditor]) -> None:
        if e.data is not None:
            editor.value = e.data
        autosave_state["revision"] += 1
        revision = autosave_state["revision"]
        set_status("تغييرات غير محفوظة · جارٍ الحفظ…", "#E4C27A")
        page.run_task(save_after_typing, revision)

    def create_project(e) -> None:
        nonlocal active_project, active_file
        try:
            save_current_file()
            new_id = store.create_project(project_name_input.value or "")
            active_project = new_id
            active_file = "main.py"
            tabs.reset(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            project_name_input.value = ""
            store.save_settings(active_project, active_file)
            refresh_project_buttons()
            refresh_file_buttons()
            refresh_project_summary()
            set_status("تم إنشاء المشروع.", SUCCESS)
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def create_template_project(template_name: str) -> None:
        nonlocal active_project, active_file
        try:
            save_current_file()
            project_id = store.create_project_from_template(
                template_name, TEMPLATES[template_name]
            )
            active_project = project_id
            active_file = "main.py"
            tabs.reset(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_project_buttons()
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تم إنشاء قالب {template_name}.", SUCCESS)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    def create_starter_project(e) -> None:
        create_template_project("Python Starter")

    def create_automation_project(e) -> None:
        create_template_project("Automation Starter")

    def create_file(e) -> None:
        nonlocal active_file
        try:
            save_current_file()
            active_file = store.create_file(active_project, file_name_input.value or "")
            tabs.open(active_file)
            file_name_input.value = ""
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تم إنشاء {active_file}.", SUCCESS)
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def create_folder(e) -> None:
        try:
            folder = store.create_folder(active_project, folder_name_input.value or "")
            folder_name_input.value = ""
            expanded_folders.add(folder)
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تم إنشاء المجلد {folder}.", SUCCESS)
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def rename_current_file(e) -> None:
        nonlocal active_file
        try:
            save_current_file()
            old_name = active_file
            new_name = store.rename_file(
                active_project, active_file, rename_input.value or ""
            )
            tabs.rename(old_name, new_name)
            active_file = new_name
            rename_input.value = ""
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تمت إعادة تسمية الملف إلى {active_file}.", SUCCESS)
            page.update()
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def delete_file(e) -> None:
        nonlocal active_file
        try:
            save_current_file()
            deleted_file = active_file
            store.delete_file(active_project, deleted_file)
            next_open = tabs.close(deleted_file)
            remaining = store.list_files(active_project)
            active_file = (
                next_open if next_open in remaining
                else ("main.py" if "main.py" in remaining else remaining[0])
            )
            if active_file not in tabs.files:
                tabs.open(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status("تم حذف الملف المحدد.", SUCCESS)
            page.update()
        except (WorkspaceError, IndexError) as exc:
            set_status(str(exc) or "تعذر حذف الملف.", DANGER)
            page.update()

    def duplicate_current_file(e) -> None:
        nonlocal active_file
        try:
            save_current_file()
            active_file = store.duplicate_file(active_project, active_file)
            tabs.open(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status(f"تم نسخ الملف إلى {active_file}.", SUCCESS)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    async def import_project_zip(e) -> None:
        nonlocal active_project, active_file
        try:
            selected = await file_picker.pick_files(
                dialog_title="اختر مشروع ZIP",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["zip"],
                allow_multiple=False,
                with_data=True,
            )
            if not selected:
                return
            picked = selected[0]
            if picked.size and picked.size > MAX_ARCHIVE_BYTES:
                raise WorkspaceError("ملف ZIP أكبر من الحد المسموح (12 ميجابايت).")
            archive_bytes = picked.bytes
            if archive_bytes is None and picked.path:
                archive_bytes = Path(picked.path).read_bytes()
            if archive_bytes is None:
                raise WorkspaceError("تعذر قراءة محتوى ملف ZIP من مدير الملفات.")
            display_name = Path(picked.name).stem[:48] or "Imported Project"
            save_current_file()
            project_id = store.import_project_archive(archive_bytes, display_name)
            active_project = project_id
            files = store.list_files(active_project)
            active_file = "main.py" if "main.py" in files else files[0]
            tabs.reset(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_project_buttons()
            refresh_file_buttons()
            refresh_project_summary()
            set_status("تم استيراد المشروع من ZIP بنجاح.", SUCCESS)
        except (WorkspaceError, OSError) as exc:
            set_status(str(exc), DANGER)
        finally:
            page.update()

    async def export_project_zip(e) -> None:
        try:
            save_current_file()
            archive_bytes = store.export_project_archive(active_project)
            file_name = f"{active_project_name().replace(' ', '_')}.zip"
            saved_path = await file_picker.save_file(
                dialog_title="تصدير المشروع",
                file_name=file_name,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["zip"],
                src_bytes=archive_bytes,
            )
            if saved_path:
                set_status(f"تم تصدير المشروع: {saved_path}", SUCCESS)
            else:
                set_status("تم تجهيز ملف ZIP أو أُلغي الحفظ.", MUTED)
        except (WorkspaceError, OSError, ValueError) as exc:
            set_status(str(exc), DANGER)
        page.update()

    async def run_project_tests(e) -> None:
        show_screen("terminal")
        if run_state["running"]:
            return
        try:
            save_current_file()
        except WorkspaceError as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status("تعذر حفظ الملف قبل الاختبارات.", DANGER)
            page.update()
            return

        project_path = str(store._project_dir(active_project))
        run_state["running"] = True
        run_state["control"] = ExecutionControl(timeout_seconds=180)
        run_button.disabled = True
        test_button.disabled = True
        stop_button.disabled = False
        output_text.value = "جارٍ اكتشاف اختبارات المشروع وتشغيلها..."
        output_text.color = TEXT
        set_status("تشغيل اختبارات المشروع...", ACCENT)
        page.update()
        started_at = time.monotonic()
        try:
            result, succeeded = await asyncio.to_thread(
                execute_unittest_discovery,
                project_path,
                "tests",
                "test*.py",
                None,
                run_state["control"],
            )
            output_text.value = result[:OUTPUT_LIMIT]
            if len(result) > OUTPUT_LIMIT:
                output_text.value += "\n\n[تم اختصار سجل الاختبارات لطوله الكبير]"
            output_text.color = SUCCESS if succeeded else DANGER
            elapsed = time.monotonic() - started_at
            set_status(
                f"نجحت اختبارات المشروع خلال {elapsed:.2f} ثانية."
                if succeeded else f"لم تنجح جميع الاختبارات ({elapsed:.2f} ثانية).",
                SUCCESS if succeeded else DANGER,
            )
        except Exception as exc:
            output_text.value = f"تعذر تشغيل الاختبارات: {exc}"
            output_text.color = DANGER
            set_status("فشل تشغيل اختبارات المشروع.", DANGER)
        finally:
            run_state["running"] = False
            run_state["control"] = None
            run_button.disabled = False
            test_button.disabled = False
            stop_button.disabled = True
            page.update()

    async def run_code(e) -> None:
        show_screen("terminal")
        if run_state["running"]:
            return
        if Path(active_file).suffix.lower() not in {".py", ".pyw"}:
            set_status("يمكن تشغيل ملفات Python فقط.", DANGER)
            page.update()
            return
        try:
            save_current_file()
        except WorkspaceError as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            page.update()
            return

        run_state["running"] = True
        run_state["control"] = ExecutionControl(timeout_seconds=60)
        run_button.disabled = True
        stop_button.disabled = False
        set_status("جارٍ التنفيذ — ستظهر المخرجات مباشرة.", ACCENT)
        output_text.value = ""
        output_text.color = TEXT
        page.update()

        code_snapshot = current_code()
        try:
            script_args = shlex.split(script_args_input.value or "", posix=True)
        except ValueError as exc:
            run_state["running"] = False
            run_state["control"] = None
            run_button.disabled = False
            stop_button.disabled = True
            output_text.value = f"وسائط التشغيل غير صحيحة: {exc}"
            output_text.color = DANGER
            set_status("راجع علامات الاقتباس في وسائط التشغيل.", DANGER)
            page.update()
            return
        file_path = str(store.root / "projects" / active_project / active_file)
        project_path = str(store.root / "projects" / active_project)
        output_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        streamed_text = ""
        was_truncated = False
        started_at = time.monotonic()

        def emit_output(chunk: str) -> None:
            if chunk:
                loop.call_soon_threadsafe(output_queue.put_nowait, chunk)

        def append_output(chunk: str) -> None:
            nonlocal streamed_text, was_truncated
            streamed_text += chunk
            if len(streamed_text) > OUTPUT_LIMIT:
                streamed_text = streamed_text[-OUTPUT_LIMIT:]
                was_truncated = True
            output_text.value = streamed_text
            if was_truncated:
                output_text.value += "\n\n[تم اختصار الإخراج لطوله الكبير]"
            page.update()

        try:
            worker = asyncio.create_task(
                asyncio.to_thread(
                    execute_python,
                    code_snapshot,
                    file_path,
                    project_path,
                    emit_output,
                    run_state["control"],
                    script_args,
                )
            )

            while not worker.done():
                try:
                    chunk = await asyncio.wait_for(
                        output_queue.get(), timeout=0.1
                    )
                    append_output(chunk)
                except asyncio.TimeoutError:
                    pass

            result, succeeded = await worker

            while not output_queue.empty():
                append_output(output_queue.get_nowait())

            if not streamed_text:
                output_text.value = result[:OUTPUT_LIMIT]
                if len(result) > OUTPUT_LIMIT:
                    output_text.value += "\n\n[تم اختصار الإخراج لطوله الكبير]"
            output_text.color = SUCCESS if succeeded else DANGER

            elapsed = time.monotonic() - started_at
            if result.startswith("تم إيقاف التنفيذ"):
                set_status("تم إيقاف التنفيذ.", MUTED)
            elif result.startswith("انتهت مهلة التنفيذ"):
                set_status("تجاوز البرنامج مهلة التنفيذ.", DANGER)
            else:
                set_status(
                    f"اكتمل التنفيذ خلال {elapsed:.2f} ثانية."
                    if succeeded
                    else f"انتهى التنفيذ بخطأ بعد {elapsed:.2f} ثانية.",
                    SUCCESS if succeeded else DANGER,
                )
        except Exception as exc:
            output_text.value = f"تعذر تشغيل الكود: {exc}"
            output_text.color = DANGER
            set_status("فشل تشغيل الكود.", DANGER)
        finally:
            run_state["running"] = False
            run_state["control"] = None
            run_button.disabled = False
            stop_button.disabled = True
            page.update()


    def stop_code(e) -> None:
        control = run_state.get("control")
        if control is not None and run_state["running"]:
            control.cancel()
            stop_button.disabled = True
            set_status("تم إرسال طلب الإيقاف...", MUTED)
            page.update()

    def analyze_current_project(e) -> None:
        show_screen("terminal")
        try:
            save_current_file()
            report = inspect_project(store, active_project)
            output_text.value = format_analysis_report(active_project_name(), report)[:OUTPUT_LIMIT]
            output_text.color = SUCCESS if report["valid_syntax"] else DANGER
            diagnostics_count = len(report["diagnostics"])
            set_status(
                f"اكتمل الفحص الثابت: {diagnostics_count} ملاحظة. لم يتم تشغيل ملفات المشروع.",
                SUCCESS if report["valid_syntax"] else DANGER,
            )
        except (WorkspaceError, OSError, ValueError) as exc:
            output_text.value = f"تعذر فحص المشروع: {exc}"
            output_text.color = DANGER
            set_status("فشل فحص المشروع.", DANGER)
        page.update()

    def preview_project_replace(e) -> None:
        show_screen("terminal")
        try:
            save_current_file()
            find_text = project_replace_find.value or ""
            replacement = project_replace_with.value or ""
            preview = store.preview_replace_project(active_project, find_text, replacement)
            replace_preview_state.update({
                "find": find_text, "replacement": replacement,
                "matches": preview["matches"],
            })
            replace_apply_button.disabled = preview["matches"] == 0
            if preview["matches"]:
                details = "\n".join(
                    f"{item['file']} — {item['matches']} تطابق" for item in preview["files"]
                )
                output_text.value = (
                    f"معاينة الاستبدال في المشروع\nالتطابقات: {preview['matches']}\n"
                    f"الملفات المتأثرة: {len(preview['files'])}\n\n{details}\n\n"
                    "لم يتم تعديل أي ملف بعد. اضغط تطبيق الاستبدال لاعتماد التغيير."
                )
                set_status("تمت المعاينة فقط؛ لم تتغير الملفات.", SUCCESS)
            else:
                output_text.value = "لم يتم العثور على النص المطلوب في ملفات المشروع."
                set_status("لا توجد تطابقات للاستبدال.", MUTED)
            output_text.color = TEXT
        except WorkspaceError as exc:
            replace_apply_button.disabled = True
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status(str(exc), DANGER)
        page.update()

    def apply_project_replace(e) -> None:
        show_screen("terminal")
        try:
            find_text = replace_preview_state["find"]
            replacement = replace_preview_state["replacement"]
            if not find_text or not replace_preview_state["matches"]:
                raise WorkspaceError("نفّذ معاينة الاستبدال أولاً.")
            # Prevent applying stale or changed preview input.
            if find_text != (project_replace_find.value or "") or replacement != (project_replace_with.value or ""):
                raise WorkspaceError("تغيرت حقول الاستبدال. أعد المعاينة قبل التطبيق.")
            result = store.replace_in_project(active_project, find_text, replacement)
            if active_file in result["files"]:
                set_editor_content(store.read_file(active_project, active_file), active_file)
            replace_preview_state.update({"find": "", "replacement": "", "matches": 0})
            replace_apply_button.disabled = True
            refresh_file_buttons()
            output_text.value = (
                f"تم الاستبدال بنجاح.\nعدد الاستبدالات: {result['matches']}\n"
                f"عدد الملفات المعدلة: {result['files_changed']}\n"
                + "\n".join(result["files"])
            )
            output_text.color = SUCCESS
            set_status("تم تطبيق الاستبدال في المشروع.", SUCCESS)
        except WorkspaceError as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status(str(exc), DANGER)
        page.update()

    def open_requirements_file(e) -> None:
        nonlocal active_file
        try:
            save_current_file()
            if "requirements.txt" not in store.list_files(active_project):
                store.create_file(active_project, "requirements.txt")
            active_file = "requirements.txt"
            tabs.open(active_file)
            set_editor_content(store.read_file(active_project, active_file), active_file)
            store.save_settings(active_project, active_file)
            refresh_file_buttons()
            refresh_project_summary()
            set_status("تم فتح ملف الاعتماديات. أضف أسماء الحزم المتوافقة مع Android يدوياً.", SUCCESS)
            show_screen("editor")
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    async def install_one_package(e) -> None:
        show_screen("terminal")
        if package_state["busy"]:
            return
        package = (package_name_input.value or "").strip()
        try:
            packages = parse_requirements(package)
            if len(packages) != 1:
                raise PackageManagerError("أدخل اسم مكتبة واحدة فقط.")
            package_state["busy"] = True
            set_status("جارٍ تثبيت المكتبة...", ACCENT)
            output_text.value = "يتم تثبيت المكتبة عبر Python الحالي..."
            output_text.color = TEXT
            page.update()
            result = await asyncio.to_thread(install_packages, packages)
            output_text.value = result
            package_name_input.value = ""
            set_status("اكتمل تثبيت المكتبة. أعد تشغيل التطبيق إذا لزم.", SUCCESS)
        except PackageManagerError as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status("تعذر تثبيت المكتبة.", DANGER)
        finally:
            package_state["busy"] = False
            page.update()

    async def install_project_requirements(e) -> None:
        show_screen("terminal")
        if package_state["busy"]:
            return
        try:
            if "requirements.txt" not in store.list_files(active_project):
                raise PackageManagerError("لا يوجد requirements.txt في المشروع.")
            requirements = store.read_file(active_project, "requirements.txt")
            packages = parse_requirements(requirements)
            if not packages:
                raise PackageManagerError("ملف requirements.txt فارغ.")
            package_state["busy"] = True
            set_status(f"جارٍ تثبيت {len(packages)} مكتبة...", ACCENT)
            output_text.value = "يتم تثبيت اعتماديات المشروع..."
            output_text.color = TEXT
            page.update()
            result = await asyncio.to_thread(install_packages, packages)
            output_text.value = result
            set_status(f"اكتمل تثبيت {len(packages)} مكتبة.", SUCCESS)
        except (PackageManagerError, WorkspaceError) as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status("تعذر تثبيت اعتماديات المشروع.", DANGER)
        finally:
            package_state["busy"] = False
            page.update()

    def show_installed_packages(e) -> None:
        show_screen("terminal")
        try:
            packages = list_installed()
            output_text.value = "المكتبات المثبتة ({})\n".format(len(packages))
            output_text.value += "\n".join(
                f"{name}  —  {version}" for name, version in packages
            )
            output_text.color = TEXT
            set_status(f"عدد المكتبات المثبتة: {len(packages)}", SUCCESS)
        except Exception as exc:
            output_text.value = f"تعذر قراءة المكتبات: {exc}"
            output_text.color = DANGER
            set_status("فشل عرض المكتبات.", DANGER)
        page.update()

    def check_current_syntax(e) -> None:
        show_screen("terminal")
        if Path(active_file).suffix.lower() not in {".py", ".pyw"}:
            set_status("الفحص النحوي متاح لملفات Python فقط.", DANGER)
            page.update()
            return
        valid, message = check_python(current_code(), active_file)
        output_text.value = message
        output_text.color = SUCCESS if valid else DANGER
        set_status("الفحص النحوي ناجح." if valid else "يوجد خطأ في الصياغة.", SUCCESS if valid else DANGER)
        page.update()

    def search_project(e) -> None:
        show_screen("terminal")
        try:
            results = store.search_project(active_project, search_input.value or "")
            if not results:
                output_text.value = "لم يتم العثور على نتائج."
            else:
                output_text.value = "\n".join(
                    f"{item['file']}:{item['line']}  {item['snippet']}"
                    for item in results
                )
            output_text.color = TEXT
            set_status(f"نتائج البحث: {len(results)}", SUCCESS)
        except WorkspaceError as exc:
            output_text.value = str(exc)
            output_text.color = DANGER
            set_status(str(exc), DANGER)
        page.update()

    def replace_in_current_file(e) -> None:
        find_text = replace_find_input.value or ""
        if not find_text:
            set_status("اكتب النص المراد استبداله.", DANGER)
            page.update()
            return
        updated, count = current_code().replace(find_text, replace_with_input.value or ""), current_code().count(find_text)
        if count == 0:
            set_status("لم يتم العثور على النص في الملف الحالي.", MUTED)
            page.update()
            return
        set_editor_content(updated, active_file)
        try:
            save_current_file()
            set_status(f"تم استبدال {count} موضعاً في الملف الحالي.", SUCCESS)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    async def fold_imports(e) -> None:
        try:
            await editor.fold_imports()
            set_status("تم طي مجموعة الاستيراد.", SUCCESS)
        except Exception as exc:
            set_status(f"تعذر طي الاستيرادات: {exc}", DANGER)
        page.update()

    async def fold_first_comment(e) -> None:
        try:
            await editor.fold_comment_at_line_zero()
            set_status("تم طي التعليق العلوي.", SUCCESS)
        except Exception as exc:
            set_status(f"تعذر طي التعليق: {exc}", DANGER)
        page.update()

    def clear_output(e) -> None:
        output_text.value = "سجل المخرجات فارغ."
        output_text.color = MUTED
        page.update()

    def load_example(e) -> None:
        if Path(active_file).suffix.lower() not in {".py", ".pyw"}:
            set_status("مثال Python متاح داخل ملفات Python فقط.", DANGER)
            page.update()
            return
        set_editor_content(
            "def greet(name: str) -> str:\n"
            "    return f'Hello, {name}!'\n\n"
            "for person in ['Python', 'AI Python Studio']:\n"
            "    print(greet(person))\n",
            active_file,
        )
        try:
            save_current_file()
            set_status("تم تحميل المثال وحفظه في الملف.", SUCCESS)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    def save_and_update() -> None:
        try:
            save_current_file(show_status=True)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    editor.on_change = on_editor_change
    run_button.on_click = run_code
    test_button.on_click = run_project_tests
    stop_button.on_click = stop_code
    replace_apply_button.on_click = apply_project_replace

    # ── Visual system: compact mobile IDE ──────────────────────────────
    def make_panel(content, *, padding=14, radius=18, height=None):
        return ft.Container(
            content=content,
            padding=padding,
            bgcolor=PANEL,
            border=ft.Border.all(1, "#243147"),
            border_radius=radius,
            height=height,
        )

    def section_heading(title, subtitle=None):
        controls = [
            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=TEXT),
        ]
        if subtitle:
            controls.append(ft.Text(subtitle, size=11, color=MUTED))
        return ft.Column(controls=controls, spacing=3)

    # Header
    project_summary = ft.Text("", size=11, color=MUTED)
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        "Py", size=20, weight=ft.FontWeight.BOLD, color="white"
                    ),
                    width=46, height=46, alignment=ft.Alignment.CENTER,
                    bgcolor=ACCENT, border_radius=15,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            "AI Python Studio", size=18,
                            weight=ft.FontWeight.BOLD, color=TEXT,
                        ),
                        ft.Text(
                            "بيئة تطوير Python للهاتف", size=11, color=MUTED
                        ),
                    ],
                    spacing=2, expand=True,
                ),
                ft.Container(
                    content=ft.Text("v1.1", size=10, color="#D8D3FF"),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    bgcolor="#252342", border_radius=20,
                ),
            ],
            spacing=11,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.only(left=16, right=16, top=10, bottom=10),
        bgcolor="#0E1623",
        border=ft.Border.only(bottom=ft.BorderSide(1, "#243147")),
    )

    # Android app configuration (used by the Flet Android project template).
    android_app_name = ft.TextField(label="اسم التطبيق", value="My Android App", text_size=13)
    android_package_id = ft.TextField(label="معرّف التطبيق Android", value="com.example.myandroidapp", text_size=13)
    android_version = ft.TextField(label="الإصدار", value="0.1.0", text_size=13)
    android_build_number = ft.TextField(label="رقم البناء", value="1", text_size=13)
    android_config_status = ft.Text("هذه الإعدادات تطبق على مشاريع Flet Android التي تحتوي pyproject.toml.", size=11, color=MUTED)

    def save_android_configuration(e) -> None:
        from flet_project import configure_flet_project, validate_flet_project
        try:
            save_current_file()
            project_path = store._project_dir(active_project)
            result = configure_flet_project(
                project_path,
                app_name=android_app_name.value or "",
                application_id=android_package_id.value or "",
                version=android_version.value or "",
                build_number=android_build_number.value or "",
            )
            android_config_status.value = "تم حفظ إعدادات Android بنجاح. " + result
            android_config_status.color = SUCCESS
            set_status("تم تحديث إعدادات تطبيق Android.", SUCCESS)
        except (ValueError, OSError) as exc:
            android_config_status.value = str(exc)
            android_config_status.color = DANGER
            set_status("تعذر حفظ إعدادات Android.", DANGER)
        page.update()

    def validate_android_project(e) -> None:
        from flet_project import validate_flet_project
        try:
            issues = validate_flet_project(store._project_dir(active_project))
            if issues:
                android_config_status.value = "مشكلات يجب إصلاحها قبل البناء:\\n• " + "\\n• ".join(issues)
                android_config_status.color = DANGER
                set_status("فشل فحص مشروع Android قبل البناء.", DANGER)
            else:
                android_config_status.value = "المشروع جاهز مبدئياً للبناء السحابي. راجع إعدادات GitHub Actions."
                android_config_status.color = SUCCESS
                set_status("اجتاز المشروع فحص ما قبل البناء.", SUCCESS)
        except OSError as exc:
            android_config_status.value = str(exc)
            android_config_status.color = DANGER
        page.update()

    android_config_panel = make_panel(
        ft.Column(controls=[
            section_heading("إعداد تطبيق Android", "اسم التطبيق ومعرّف الحزمة والإصدار قبل إنشاء APK"),
            android_app_name,
            android_package_id,
            ft.Row(controls=[android_version, android_build_number], spacing=8),
            ft.Row(controls=[
                ft.Button(content="حفظ الإعدادات", on_click=save_android_configuration, bgcolor=ACCENT, color="white"),
                ft.Button(content="فحص قبل البناء", on_click=validate_android_project),
            ], wrap=True, spacing=8),
            android_config_status,
        ], spacing=9)
    )


    # GitHub cloud build integration. OAuth tokens remain in memory only.
    github_client_id = ft.TextField(label="OAuth Client ID", hint_text="Client ID من GitHub OAuth App", text_size=12)
    github_repository = ft.TextField(label="المستودع owner/repository", hint_text="username/my-flet-app", text_size=12)
    github_branch = ft.TextField(label="الفرع", value="main", text_size=12)
    github_device_info = ft.Text("لم يتم ربط GitHub بعد.", size=11, color=MUTED, selectable=True)
    github_private = ft.Checkbox(label="مستودع خاص (Private)", value=True)
    github_status = ft.Text("الرمز لا يُحفظ على الجهاز؛ ينتهي عند إغلاق التطبيق أو قطع الاتصال.", size=11, color=MUTED)

    async def start_github_login(e) -> None:
        try:
            client_id = (github_client_id.value or "").strip()
            auth = await asyncio.to_thread(GitHubClient.start_device_authorization, client_id)
            github_state["device"] = auth
            github_state["client_id"] = client_id
            github_device_info.value = (
                f"افتح: {auth.verification_uri}\\n"
                f"أدخل الرمز: {auth.user_code}\\n"
                "بعد الموافقة اضغط «التحقق من تسجيل الدخول»."
            )
            github_status.value = "في انتظار موافقتك من صفحة GitHub."
            github_status.color = ACCENT
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def verify_github_login(e) -> None:
        auth = github_state.get("device")
        if auth is None:
            github_status.value = "ابدأ تسجيل الدخول أولاً."
            github_status.color = DANGER
            page.update()
            return
        try:
            token = await asyncio.to_thread(
                GitHubClient.poll_device_authorization, github_state["client_id"], auth
            )
            if not token:
                github_status.value = "لم تتم الموافقة بعد. أكمل الخطوات في GitHub ثم أعد المحاولة."
                github_status.color = ACCENT
            else:
                client = GitHubClient(token)
                user = await asyncio.to_thread(client.current_user)
                old = github_state.get("client")
                if old:
                    old.clear()
                github_state["client"] = client
                github_state["device"] = None
                github_status.value = f"تم الاتصال بالحساب @{user.get('login', 'GitHub')} بنجاح."
                github_status.color = SUCCESS
                github_device_info.value = "تم تسجيل الدخول. يمكنك الآن اختيار مستودع أو إنشاؤه."
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def disconnect_github(e) -> None:
        client = github_state.get("client")
        if client:
            client.clear()
        github_state.update({"client": None, "device": None, "run_id": None})
        github_status.value = "تم قطع الاتصال ومسح الرمز من ذاكرة التطبيق."
        github_status.color = MUTED
        github_device_info.value = "لم يتم ربط GitHub."
        page.update()

    async def list_github_repositories(e) -> None:
        client = github_state.get("client")
        if not client:
            github_status.value = "سجّل الدخول إلى GitHub أولاً."
            github_status.color = DANGER
            page.update()
            return
        try:
            repos = await asyncio.to_thread(client.list_repositories)
            lines = [f"{item['full_name']}  ·  {'Private' if item.get('private') else 'Public'}"
                     for item in repos[:80]]
            output_text.value = "مستودعات GitHub المتاحة (حتى 80):\\n" + "\\n".join(lines)
            output_text.color = TEXT
            github_status.value = f"تم جلب {len(repos)} مستودعاً. اكتب owner/repository في الحقل."
            github_status.color = SUCCESS
            show_screen("terminal")
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def create_github_repository(e) -> None:
        client = github_state.get("client")
        if not client:
            github_status.value = "سجّل الدخول إلى GitHub أولاً."
            github_status.color = DANGER
            page.update()
            return
        name = (github_repository.value or "").strip()
        if "/" in name or not name:
            github_status.value = "عند إنشاء مستودع جديد اكتب الاسم فقط، دون owner/."
            github_status.color = DANGER
            page.update()
            return
        try:
            created = await asyncio.to_thread(
                client.create_repository, name, bool(github_private.value)
            )
            github_repository.value = created["full_name"]
            github_branch.value = created.get("default_branch") or "main"
            github_status.value = f"تم إنشاء المستودع {created['full_name']}."
            github_status.color = SUCCESS
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    def parse_github_repository():
        value = (github_repository.value or "").strip().strip("/")
        parts = value.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise GitHubError("اكتب المستودع بالصيغة owner/repository.")
        branch = (github_branch.value or "").strip()
        if not branch or branch.startswith("-") or ".." in branch:
            raise GitHubError("اسم الفرع غير صالح.")
        return parts[0], parts[1], branch

    async def upload_project_to_github(e) -> None:
        client = github_state.get("client")
        if not client:
            github_status.value = "سجّل الدخول إلى GitHub أولاً."
            github_status.color = DANGER
            page.update()
            return
        try:
            owner, repo_name, branch = parse_github_repository()
            save_current_file()
            archive = store.export_project_archive(active_project)
            github_status.value = "جارٍ رفع ملفات المشروع إلى GitHub..."
            github_status.color = ACCENT
            page.update()
            commit_sha = await asyncio.to_thread(
                client.push_project_archive, owner, repo_name, branch, archive
            )
            github_state.update({"owner": owner, "repo": repo_name, "branch": branch})
            github_status.value = f"تم رفع المشروع. Commit: {commit_sha[:10]}"
            github_status.color = SUCCESS
        except (GitHubError, WorkspaceError, OSError) as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def trigger_github_build(e) -> None:
        client = github_state.get("client")
        if not client:
            github_status.value = "سجّل الدخول إلى GitHub أولاً."
            github_status.color = DANGER
            page.update()
            return
        try:
            owner, repo_name, branch = parse_github_repository()
            github_status.value = "جارٍ تشغيل GitHub Actions..."
            github_status.color = ACCENT
            page.update()
            await asyncio.to_thread(
                client.dispatch_workflow, owner, repo_name, "build-apk.yml", branch
            )
            github_state.update({"owner": owner, "repo": repo_name, "branch": branch})
            github_status.value = "تم إرسال طلب البناء. انتظر قليلاً ثم اضغط متابعة البناء."
            github_status.color = SUCCESS
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def refresh_github_build(e) -> None:
        client = github_state.get("client")
        if not client:
            github_status.value = "سجّل الدخول إلى GitHub أولاً."
            github_status.color = DANGER
            page.update()
            return
        try:
            owner, repo_name, branch = parse_github_repository()
            runs = await asyncio.to_thread(client.list_workflow_runs, owner, repo_name, branch, 5)
            if not runs:
                github_status.value = "لم يظهر بناء بعد. تأكد من وجود workflow باسم build-apk.yml."
                github_status.color = MUTED
            else:
                run = runs[0]
                github_state["run_id"] = run["id"]
                jobs = await asyncio.to_thread(client.list_run_jobs, owner, repo_name, run["id"])
                job_lines = []
                for job in jobs:
                    job_lines.append(f"{job.get('name')}: {job.get('status')} / {job.get('conclusion') or 'قيد التنفيذ'}")
                    for step in job.get("steps", []):
                        job_lines.append(f"  - {step.get('name')}: {step.get('conclusion') or step.get('status')}")
                output_text.value = (
                    f"GitHub Actions · Run #{run.get('run_number')}\\n"
                    f"الحالة: {run.get('status')} · النتيجة: {run.get('conclusion') or 'لم تنته'}\\n"
                    f"الرابط: {run.get('html_url')}\\n\\n" + "\\n".join(job_lines)
                )
                output_text.color = SUCCESS if run.get("conclusion") == "success" else (DANGER if run.get("conclusion") == "failure" else TEXT)
                github_status.value = f"آخر بناء: {run.get('status')} / {run.get('conclusion') or 'قيد التنفيذ'}"
                github_status.color = SUCCESS if run.get("conclusion") == "success" else (DANGER if run.get("conclusion") == "failure" else ACCENT)
                show_screen("terminal")
        except GitHubError as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    async def download_github_apk(e) -> None:
        client = github_state.get("client")
        run_id = github_state.get("run_id")
        if not client or not run_id:
            github_status.value = "حدّث حالة البناء أولاً بعد تسجيل الدخول."
            github_status.color = DANGER
            page.update()
            return
        try:
            owner, repo_name, _ = parse_github_repository()
            artifacts = await asyncio.to_thread(client.list_artifacts, owner, repo_name, run_id)
            artifact = next((item for item in artifacts if not item.get("expired")), None)
            if not artifact:
                raise GitHubError("لا يوجد APK artifact صالح لهذا البناء.")
            archive = await asyncio.to_thread(
                client.download_artifact, owner, repo_name, artifact["id"]
            )
            path = await file_picker.save_file(
                dialog_title="حفظ APK build artifact",
                file_name=f"{repo_name}-apk.zip",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["zip"],
                src_bytes=archive,
            )
            github_status.value = f"تم تنزيل أرشيف البناء إلى: {path}" if path else "تم تجهيز الأرشيف أو أُلغي الحفظ."
            github_status.color = SUCCESS if path else MUTED
        except (GitHubError, ValueError) as exc:
            github_status.value = str(exc)
            github_status.color = DANGER
        page.update()

    github_panel = make_panel(
        ft.Column(controls=[
            section_heading("GitHub والبناء السحابي", "ارفع مشروع Flet وشغّل بناء APK من الهاتف"),
            github_client_id,
            ft.Row(controls=[
                ft.Button(content="بدء تسجيل الدخول", on_click=start_github_login, bgcolor=ACCENT, color="white"),
                ft.Button(content="التحقق من تسجيل الدخول", on_click=verify_github_login),
                ft.Button(content="قطع الاتصال", on_click=disconnect_github),
            ], wrap=True, spacing=7),
            github_device_info,
            ft.Divider(color="#26354C", height=1),
            github_repository,
            github_branch,
            github_private,
            ft.Row(controls=[
                ft.Button(content="عرض مستودعاتي", on_click=list_github_repositories),
                ft.Button(content="إنشاء مستودع", on_click=create_github_repository),
            ], wrap=True, spacing=7),
            ft.Row(controls=[
                ft.Button(content="رفع المشروع", on_click=upload_project_to_github, bgcolor=ACCENT, color="white"),
                ft.Button(content="تشغيل البناء", on_click=trigger_github_build, bgcolor="#237A55", color="white"),
            ], wrap=True, spacing=7),
            ft.Row(controls=[
                ft.Button(content="متابعة البناء والسجلات", on_click=refresh_github_build),
                ft.Button(content="تنزيل APK", on_click=download_github_apk),
            ], wrap=True, spacing=7),
            github_status,
            ft.Text(
                "الأمان: Device Flow بنطاق repo وworkflow. الرمز مؤقت في الذاكرة ولا يُكتب إلى التخزين. "
                "شغّل مشاريعك الموثوقة فقط؛ لا يمكن اعتبار تنفيذ كود المستخدم معزولاً أمنياً.",
                size=10, color="#DDBB78",
            ),
        ], spacing=9)
    )

    # Projects screen
    project_panel = make_panel(
        ft.Column(
            controls=[
                section_heading("مساحة المشاريع", "أنشئ مشاريعك وافتحها ونظّم ملفاتك"),
                project_buttons,
                project_summary,
                ft.Row(
                    controls=[
                        project_name_input,
                        ft.Button(
                            content="إنشاء مشروع", on_click=create_project,
                            bgcolor=ACCENT, color="white",
                        ),
                    ],
                    spacing=8,
                ),
                ft.Row(
                    controls=[
                        ft.Button(
                            content=template_name,
                            on_click=lambda e, selected=template_name: create_template_project(selected),
                        )
                        for template_name in TEMPLATES
                    ],
                    wrap=True, spacing=7,
                ),
                ft.Row(
                    controls=[
                        ft.Button(content="استيراد ZIP", on_click=import_project_zip),
                        ft.Button(content="تصدير ZIP", on_click=export_project_zip),
                    ],
                    wrap=True, spacing=7,
                ),
            ],
            spacing=12,
        )
    )

    project_welcome = make_panel(
        ft.Column(
            controls=[
                ft.Text("مساحة عملك، مرتّبة.", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(
                    "اختر مشروعاً للمتابعة، أو ابدأ مشروعاً جديداً من الصفر أو من أحد القوالب.",
                    size=12, color=MUTED,
                ),
                ft.Row(
                    controls=[
                        ft.Text("●", color=SUCCESS, size=12),
                        ft.Text("الحفظ التلقائي مفعّل", color=SUCCESS, size=11),
                    ],
                    spacing=6,
                ),
            ],
            spacing=8,
        ),
        padding=16,
    )

    # Editor screen: code comes first; file operations stay below it.
    toolbar = ft.Row(
        controls=[
            script_args_input,
            run_button,
            test_button,
            stop_button,
            ft.Button(content="فحص", on_click=check_current_syntax),
            ft.Button(content="حفظ", on_click=lambda e: save_and_update()),
            ft.Button(content="مثال", on_click=load_example),
        ],
        wrap=True, spacing=7,
    )

    editor_panel = make_panel(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("محرر الأكواد", size=15, weight=ft.FontWeight.BOLD, color=TEXT),
                                active_file_label,
                            ],
                            spacing=2, expand=True,
                        ),
                        ft.Button(content="نسخ", on_click=duplicate_current_file),
                        ft.Button(content="حذف", on_click=delete_file),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=tab_buttons,
                    padding=ft.Padding.only(top=2, bottom=3),
                ),
                ft.Container(
                    content=editor,
                    bgcolor=EDITOR_BG,
                    border=ft.Border.all(1, "#26354C"),
                    border_radius=14,
                    padding=4,
                    height=470,
                ),
                ft.Row(
                    controls=[
                        ft.Button(content="طي الاستيرادات", on_click=fold_imports),
                        ft.Button(content="طي التعليق", on_click=fold_first_comment),
                    ],
                    wrap=True, spacing=7,
                ),
                ft.Divider(color="#26354C", height=1),
                section_heading("ملفات المشروع", "اضغط على المجلد لعرض محتوياته أو اختر ملفاً لفتحه"),
                ft.Container(
                    content=tree_view,
                    height=175,
                    bgcolor="#0B1320",
                    border=ft.Border.all(1, "#26354C"),
                    border_radius=12,
                    padding=8,
                ),
                ft.Row(
                    controls=[
                        file_name_input,
                        ft.Button(content="ملف جديد", on_click=create_file),
                    ],
                    spacing=7,
                ),
                ft.Row(
                    controls=[
                        folder_name_input,
                        ft.Button(content="مجلد جديد", on_click=create_folder),
                    ],
                    spacing=7,
                ),
                ft.Row(
                    controls=[
                        rename_input,
                        ft.Button(content="إعادة تسمية", on_click=rename_current_file),
                    ],
                    spacing=7,
                ),
            ],
            spacing=11,
        )
    )

    # Search and project tools
    search_panel = make_panel(
        ft.Column(
            controls=[
                section_heading("البحث والاستبدال", "ابحث داخل المشروع أو عدّل الملف الحالي"),
                ft.Row(
                    controls=[
                        search_input,
                        ft.Button(content="بحث المشروع", on_click=search_project),
                    ],
                    spacing=7,
                ),
                ft.Row(
                    controls=[replace_find_input, replace_with_input],
                    spacing=7, wrap=True,
                ),
                ft.Button(content="استبدال في الملف الحالي", on_click=replace_in_current_file),
            ],
            spacing=11,
        )
    )

    project_tools_panel = make_panel(
        ft.Column(
            controls=[
                section_heading("أدوات المطوّر", "تحليل المشروع وتعديل الملفات بأمان"),
                ft.Row(
                    controls=[
                        ft.Button(content="تحليل المشروع", on_click=analyze_current_project),
                        ft.Button(content="فتح requirements.txt", on_click=open_requirements_file),
                    ],
                    wrap=True, spacing=7,
                ),
                ft.Divider(color="#26354C", height=1),
                ft.Text("استبدال شامل مع معاينة قبل التطبيق", size=12, color=MUTED),
                ft.Row(
                    controls=[project_replace_find, project_replace_with],
                    wrap=True, spacing=7,
                ),
                ft.Row(
                    controls=[
                        ft.Button(content="معاينة الاستبدال", on_click=preview_project_replace),
                        replace_apply_button,
                    ],
                    wrap=True, spacing=7,
                ),
            ],
            spacing=11,
        )
    )

    # Package manager
    package_panel = make_panel(
        ft.Column(
            controls=[
                section_heading("مدير مكتبات Python", "ثبّت الاعتماديات وتابع المكتبات المتاحة"),
                ft.Row(
                    controls=[
                        package_name_input,
                        ft.Button(
                            content="تثبيت المكتبة",
                            on_click=install_one_package,
                            bgcolor=ACCENT, color="white",
                        ),
                    ],
                    spacing=7,
                ),
                ft.Row(
                    controls=[
                        ft.Button(
                            content="تثبيت requirements.txt",
                            on_click=install_project_requirements,
                        ),
                        ft.Button(
                            content="المكتبات المثبتة",
                            on_click=show_installed_packages,
                        ),
                    ],
                    wrap=True, spacing=7,
                ),
                ft.Container(
                    content=ft.Text(
                        "ملاحظة: التثبيت يستهدف مفسر Python الحالي. توافق المكتبات مع Android يختلف حسب الحزمة.",
                        size=11, color=MUTED,
                    ),
                    padding=12, bgcolor="#0D1725", border_radius=12,
                ),
            ],
            spacing=12,
        )
    )

    # Output / terminal
    output_panel = make_panel(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        section_heading("الطرفية والنتائج", "مخرجات التشغيل وتشخيص الأخطاء"),
                        ft.Button(content="مسح السجل", on_click=clear_output),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=output_text,
                    bgcolor="#080E17",
                    border=ft.Border.all(1, "#26354C"),
                    padding=14,
                    border_radius=12,
                    expand=True,
                ),
            ],
            spacing=10,
            expand=True,
        ),
        height=390,
    )

    safety_note = ft.Text(
        "تنبيه أمني: تشغيل Python محلياً ليس بيئة معزولة. شغّل الأكواد التي تثق بها فقط.",
        color="#DDBB78", size=10,
    )

    # Independent screens, switched without destroying editor/project state.
    screens = {
        "projects": ft.Column(
            controls=[project_panel, android_config_panel, project_welcome, safety_note],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
        "editor": ft.Column(
            controls=[toolbar, editor_panel],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
        "tools": ft.Column(
            controls=[search_panel, project_tools_panel],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
        "packages": ft.Column(
            controls=[package_panel],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
        "terminal": ft.Column(
            controls=[output_panel],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
        "github": ft.Column(
            controls=[github_panel],
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True,
        ),
    }

    screen_host = ft.Container(content=screens["editor"], expand=True, padding=12)
    nav_buttons = {}
    navigation_items = [
        ("projects", "▦", "المشاريع"),
        ("editor", "⌨", "المحرر"),
        ("tools", "⌕", "الأدوات"),
        ("packages", "◇", "الحزم"),
        ("terminal", "▤", "النتائج"),
        ("github", "◈", "GitHub"),
    ]
    active_screen = {"name": "editor"}

    def show_screen(name: str) -> None:
        if name not in screens:
            return
        active_screen["name"] = name
        screen_host.content = screens[name]
        for key, button in nav_buttons.items():
            selected = key == name
            button.bgcolor = "#302D59" if selected else "#121C2A"
            button.color = "#E3DFFF" if selected else MUTED
        page.update()

    nav_cells = []
    for key, symbol, label in navigation_items:
        button = ft.Button(
            content=ft.Column(
                controls=[
                    ft.Text(symbol, size=17, weight=ft.FontWeight.BOLD),
                    ft.Text(label, size=10, weight=ft.FontWeight.BOLD),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=1,
            ),
            on_click=lambda e, target=key: show_screen(target),
            bgcolor="#302D59" if key == "editor" else "#121C2A",
            color="#E3DFFF" if key == "editor" else MUTED,
            expand=True,
        )
        nav_buttons[key] = button
        nav_cells.append(ft.Container(content=button, expand=1))

    nav_bar = ft.Container(
        content=ft.Row(controls=nav_cells, spacing=5),
        padding=ft.Padding.only(left=9, right=9, top=8, bottom=8),
        bgcolor="#0E1623",
        border=ft.Border.only(top=ft.BorderSide(1, "#243147")),
    )

    status_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    width=7, height=7, bgcolor=SUCCESS, border_radius=8,
                ),
                ft.Container(content=status_text, expand=True),
                ft.Text("ANDROID · PYTHON", size=9, color="#718098"),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        bgcolor="#0B1320",
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[header, screen_host, status_bar, nav_bar],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )
    )
    refresh_project_buttons()
    refresh_file_buttons()
    refresh_project_summary()
    show_screen("editor")


if __name__ == "__main__":
    ft.run(main)
