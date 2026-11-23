"""Browser-only preview for verifying the Flet web client and CodeEditor extension.

This intentionally avoids the Android runner, filesystem, package installer and
GitHub integration. Those features require the full native/dynamic application.
"""

from __future__ import annotations

import ast

import flet as ft
import flet_code_editor as fce


BG = "#080D16"
PANEL = "#121B2A"
EDITOR_BG = "#0A111D"
ACCENT = "#8175F5"
TEXT = "#F2F4FC"
MUTED = "#9AA8BC"
SUCCESS = "#83DDB8"
DANGER = "#FF8F9B"

STARTER_FILES = {
    "main.py": '''"""AI Python Studio — browser editor preview."""


def greet(name: str) -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(greet("Python developer"))
''',
    "utils.py": '''"""Small helper functions for the preview project."""


def square(number: int) -> int:
    """Return the square of a number."""
    return number * number


def is_even(number: int) -> bool:
    return number % 2 == 0
''',
}

AUTOCOMPLETE_WORDS = [
    "print", "input", "len", "range", "enumerate", "zip", "sum", "min",
    "max", "sorted", "list", "dict", "str", "int", "float", "bool",
    "class", "def", "return", "async", "await", "import", "from", "as",
    "if", "elif", "else", "for", "while", "try", "except", "finally",
    "with", "lambda", "yield", "self", "True", "False", "None",
]


def validate_python_source(source: str) -> tuple[bool, str]:
    """Validate Python syntax without executing user code."""
    if not isinstance(source, str):
        return False, "محتوى الكود غير صالح."
    try:
        ast.parse(source, filename="main.py")
    except SyntaxError as exc:
        line = exc.lineno or "?"
        column = exc.offset or "?"
        return False, f"خطأ نحوي في السطر {line}، العمود {column}: {exc.msg}"
    return True, "الكود سليم نحوياً. لم يتم تشغيله."


