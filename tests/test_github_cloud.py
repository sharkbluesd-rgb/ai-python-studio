import io
import stat
import time
import unittest
import urllib.parse
import zipfile
from unittest.mock import patch

from github_cloud import (
    DeviceAuthorization,
    GitHubClient,
    GitHubError,
    _oauth_request,
    validate_branch,
    validate_repository,
)


class GitHubCloudTests(unittest.TestCase):
    def setUp(self):
        self.client = GitHubClient("gho_" + "x" * 36)

    def test_rejects_empty_token(self):
        with self.assertRaises(GitHubError):
            GitHubClient("")

    def test_device_authorization_requires_client_id(self):
        with self.assertRaises(GitHubError):
            GitHubClient.start_device_authorization("")

    @patch("github_cloud._read_json_response")
    def test_oauth_requests_use_form_encoding(self, response):
        response.return_value = {"ok": True}
        _oauth_request("https://github.com/login/device/code", {
            "client_id": "client id", "scope": "repo workflow",
        })
        request = response.call_args.args[0]
        self.assertEqual(request.get_header("Content-type"), "application/x-www-form-urlencoded")
        self.assertEqual(
            urllib.parse.parse_qs(request.data.decode()),
            {"client_id": ["client id"], "scope": ["repo workflow"]},
        )

    @patch("github_cloud._oauth_request")
    def test_device_flow_pending_then_token(self, oauth):
        oauth.side_effect = [
            {"device_code": "device-secret", "user_code": "ABCD-EFGH",
             "verification_uri": "https://github.com/login/device",
             "interval": 5, "expires_in": 600},
            {"error": "authorization_pending"},
            {"access_token": "gho_" + "x" * 36},
        ]
        auth = GitHubClient.start_device_authorization("client-id")
        self.assertEqual(auth.user_code, "ABCD-EFGH")
        self.assertIsNone(GitHubClient.poll_device_authorization("client-id", auth))
        auth.last_poll_at = None  # Skip the real wait in this deterministic test.
        self.assertTrue(GitHubClient.poll_device_authorization("client-id", auth).startswith("gho_"))

    @patch("github_cloud._oauth_request")
    def test_rejects_untrusted_verification_url(self, oauth):
        oauth.return_value = {
            "device_code": "secret", "user_code": "ABCD-EFGH",
            "verification_uri": "https://attacker.example/login/device",
            "interval": 5, "expires_in": 600,
        }
        with self.assertRaises(GitHubError):
            GitHubClient.start_device_authorization("client-id")

    @patch("github_cloud._json_request")
    def test_repository_creation_is_private_by_default(self, request):
        request.return_value = {"full_name": "user/demo"}
        self.client.create_repository("demo")
        self.assertTrue(request.call_args.kwargs["data"]["private"])

    def test_repository_validation_rejects_path_injection(self):
        for owner, repo in (("owner/other", "repo"), ("owner", "../repo"),
                            ("owner?x=1", "repo"), ("", "repo")):
            with self.subTest(owner=owner, repo=repo), self.assertRaises(GitHubError):
                validate_repository(owner, repo)

    def test_branch_validation(self):
        self.assertEqual(validate_branch("feature/studio-2.0"), "feature/studio-2.0")
        for branch in ("../main", "main?query=1", "branch name", "refs//heads/x",
                       "bad.lock", "-option", "trailing.", "foo\\bar"):
            with self.subTest(branch=branch), self.assertRaises(GitHubError):
                validate_branch(branch)

    def make_zip(self, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in entries:
                archive.writestr(name, content)
        return buffer.getvalue()

    def test_path_traversal_archive_is_rejected(self):
        archive = self.make_zip([("../escape.py", "print('bad')")])
        with patch.object(self.client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaises(GitHubError):
                self.client.push_project_archive("owner", "repo", "main", archive)

    def test_oversized_member_is_rejected_before_decompression(self):
        archive = self.make_zip([("large.py", b"x" * (512 * 1024 + 1))])
        with patch.object(self.client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaisesRegex(GitHubError, "512 KB"):
                self.client.push_project_archive("owner", "repo", "main", archive)

    def test_environment_files_are_rejected(self):
        archive = self.make_zip([(".env", "TOKEN=secret")])
        with patch.object(self.client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaisesRegex(GitHubError, r"\.env"):
                self.client.push_project_archive("owner", "repo", "main", archive)

    def test_symlink_archive_member_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            info = zipfile.ZipInfo("linked.py")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "../outside.py")
        with patch.object(self.client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaises(GitHubError):
                self.client.push_project_archive("owner", "repo", "main", buffer.getvalue())

    def test_secret_assignments_are_blocked_before_upload(self):
        secret = 'github_token = "github_pat_' + "A" * 30 + '"'
        archive = self.make_zip([("settings.py", secret)])
        with patch.object(self.client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaisesRegex(GitHubError, "رمز وصول GitHub"):
                self.client.push_project_archive("owner", "repo", "main", archive)

    def test_dispatched_run_selection_ignores_stale_success(self):
        runs = [
            {"id": 12, "event": "push", "conclusion": "success"},
            {"id": 11, "event": "workflow_dispatch", "conclusion": "failure"},
            {"id": 10, "event": "workflow_dispatch", "conclusion": "success"},
        ]
        selected = select_dispatched_run(runs, {10, 11})
        self.assertEqual(selected["id"], 12) if False else None
        self.assertIsNone(selected)
        runs.insert(0, {"id": 13, "event": "workflow_dispatch", "status": "queued"})
        self.assertEqual(select_dispatched_run(runs, {10, 11})["id"], 13)

    def test_workflow_runs_are_scoped_to_android_workflow(self):
        with patch.object(self.client, "request", return_value={"workflow_runs": []}) as request:
            self.client.list_workflow_runs("owner", "repo", "main")
        self.assertIn("/actions/workflows/build-apk.yml/runs?", request.call_args.args[0])

    def test_polling_respects_minimum_device_interval(self):
        auth = DeviceAuthorization(
            device_code="hidden", user_code="hidden",
            verification_uri="https://github.com/login/device",
            interval=5, expires_in=600, created_at=time.monotonic(),
            last_poll_at=time.monotonic(),
        )
        with patch("github_cloud._oauth_request", side_effect=AssertionError("must wait")):
            with self.assertRaisesRegex(GitHubError, "انتظر"):
                GitHubClient.poll_device_authorization("client-id", auth)

    def test_extract_apk_requires_real_android_package(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as package:
            package.writestr("AndroidManifest.xml", b"binary manifest")
            package.writestr("classes.dex", b"x" * 1500)
        apk_bytes = inner.getvalue()
        wrapper = self.make_zip([("flet-apk.zip", self.make_zip([("app-release.apk", apk_bytes)]))])
        filename, content = GitHubClient.extract_apk(wrapper)
        self.assertEqual(filename, "app-release.apk")
        self.assertEqual(content, apk_bytes)

    def test_extract_apk_rejects_non_apk_zip(self):
        outer = self.make_zip([("app.apk", b"not a package" * 200)])
        with self.assertRaises(GitHubError):
            GitHubClient.extract_apk(outer)


if __name__ == "__main__":
    unittest.main()
