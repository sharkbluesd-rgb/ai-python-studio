
import contextlib
import io
import traceback

import flet as ft


DEFAULT_CODE = 'print("Hello World")\n'


def main(page: ft.Page):
    page.title = "AI Python Studio"
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0D12"

    output = ft.Text(
        "اضغط تشغيل لتنفيذ الكود.",
        selectable=True,
        color="#AAB3C5",
    )

    editor = ft.TextField(
        value=DEFAULT_CODE,
        multiline=True,
        min_lines=12,
        max_lines=24,
        expand=True,
        text_size=14,
        border_color="#303747",
        focused_border_color="#8B7CFF",
        cursor_color="#B7A9FF",
    )

    def run_code(e):
        buffer = io.StringIO()

        try:
            with contextlib.redirect_stdout(buffer):
                exec(editor.value or "", {})

            result = buffer.getvalue()
            output.value = (
                result if result
                else "تم التنفيذ بنجاح."
            )
            output.color = "#A6F3C2"

        except Exception:
            output.value = traceback.format_exc()
            output.color = "#FF8D8D"

        page.update()

    def clear_output(e):
        output.value = "تم مسح النتائج."
        output.color = "#AAB3C5"
        page.update()

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "AI Python Studio",
                        size=26,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "محرر Python — الإصدار الأول",
                        size=14,
                        color="#9BA4B8",
                    ),
                    ft.Row(
                        controls=[
                            ft.Button(
                                "تشغيل",
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=run_code,
                            ),
                            ft.Button(
                                "مسح النتائج",
                                icon=ft.Icons.CLEAR,
                                on_click=clear_output,
                            ),
                        ],
                        wrap=True,
                    ),
                    ft.Text(
                        "main.py",
                        size=13,
                        color="#B7A9FF",
                    ),
                    editor,
                    ft.Divider(),
                    ft.Text(
                        "OUTPUT",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=output,
                        bgcolor="#11151D",
                        padding=12,
                        border_radius=10,
                    ),
                ],
                spacing=12,
                expand=True,
            )
        )
    )


ft.run(main)
