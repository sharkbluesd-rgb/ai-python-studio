"""Copy the responsive Flet APK Studio preview into a deployable directory."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("index.html", "style.css", "app.js")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    source = ROOT / "web-preview-static"
    missing = [name for name in ASSETS if not (source / name).is_file()]
    if missing:
        raise SystemExit("Preview assets are missing: " + ", ".join(missing))
    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copy2(source / name, output / name)
    print("Built the responsive Flet APK Studio preview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
