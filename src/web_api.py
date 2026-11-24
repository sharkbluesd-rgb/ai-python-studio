"""Same-origin FastAPI web backend for Flet APK Studio.

The first web release intentionally uses short-lived in-memory sessions and
temporary per-session workspaces. Deploy as a single worker/instance until a
shared session and job store is introduced.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flet_project import configure_flet_project, validate_flet_project
from github_cloud import (
    DeviceAuthorization,
    GitHubClient,
    GitHubError,
    select_dispatched_run,
    validate_branch,
    validate_repository,
)
from templates import TEMPLATES
from workspace import MAX_ARCHIVE_BYTES, WorkspaceError, WorkspaceStore


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web-preview-static"
DATA_ROOT = Path(os.getenv("FLET_APK_STUDIO_DATA_DIR", tempfile.gettempdir())) / "flet-apk-studio"
SESSION_COOKIE = "flet_apk_session"
SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 500
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
SESSION_SECRET = os.getenv("FLET_APK_STUDIO_SESSION_SECRET", "")
if not SESSION_SECRET:
    # Suitable only for local development; production deployment must set a
    # stable secret so signed cookies cannot be forged by an external party.
    SESSION_SECRET = secrets.token_urlsafe(48)
_SECRET = SESSION_SECRET.encode("utf-8")
_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()

app = FastAPI(
    title="Flet APK Studio API",
    version="2.0.0",
    docs_url="/api/docs" if os.getenv("ENABLE_API_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
)


class DeviceStart(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)


class RepoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    private: bool = True


class ProjectSettings(BaseModel):
    app_name: str = Field(min_length=1, max_length=60)
    application_id: str = Field(min_length=3, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    build_number: str = Field(min_length=1, max_length=12)


class BuildRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=39)
    repository: str = Field(min_length=1, max_length=100)
    branch: str = Field(default="main", min_length=1, max_length=255)


def _cookie_signature(session_id: str) -> str:
    digest = hmac.new(_SECRET, session_id.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{session_id}.{digest}"


def _decode_cookie(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    session_id, signature = value.rsplit(".", 1)
    if not session_id or not hmac.compare_digest(_cookie_signature(session_id), value):
        return None
    return session_id


def _new_session() -> tuple[str, dict[str, Any]]:
    now = time.monotonic()
    with _LOCK:
        expired = [
            key for key, value in _SESSIONS.items()
            if now - value["last_seen"] > SESSION_TTL_SECONDS
        ]
        for key in expired:
            _SESSIONS.pop(key, None)
            shutil.rmtree(DATA_ROOT / key, ignore_errors=True)
        if len(_SESSIONS) >= MAX_SESSIONS:
            raise HTTPException(status_code=503, detail="الخدمة مشغولة حالياً. حاول بعد قليل.")
        session_id = secrets.token_urlsafe(32)
        session = {
            "csrf": secrets.token_urlsafe(32),
            "created": now,
            "last_seen": now,
            "device": None,
            "client_id": None,
            "github": None,
            "project_id": None,
            "project_name": None,
            "owner": None,
            "repository": None,
            "branch": None,
            "baseline_run_ids": set(),
            "run_id": None,
        }
        _SESSIONS[session_id] = session
        return session_id, session


def _session(request: Request) -> tuple[str, dict[str, Any]]:
    session_id = _decode_cookie(request.cookies.get(SESSION_COOKIE))
    if not session_id:
        raise HTTPException(status_code=401, detail="انتهت الجلسة. أعد تهيئة الاتصال.")
    with _LOCK:
        value = _SESSIONS.get(session_id)
        if value is None:
            raise HTTPException(status_code=401, detail="الجلسة غير موجودة أو انتهت صلاحيتها.")
        value["last_seen"] = time.monotonic()
    return session_id, value


def _csrf(request: Request, session: dict[str, Any]) -> None:
    supplied = request.headers.get("x-csrf-token", "")
    origin = request.headers.get("origin")
    if not supplied or not hmac.compare_digest(supplied, session["csrf"]):
        raise HTTPException(status_code=403, detail="فشل التحقق الأمني للطلب. حدّث الصفحة وحاول مجدداً.")
    if origin:
        allowed = {str(request.base_url).rstrip("/")}
        allowed.update(
            item.strip().rstrip("/")
            for item in os.getenv("FLET_APK_STUDIO_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        )
        if origin.rstrip("/") not in allowed:
            raise HTTPException(status_code=403, detail="مصدر الطلب غير مسموح.")


def _store(session_id: str) -> WorkspaceStore:
    return WorkspaceStore(DATA_ROOT / session_id / "workspace")


def _github(session: dict[str, Any]) -> GitHubClient:
    client = session.get("github")
    if not isinstance(client, GitHubClient):
        raise HTTPException(status_code=401, detail="اربط حساب GitHub أولاً.")
    return client


def _github_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GitHubError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, WorkspaceError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="حدث خطأ داخلي. راجع سجل الخادم.")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "flet-apk-studio-api", "version": "2.0.0"}


@app.post("/api/session")
async def create_session(request: Request, response: Response) -> dict[str, str]:
    origin = request.headers.get("origin")
    if origin:
        allowed = {str(request.base_url).rstrip("/")}
        allowed.update(
            item.strip().rstrip("/")
            for item in os.getenv("FLET_APK_STUDIO_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        )
        if origin.rstrip("/") not in allowed:
            raise HTTPException(status_code=403, detail="مصدر الطلب غير مسموح.")
    session_id, session = _new_session()
    response.set_cookie(
        SESSION_COOKIE,
        _cookie_signature(session_id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": session["csrf"], "expires_in": SESSION_TTL_SECONDS}


@app.get("/api/session")
async def get_session(request: Request) -> dict[str, Any]:
    _, session = _session(request)
    client = session.get("github")
    return {
        "authenticated": isinstance(client, GitHubClient),
        "project": (
            {"id": session["project_id"], "name": session["project_name"]}
            if session.get("project_id") else None
        ),
        "repository": (
            {"owner": session["owner"], "name": session["repository"], "branch": session["branch"]}
            if session.get("repository") else None
        ),
    }


@app.post("/api/auth/github/device/start")
async def github_device_start(
    body: DeviceStart, request: Request
) -> dict[str, Any]:
    _, session = _session(request)
    _csrf(request, session)
    try:
        authorization = await asyncio.to_thread(
            GitHubClient.start_device_authorization, body.client_id
        )
    except GitHubError as exc:
        raise _github_error(exc) from exc
    session["device"] = authorization
    session["client_id"] = body.client_id.strip()
    return {
        "verification_uri": authorization.verification_uri,
        "user_code": authorization.user_code,
        "interval": authorization.interval,
        "expires_in": authorization.expires_in,
    }


@app.post("/api/auth/github/device/poll")
async def github_device_poll(request: Request) -> dict[str, Any]:
    _, session = _session(request)
    _csrf(request, session)
    authorization = session.get("device")
    if not isinstance(authorization, DeviceAuthorization):
        raise HTTPException(status_code=400, detail="ابدأ تسجيل الدخول إلى GitHub أولاً.")
    try:
        token = await asyncio.to_thread(
            GitHubClient.poll_device_authorization,
            session["client_id"],
            authorization,
        )
        if not token:
            return {"authorized": False, "pending": True}
        client = GitHubClient(token)
        user = await asyncio.to_thread(client.current_user)
    except GitHubError as exc:
        raise _github_error(exc) from exc
    old = session.get("github")
    if isinstance(old, GitHubClient):
        old.clear()
    session["github"] = client
    session["device"] = None
    session["client_id"] = None
    return {
        "authorized": True,
        "user": {"login": user.get("login"), "name": user.get("name")},
    }


@app.post("/api/auth/github/disconnect")
async def github_disconnect(request: Request) -> dict[str, bool]:
    _, session = _session(request)
    _csrf(request, session)
    client = session.get("github")
    if isinstance(client, GitHubClient):
        client.clear()
    session["github"] = None
    session["device"] = None
    session["client_id"] = None
    return {"disconnected": True}


@app.get("/api/github/me")
async def github_me(request: Request) -> dict[str, Any]:
    _, session = _session(request)
    try:
        user = await asyncio.to_thread(_github(session).current_user)
    except GitHubError as exc:
        raise _github_error(exc) from exc
    return {"login": user.get("login"), "name": user.get("name")}


@app.get("/api/github/repos")
async def github_repositories(request: Request) -> dict[str, Any]:
    _, session = _session(request)
    try:
        repositories = await asyncio.to_thread(_github(session).list_repositories)
    except GitHubError as exc:
        raise _github_error(exc) from exc
    return {
        "repositories": [
            {
                "full_name": item.get("full_name"),
                "private": item.get("private"),
                "default_branch": item.get("default_branch"),
                "updated_at": item.get("updated_at"),
            }
            for item in repositories
            if item.get("full_name") and item.get("default_branch")
        ]
    }


@app.post("/api/github/repos")
async def github_create_repository(
    body: RepoCreate, request: Request
) -> dict[str, Any]:
    _, session = _session(request)
    _csrf(request, session)
    try:
        result = await asyncio.to_thread(
            _github(session).create_repository, body.name, body.private
        )
    except GitHubError as exc:
        raise _github_error(exc) from exc
    return {
        "full_name": result.get("full_name"),
        "private": result.get("private"),
        "default_branch": result.get("default_branch") or "main",
    }


@app.post("/api/projects/import")
async def import_project(
    request: Request, file: UploadFile = File(...)
) -> dict[str, Any]:
    session_id, session = _session(request)
    _csrf(request, session)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="اختر ملف ZIP فقط.")
    payload = await file.read(MAX_ARCHIVE_BYTES + 1)
    await file.close()
    if not payload or len(payload) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="ملف ZIP فارغ أو يتجاوز حد 12 MB.")
    name = Path(file.filename).stem[:48] or "Imported Flet Project"
    try:
        store = _store(session_id)
        project_id = await asyncio.to_thread(store.import_project_archive, payload, name)
        session["project_id"] = project_id
        session["project_name"] = name
        issues = await asyncio.to_thread(
            validate_flet_project, store._project_dir(project_id)
        )
    except (WorkspaceError, OSError, ValueError) as exc:
        raise _github_error(exc) from exc
    return {"project": {"id": project_id, "name": name}, "issues": issues}


@app.post("/api/projects/starter")
async def create_starter(request: Request) -> dict[str, Any]:
    session_id, session = _session(request)
    _csrf(request, session)
    name = "Flet Android Project"
    try:
        store = _store(session_id)
        project_id = await asyncio.to_thread(
            store.create_project_from_template, name, TEMPLATES["Flet Android App"]
        )
    except (WorkspaceError, OSError, KeyError) as exc:
        raise _github_error(exc) from exc
    session["project_id"] = project_id
    session["project_name"] = name
    return {"project": {"id": project_id, "name": name}, "issues": []}


@app.get("/api/projects/current")
async def current_project(request: Request) -> dict[str, Any]:
    session_id, session = _session(request)
    project_id = session.get("project_id")
    if not project_id:
        raise HTTPException(status_code=404, detail="لا يوجد مشروع محدد.")
    try:
        store = _store(session_id)
        root = store._project_dir(project_id)
        files = await asyncio.to_thread(store.list_files, project_id)
        issues = await asyncio.to_thread(validate_flet_project, root)
    except (WorkspaceError, OSError, ValueError) as exc:
        raise _github_error(exc) from exc
    return {
        "project": {"id": project_id, "name": session["project_name"]},
        "files": files,
        "issues": issues,
        "ready": not issues,
    }


@app.post("/api/projects/configure")
async def configure_project(
    body: ProjectSettings, request: Request
) -> dict[str, Any]:
    session_id, session = _session(request)
    _csrf(request, session)
    project_id = session.get("project_id")
    if not project_id:
        raise HTTPException(status_code=404, detail="ارفع مشروعاً أو أنشئ قالباً أولاً.")
    try:
        result = await asyncio.to_thread(
            configure_flet_project,
            _store(session_id)._project_dir(project_id),
            app_name=body.app_name,
            application_id=body.application_id,
            version=body.version,
            build_number=body.build_number,
        )
        issues = await asyncio.to_thread(
            validate_flet_project, _store(session_id)._project_dir(project_id)
        )
    except (WorkspaceError, OSError, ValueError) as exc:
        raise _github_error(exc) from exc
    return {"message": result, "issues": issues, "ready": not issues}


@app.post("/api/build/start")
async def start_build(body: BuildRequest, request: Request) -> dict[str, Any]:
    session_id, session = _session(request)
    _csrf(request, session)
    project_id = session.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="ارفع مشروع Flet أولاً.")
    try:
        owner, repository = validate_repository(body.owner, body.repository)
        branch = validate_branch(body.branch)
        store = _store(session_id)
        root = store._project_dir(project_id)
        issues = await asyncio.to_thread(validate_flet_project, root)
        if issues:
            raise HTTPException(
                status_code=400,
                detail={"message": "المشروع غير جاهز للبناء.", "issues": issues},
            )
        client = _github(session)
        runs = await asyncio.to_thread(
            client.list_workflow_runs, owner, repository, branch, 20
        )
        baseline = {
            int(item["id"]) for item in runs
            if str(item.get("id", "")).isdigit()
        }
        archive = await asyncio.to_thread(store.export_project_archive, project_id)
        commit_sha = await asyncio.to_thread(
            client.push_project_archive, owner, repository, branch, archive
        )
        await asyncio.to_thread(
            client.dispatch_workflow, owner, repository, "build-apk.yml", branch
        )
    except HTTPException:
        raise
    except (GitHubError, WorkspaceError, OSError, ValueError) as exc:
        raise _github_error(exc) from exc
    session.update({
        "owner": owner,
        "repository": repository,
        "branch": branch,
        "baseline_run_ids": baseline,
        "run_id": None,
    })
    return {
        "queued": True,
        "commit": commit_sha,
        "message": "تم رفع المشروع وإرسال طلب البناء. ستظهر العملية بعد أن يسجلها GitHub Actions.",
    }


@app.get("/api/build/status")
async def build_status(request: Request) -> dict[str, Any]:
    _, session = _session(request)
    if not session.get("repository"):
        raise HTTPException(status_code=404, detail="لم يتم بدء عملية بناء لهذه الجلسة.")
    client = _github(session)
    owner, repository, branch = session["owner"], session["repository"], session["branch"]
    try:
        runs = await asyncio.to_thread(
            client.list_workflow_runs, owner, repository, branch, 20
        )
        run = None
        if session.get("run_id"):
            run = await asyncio.to_thread(
                client.get_workflow_run, owner, repository, session["run_id"]
            )
        else:
            run = select_dispatched_run(runs, session["baseline_run_ids"])
            if run:
                session["run_id"] = int(run["id"])
                run = await asyncio.to_thread(
                    client.get_workflow_run, owner, repository, session["run_id"]
                )
        if not run:
            return {"found": False, "status": "queued", "message": "بانتظار ظهور عملية البناء في GitHub Actions."}
        jobs = await asyncio.to_thread(
            client.list_run_jobs, owner, repository, int(run["id"])
        )
    except GitHubError as exc:
        raise _github_error(exc) from exc
    return {
        "found": True,
        "run_id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "jobs": [
            {
                "name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "steps": [
                    {
                        "name": step.get("name"),
                        "status": step.get("status"),
                        "conclusion": step.get("conclusion"),
                    }
                    for step in job.get("steps", [])
                ],
            }
            for job in jobs
        ],
    }


@app.get("/api/build/download")
async def download_apk(request: Request) -> Response:
    _, session = _session(request)
    run_id = session.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="لم يتم العثور على عملية بناء.")
    client = _github(session)
    owner, repository = session["owner"], session["repository"]
    try:
        run = await asyncio.to_thread(client.get_workflow_run, owner, repository, run_id)
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise HTTPException(status_code=409, detail="لا يمكن تنزيل APK قبل نجاح البناء.")
        artifacts = await asyncio.to_thread(client.list_artifacts, owner, repository, run_id)
        artifact = next(
            (
                item for item in artifacts
                if item.get("name") == "flet-apk" and not item.get("expired")
            ),
            None,
        )
        if not artifact:
            raise HTTPException(status_code=404, detail="لم يتم العثور على ملف APK صالح ضمن مخرجات البناء.")
        archive = await asyncio.to_thread(
            client.download_artifact, owner, repository, int(artifact["id"])
        )
        filename, apk = await asyncio.to_thread(client.extract_apk, archive)
    except HTTPException:
        raise
    except (GitHubError, ValueError) as exc:
        raise _github_error(exc) from exc
    return StreamingResponse(
        iter([apk]),
        media_type="application/vnd.android.package-archive",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/session/end")
async def end_session(request: Request, response: Response) -> dict[str, bool]:
    session_id, session = _session(request)
    _csrf(request, session)
    client = session.get("github")
    if isinstance(client, GitHubClient):
        client.clear()
    with _LOCK:
        _SESSIONS.pop(session_id, None)
    shutil.rmtree(DATA_ROOT / session_id, ignore_errors=True)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    return {"ended": True}


@app.get("/", include_in_schema=False)
async def web_home() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/style.css", include_in_schema=False)
async def web_styles() -> FileResponse:
    return FileResponse(WEB_ROOT / "style.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
async def web_script() -> FileResponse:
    return FileResponse(WEB_ROOT / "app.js", media_type="application/javascript")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)
