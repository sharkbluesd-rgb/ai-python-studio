import unittest

from package_manager import (
    PackageManagerError,
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
        for value in ("--index-url https://example.com", "-e git+https://example.com/x", "https://example.com/pkg.whl"):
            with self.subTest(value=value):
                with self.assertRaises(PackageManagerError):
                    parse_requirements(value)

    def test_rejects_invalid_package_name(self):
        with self.assertRaises(PackageManagerError):
            parse_requirements("requests; rm -rf /")

if __name__ == "__main__":
    unittest.main()
