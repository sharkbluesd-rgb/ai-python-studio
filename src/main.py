"""AI Python Studio — mobile-first Python workspace for Android."""

from __future__ import annotations

import asyncio
from pathlib import Path

import flet as ft
import flet_code_editor as fce

from runner import check_python, execute_python
from templates import TEMPLATES
from editor_tabs import OpenFileTabs
from project_tools import analyze_project as inspect_project, format_analysis_report
from workspace import MAX_ARCHIVE_BYTES, WorkspaceError, WorkspaceStore


APP_BG = "#080B12"
PANEL = "#111722"
EDITOR_BG = "#0B111B"
ACCENT = "#8B7CFF"
TEXT = "#EEF1F8"
MUTED = "#9BA7BA"
SUCCESS = "#9AE6B4"
DANGER = "#FF9292"
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
    page.padding = 12
    page.spacing = 10
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

    run_button = ft.Button(content="تشغيل Python", bgcolor="#237A55", color="white")
    run_state = {"running": False}
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

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

    def refresh_file_buttons() -> None:
        file_buttons.controls = []
        for name in store.list_files(active_project):
            is_active = name == active_file
            file_buttons.controls.append(
                ft.Button(
                    content=name,
                    on_click=lambda e, selected=name: open_file(selected),
                    bgcolor=ACCENT if is_active else "#202A3A",
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

    def on_editor_change(e: ft.Event[fce.CodeEditor]) -> None:
        try:
            if e.data is not None:
                editor.value = e.data
            save_current_file()
            set_status("حفظ تلقائي · التغييرات محفوظة على الجهاز", SUCCESS)
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)

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

    async def run_code(e) -> None:
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
        run_button.disabled = True
        set_status("جارٍ تنفيذ الكود... (شغّل الأكواد التي تثق بها فقط)", ACCENT)
        output_text.value = "يتم تنفيذ البرنامج..."
        output_text.color = MUTED
        page.update()

        code_snapshot = current_code()
        file_path = str(store.root / "projects" / active_project / active_file)
        project_path = str(store.root / "projects" / active_project)
        try:
            result, succeeded = await asyncio.to_thread(
                execute_python, code_snapshot, file_path, project_path
            )
            output_text.value = result[:OUTPUT_LIMIT]
            if len(result) > OUTPUT_LIMIT:
                output_text.value += "\n\n[تم اختصار الإخراج لطوله الكبير]"
            output_text.color = SUCCESS if succeeded else DANGER
            set_status(
                "اكتمل التنفيذ." if succeeded else "انتهى التنفيذ مع وجود خطأ.",
                SUCCESS if succeeded else DANGER,
            )
        except Exception as exc:
            output_text.value = f"تعذر تشغيل الكود: {exc}"
            output_text.color = DANGER
            set_status("فشل تشغيل الكود.", DANGER)
        finally:
            run_state["running"] = False
            run_button.disabled = False
            page.update()

    def analyze_current_project(e) -> None:
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
        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
        page.update()

    def check_current_syntax(e) -> None:
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
        output_text.value = "تم مسح نافذة النتائج."
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
    replace_apply_button.on_click = apply_project_replace

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text("Py", size=19, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor=ACCENT,
                    padding=12,
                    border_radius=12,
                ),
                ft.Column(
                    controls=[
                        ft.Text("AI Python Studio", size=22, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text("Mobile Python Development Workspace", size=11, color=MUTED),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Text("1.1", size=12, color="#C7BFFF", weight=ft.FontWeight.BOLD),
            ],
            spacing=12,
        ),
        padding=14,
        bgcolor=PANEL,
        border_radius=16,
        border=ft.Border.all(1, "#202B3B"),
    )

    project_summary = ft.Text("", size=11, color=MUTED)
    project_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("المشاريع", size=13, weight=ft.FontWeight.BOLD, color=MUTED),
                project_buttons,
                project_summary,
                ft.Row(
                    controls=[project_name_input, ft.Button(content="إنشاء", on_click=create_project)],
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        *[
                            ft.Button(
                                content=template_name,
                                on_click=lambda e, selected=template_name: create_template_project(selected),
                            )
                            for template_name in TEMPLATES
                        ],
                        ft.Button(content="استيراد ZIP", on_click=import_project_zip),
                        ft.Button(content="تصدير ZIP", on_click=export_project_zip),
                    ],
                    wrap=True,
                    spacing=6,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        bgcolor=PANEL,
        border_radius=14,
        border=ft.Border.all(1, "#202B3B"),
    )

    toolbar = ft.Row(
        controls=[
            run_button,
            ft.Button(content="فحص الكود", on_click=check_current_syntax),
            ft.Button(content="حفظ", on_click=lambda e: save_and_update()),
            ft.Button(content="مثال", on_click=load_example),
        ],
        wrap=True,
        spacing=6,
    )

    editor_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("مستكشف الملفات", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
                        ft.Button(content="نسخ", on_click=duplicate_current_file),
                        ft.Button(content="حذف", on_click=delete_file),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
                ft.Text("التبويبات المفتوحة", size=11, color=MUTED),
                tab_buttons,
                file_buttons,
                ft.Row(
                    controls=[file_name_input, ft.Button(content="ملف جديد", on_click=create_file)],
                    spacing=6,
                ),
                ft.Row(
                    controls=[folder_name_input, ft.Button(content="مجلد جديد", on_click=create_folder)],
                    spacing=6,
                ),
                ft.Row(
                    controls=[rename_input, ft.Button(content="إعادة تسمية", on_click=rename_current_file)],
                    spacing=6,
                ),
                ft.Row(
                    controls=[active_file_label, ft.Text("EDITOR", size=11, color=MUTED)],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=editor,
                    bgcolor=EDITOR_BG,
                    border_radius=12,
                    padding=4,
                    expand=True,
                    height=440,
                ),
                ft.Row(
                    controls=[
                        ft.Button(content="طي الاستيرادات", on_click=fold_imports),
                        ft.Button(content="طي التعليق العلوي", on_click=fold_first_comment),
                    ],
                    wrap=True,
                    spacing=6,
                ),
            ],
            spacing=9,
            expand=True,
        ),
        bgcolor=PANEL,
        padding=10,
        border_radius=16,
        border=ft.Border.all(1, "#202B3B"),
    )

    search_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("البحث والاستبدال", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
                ft.Row(
                    controls=[search_input, ft.Button(content="بحث المشروع", on_click=search_project)],
                    spacing=6,
                ),
                ft.Row(
                    controls=[replace_find_input, replace_with_input, ft.Button(content="استبدال", on_click=replace_in_current_file)],
                    spacing=6,
                    wrap=True,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        bgcolor=PANEL,
        border_radius=14,
        border=ft.Border.all(1, "#202B3B"),
    )

    project_tools_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("أدوات المشروع", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
                ft.Row(
                    controls=[
                        ft.Button(content="تحليل المشروع", on_click=analyze_current_project),
                        ft.Button(content="فتح requirements.txt", on_click=open_requirements_file),
                    ],
                    wrap=True,
                    spacing=6,
                ),
                ft.Text("استبدال شامل مع معاينة قبل تعديل الملفات", size=11, color=MUTED),
                ft.Row(controls=[project_replace_find, project_replace_with], wrap=True, spacing=6),
                ft.Row(
                    controls=[
                        ft.Button(content="معاينة الاستبدال", on_click=preview_project_replace),
                        replace_apply_button,
                    ],
                    wrap=True,
                    spacing=6,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        bgcolor=PANEL,
        border_radius=14,
        border=ft.Border.all(1, "#202B3B"),
    )

    output_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("OUTPUT / DIAGNOSTICS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                        ft.Button(content="مسح", on_click=clear_output),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=output_text,
                    bgcolor="#080C12",
                    padding=12,
                    border_radius=10,
                    expand=True,
                ),
            ],
            spacing=8,
            expand=True,
        ),
        bgcolor=PANEL,
        padding=10,
        border_radius=16,
        border=ft.Border.all(1, "#202B3B"),
        height=230,
    )

    safety_note = ft.Text(
        "تنبيه: تشغيل Python محلياً ليس بيئة معزولة. شغّل الأكواد التي تثق بها فقط.",
        color="#DDBB78",
        size=10,
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[header, project_panel, toolbar, editor_panel, search_panel, project_tools_panel, output_panel, status_text, safety_note],
                spacing=10,
                expand=True,
            )
        )
    )
    refresh_project_buttons()
    refresh_file_buttons()
    refresh_project_summary()


if __name__ == "__main__":
    ft.run(main)
