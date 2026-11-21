
"""AI Python Studio — persistent mobile Python workspace."""

from __future__ import annotations

import asyncio

import flet as ft
import flet_code_editor as fce

from runner import execute_python
from workspace import WorkspaceError, WorkspaceStore


APP_BG = "#080B12"
PANEL = "#111722"
EDITOR_BG = "#0B111B"
ACCENT = "#8B7CFF"
TEXT = "#EEF1F8"
MUTED = "#9BA7BA"
SUCCESS = "#9AE6B4"
DANGER = "#FF9292"
OUTPUT_LIMIT = 40_000


def main(page: ft.Page):
    store = WorkspaceStore()

    page.title = "AI Python Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = APP_BG
    page.padding = 12
    page.spacing = 10
    page.scroll = ft.ScrollMode.AUTO

    # Load workspace
    settings = store.load_settings()
    available_projects = store.list_projects()

    if not available_projects:
        raise RuntimeError("لا توجد مشاريع في مساحة العمل.")

    project_ids = {item["id"] for item in available_projects}
    active_project = settings.get("active_project", "")

    if active_project not in project_ids:
        active_project = available_projects[0]["id"]

    available_files = store.list_files(active_project)

    if not available_files:
        raise RuntimeError("المشروع الحالي لا يحتوي على ملفات.")

    active_file = settings.get("active_file", "main.py")

    if active_file not in available_files:
        active_file = available_files[0]

    # Professional Python code editor
    editor = fce.CodeEditor(
        value=store.read_file(active_project, active_file),
        language=fce.CodeLanguage.PYTHON,
        code_theme=fce.CodeTheme.ATOM_ONE_DARK,
        autocomplete=True,
        autocomplete_words=[
            "print",
            "input",
            "len",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sum",
            "min",
            "max",
            "sorted",
            "list",
            "dict",
            "tuple",
            "set",
            "str",
            "int",
            "float",
            "bool",
            "open",
            "class",
            "def",
            "return",
            "async",
            "await",
            "import",
            "from",
            "as",
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "lambda",
            "yield",
            "self",
            "True",
            "False",
            "None",
        ],
        text_style=ft.TextStyle(
            size=14,
            font_family="monospace",
        ),
        padding=12,
        autofocus=False,
        expand=True,
    )

    output_text = ft.Text(
        "المخرجات ستظهر هنا بعد تشغيل الكود.",
        selectable=True,
        color=MUTED,
        size=13,
    )

    status_text = ft.Text(
        "تم تحميل مساحة العمل.",
        size=12,
        color=SUCCESS,
    )

    project_buttons = ft.Row(wrap=True, spacing=6)
    file_buttons = ft.Row(wrap=True, spacing=6)

    active_file_label = ft.Text(
        active_file,
        size=13,
        color="#C7BFFF",
        weight=ft.FontWeight.BOLD,
    )

    project_name_input = ft.TextField(
        hint_text="اسم المشروع الجديد (بالإنجليزية)",
        text_size=13,
        expand=True,
    )

    file_name_input = ft.TextField(
        hint_text="اسم الملف مثل utils.py",
        text_size=13,
        expand=True,
    )

    run_button = ft.Button(
        content="تشغيل الكود",
        bgcolor="#237A55",
        color="white",
    )

    run_state = {"running": False}

    def current_code() -> str:
        return editor.value or ""

    def set_editor_code(code: str) -> None:
        editor.value = code

    def set_status(message: str, color: str = MUTED) -> None:
        status_text.value = message
        status_text.color = color

    def save_current_file(show_status: bool = False) -> None:
        store.write_file(
            active_project,
            active_file,
            current_code(),
        )
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
                    on_click=lambda e, selected=project_id: open_project(
                        selected
                    ),
                    bgcolor=ACCENT if is_active else "#202A3A",
                    color="white",
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

    def open_file(name: str) -> None:
        nonlocal active_file

        try:
            save_current_file()

            active_file = name
            set_editor_code(
                store.read_file(active_project, active_file)
            )

            store.save_settings(active_project, active_file)
            refresh_file_buttons()

            set_status(f"تم فتح {active_file}", SUCCESS)
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
                raise WorkspaceError(
                    "المشروع المحدد لا يحتوي على ملفات."
                )

            active_file = (
                "main.py"
                if "main.py" in project_files
                else project_files[0]
            )

            set_editor_code(
                store.read_file(active_project, active_file)
            )

            store.save_settings(active_project, active_file)

            refresh_project_buttons()
            refresh_file_buttons()

            set_status(
                "تم فتح المشروع وحفظ التغييرات السابقة.",
                SUCCESS,
            )
            page.update()

        except (WorkspaceError, IndexError) as exc:
            set_status(str(exc) or "تعذر فتح المشروع.", DANGER)
            page.update()

    def on_editor_change(e) -> None:
        try:
            # Flet CodeEditor sends the new source through e.data.
            if e.data is not None:
                editor.value = e.data

            save_current_file()
            set_status(
                "حفظ تلقائي · التغييرات محفوظة على الجهاز",
                SUCCESS,
            )

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)

    def create_project(e) -> None:
        nonlocal active_project, active_file

        try:
            save_current_file()

            new_id = store.create_project(
                project_name_input.value or ""
            )

            active_project = new_id
            active_file = "main.py"

            set_editor_code(
                store.read_file(active_project, active_file)
            )

            project_name_input.value = ""

            store.save_settings(active_project, active_file)

            refresh_project_buttons()
            refresh_file_buttons()

            set_status(
                "تم إنشاء المشروع وحفظه على الجهاز.",
                SUCCESS,
            )
            page.update()

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def create_file(e) -> None:
        nonlocal active_file

        try:
            save_current_file()

            active_file = store.create_file(
                active_project,
                file_name_input.value or "",
            )

            file_name_input.value = ""

            set_editor_code(
                store.read_file(active_project, active_file)
            )

            store.save_settings(active_project, active_file)
            refresh_file_buttons()

            set_status(f"تم إنشاء {active_file}.", SUCCESS)
            page.update()

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)
            page.update()

    def delete_file(e) -> None:
        nonlocal active_file

        try:
            store.delete_file(active_project, active_file)

            remaining = store.list_files(active_project)

            if not remaining:
                raise WorkspaceError(
                    "لا توجد ملفات متبقية في المشروع."
                )

            active_file = (
                "main.py"
                if "main.py" in remaining
                else remaining[0]
            )

            set_editor_code(
                store.read_file(active_project, active_file)
            )

            store.save_settings(active_project, active_file)
            refresh_file_buttons()

            set_status("تم حذف الملف المحدد.", SUCCESS)
            page.update()

        except (WorkspaceError, IndexError) as exc:
            set_status(str(exc) or "تعذر حذف الملف.", DANGER)
            page.update()

    def duplicate_current_file(e) -> None:
        nonlocal active_file

        try:
            save_current_file()

            active_file = store.duplicate_file(
                active_project,
                active_file,
            )

            set_editor_code(
                store.read_file(active_project, active_file)
            )

            store.save_settings(active_project, active_file)
            refresh_file_buttons()

            set_status(
                f"تم نسخ الملف إلى {active_file}.",
                SUCCESS,
            )

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)

        page.update()

    async def run_code(e) -> None:
        if run_state["running"]:
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

        set_status("جارٍ تنفيذ الكود...", ACCENT)

        output_text.value = "يتم تنفيذ البرنامج..."
        output_text.color = MUTED

        page.update()

        code_snapshot = current_code()

        file_path = str(
            store.root
            / "projects"
            / active_project
            / active_file
        )

        try:
            result, succeeded = await asyncio.to_thread(
                execute_python,
                code_snapshot,
                file_path,
            )

            output_text.value = result[:OUTPUT_LIMIT]

            if len(result) > OUTPUT_LIMIT:
                output_text.value += (
                    "\n\n[تم اختصار الإخراج لطوله الكبير]"
                )

            output_text.color = (
                SUCCESS if succeeded else DANGER
            )

            set_status(
                "اكتمل التنفيذ."
                if succeeded
                else "انتهى التنفيذ مع وجود خطأ.",
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

    def clear_output(e) -> None:
        output_text.value = "تم مسح نافذة النتائج."
        output_text.color = MUTED
        page.update()

    def load_example(e) -> None:
        set_editor_code(
            "def greet(name):\n"
            "    return f'Hello, {name}!'\n\n"
            "for person in ['Python', 'AI Python Studio']:\n"
            "    print(greet(person))\n"
        )

        try:
            save_current_file()
            set_status(
                "تم تحميل المثال وحفظه في الملف.",
                SUCCESS,
            )

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)

        page.update()

    def save_and_update() -> None:
        try:
            save_current_file(show_status=True)

        except WorkspaceError as exc:
            set_status(str(exc), DANGER)

        page.update()

    # Editor events
    editor.on_change = on_editor_change
    run_button.on_click = run_code

    # Header
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        "Py",
                        size=19,
                        weight=ft.FontWeight.BOLD,
                        color="white",
                    ),
                    bgcolor=ACCENT,
                    padding=12,
                    border_radius=12,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            "AI Python Studio",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT,
                        ),
                        ft.Text(
                            "Your mobile Python workspace",
                            size=12,
                            color=MUTED,
                        ),
                    ],
                    spacing=2,
                ),
            ],
            spacing=12,
        ),
        padding=14,
        bgcolor=PANEL,
        border_radius=16,
        border=ft.Border.all(1, "#202B3B"),
    )

    # Projects panel
    project_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "المشاريع",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    color=MUTED,
                ),
                project_buttons,
                ft.Row(
                    controls=[
                        project_name_input,
                        ft.Button(
                            content="إنشاء",
                            on_click=create_project,
                        ),
                    ],
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

    # Main toolbar
    toolbar = ft.Row(
        controls=[
            run_button,
            ft.Button(
                content="حفظ الآن",
                on_click=lambda e: save_and_update(),
            ),
            ft.Button(
                content="مثال Python",
                on_click=load_example,
            ),
        ],
        wrap=True,
        spacing=6,
    )

    # Editor panel
    editor_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "ملفات المشروع",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=MUTED,
                        ),
                        ft.Button(
                            content="نسخ الملف",
                            on_click=duplicate_current_file,
                        ),
                        ft.Button(
                            content="حذف الملف",
                            on_click=delete_file,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                file_buttons,
                ft.Row(
                    controls=[
                        file_name_input,
                        ft.Button(
                            content="ملف جديد",
                            on_click=create_file,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        active_file_label,
                        ft.Text(
                            "PYTHON",
                            size=11,
                            color=MUTED,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=editor,
                    bgcolor=EDITOR_BG,
                    border_radius=12,
                    padding=4,
                    expand=True,
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

    # Output panel
    output_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "OUTPUT",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=MUTED,
                        ),
                        ft.Button(
                            content="مسح النتائج",
                            on_click=clear_output,
                        ),
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
        height=220,
    )

    # Assemble application
    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    header,
                    project_panel,
                    toolbar,
                    editor_panel,
                    output_panel,
                    status_text,
                ],
                spacing=10,
                expand=True,
            )
        )
    )

    refresh_project_buttons()
    refresh_file_buttons()


if __name__ == "__main__":
    ft.run(main)
