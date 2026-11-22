import unittest
from unittest.mock import patch

from github_cloud import DeviceAuthorization, GitHubClient, GitHubError


class GitHubCloudTests(unittest.TestCase):
    def test_rejects_empty_token(self):
        with self.assertRaises(GitHubError):
            GitHubClient("")

    def test_device_authorization_requires_client_id(self):
        with self.assertRaises(GitHubError):
            GitHubClient.start_device_authorization("")

    @patch("github_cloud._json_request")
    def test_device_flow_pending_then_token(self, request):
        request.side_effect = [
            {"device_code": "device-secret", "user_code": "ABCD-EFGH",
             "verification_uri": "https://github.com/login/device",
             "interval": 5, "expires_in": 600},
            {"error": "authorization_pending"},
            {"access_token": "gho_" + "x" * 36},
        ]
        auth = GitHubClient.start_device_authorization("client-id")
        self.assertEqual(auth.user_code, "ABCD-EFGH")
        self.assertIsNone(GitHubClient.poll_device_authorization("client-id", auth))
        self.assertTrue(GitHubClient.poll_device_authorization("client-id", auth).startswith("gho_"))

    @patch("github_cloud._json_request")
    def test_repository_creation_is_private_by_default(self, request):
        request.return_value = {"full_name": "user/demo"}
        client = GitHubClient("gho_" + "x" * 36)
        client.create_repository("demo")
        self.assertTrue(request.call_args.kwargs["data"]["private"])

    def test_path_traversal_archive_is_rejected(self):
        import io, zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.py", "print('bad')")
        client = GitHubClient("gho_" + "x" * 36)
        with patch.object(client, "request", side_effect=AssertionError("network should not be called")):
            with self.assertRaises(GitHubError):
                client.push_project_archive("owner", "repo", "main", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
