"""Build a dependency-light static browser preview and export real skill references."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    source = ROOT / "web-preview-static"
    if not (source / "index.html").is_file():
        raise SystemExit("Static preview source is missing.")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "style.css", "app.js"):
        shutil.copy2(source / name, output / name)

    from skills_manager import SkillsManager

    manager = SkillsManager(ROOT / "src" / "agent_skills")
    catalog = []
    for summary in manager.list_skills():
        doc = manager.get_skill(summary.name)
        catalog.append({
            "name": summary.name,
            "label_ar": summary.label_ar,
            "category": summary.category,
            "description": summary.description,
            "content": doc.content,
        })
    if len(catalog) < 20:
        raise SystemExit(f"Expected at least 20 skills, found {len(catalog)}.")
    (output / "skills.json").write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built static preview with {len(catalog)} real skill documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