def main(page: ft.Page) -> None:
    page.title = "AI Python Studio — Web Preview"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.spacing = 0

    active_file = {"name": "main.py"}
    source_files = dict(STARTER_FILES)

    current_file = ft.Text(
        "main.py", size=12, color="#C7BFFF", weight=ft.FontWeight.BOLD
    )
    status = ft.Text("جاهز — هذه نسخة معاينة للويب.", size=12, color=SUCCESS)
    output = ft.Text(
        "ستظهر هنا نتيجة فحص الصياغة.", size=12, color=MUTED, selectable=True
    )
    file_buttons = ft.Row(wrap=True, spacing=6)
    file_button_refs = {}

    editor = fce.CodeEditor(
        value=source_files["main.py"],
        language=fce.CodeLanguage.PYTHON,
        code_theme=fce.CodeTheme.ATOM_ONE_DARK,
        autocomplete=True,
        autocomplete_words=AUTOCOMPLETE_WORDS,
        gutter_style=fce.GutterStyle(
            show_line_numbers=True,
            show_folding_handles=True,
            show_errors=True,
            width=48,
        ),
        text_style=ft.TextStyle(size=14, font_family="monospace"),
        padding=12,
        autofocus=False,
        expand=True,
    )

    def set_status(message: str, color: str = MUTED) -> None:
        status.value = message
        status.color = color

    def on_editor_change(e: ft.Event[fce.CodeEditor]) -> None:
        if e.data is not None:
            editor.value = e.data
        source_files[active_file["name"]] = editor.value or ""
        set_status("هناك تغييرات في الملف الحالي.", "#E4C27A")
        page.update()

    editor.on_change = on_editor_change

    def check_syntax(e: ft.Event[ft.Button]) -> None:
        valid, message = validate_python_source(editor.value or "")
        output.value = message
        output.color = SUCCESS if valid else DANGER
        set_status(
            "اكتمل فحص الصياغة." if valid else "تم العثور على خطأ نحوي.",
            SUCCESS if valid else DANGER,
        )
        page.update()

    def reset_file(e: ft.Event[ft.Button]) -> None:
        name = active_file["name"]
        editor.value = STARTER_FILES[name]
        source_files[name] = editor.value
        output.value = "تمت استعادة المثال الأصلي."
        output.color = MUTED
        set_status("تمت استعادة محتوى الملف.", SUCCESS)
        page.update()

    def select_file(name: str) -> None:
        source_files[active_file["name"]] = editor.value or ""
        active_file["name"] = name
        editor.value = source_files[name]
        editor.language = fce.CodeLanguage.PYTHON
        current_file.value = name
        for file_name, button in file_button_refs.items():
            button.bgcolor = ACCENT if file_name == name else "#202A3A"
        set_status(f"تم فتح {name}.", SUCCESS)
        page.update()

    # Keep stable references so file selection can update the active state.
    for name in STARTER_FILES:
        button = ft.Button(
            content=name,
            bgcolor=ACCENT if name == "main.py" else "#202A3A",
            color="white",
            on_click=lambda e, selected=name: select_file(selected),
        )
        file_buttons.controls.append(button)
        file_button_refs[name] = button

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        "Py", size=25, weight=ft.FontWeight.BOLD, color="white"
                    ),
                    width=58,
                    height=58,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ACCENT,
                    border_radius=16,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            "AI Python Studio",
                            size=19,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT,
                        ),
                        ft.Text(
                            "معاينة محرر Python عبر المتصفح",
                            size=11,
                            color=MUTED,
                        ),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text("WEB", size=11, color="#D8D3FF"),
                    padding=ft.Padding.symmetric(horizontal=11, vertical=8),
                    bgcolor="#242143",
                    border_radius=20,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#0E1725",
        padding=14,
        border=ft.Border.only(bottom=ft.BorderSide(1, "#26354C")),
    )

    notice = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE, color="#E4C27A", size=18),
                ft.Text(
                    "نسخة اختبار: تعرض محرر الأكواد والإضافات في الويب. "
                    "لا تتصل بملفات الهاتف أو مدير الحزم أو GitHub.",
                    color="#E4D5AE",
                    size=11,
                    expand=True,
                ),
            ],
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#292315",
        border=ft.Border.all(1, "#57472A"),
        border_radius=12,
        padding=11,
    )

    editor_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "محرر الأكواد",
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXT,
                                ),
                                current_file,
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.Text("Python", size=11, color=MUTED),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                file_buttons,
                ft.Container(
                    content=editor,
                    bgcolor=EDITOR_BG,
                    border=ft.Border.all(1, "#26354C"),
                    border_radius=12,
                    padding=4,
                    height=420,
                ),
                ft.Row(
                    controls=[
                        ft.Button(
                            content="فحص الكود",
                            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                            bgcolor="#237A55",
                            color="white",
                            on_click=check_syntax,
                            expand=True,
                        ),
                        ft.Button(
                            content="استعادة المثال",
                            icon=ft.Icons.RESTART_ALT,
                            bgcolor="#303B50",
                            color="white",
                            on_click=reset_file,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=12,
        ),
        bgcolor=PANEL,
        border=ft.Border.all(1, "#26354C"),
        border_radius=14,
        padding=13,
    )

    output_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("نتيجة الفحص", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                output,
                ft.Divider(color="#26354C", height=1),
                status,
            ],
            spacing=8,
        ),
        bgcolor="#0D1522",
        border=ft.Border.all(1, "#26354C"),
        border_radius=12,
        padding=13,
    )

    content = ft.Column(
        controls=[
            notice,
            ft.Row(
                controls=[
                    ft.Text("المشروع التجريبي", size=13, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text("My First Project", size=11, color=MUTED),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            editor_card,
            output_card,
            ft.Text(
                "الاختبار يركز على عرض عنصر CodeEditor في متصفح الهاتف "
                "قبل دمج عميل الويب المبني مع التطبيق الكامل.",
                size=10,
                color=MUTED,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        spacing=13,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    header,
                    ft.Container(content=content, expand=True, padding=12),
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.run(main)
