"""Focused regression tests for the FastAPI web backend."""
from pathlib import Path
import tempfile
import unittest

import web_api
from fastapi.testclient import TestClient
from unittest.mock import patch


class WebApiSecurityTests(unittest.TestCase):
    def test_signed_session_cookie_rejects_tampering(self):
        value = web_api._cookie_signature("session-example")
        self.assertEqual(web_api._decode_cookie(value), "session-example")
        self.assertIsNone(web_api._decode_cookie(value + "tampered"))
        self.assertIsNone(web_api._decode_cookie(""))

    def test_new_session_has_separate_csrf_and_server_side_state(self):
        session_id, session = web_api._new_session()
        try:
            self.assertTrue(session_id)
            self.assertGreaterEqual(len(session["csrf"]), 32)
            self.assertIsNone(session["github"])
            self.assertNotIn("token", session)
        finally:
            with web_api._LOCK:
                web_api._SESSIONS.pop(session_id, None)

    def test_api_exposes_required_web_workflow_routes(self):
        routes = {route.path for route in web_api.app.routes}
        expected = {
            "/api/health", "/api/session",
            "/api/auth/github/device/start", "/api/auth/github/device/poll",
            "/api/github/repos", "/api/projects/import",
            "/api/projects/configure", "/api/build/start",
            "/api/build/status", "/api/build/download",
        }
        self.assertTrue(expected.issubset(routes))

    def test_session_bootstrap_csrf_and_starter_project(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(web_api, "DATA_ROOT", Path(directory)):
                with patch.object(web_api, "COOKIE_SECURE", False):
                    with TestClient(web_api.app) as client:
                        created = client.post("/api/session")
                        self.assertEqual(created.status_code, 200)
                        csrf = created.json()["csrf_token"]
                        session = client.get("/api/session")
                        self.assertEqual(session.status_code, 200)
                        self.assertEqual(session.json()["csrf_token"], csrf)

                        denied = client.post("/api/projects/starter")
                        self.assertEqual(denied.status_code, 403)

                        starter = client.post(
                            "/api/projects/starter",
                            headers={"X-CSRF-Token": csrf},
                        )
                        self.assertEqual(starter.status_code, 200)
                        current = client.get("/api/projects/current")
                        self.assertEqual(current.status_code, 200)
                        self.assertTrue(current.json()["ready"])

    def test_imported_projects_receive_trusted_build_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_api._ensure_build_workflow(root)
            workflow = root / ".github" / "workflows" / "build-apk.yml"
            self.assertTrue(workflow.is_file())
            content = workflow.read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", content)
            self.assertIn("target: apk", content)


if __name__ == "__main__":
    unittest.main()
