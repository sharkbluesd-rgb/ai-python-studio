"""GitHub OAuth device flow and Actions client.

Security notes:
- OAuth access tokens are process-memory secrets and are never persisted.
- The caller must not execute untrusted Python in the same process while logged in.
- Repository names, refs, archive entries, sizes, and redirects are validated.
"""
from __future__ import annotations

import base64
import io
import json
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


API = "https://api.github.com"
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_AGENT = "AI-Python-Studio"
_SECRET_ASSIGNMENT = re.compile(
    r"""(?i)\b(?:api[_-]?key|client[_-]?secret|password|passwd|access[_-]?token|refresh[_-]?token|github[_-]?token)\b\s*[:=]\s*(['"])[^'"]{20,}['"]"""
)
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
MAX_ARCHIVE_BYTES = 24 * 1024 * 1024
MAX_PROJECT_BYTES = 24 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_FILES = 150
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
MAX_JSON_BYTES = 5 * 1024 * 1024
_IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                  ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist"}
_ALLOWED_HIDDEN_DIRS = {".github", ".vscode", ".idea"}
_ALLOWED_HIDDEN_FILES = {".gitignore", ".editorconfig"}
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubError(RuntimeError):
    """A safe, user-displayable GitHub integration error."""


def _read_json_response(request: urllib.request.Request, *, timeout: int = 35) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", "replace")
        try:
            parsed = json.loads(detail)
            detail = str(parsed.get("message") or parsed.get("error_description") or parsed.get("error") or detail)
        except (ValueError, AttributeError):
            pass
        raise GitHubError(f"GitHub HTTP {exc.code}: {detail[:1000]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubError(f"تعذر الاتصال بـ GitHub: {exc}") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise GitHubError("استجابة GitHub تجاوزت حد الحجم المسموح.")
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise GitHubError("استجابة GitHub غير صالحة.") from exc


def _json_request(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    token: str | None = None,
    accept: str = "application/vnd.github+json",
) -> Any:
    headers = {"Accept": accept, "User-Agent": USER_AGENT}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _read_json_response(
        urllib.request.Request(url, data=body, headers=headers, method=method)
    )


def _oauth_request(url: str, data: dict[str, str]) -> Any:
    """GitHub's device endpoints require URL-encoded form fields, not JSON."""
    body = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    return _read_json_response(request)


def _potential_secret(content: bytes) -> str | None:
    """Return only the secret category; never include matching values in errors."""
    sample = content.decode("utf-8", "ignore")
    if _PRIVATE_KEY.search(sample):
        return "مفتاح خاص"
    if _GITHUB_TOKEN.search(sample):
        return "رمز وصول GitHub"
    if _AWS_KEY.search(sample):
        return "مفتاح AWS"
    if _SECRET_ASSIGNMENT.search(sample):
        return "قيمة سرية ضمن إعداد أو متغير"
    return None


def validate_repository(owner: str, repo: str) -> tuple[str, str]:
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not _OWNER_RE.fullmatch(owner) or not _REPO_RE.fullmatch(repo) or repo in {".", ".."}:
        raise GitHubError("اسم المستودع غير صالح. استخدم owner/repository بأحرف وأرقام وشرطة.")
    return owner, repo


def validate_branch(branch: str) -> str:
    branch = (branch or "").strip()
    forbidden = set(" ~^:?*[\\")
    if (
        not branch or len(branch) > 255 or branch.startswith("-") or branch.startswith("/") or branch.endswith("/")
        or branch.endswith(".") or branch.startswith(".") or "//" in branch
        or ".." in branch or "@{" in branch or any(ch in forbidden or ord(ch) < 32 or ord(ch) == 127 for ch in branch)
    ):
        raise GitHubError("اسم فرع Git غير صالح.")
    parts = branch.split("/")
    if any(not part or part.startswith(".") or part.endswith(".lock") for part in parts):
        raise GitHubError("اسم فرع Git غير صالح.")
    return branch


def _repo_path(owner: str, repo: str) -> str:
    owner, repo = validate_repository(owner, repo)
    return f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"


def _download_redirect_safely(url: str, *, token: str | None, max_bytes: int, timeout: int) -> bytes:
    """Follow GitHub's signed artifact redirect without forwarding the OAuth token."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    headers = {"User-Agent": USER_AGENT, "Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers=headers)
    response = None
    try:
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise
            location = exc.headers.get("Location")
            exc.close()
            if not location:
                raise GitHubError("GitHub لم يرسل رابط تنزيل صالحاً.")
            target = urllib.parse.urljoin(url, location)
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise GitHubError("رابط تنزيل الأداة غير آمن.")
            # The signed storage URL is fetched without Authorization.
            response = urllib.request.urlopen(
                urllib.request.Request(target, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "application/octet-stream"}),
                timeout=timeout,
            )
        with response:
            data = response.read(max_bytes + 1)
    except GitHubError:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubError(f"تعذر تنزيل بيانات البناء: {exc}") from exc
    if len(data) > max_bytes:
        raise GitHubError("حجم البيانات المنزلة يتجاوز الحد المسموح.")
    return data


@dataclass
class DeviceAuthorization:
    device_code: str = field(repr=False)
    user_code: str = field(repr=False)
    verification_uri: str
    interval: int
    expires_in: int
    created_at: float = field(repr=False)
    last_poll_at: float | None = field(default=None, repr=False)


class GitHubClient:
    """Short-lived authenticated GitHub client. Never serialize this object."""

    def __init__(self, access_token: str):
        if not isinstance(access_token, str) or len(access_token) < 20:
            raise GitHubError("رمز GitHub غير صالح.")
        self._token = access_token

    @classmethod
    def start_device_authorization(cls, client_id: str) -> DeviceAuthorization:
        client_id = (client_id or "").strip()
        if not client_id or len(client_id) > 128 or any(ord(ch) < 33 for ch in client_id):
            raise GitHubError("أدخل OAuth Client ID صالحاً.")
        data = _oauth_request(
            DEVICE_URL,
            {"client_id": client_id, "scope": "repo workflow"},
        )
        required = ("device_code", "user_code", "verification_uri")
        if any(not data.get(key) for key in required):
            raise GitHubError(data.get("error_description") or "تعذر بدء تسجيل دخول GitHub.")
        verification_uri = data["verification_uri"]
        parsed = urllib.parse.urlsplit(verification_uri)
        try:
            invalid_verification_uri = (
                parsed.scheme != "https" or parsed.hostname != "github.com"
                or parsed.path.rstrip("/") != "/login/device"
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or parsed.query or parsed.fragment
            )
        except ValueError:
            invalid_verification_uri = True
        if invalid_verification_uri:
            raise GitHubError("أعاد GitHub رابط تحقق غير متوقع.")
        try:
            interval = max(5, int(data.get("interval", 5)))
            expires_in = min(max(int(data.get("expires_in", 900)), 60), 1800)
        except (TypeError, ValueError) as exc:
            raise GitHubError("بيانات انتهاء صلاحية رمز الجهاز غير صالحة.") from exc
        return DeviceAuthorization(
            device_code=str(data["device_code"]),
            user_code=str(data["user_code"]),
            verification_uri=verification_uri,
            interval=interval,
            expires_in=expires_in,
            created_at=time.monotonic(),
        )

    @staticmethod
    def poll_device_authorization(client_id: str, authorization: DeviceAuthorization) -> str | None:
        now = time.monotonic()
        if now - authorization.created_at >= authorization.expires_in:
            raise GitHubError("انتهت صلاحية رمز الجهاز. ابدأ تسجيل الدخول من جديد.")
        if authorization.last_poll_at is not None:
            wait_left = authorization.interval - (now - authorization.last_poll_at)
            if wait_left > 0:
                raise GitHubError(f"انتظر {int(wait_left) + 1} ثوانٍ قبل التحقق مرة أخرى.")
        authorization.last_poll_at = now
        data = _oauth_request(
            TOKEN_URL,
            {
                "client_id": client_id.strip(),
                "device_code": authorization.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        if data.get("access_token"):
            return str(data["access_token"])
        error = data.get("error")
        if error in ("authorization_pending", "slow_down"):
            if error == "slow_down":
                authorization.interval += 5
            return None
        descriptions = {
            "expired_token": "انتهت صلاحية رمز الجهاز.",
            "token_expired": "انتهت صلاحية رمز الجهاز.",
            "access_denied": "رفضت عملية تسجيل الدخول.",
            "incorrect_client_credentials": "OAuth Client ID غير صحيح.",
            "device_flow_disabled": "يجب تفعيل Device Flow في إعدادات OAuth App.",
        }
        if error:
            raise GitHubError(descriptions.get(error, data.get("error_description") or str(error)))
        raise GitHubError("لم يتعرف التطبيق على استجابة تسجيل الدخول.")

    def request(self, path: str, *, method: str = "GET", data: dict | None = None) -> Any:
        if not isinstance(path, str):
            raise GitHubError("مسار GitHub غير صالح.")
        parsed = urllib.parse.urlsplit(path)
        decoded_path = urllib.parse.unquote(parsed.path)
        if (
            parsed.scheme or parsed.netloc or parsed.fragment or not decoded_path.startswith("/")
            or "\\" in decoded_path or any(part in {".", ".."} for part in decoded_path.split("/"))
            or any(ord(ch) < 32 for ch in path)
        ):
            raise GitHubError("مسار GitHub غير صالح.")
        return _json_request(API + path, method=method, data=data, token=self._token)

    def current_user(self) -> dict:
        return self.request("/user")

    def list_repositories(self) -> list[dict]:
        repositories = []
        for page in range(1, 6):
            batch = self.request(
                "/user/repos?" + urllib.parse.urlencode({
                    "visibility": "all", "sort": "updated", "per_page": 100, "page": page,
                })
            )
            if not isinstance(batch, list):
                raise GitHubError("استجابة قائمة المستودعات غير صالحة.")
            repositories.extend(batch)
            if len(batch) < 100:
                break
        return repositories

    def create_repository(self, name: str, private: bool = True) -> dict:
        name = (name or "").strip()
        if not _REPO_RE.fullmatch(name) or name in {".", ".."}:
            raise GitHubError("اسم المستودع غير صالح.")
        return self.request("/user/repos", method="POST", data={
            "name": name, "private": bool(private), "auto_init": True,
            "description": "Created with AI Python Studio",
        })

    def push_project_archive(
        self, owner: str, repo: str, branch: str, archive: bytes,
        message: str = "Upload project from AI Python Studio",
    ) -> str:
        """Validate and upload a complete project ZIP as one Git commit."""
        base = _repo_path(owner, repo)
        branch = validate_branch(branch)
        if not isinstance(archive, (bytes, bytearray)) or not archive or len(archive) > MAX_ARCHIVE_BYTES:
            raise GitHubError("حجم المشروع المضغوط غير صالح أو يتجاوز 24 MB.")
        try:
            zipped = zipfile.ZipFile(io.BytesIO(archive))
        except (zipfile.BadZipFile, OSError) as exc:
            raise GitHubError("أرشيف المشروع غير صالح.") from exc

        files: dict[str, bytes] = {}
        seen: set[str] = set()
        total = 0
        try:
            with zipped:
                infos = [item for item in zipped.infolist() if not item.is_dir()]
                if not infos or len(infos) > MAX_FILES:
                    raise GitHubError("عدد ملفات المشروع غير صالح أو يتجاوز 150 ملفاً.")
                for item in infos:
                    name = item.filename.replace("\\", "/")
                    path = PurePosixPath(name)
                    parts = path.parts
                    if (
                        not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name)
                        or path.is_absolute() or any(part in {"", ".", ".."} for part in parts)
                        or "//" in name or len(name) > 240
                        or any(len(part) > 100 for part in parts)
                    ):
                        raise GitHubError("الأرشيف يحتوي مسار ملف غير آمن.")
                    if any(part in _IGNORED_PARTS for part in parts):
                        continue
                    if any(part.lower() == ".env" or part.lower().startswith(".env.") for part in parts):
                        raise GitHubError("أزل ملفات البيئة والأسرار (.env) قبل رفع المشروع.")
                    for part in parts[:-1]:
                        if part.startswith(".") and part not in _ALLOWED_HIDDEN_DIRS:
                            raise GitHubError("الأرشيف يحتوي مجلداً مخفياً غير مسموح.")
                    if path.name.startswith(".") and path.name not in _ALLOWED_HIDDEN_FILES:
                        if parts[0] in _IGNORED_PARTS:
                            continue
                        raise GitHubError("الأرشيف يحتوي ملفاً مخفياً غير مسموح.")
                    mode = (item.external_attr >> 16) & 0xFFFF
                    file_type = stat.S_IFMT(mode)
                    if file_type == stat.S_IFLNK or (file_type and file_type != stat.S_IFREG):
                        raise GitHubError("الأرشيف يحتوي رابطاً رمزياً أو نوع ملف غير مسموح.")
                    if item.flag_bits & 0x1:
                        raise GitHubError("الأرشيف يحتوي ملفات مشفرة غير مدعومة.")
                    if item.file_size > MAX_FILE_BYTES:
                        raise GitHubError(f"الملف {name} يتجاوز 512 KB.")
                    total += item.file_size
                    if total > MAX_PROJECT_BYTES:
                        raise GitHubError("الحجم الإجمالي لملفات المشروع يتجاوز 24 MB.")
                    canonical = name.casefold()
                    if canonical in seen:
                        raise GitHubError("الأرشيف يحتوي أسماء ملفات مكررة أو متصادمة.")
                    seen.add(canonical)
                    try:
                        with zipped.open(item) as source:
                            raw = source.read(MAX_FILE_BYTES + 1)
                    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                        raise GitHubError(f"تعذر قراءة الملف {name} داخل الأرشيف.") from exc
                    if len(raw) != item.file_size or len(raw) > MAX_FILE_BYTES:
                        raise GitHubError(f"حجم الملف {name} داخل الأرشيف غير متطابق.")
                    secret_type = _potential_secret(raw)
                    if secret_type:
                        raise GitHubError(
                            f"أوقف رفع الملف {name}: قد يحتوي على {secret_type}. "
                            "أزل الأسرار واستبدلها بمتغيرات بيئة قبل الرفع."
                        )
                    files[name] = raw
        except GitHubError:
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            raise GitHubError("الأرشيف تالف أو يحتوي بيانات مضغوطة غير صالحة.") from exc

        if not files:
            raise GitHubError("لا توجد ملفات قابلة للرفع في المشروع.")

        encoded_branch = urllib.parse.quote(branch, safe="/")
        base_commit = None
        try:
            ref_data = self.request(f"{base}/git/ref/heads/{encoded_branch}")
            base_commit = self.request(f"{base}/git/commits/{ref_data['object']['sha']}")
        except (GitHubError, KeyError) as exc:
            if not isinstance(exc, GitHubError) or "HTTP 404" not in str(exc):
                raise
        base_tree = base_commit["tree"]["sha"] if base_commit else None

        entries = []
        for path, raw in sorted(files.items()):
            blob = self.request(f"{base}/git/blobs", method="POST", data={
                "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
            })
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree_data = {"tree": entries}
        if base_tree:
            tree_data["base_tree"] = base_tree
        tree = self.request(f"{base}/git/trees", method="POST", data=tree_data)
        commit_data = {"message": message[:200], "tree": tree["sha"]}
        if base_commit:
            commit_data["parents"] = [base_commit["sha"]]
        commit = self.request(f"{base}/git/commits", method="POST", data=commit_data)
        if base_commit:
            self.request(
                f"{base}/git/refs/heads/{encoded_branch}",
                method="PATCH", data={"sha": commit["sha"], "force": False},
            )
        else:
            self.request(
                f"{base}/git/refs", method="POST",
                data={"ref": f"refs/heads/{branch}", "sha": commit["sha"]},
            )
        return commit["sha"]

    def dispatch_workflow(self, owner: str, repo: str, workflow: str, branch: str) -> None:
        base = _repo_path(owner, repo)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}\.ya?ml", workflow or "") or ".." in workflow:
            raise GitHubError("اسم ملف workflow غير صالح.")
        branch = validate_branch(branch)
        self.request(
            f"{base}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches",
            method="POST", data={"ref": branch},
        )

    def list_workflow_runs(
        self, owner: str, repo: str, branch: str, per_page: int = 5,
        workflow: str = "build-apk.yml",
    ) -> list[dict]:
        base = _repo_path(owner, repo)
        branch = validate_branch(branch)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}\.ya?ml", workflow or "") or ".." in workflow:
            raise GitHubError("اسم ملف workflow غير صالح.")
        query = urllib.parse.urlencode({"branch": branch, "per_page": min(max(int(per_page), 1), 20)})
        endpoint = urllib.parse.quote(workflow, safe="")
        result = self.request(f"{base}/actions/workflows/{endpoint}/runs?{query}")
        return result["workflow_runs"]

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> dict:
        if int(run_id) < 1:
            raise GitHubError("رقم عملية البناء غير صالح.")
        return self.request(f"{_repo_path(owner, repo)}/actions/runs/{int(run_id)}")

    def list_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict]:
        if int(run_id) < 1:
            raise GitHubError("رقم عملية البناء غير صالح.")
        return self.request(f"{_repo_path(owner, repo)}/actions/runs/{int(run_id)}/jobs")["jobs"]

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        if int(job_id) < 1:
            raise GitHubError("رقم الوظيفة غير صالح.")
        url = f"{API}{_repo_path(owner, repo)}/actions/jobs/{int(job_id)}/logs"
        raw = _download_redirect_safely(url, token=self._token, max_bytes=20 * 1024 * 1024, timeout=45)
        if raw.startswith(b"PK"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    chunks = [
                        archive.read(name).decode("utf-8", "replace")
                        for name in archive.namelist()
                        if name.lower().endswith(".txt") and not name.startswith("/")
                        and ".." not in PurePosixPath(name).parts
                    ]
                    return "\n".join(chunks)[-40000:]
            except zipfile.BadZipFile as exc:
                raise GitHubError("أرشيف سجل البناء غير صالح.") from exc
        return raw.decode("utf-8", "replace")[-40000:]

    def list_artifacts(self, owner: str, repo: str, run_id: int) -> list[dict]:
        if int(run_id) < 1:
            raise GitHubError("رقم عملية البناء غير صالح.")
        return self.request(f"{_repo_path(owner, repo)}/actions/runs/{int(run_id)}/artifacts")["artifacts"]

    def download_artifact(self, owner: str, repo: str, artifact_id: int) -> bytes:
        if int(artifact_id) < 1:
            raise GitHubError("رقم ملف البناء غير صالح.")
        url = f"{API}{_repo_path(owner, repo)}/actions/artifacts/{int(artifact_id)}/zip"
        data = _download_redirect_safely(
            url, token=self._token, max_bytes=MAX_ARTIFACT_BYTES, timeout=90,
        )
        if not data.startswith(b"PK"):
            raise GitHubError("الملف المستلم ليس أرشيف ZIP صالحاً.")
        return data

    @staticmethod
    def extract_apk(artifact_zip: bytes) -> tuple[str, bytes]:
        """Unwrap the Actions artifact, extract one APK, and verify Android structure."""
        def find_apk(data: bytes, depth: int = 0) -> tuple[str, bytes]:
            if depth > 2:
                raise GitHubError("بنية أرشيف البناء متداخلة بشكل غير متوقع.")
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    files = [item for item in archive.infolist() if not item.is_dir()]
                    apks = [item for item in files if item.filename.lower().endswith(".apk")]
                    if len(apks) == 1:
                        item = apks[0]
                        path = PurePosixPath(item.filename)
                        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                            raise GitHubError("مسار APK داخل الأرشيف غير آمن.")
                        if item.file_size < 1024 or item.file_size > MAX_ARTIFACT_BYTES:
                            raise GitHubError("حجم ملف APK غير منطقي أو يتجاوز الحد المسموح.")
                        with archive.open(item) as source:
                            apk = source.read(MAX_ARTIFACT_BYTES + 1)
                        if len(apk) != item.file_size or len(apk) > MAX_ARTIFACT_BYTES:
                            raise GitHubError("حجم ملف APK المستخرج غير متطابق.")
                        return path.name, apk
                    if len(apks) > 1:
                        raise GitHubError("يحتوي ملف البناء أكثر من APK واحد؛ اختر نسخة محددة.")
                    nested = [
                        item for item in files
                        if item.filename.lower().endswith(".zip")
                        and not item.filename.startswith("/")
                        and ".." not in PurePosixPath(item.filename).parts
                    ]
                    if depth < 2 and len(nested) == 1:
                        item = nested[0]
                        if item.file_size > MAX_ARTIFACT_BYTES:
                            raise GitHubError("أرشيف APK الداخلي يتجاوز الحد المسموح.")
                        with archive.open(item) as source:
                            inner = source.read(MAX_ARTIFACT_BYTES + 1)
                        if len(inner) != item.file_size or len(inner) > MAX_ARTIFACT_BYTES:
                            raise GitHubError("حجم أرشيف APK الداخلي غير متطابق.")
                        return find_apk(inner, depth + 1)
                    raise GitHubError("لم يتم العثور على APK داخل ملف البناء.")
            except GitHubError:
                raise
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                raise GitHubError("أرشيف البناء تالف أو غير صالح.") from exc

        filename, apk = find_apk(artifact_zip)
        try:
            with zipfile.ZipFile(io.BytesIO(apk)) as package:
                if "AndroidManifest.xml" not in set(package.namelist()):
                    raise GitHubError("الملف المستخرج ليس تطبيق Android APK صالحاً.")
        except zipfile.BadZipFile as exc:
            raise GitHubError("ملف APK المستخرج غير صالح.") from exc
        return filename, apk

    def clear(self) -> None:
        """Best-effort removal of the token reference from this client."""
        self._token = ""
