"""Flet APK Studio — prepare and build Python/Flet projects for Android."""
from __future__ import annotations

import asyncio
from pathlib import Path

import flet as ft

from flet_project import configure_flet_project, validate_flet_project
from github_cloud import (
    GitHubClient,
    GitHubError,
    select_dispatched_run,
    validate_branch,
    validate_repository,
)
from templates import TEMPLATES
from workspace import MAX_ARCHIVE_BYTES, WorkspaceError, WorkspaceStore


BG = "#080C14"
PANEL = "#111A28"
PANEL_ALT = "#172338"
LINE = "#293A52"
TEXT = "#F3F6FC"
MUTED = "#9AA9BD"
ACCENT = "#8B7CFF"
GREEN = "#6EE7B7"
RED = "#FB7185"
AMBER = "#E5B96E"


def main(page: ft.Page) -> None:
    """Create the focused Flet-to-APK workflow UI."""
    page.title = "Flet APK Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.spacing = 0
    page.scroll = ft.ScrollMode.AUTO

    store = WorkspaceStore()
    picker = ft.FilePicker()
    page.services.append(picker)

    projects = store.list_projects()
    saved = store.load_settings()
    selected = saved.get("active_project", "")
    if selected not in {item["id"] for item in projects}:
        selected = projects[0]["id"] if projects else ""
    state = {"project_id": selected}
    github = {
        "client": None,
        "device": None,
        "client_id": "",
        "owner": "",
        "repo": "",
        "branch": "main",
        "run_id": None,
        "pending_run_ids": None,
    }

    status_text = ft.Text("ابدأ بإنشاء مشروع Flet أو استيراد ملف ZIP.", size=12, color=MUTED)
    project_name_text = ft.Text("لا يوجد مشروع محدد", size=14, weight=ft.FontWeight.BOLD, color=TEXT)
    project_summary = ft.Text("", size=12, color=MUTED, selectable=True)
    project_check = ft.Text("", size=12, color=MUTED, selectable=True)
    project_list = ft.Column(spacing=5)
    github_status = ft.Text("لم يتم ربط GitHub بعد.", size=12, color=MUTED, selectable=True)
    github_device_info = ft.Text(
        "أدخل OAuth Client ID الخاص بتطبيق GitHub الذي أنشأته.",
        size=12, color=MUTED, selectable=True,
    )
    repo_choices = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
    build_log = ft.Text(
        "ستظهر هنا حالة GitHub Actions وخطوات البناء.",
        size=11, color=MUTED, selectable=True,
    )

    app_name = ft.TextField(label="اسم تطبيق Android", value="My Flet App", text_size=13)
    package_id = ft.TextField(
        label="معرّف الحزمة",
        value="com.example.myapp",
        hint_text="com.example.myapp",
        text_size=13,
    )
    app_version = ft.TextField(label="الإصدار", value="1.0.0", text_size=13)
    build_number = ft.TextField(label="رقم البناء", value="1", text_size=13)
    oauth_client_id = ft.TextField(
        label="GitHub OAuth Client ID",
        hint_text="أدخل Client ID فقط — لا تضع كلمة مرور أو Client Secret",
        text_size=13,
    )
    repository = ft.TextField(
        label="المستودع owner/repository",
        hint_text="username/my-flet-app",
        text_size=13,
    )
    branch = ft.TextField(label="فرع Git", value="main", text_size=13)
    private_repo = ft.Checkbox(label="إنشاء المستودع كخاص (Private)", value=True)

    build_button = ft.Button(
        content="رفع المشروع وبدء بناء APK",
        bgcolor="#176B50",
        color="white",
    )
    refresh_button = ft.Button(content="متابعة حالة البناء", disabled=True)
    download_button = ft.Button(content="تنزيل APK", disabled=True, bgcolor=ACCENT, color="white")

    def update_page() -> None:
        page.update()

    def set_status(message: str, color: str = MUTED) -> None:
        status_text.value = message
        status_text.color = color

    def set_github_status(message: str, color: str = MUTED) -> None:
        github_status.value = message
        github_status.color = color

    def active_project_id() -> str:
        project_id = state.get("project_id")
        if not project_id:
            raise WorkspaceError("أنشئ مشروع Flet أو استورد ملف ZIP أولاً.")
        return str(project_id)

    def refresh_project_summary() -> None:
        try:
            project_id = active_project_id()
            files = store.list_files(project_id)
            root = store._project_dir(project_id)
            issues = validate_flet_project(root)
            project_summary.value = (
                f"{len(files)} ملف داخل المشروع · "
                f"{'src/main.py' if (root / 'src' / 'main.py').is_file() else 'main.py غير موجود'} · "
                f"{'pyproject.toml موجود' if (root / 'pyproject.toml').is_file() else 'pyproject.toml غير موجود'}"
            )
            if issues:
                project_check.value = "فحص المشروع: توجد متطلبات ناقصة\n• " + "\n• ".join(issues)
                project_check.color = AMBER
            else:
                project_check.value = "فحص المشروع: جاهز مبدئياً لبناء Android."
                project_check.color = GREEN
        except (WorkspaceError, OSError, ValueError) as exc:
            project_summary.value = ""
            project_check.value = str(exc)
            project_check.color = RED

    def set_active_project(project_id: str) -> None:
        state["project_id"] = project_id
        files = store.list_files(project_id)
        settings_file = "src/main.py" if "src/main.py" in files else (files[0] if files else "")
        if settings_file:
            try:
                store.save_settings(project_id, settings_file)
            except WorkspaceError:
                pass
        refresh_project_list()
        refresh_project_summary()
        for item in store.list_projects():
            if item["id"] == project_id:
                project_name_text.value = item["name"]
                break
        set_status("تم تحديد المشروع. راجع إعدادات Android وفحص الجاهزية.", GREEN)
        update_page()

    def refresh_project_list() -> None:
        project_list.controls = []
        for item in store.list_projects():
            selected_project = item["id"] == state.get("project_id")
            project_list.controls.append(
                ft.Button(
                    content=("✓ " if selected_project else "") + item["name"],
                    on_click=lambda e, project_id=item["id"]: set_active_project(project_id),
                    bgcolor="#302A59" if selected_project else PANEL_ALT,
                    color=TEXT,
                )
            )

    def make_panel(title: str, description: str, controls: list) -> ft.Container:
        return ft.Container(
            bgcolor=PANEL,
            border=ft.Border.all(1, LINE),
            border_radius=17,
            padding=15,
            content=ft.Column(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                            ft.Text(description, size=11, color=MUTED),
                        ],
                        spacing=4,
                    ),
                    *controls,
                ],
                spacing=10,
            ),
        )

    async def import_project(e) -> None:
        try:
            picked_files = await picker.pick_files(
                dialog_title="اختر مشروع Flet بصيغة ZIP",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["zip"],
                allow_multiple=False,
                with_data=True,
            )
            if not picked_files:
                return
            picked = picked_files[0]
            if picked.size and picked.size > MAX_ARCHIVE_BYTES:
                raise WorkspaceError("حجم ZIP يتجاوز الحد المسموح (12 MB).")
            archive = picked.bytes
            if archive is None and picked.path:
                archive = Path(picked.path).read_bytes()
            if not archive:
                raise WorkspaceError("تعذر قراءة ملف ZIP.")
            name = Path(picked.name).stem[:48] or "Flet Project"
            project_id = store.import_project_archive(archive, name)
            set_active_project(project_id)
            set_status("تم استيراد المشروع. افحص الملفات قبل تشغيل البناء.", GREEN)
        except (WorkspaceError, OSError, ValueError) as exc:
            set_status(str(exc), RED)
            update_page()

    def create_flet_starter(e) -> None:
        try:
            project_id = store.create_project_from_template(
                "Flet Android App",
                TEMPLATES["Flet Android App"],
            )
            set_active_project(project_id)
            set_status("تم إنشاء قالب Flet Android جاهز للتخصيص.", GREEN)
        except (WorkspaceError, KeyError, OSError) as exc:
            set_status(str(exc), RED)
            update_page()

    def save_android_settings(e) -> None:
        try:
            root = store._project_dir(active_project_id())
            result = configure_flet_project(
                root,
                app_name=app_name.value or "",
                application_id=package_id.value or "",
                version=app_version.value or "",
                build_number=build_number.value or "",
            )
            refresh_project_summary()
            set_status("تم حفظ إعدادات Android: " + result, GREEN)
        except (WorkspaceError, ValueError, OSError) as exc:
            set_status(str(exc), RED)
        update_page()

    def validate_project(e) -> None:
        try:
            issues = validate_flet_project(store._project_dir(active_project_id()))
            if issues:
                set_status("المشروع غير جاهز:\n• " + "\n• ".join(issues), RED)
            else:
                set_status("اجتاز المشروع فحص المتطلبات الأساسية.", GREEN)
            refresh_project_summary()
        except (WorkspaceError, OSError, ValueError) as exc:
            set_status(str(exc), RED)
        update_page()

    async def start_github_login(e) -> None:
        try:
            client_id = (oauth_client_id.value or "").strip()
            authorization = await asyncio.to_thread(
                GitHubClient.start_device_authorization, client_id
            )
            github["device"] = authorization
            github["client_id"] = client_id
            github_device_info.value = (
                f"افتح الرابط: {authorization.verification_uri}\n"
                f"رمز التحقق: {authorization.user_code}\n"
                "بعد الموافقة ارجع للتطبيق واضغط «التحقق من الدخول»."
            )
            set_github_status("في انتظار موافقتك من GitHub.", ACCENT)
        except GitHubError as exc:
            set_github_status(str(exc), RED)
        update_page()

    async def verify_github_login(e) -> None:
        authorization = github.get("device")
        if authorization is None:
            set_github_status("ابدأ تسجيل الدخول أولاً.", RED)
            update_page()
            return
        try:
            token = await asyncio.to_thread(
                GitHubClient.poll_device_authorization,
                github["client_id"],
                authorization,
            )
            if not token:
                set_github_status(
                    "لم تتم الموافقة بعد. أكمل التحقق في صفحة GitHub ثم أعد المحاولة.",
                    ACCENT,
                )
            else:
                client = GitHubClient(token)
                user = await asyncio.to_thread(client.current_user)
                previous = github.get("client")
                if previous:
                    previous.clear()
                github.update({"client": client, "device": None})
                github_device_info.value = f"تم ربط الحساب @{user.get('login', 'GitHub')}."
                set_github_status("اتصال GitHub جاهز.", GREEN)
        except GitHubError as exc:
            set_github_status(str(exc), RED)
        update_page()

    async def disconnect_github(e) -> None:
        previous = github.get("client")
        if previous:
            previous.clear()
        github.update({
            "client": None,
            "device": None,
            "client_id": "",
            "run_id": None,
            "pending_run_ids": None,
        })
        github_device_info.value = "لم يتم ربط GitHub."
        set_github_status("تم قطع الاتصال ومسح الرمز من ذاكرة التطبيق.", MUTED)
        download_button.disabled = True
        refresh_button.disabled = True
        update_page()

    def choose_repository(full_name: str, default_branch: str) -> None:
        repository.value = full_name
        branch.value = default_branch or "main"
        set_github_status("تم اختيار المستودع " + full_name, GREEN)
        update_page()

    async def list_repositories(e) -> None:
        client = github.get("client")
        if client is None:
            set_github_status("سجّل الدخول إلى GitHub أولاً.", RED)
            update_page()
            return
        try:
            items = await asyncio.to_thread(client.list_repositories)
            repo_choices.controls = []
            for item in items[:60]:
                full_name = item.get("full_name", "")
                default_branch = item.get("default_branch") or "main"
                visibility = "خاص" if item.get("private") else "عام"
                repo_choices.controls.append(
                    ft.Button(
                        content=f"{full_name} · {visibility}",
                        on_click=lambda e, name=full_name, ref=default_branch:
                            choose_repository(name, ref),
                        bgcolor=PANEL_ALT,
                        color=TEXT,
                    )
                )
            if not items:
                repo_choices.controls.append(ft.Text("لا توجد مستودعات في الحساب.", color=MUTED))
            set_github_status(f"تم جلب {len(items)} مستودعاً. اختر واحداً من القائمة.", GREEN)
        except GitHubError as exc:
            set_github_status(str(exc), RED)
        update_page()

    async def create_repository(e) -> None:
        client = github.get("client")
        if client is None:
            set_github_status("سجّل الدخول إلى GitHub أولاً.", RED)
            update_page()
            return
        name = (repository.value or "").strip()
        if not name or "/" in name:
            set_github_status("لإنشاء مستودع جديد اكتب الاسم فقط دون owner/.", RED)
            update_page()
            return
        try:
            created = await asyncio.to_thread(
                client.create_repository, name, bool(private_repo.value)
            )
            repository.value = created["full_name"]
            branch.value = created.get("default_branch") or "main"
            set_github_status("تم إنشاء المستودع " + created["full_name"], GREEN)
        except GitHubError as exc:
            set_github_status(str(exc), RED)
        update_page()

    def repository_details() -> tuple[str, str, str]:
        parts = (repository.value or "").strip().strip("/").split("/")
        if len(parts) != 2:
            raise GitHubError("اكتب اسم المستودع بالصيغة owner/repository.")
        owner, repo_name = validate_repository(parts[0], parts[1])
        target_branch = validate_branch(branch.value or "")
        return owner, repo_name, target_branch

    async def start_build(e) -> None:
        client = github.get("client")
        if client is None:
            set_github_status("اربط GitHub قبل بدء البناء.", RED)
            update_page()
            return
        build_button.disabled = True
        refresh_button.disabled = True
        download_button.disabled = True
        set_status("جارٍ تجهيز المشروع ورفع الملفات ثم بدء البناء...", ACCENT)
        set_github_status("جارٍ التحقق من إعدادات المشروع...", ACCENT)
        update_page()
        try:
            project_id = active_project_id()
            root = store._project_dir(project_id)
            configure_flet_project(
                root,
                app_name=app_name.value or "",
                application_id=package_id.value or "",
                version=app_version.value or "",
                build_number=build_number.value or "",
            )
            issues = validate_flet_project(root)
            if issues:
                raise GitHubError("أصلح متطلبات المشروع أولاً:\n• " + "\n• ".join(issues))
            owner, repo_name, target_branch = repository_details()
            archive = store.export_project_archive(project_id)
            set_github_status("جارٍ رفع ملفات المشروع إلى GitHub...", ACCENT)
            update_page()
            commit = await asyncio.to_thread(
                client.push_project_archive,
                owner,
                repo_name,
                target_branch,
                archive,
                "Upload Flet Android project",
            )
            previous_runs = await asyncio.to_thread(
                client.list_workflow_runs, owner, repo_name, target_branch, 20
            )
            github["pending_run_ids"] = {
                int(item["id"]) for item in previous_runs if item.get("id") is not None
            }
            github["run_id"] = None
            github.update({"owner": owner, "repo": repo_name, "branch": target_branch})
            set_github_status(
                f"تم رفع المشروع ({commit[:10]}). جارٍ تشغيل GitHub Actions...",
                ACCENT,
            )
            update_page()
            await asyncio.to_thread(
                client.dispatch_workflow,
                owner,
                repo_name,
                "build-apk.yml",
                target_branch,
            )
            refresh_button.disabled = False
            set_status("تم إرسال طلب بناء APK. تابع الحالة من الزر التالي.", GREEN)
            set_github_status("تم بدء طلب البناء السحابي بنجاح.", GREEN)
        except (GitHubError, WorkspaceError, ValueError, OSError) as exc:
            set_status(str(exc), RED)
            set_github_status(str(exc), RED)
        finally:
            build_button.disabled = False
            update_page()

    async def refresh_build(e) -> None:
        client = github.get("client")
        if client is None:
            set_github_status("سجّل الدخول إلى GitHub أولاً.", RED)
            update_page()
            return
        try:
            owner, repo_name, target_branch = repository_details()
            runs = await asyncio.to_thread(
                client.list_workflow_runs, owner, repo_name, target_branch, 20
            )
            pending = github.get("pending_run_ids")
            if pending is not None:
                run = select_dispatched_run(runs, pending)
                if run is None:
                    build_log.value = (
                        "تم إرسال طلب البناء، لكن GitHub لم ينشئ عملية جديدة ظاهرة بعد.\n"
                        "أعد التحديث بعد قليل. لن نعرض بناءً سابقاً على أنه البناء الحالي."
                    )
                    set_github_status("في انتظار ظهور عملية البناء الجديدة.", ACCENT)
                    update_page()
                    return
                github["pending_run_ids"] = None
            else:
                run = runs[0] if runs else None

            if run is None:
                raise GitHubError("لم يعثر GitHub على بناء لهذا الفرع.")
            github["run_id"] = int(run["id"])
            jobs = await asyncio.to_thread(
                client.list_run_jobs, owner, repo_name, int(run["id"])
            )
            lines = [
                f"Run #{run.get('run_number')} · {run.get('status')} · "
                f"{run.get('conclusion') or 'لم تنتهِ بعد'}",
                str(run.get("html_url") or ""),
                "",
            ]
            for job in jobs:
                lines.append(
                    f"{job.get('name')}: {job.get('status')} / "
                    f"{job.get('conclusion') or 'قيد التنفيذ'}"
                )
                for step in job.get("steps", []):
                    lines.append(
                        f"  - {step.get('name')}: "
                        f"{step.get('conclusion') or step.get('status')}"
                    )
                if job.get("conclusion") in {"failure", "cancelled", "timed_out"}:
                    try:
                        logs = await asyncio.to_thread(
                            client.get_job_logs, owner, repo_name, int(job["id"])
                        )
                        lines.extend(["", "سجل الوظيفة:", logs[-12000:]])
                    except GitHubError as log_error:
                        lines.append("تعذر تحميل السجل: " + str(log_error))
            build_log.value = "\n".join(lines)
            success = run.get("status") == "completed" and run.get("conclusion") == "success"
            failed = run.get("status") == "completed" and run.get("conclusion") != "success"
            download_button.disabled = not success
            refresh_button.disabled = success or failed
            color = GREEN if success else RED if failed else ACCENT
            set_github_status(
                "اكتمل البناء بنجاح. يمكنك تنزيل APK."
                if success
                else "فشل البناء. راجع سجل الخطوات لمعرفة السبب."
                if failed
                else "البناء جارٍ. أعد التحديث لمتابعة التقدم.",
                color,
            )
            set_status("اكتمل بناء APK بنجاح." if success else "تحديث حالة البناء.", color)
        except (GitHubError, ValueError, OSError) as exc:
            set_github_status(str(exc), RED)
        update_page()

    async def download_apk(e) -> None:
        client = github.get("client")
        run_id = github.get("run_id")
        if client is None or not run_id:
            set_github_status("تابع حالة بناء ناجح أولاً.", RED)
            update_page()
            return
        try:
            owner, repo_name, _ = repository_details()
            run = await asyncio.to_thread(client.get_workflow_run, owner, repo_name, int(run_id))
            if run.get("status") != "completed" or run.get("conclusion") != "success":
                raise GitHubError("لا يمكن تنزيل APK قبل اكتمال البناء بنجاح.")
            artifacts = await asyncio.to_thread(
                client.list_artifacts, owner, repo_name, int(run_id)
            )
            available = [item for item in artifacts if not item.get("expired")]
            artifact = next(
                (item for item in available if "apk" in str(item.get("name", "")).lower()),
                available[0] if len(available) == 1 else None,
            )
            if artifact is None:
                raise GitHubError(
                    "لم أجد ملف APK واضحاً ضمن مخرجات البناء. راجع أسماء Artifacts في GitHub Actions."
                )
            archive = await asyncio.to_thread(
                client.download_artifact, owner, repo_name, int(artifact["id"])
            )
            apk_name, apk_bytes = await asyncio.to_thread(client.extract_apk, archive)
            saved_path = await picker.save_file(
                dialog_title="حفظ تطبيق Android",
                file_name=f"{repo_name}-release.apk",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["apk"],
                src_bytes=apk_bytes,
            )
            if saved_path:
                set_github_status(f"تم حفظ {apk_name} في: {saved_path}", GREEN)
                set_status("تم تجهيز APK وحفظه.", GREEN)
            else:
                set_github_status("تم تجهيز APK لكن أُلغيت عملية اختيار مكان الحفظ.", MUTED)
        except (GitHubError, ValueError, OSError) as exc:
            set_github_status(str(exc), RED)
        update_page()

    def text_button(label: str, handler, color: str = PANEL_ALT) -> ft.Button:
        return ft.Button(content=label, on_click=handler, bgcolor=color, color=TEXT)

    header = ft.Container(
        padding=16,
        bgcolor="#0D1624",
        border=ft.Border.only(bottom=ft.BorderSide(1, LINE)),
        content=ft.Row(
            controls=[
                ft.Container(
                    width=44,
                    height=44,
                    border_radius=13,
                    bgcolor="#302A59",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("APK", size=13, weight=ft.FontWeight.BOLD, color="white"),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Flet APK Studio", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text("حوّل مشروع Python/Flet إلى تطبيق Android", size=11, color=MUTED),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.Text("ANDROID", size=10, color=GREEN, weight=ft.FontWeight.BOLD),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=11,
        ),
    )

    project_panel = make_panel(
        "1 · مشروع Flet",
        "استورد ZIP لمشروعك أو أنشئ قالب Flet جاهزاً. لا يوجد محرر أكواد داخل التطبيق.",
        [
            project_name_text,
            project_summary,
            project_check,
            ft.Row(
                controls=[
                    text_button("استيراد مشروع ZIP", import_project, ACCENT),
                    text_button("إنشاء قالب Flet جديد", create_flet_starter),
                ],
                wrap=True,
                spacing=7,
            ),
            ft.Text("مشاريع محفوظة على الجهاز", size=11, color=MUTED),
            project_list,
        ],
    )

    android_panel = make_panel(
        "2 · إعدادات APK",
        "هذه البيانات تُكتب في pyproject.toml وملف بناء Android قبل الرفع.",
        [
            app_name,
            package_id,
            ft.Row(controls=[app_version, build_number], wrap=True, spacing=8),
            ft.Row(
                controls=[
                    text_button("حفظ إعدادات Android", save_android_settings, ACCENT),
                    text_button("فحص المشروع", validate_project),
                ],
                wrap=True,
                spacing=7,
            ),
        ],
    )

    github_panel = make_panel(
        "3 · ربط GitHub",
        "البناء يتم سحابياً عبر GitHub Actions؛ لا يحتاج التطبيق إلى Android SDK على الهاتف.",
        [
            oauth_client_id,
            ft.Row(
                controls=[
                    text_button("بدء تسجيل الدخول", start_github_login, ACCENT),
                    text_button("التحقق من الدخول", verify_github_login),
                    text_button("قطع الاتصال", disconnect_github),
                ],
                wrap=True,
                spacing=7,
            ),
            github_device_info,
            ft.Divider(color=LINE, height=1),
            repository,
            branch,
            private_repo,
            ft.Row(
                controls=[
                    text_button("عرض مستودعاتي", list_repositories),
                    text_button("إنشاء مستودع", create_repository),
                ],
                wrap=True,
                spacing=7,
            ),
            repo_choices,
            ft.Text(
                "ملاحظة أمنية: صلاحيتا repo وworkflow تمنحان وصولاً واسعاً. "
                "راجع المشروع وملفات GitHub Actions قبل البناء، ولا ترفع كلمات مرور أو مفاتيح API.",
                size=10,
                color=AMBER,
            ),
        ],
    )

    build_panel = make_panel(
        "4 · بناء وتنزيل APK",
        "ارفع المشروع وشغّل build-apk.yml، ثم تابع حالة الوظائف ونزّل الملف بعد نجاح البناء فقط.",
        [
            ft.Row(
                controls=[build_button, refresh_button, download_button],
                wrap=True,
                spacing=7,
            ),
            github_status,
            ft.Container(
                padding=11,
                bgcolor="#0B1320",
                border=ft.Border.all(1, LINE),
                border_radius=11,
                content=build_log,
            ),
        ],
    )
    build_button.on_click = start_build
    refresh_button.on_click = refresh_build
    download_button.on_click = download_apk

    refresh_project_list()
    if selected:
        for item in projects:
            if item["id"] == selected:
                project_name_text.value = item["name"]
                break
    refresh_project_summary()

    content = ft.Column(
        controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=15, vertical=12),
                content=ft.Column(
                    controls=[
                        ft.Text("رحلة البناء", size=12, color=MUTED),
                        ft.Row(
                            controls=[
                                ft.Container(
                                    expand=True,
                                    padding=9,
                                    bgcolor=PANEL_ALT,
                                    border_radius=10,
                                    content=ft.Text("① مشروع", size=11, color=TEXT, text_align=ft.TextAlign.CENTER),
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=9,
                                    bgcolor=PANEL_ALT,
                                    border_radius=10,
                                    content=ft.Text("② إعداد", size=11, color=TEXT, text_align=ft.TextAlign.CENTER),
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=9,
                                    bgcolor=PANEL_ALT,
                                    border_radius=10,
                                    content=ft.Text("③ GitHub", size=11, color=TEXT, text_align=ft.TextAlign.CENTER),
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=9,
                                    bgcolor="#214B3D",
                                    border_radius=10,
                                    content=ft.Text("④ APK", size=11, color=GREEN, text_align=ft.TextAlign.CENTER),
                                ),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=8,
                ),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=15),
                content=ft.Column(
                    controls=[
                        project_panel,
                        android_panel,
                        github_panel,
                        build_panel,
                        ft.Container(
                            padding=12,
                            content=ft.Column(
                                controls=[
                                    status_text,
                                    ft.Text(
                                        "النسخة الويب للمعاينة تعرض التصميم فقط. الرفع والبناء والتنزيل الفعلي "
                                        "يتطلب تشغيل تطبيق Flet وربط GitHub.",
                                        size=10,
                                        color=MUTED,
                                    ),
                                ],
                                spacing=5,
                            ),
                        ),
                    ],
                    spacing=12,
                ),
            ),
        ],
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    page.clean()
    page.add(
        ft.Container(
            expand=True,
            bgcolor=BG,
            content=ft.Column(
                controls=[header, content],
                spacing=0,
                expand=True,
            ),
        )
    )
    page.update()


if __name__ == "__main__":
    ft.run(main)
