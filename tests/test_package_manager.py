import subprocess
import unittest
from unittest.mock import patch

from package_manager import (
    MAX_INSTALL_TIMEOUT,
    PackageManagerError,
    install_packages,
    parse_requirements,
)


class PackageManagerTests(unittest.TestCase):
    def test_parses_requirements(self):
        self.assertEqual(
            parse_requirements("# comment\nrequests>=2.0\nrich==13.7.0\n"),
            ["requests>=2.0", "rich==13.7.0"],
        )

    def test_ignores_empty_lines(self):
        self.assertEqual(parse_requirements("\n # note\n"), [])

    def test_rejects_pip_options_and_urls(self):
        for value in (
            "--index-url https://example.com",
            "-e git+https://example.com/x",
            "https://example.com/pkg.whl",
            "-r other.txt",
            "git+https://example.com/repo.git",
        ):
            with self.subTest(value=value), self.assertRaises(PackageManagerError):
                parse_requirements(value)

    def test_rejects_invalid_package_name(self):
        with self.assertRaises(PackageManagerError):
            parse_requirements("requests; rm -rf /")

    def test_rejects_non_text_requirements(self):
        with self.assertRaises(PackageManagerError):
            parse_requirements(None)

    def test_invalid_package_errors_do_not_echo_credentials(self):
        secret_url = "https://user:private-password@example.com/package.whl"
        with self.assertRaises(PackageManagerError) as raised:
            parse_requirements(secret_url)
        self.assertNotIn("private-password", str(raised.exception))
        self.assertNotIn("user:", str(raised.exception))

    def test_bounds_requirements_size_and_line_count(self):
        with self.assertRaisesRegex(PackageManagerError, "64 كيلوبايت"):
            parse_requirements("x" * (64 * 1024 + 1))
        with self.assertRaisesRegex(PackageManagerError, "100 سطر"):
            parse_requirements("\n".join(["# comment"] * 101))

    def test_rejects_non_list_and_empty_install_requests(self):
        for packages in (None, (), [], [""]):
            with self.subTest(packages=packages), self.assertRaises(PackageManagerError):
                install_packages(packages)

    def test_install_uses_argument_list_and_clamps_timeout(self):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        with patch("package_manager.subprocess.run", return_value=completed) as run:
            self.assertEqual(install_packages(["requests>=2"], timeout=9999), "ok")
        args, kwargs = run.call_args
        self.assertIn("requests>=2", args[0])
        self.assertEqual(kwargs["timeout"], MAX_INSTALL_TIMEOUT)
        self.assertFalse(kwargs.get("shell", False))

    def test_install_rejects_option_injection_before_running_pip(self):
        with patch("package_manager.subprocess.run") as run:
            with self.assertRaises(PackageManagerError):
                install_packages(["--index-url=https://evil.example"])
        run.assert_not_called()

    def test_install_rejects_too_many_packages(self):
        with self.assertRaises(PackageManagerError):
            install_packages(["requests"] * 101)

    def test_install_handles_invalid_timeout(self):
        for timeout in (True, "30", None):
            with self.subTest(timeout=timeout), self.assertRaises(PackageManagerError):
                install_packages(["requests"], timeout=timeout)

    def test_install_reports_timeout(self):
        with patch(
            "package_manager.subprocess.run",
            side_effect=subprocess.TimeoutExpired("pip", 5),
        ):
            with self.assertRaisesRegex(PackageManagerError, "انتهت مهلة التثبيت"):
                install_packages(["requests"], timeout=5)


if __name__ == "__main__":
    unittest.main()
