"""Generate a Python module containing the project's bundled skills for static Flet web."""
from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skills_manager import SkillsManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
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
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        '"""Generated from src/agent_skills; do not edit by hand."""' + chr(10)
        + "SKILL_CATALOG = "
        + pprint.pformat(catalog, width=100, sort_dicts=True)
        + chr(10),
        encoding="utf-8",
    )
    print(f"Generated {len(catalog)} skill references at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
