"""GitHub device authentication and cloud Android build integration.

Tokens are held only by the in-memory client instance. Never persist this client
or its access token in workspace settings, project files, logs, or environment.
"""
from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any


API = "https://api.github.com"
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_AGENT = "AI-Python-Studio"


class GitHubError(RuntimeError):
    pass


def _json_request(url: str, *, method: str = "GET", data: dict | None = None,
                  token: str | None = None, accept: str = "application/vnd.github+json") -> Any:
    headers = {"Accept": accept, "User-Agent": USER_AGENT}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1200]
        try:
            parsed = json.loads(detail)
            detail = parsed.get("message", detail)
        except (ValueError, AttributeError):
            pass
        raise GitHubError(f"GitHub HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubError(f"تعذر الاتصال بـ GitHub: {exc}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise GitHubError("استجابة GitHub غير صالحة.") from exc


@dataclass
class DeviceAuthorization:
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int
    created_at: float


class GitHubClient:
    """A short-lived authenticated GitHub client; do not serialize it."""

    def __init__(self, access_token: str):
        if not access_token or len(access_token) < 20:
            raise GitHubError("رمز GitHub غير صالح.")
        self._token = access_token

    @classmethod
    def start_device_authorization(cls, client_id: str) -> DeviceAuthorization:
        client_id = (client_id or "").strip()
        if not client_id or len(client_id) > 128:
            raise GitHubError("أدخل OAuth Client ID صالحاً.")
        data = _json_request(
            DEVICE_URL, method="POST",
            data={"client_id": client_id, "scope": "repo workflow"},
            accept="application/json",
        )
        required = ("device_code", "user_code", "verification_uri")
        if any(not data.get(key) for key in required):
            raise GitHubError(data.get("error_description") or "تعذر بدء تسجيل دخول GitHub.")
        return DeviceAuthorization(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            interval=max(5, int(data.get("interval", 5))),
            expires_in=int(data.get("expires_in", 900)),
            created_at=time.monotonic(),
        )

    @staticmethod
    def poll_device_authorization(client_id: str, authorization: DeviceAuthorization) -> str | None:
        if time.monotonic() - authorization.created_at >= authorization.expires_in:
            raise GitHubError("انتهت صلاحية رمز الجهاز. ابدأ تسجيل الدخول من جديد.")
        data = _json_request(
            TOKEN_URL, method="POST",
            data={
                "client_id": client_id.strip(),
                "device_code": authorization.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            accept="application/json",
        )
        if data.get("access_token"):
            return data["access_token"]
        error = data.get("error")
        if error in ("authorization_pending", "slow_down"):
            if error == "slow_down":
                authorization.interval += 5
            return None
        descriptions = {
            "expired_token": "انتهت صلاحية رمز الجهاز.",
            "access_denied": "رفضت عملية تسجيل الدخول.",
            "incorrect_client_credentials": "OAuth Client ID غير صحيح.",
        }
        if error:
            raise GitHubError(descriptions.get(error, data.get("error_description") or error))
        raise GitHubError("لم يتعرف التطبيق على استجابة تسجيل الدخول.")

    def request(self, path: str, *, method: str = "GET", data: dict | None = None) -> Any:
        if not path.startswith("/") or ".." in path:
            raise GitHubError("مسار GitHub غير صالح.")
        return _json_request(API + path, method=method, data=data, token=self._token)

    def current_user(self) -> dict:
        return self.request("/user")

    def list_repositories(self) -> list[dict]:
        return self.request("/user/repos?visibility=all&sort=updated&per_page=100")

    def create_repository(self, name: str, private: bool = True) -> dict:
        name = (name or "").strip()
        if not name or len(name) > 100:
            raise GitHubError("اسم المستودع مطلوب وبحد أقصى 100 حرف.")
        return self.request("/user/repos", method="POST", data={
            "name": name, "private": bool(private),
            "auto_init": True, "description": "Created with AI Python Studio",
        })

    def push_project_archive(self, owner: str, repo: str, branch: str, archive: bytes,
                             message: str = "Upload project from AI Python Studio") -> str:
        """Upload archive contents atomically using Git blobs/tree/commit/ref APIs."""
        for value in (owner, repo, branch):
            if not value or any(ch in value for ch in "\r\n"):
                raise GitHubError("بيانات المستودع أو الفرع غير صالحة.")
        if len(archive) > 24 * 1024 * 1024:
            raise GitHubError("حجم المشروع يتجاوز 24 MB.")
        try:
            zipped = zipfile.ZipFile(io.BytesIO(archive))
        except (zipfile.BadZipFile, OSError) as exc:
            raise GitHubError("أرشيف المشروع غير صالح.") from exc

        files = {}
        total = 0
        for item in zipped.infolist():
            if item.is_dir():
                continue
            name = item.filename.replace("\\", "/")
            parts = name.split("/")
            if name.startswith("/") or any(p in ("", ".", "..") for p in parts):
                raise GitHubError("الأرشيف يحتوي مساراً غير آمن.")
            if any(p in {".git", ".venv", "venv", "node_modules", "__pycache__"} for p in parts):
                continue
            raw = zipped.read(item)
            total += len(raw)
            if total > 24 * 1024 * 1024 or len(files) >= 150:
                raise GitHubError("المشروع يتجاوز حدود الرفع (24 MB / 150 ملفاً).")
            files[name] = raw
        if not files:
            raise GitHubError("لا توجد ملفات لرفعها.")

        base_ref = None
        try:
            base_ref = self.request(f"/repos/{owner}/{repo}/git/ref/heads/{urllib.parse.quote(branch, safe='/')}")
            base_commit = self.request(base_ref["object"]["url"].replace(API, ""))
            base_tree = base_commit["tree"]["sha"]
        except GitHubError as exc:
            if "404" not in str(exc):
                raise
            base_tree = None

        entries = []
        for path, raw in sorted(files.items()):
            blob = self.request(f"/repos/{owner}/{repo}/git/blobs", method="POST", data={
                "content": base64.b64encode(raw).decode("ascii"),
                "encoding": "base64",
            })
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree_data = {"tree": entries}
        if base_tree:
            tree_data["base_tree"] = base_tree
        tree = self.request(f"/repos/{owner}/{repo}/git/trees", method="POST", data=tree_data)
        parent = base_commit["sha"] if base_ref else None
        commit_data = {"message": message, "tree": tree["sha"]}
        if parent:
            commit_data["parents"] = [parent]
        commit = self.request(f"/repos/{owner}/{repo}/git/commits", method="POST", data=commit_data)
        if base_ref:
            self.request(f"/repos/{owner}/{repo}/git/refs/heads/{urllib.parse.quote(branch, safe='/')}",
                         method="PATCH", data={"sha": commit["sha"], "force": False})
        else:
            self.request(f"/repos/{owner}/{repo}/git/refs", method="POST",
                         data={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        return commit["sha"]

    def dispatch_workflow(self, owner: str, repo: str, workflow: str, branch: str) -> None:
        self.request(f"/repos/{owner}/{repo}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches",
                     method="POST", data={"ref": branch})

    def list_workflow_runs(self, owner: str, repo: str, branch: str, per_page: int = 5) -> list[dict]:
        query = urllib.parse.urlencode({"branch": branch, "per_page": min(max(per_page, 1), 20)})
        return self.request(f"/repos/{owner}/{repo}/actions/runs?{query}")["workflow_runs"]

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> dict:
        return self.request(f"/repos/{owner}/{repo}/actions/runs/{int(run_id)}")

    def list_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict]:
        return self.request(f"/repos/{owner}/{repo}/actions/runs/{int(run_id)}/jobs")["jobs"]

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        url = f"{API}/repos/{owner}/{repo}/actions/jobs/{int(job_id)}/logs"
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        })
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(20 * 1024 * 1024 + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubError(f"تعذر جلب سجل البناء: {exc}") from exc
        if len(raw) > 20 * 1024 * 1024:
            raise GitHubError("سجل البناء أكبر من 20 MB.")
        if raw.startswith(b"PK"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    chunks = [archive.read(name).decode("utf-8", "replace") for name in archive.namelist() if name.lower().endswith(".txt")]
                    return "\n".join(chunks)[-40000:]
            except zipfile.BadZipFile as exc:
                raise GitHubError("أرشيف سجل البناء غير صالح.") from exc
        return raw.decode("utf-8", "replace")[-40000:]

    def list_artifacts(self, owner: str, repo: str, run_id: int) -> list[dict]:
        return self.request(f"/repos/{owner}/{repo}/actions/runs/{int(run_id)}/artifacts")["artifacts"]

    def download_artifact(self, owner: str, repo: str, artifact_id: int) -> bytes:
        url = f"{API}/repos/{owner}/{repo}/actions/artifacts/{int(artifact_id)}/zip"
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        })
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(100 * 1024 * 1024 + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubError(f"تعذر تنزيل ملف البناء: {exc}") from exc
        if len(data) > 100 * 1024 * 1024:
            raise GitHubError("حجم ملف البناء يتجاوز 100 MB.")
        if not data.startswith(b"PK"):
            raise GitHubError("الملف المستلم ليس أرشيف APK صالحاً.")
        return data

    def clear(self) -> None:
        self._token = ""
