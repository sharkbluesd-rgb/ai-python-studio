"""Isolated browser smoke test for the Flet CodeEditor extension.

This is intentionally not the full Android application. It verifies that the
actual Flet CodeEditor control can be packaged for a static browser build.
Python execution, native filesystem access and package installation are omitted.
"""
from __future__ import annotations

import ast
from pathlib import Path

import flet as ft


STARTER_FILES = {
    "main.py": (
        '"""AI Python Studio — browser editor smoke test."""\n\n'
        "def greet(name: str) -> str:\n"
        '    return f"Hello, {name}!"\n\n'
        "if __name__ == \"__main__\":\n"
        '    print(greet("Python developer"))\n'
    ),
    "utils.py": (
        '"""Small helper functions."""\n\n'
        "def square(number: int) -> int:\n"
        "    return number * number\n"
    ),
}


def _build_editor(page: ft.Page, fce) -> None:
    page.title = "AI Python Studio — Web Editor Test"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#080C14"
    page.padding = 0
    page.spacing = 0

    files = dict(STARTER_FILES)
    state = {"active": "main.py", "dirty": False}

    status = ft.Text(
        "محرر Flet الحقيقي — اختبار توافق المتصفح",
        color="#94A3B8",
        size=11,
    )
    output = ft.Text(
        "اختر ملفاً، عدّل الكود، ثم احفظ أو افحص الصياغة.",
        color="#CBD5E1",
        selectable=True,
        size=12,
    )
    file_label = ft.Text("main.py", color="#C7BFFF", size=12, weight=ft.FontWeight.BOLD)

    editor = fce.CodeEditor(
        value=files["main.py"],
        language=fce.CodeLanguage.PYTHON,
        code_theme=fce.CodeTheme.ATOM_ONE_DARK,
        autocomplete=True,
        gutter_style=fce.GutterStyle(
            show_line_numbers=True,
            show_folding_handles=True,
            show_errors=True,
            width=48,
        ),
        text_style=ft.TextStyle(size=14, font_family="monospace"),
        padding=12,
        expand=True,
    )

    def on_editor_change(e: ft.Event[fce.CodeEditor]) -> None:
        if e.data is not None:
            editor.value = e.data
        state["dirty"] = True
        status.value = "توجد تعديلات غير محفوظة داخل جلسة المتصفح."
        status.color = "#E4C27A"
        page.update()

    editor.on_change = on_editor_change

    def save_current(e: ft.Event[ft.Button]) -> None:
        files[state["active"]] = editor.value or ""
        state["dirty"] = False
        status.value = "تم الحفظ في ذاكرة جلسة المتصفح (ليس تخزيناً دائماً)."
        status.color = "#6EE7B7"
        page.update()

    def open_file(name: str) -> None:
        files[state["active"]] = editor.value or ""
        state["active"] = name
        state["dirty"] = False
        editor.value = files[name]
        editor.language = (
            fce.CodeLanguage.PYTHON
            if Path(name).suffix == ".py"
            else fce.CodeLanguage.PLAINTEXT
        )
        file_label.value = name
        file_row.controls = [file_button(item) for item in files]
        status.value = f"تم فتح {name}."
        status.color = "#94A3B8"
        page.update()

    def check_syntax(e: ft.Event[ft.Button]) -> None:
        source = editor.value or ""
        if len(source) > 64 * 1024:
            output.value = "حجم الملف يتجاوز 64 كيلوبايت في نسخة الاختبار."
            output.color = "#FB7185"
            page.update()
            return
        try:
            ast.parse(source, filename=state["active"])
        except SyntaxError as exc:
            output.value = (
                f"خطأ نحوي في السطر {exc.lineno or '?'}، "
                f"العمود {exc.offset or '?'}: {exc.msg}"
            )
            output.color = "#FB7185"
        else:
            output.value = "الكود سليم نحوياً. لم يتم تشغيله."
            output.color = "#6EE7B7"
        page.update()

    def file_button(name: str) -> ft.Button:
        return ft.Button(
            content=name,
            on_click=lambda e, selected=name: open_file(selected),
            bgcolor="#302A59" if name == state["active"] else "#152236",
            color="#F3F6FC",
        )

    file_row = ft.Row(
        controls=[file_button(name) for name in files],
        spacing=7,
        wrap=True,
    )

    page.add(
        ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "AI Python Studio",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color="#F3F6FC",
                            ),
                            ft.Text(
                                "Flet CodeEditor · Browser Compatibility Test",
                                size=10,
                                color="#94A3B8",
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text("WEB TEST", size=10, color="#D6D0FF"),
                        bgcolor="#282548",
                        padding=ft.Padding.symmetric(horizontal=9, vertical=6),
                        border_radius=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor="#111A28",
            border=ft.Border.only(bottom=ft.BorderSide(1, "#26364D")),
        ),
        ft.Container(
            content=ft.Column(
                controls=[
                    file_row,
                    ft.Row(
                        controls=[
                            file_label,
                            ft.Row(
                                controls=[
                                    ft.Button(
                                        content="حفظ",
                                        on_click=save_current,
                                        bgcolor="#302A59",
                                        color="#FFFFFF",
                                    ),
                                    ft.Button(
                                        content="فحص Python",
                                        on_click=check_syntax,
                                        bgcolor="#1D654C",
                                        color="#FFFFFF",
                                    ),
                                ],
                                spacing=7,
                                wrap=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Container(
                        content=editor,
                        expand=True,
                        bgcolor="#080F1A",
                        border=ft.Border.all(1, "#26364D"),
                        border_radius=12,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    status,
                    ft.Container(
                        content=output,
                        bgcolor="#111A28",
                        border=ft.Border.all(1, "#26364D"),
                        border_radius=10,
                        padding=10,
                    ),
                    ft.Text(
                        "نسخة توافق فقط: لا تنفّذ Python ولا تثبّت مكتبات ولا تصل إلى ملفات الهاتف. "
                        "الحفظ مؤقت داخل جلسة المتصفح.",
                        color="#DDBB78",
                        size=10,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            padding=12,
            expand=True,
        ),
    )



def main(page: ft.Page) -> None:
    """Start with a visible diagnostic state and never hide startup exceptions."""
    page.title = "AI Python Studio — STARTING"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#080C14"
    page.padding = 16
    page.add(
        ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "AI Python Studio",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color="#F3F6FC",
                    ),
                    ft.Text(
                        "جارٍ تشغيل محرر Python...",
                        color="#94A3B8",
                        size=13,
                    ),
                ],
                spacing=10,
            ),
            padding=20,
            bgcolor="#111A28",
            border_radius=12,
        )
    )

    try:
        # Import the extension inside the guarded startup path. An import-time
        # failure must be shown in the app instead of leaving the Flet splash.
        import flet_code_editor as fce

        page.controls.clear()
        _build_editor(page, fce)
        page.title = "AI Python Studio — READY"
        page.update()
    except Exception as exc:
        page.controls.clear()
        page.title = "AI Python Studio — ERROR"
        page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "تعذر تشغيل محرر Flet",
                            size=19,
                            weight=ft.FontWeight.BOLD,
                            color="#FB7185",
                        ),
                        ft.Text(
                            f"{type(exc).__name__}: {str(exc)[:500]}",
                            selectable=True,
                            color="#F3F6FC",
                            size=12,
                        ),
                        ft.Text(
                            "هذه رسالة خطأ بدء التشغيل. أرسل نصها عند طلب الدعم.",
                            color="#94A3B8",
                            size=11,
                        ),
                    ],
                    spacing=12,
                ),
                padding=18,
                bgcolor="#111A28",
                border_radius=12,
            )
        )
        page.update()


if __name__ == "__main__":
    ft.run(main)
