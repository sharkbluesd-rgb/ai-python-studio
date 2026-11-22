"""Built-in offline project templates."""

from __future__ import annotations


TEMPLATES: dict[str, dict[str, str]] = {
    "Python Starter": {
        "main.py": (
            "from utils import greet\n\n"
            "def main():\n"
            "    print(greet('Python Developer'))\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "utils.py": (
            'def greet(name: str) -> str:\n'
            '    return f"Hello, {name}!"\n'
        ),
        "README.md": (
            "# Python Starter\n\n"
            "A small multi-file Python project.\n\n"
            "Run `main.py` from AI Python Studio.\n"
        ),
        "tests/test_utils.py": (
            "from utils import greet\n\n"
            "def test_greet():\n"
            "    assert greet('Studio') == 'Hello, Studio!'\n"
        ),
    },
    "Automation Starter": {
        "main.py": (
            "from pathlib import Path\n\n"
            "def list_python_files(folder='.'): \n"
            "    return sorted(Path(folder).glob('*.py'))\n\n"
            "if __name__ == '__main__':\n"
            "    for item in list_python_files():\n"
            "        print(item.name)\n"
        ),
        "README.md": (
            "# Automation Starter\n\n"
            "A safe starting point for local file automation.\n"
            "Always review scripts before running them.\n"
        ),
        "requirements.txt": "# Add compatible packages here, one per line.\n",
    },
    "CLI Tool Starter": {
        "main.py": (
            "import argparse\n\n"
            "def main():\n"
            "    parser = argparse.ArgumentParser(description='My Python tool')\n"
            "    parser.add_argument('--name', default='Developer')\n"
            "    args = parser.parse_args()\n"
            "    print(f'Hello, {args.name}!')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "README.md": "# CLI Tool\n\nA command-line Python project starter.\n",
        "tests/test_main.py": (
            "import unittest\n\n"
            "class BasicTests(unittest.TestCase):\n"
            "    def test_example(self):\n"
            "        self.assertEqual(2 + 2, 4)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
    },
    "Flet App Starter": {
        "main.py": (
            "import flet as ft\n\n"
            "def main(page: ft.Page):\n"
            "    page.title = 'My Flet App'\n"
            "    page.add(ft.Text('Hello from Flet!', size=24))\n\n"
            "if __name__ == '__main__':\n"
            "    ft.run(main)\n"
        ),
        "README.md": (
            "# Flet App Starter\n\n"
            "A starter for building a Python UI with Flet.\n"
            "Flet must be available in the target runtime.\n"
        ),
        "requirements.txt": "flet\n",
    },
    "Flet Android App": {
        "src/main.py": (
            "import flet as ft\n\n"
            "def main(page: ft.Page):\n"
            "    page.title = \"My Android App\"\n"
            "    page.add(ft.SafeArea(content=ft.Column(controls=[\n"
            "        ft.Text(\"Hello from Python!\", size=26),\n"
            "        ft.Text(\"Your Android app starts here.\"),\n"
            "    ], spacing=16)))\n\n"
            "if __name__ == \"__main__\":\n"
            "    ft.run(main)\n"
        ),
        "pyproject.toml": (
            "[project]\nname = \"my-android-app\"\nversion = \"0.1.0\"\n"
            "requires-python = \">=3.10\"\ndependencies = [\"flet==1.1.2\"]\n\n"
            "[tool.flet]\nproduct = \"My Android App\"\norg = \"com.example.myandroidapp\"\n\n"
            "[tool.flet.app]\npath = \"src\"\n"
        ),
        "requirements.txt": "flet==1.1.2\n",
        ".github/workflows/build-apk.yml": (
            "name: Build Android APK\n\non:\n  workflow_dispatch:\n  push:\n    branches: [main]\n\n"
            "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Build APK\n        id: build\n        uses: flet-dev/flet-build-action@v1\n"
            "        with:\n          target: apk\n          runner-python-version: '3.12'\n"
            "          bundled-python-version: '3.12'\n          build-version: '0.1.0'\n"
            "          build-number: \${{ github.run_number }}\n"
            "      - uses: actions/upload-artifact@v4\n        with:\n          name: android-apk\n"
            "          path: \${{ steps.build.outputs.archive-path }}\n          if-no-files-found: error\n"
        ),
        "README.md": "# Flet Android App\n\nUpload this project to GitHub, run Build Android APK from Actions, then download the android-apk artifact.\n",
    },
    "Unit Testing Starter": {
        "main.py": (
            "def add(first: int, second: int) -> int:\n"
            "    return first + second\n\n"
            "if __name__ == '__main__':\n"
            "    print(add(2, 3))\n"
        ),
        "tests/test_main.py": (
            "import unittest\n"
            "from main import add\n\n"
            "class AddTests(unittest.TestCase):\n"
            "    def test_adds_two_numbers(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "README.md": "# Unit Testing Starter\n\nA small project with a unittest example.\n",
    },
}
