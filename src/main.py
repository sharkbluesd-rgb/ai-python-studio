
import flet as ft


def main(page: ft.Page):
    page.title = "AI Python Studio"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    counter = ft.Text("مرحباً بك في AI Python Studio", size=22)

    def on_start(e):
        counter.value = "بيئة التطوير جاهزة!"
        page.update()

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "AI Python Studio",
                        size=28,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "بيئة تطوير Python الذكية على Android",
                        size=15,
                    ),
                    ft.Divider(),
                    counter,
                    ft.Button(
                        "ابدأ",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=on_start,
                    ),
                ],
                spacing=20,
            )
        )
    )


ft.run(main)
