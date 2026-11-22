"""Validation and safe configuration helpers for Flet Android projects."""
from __future__ import annotations

import json
import re
from pathlib import Path

_APP_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_BUILD = re.compile(r"^[1-9]\d*$")


def validate_application_id(value: str) -> str:
    value = value.strip()
    if not _APP_ID.fullmatch(value):
        raise ValueError(
            "معرّف التطبيق غير صالح. استخدم أجزاء صغيرة بحروف إنجليزية وأرقام وشرطة سفلية، "
            "مثل com.example.myapp."
        )
    if len(value) > 255 or any(len(part) > 63 for part in value.split(".")):
        raise ValueError("معرّف التطبيق أطول من الحد المسموح.")
    return value


def _replace_key(text: str, section: str, key: str, value: str) -> str:
    section_pattern = re.compile(
        rf"(?ms)(^\[{re.escape(section)}\]\s*\n)(.*?)(?=^\[|\Z)"
    )
    match = section_pattern.search(text)
    if not match:
        raise ValueError(f"ملف pyproject.toml لا يحتوي القسم [{section}].")
    body = match.group(2)
    line = f"{key} = {json.dumps(value, ensure_ascii=False)}"
    key_pattern = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
    if key_pattern.search(body):
        body = key_pattern.sub(line, body, count=1)
    else:
        body = body.rstrip() + "\n" + line + "\n"
    return text[:match.start(2)] + body + text[match.end(2):]


def configure_flet_project(
    project_path: str | Path,
    *,
    app_name: str,
    application_id: str,
    version: str,
    build_number: str,
) -> str:
    root = Path(project_path)
    config = root / "pyproject.toml"
    if not config.is_file():
        raise ValueError("هذا المشروع لا يحتوي pyproject.toml. أنشئه باستخدام قالب Flet Android أولاً.")
    app_name = app_name.strip()
    if not app_name or len(app_name) > 60 or any(ord(ch) < 32 for ch in app_name):
        raise ValueError("اسم التطبيق مطلوب ويجب ألا يتجاوز 60 حرفاً.")
    application_id = validate_application_id(application_id)
    version = version.strip()
    if not _VERSION.fullmatch(version):
        raise ValueError("صيغة الإصدار غير صحيحة. استخدم مثلاً 1.0.0.")
    build_number = build_number.strip()
    if not _BUILD.fullmatch(build_number):
        raise ValueError("رقم البناء يجب أن يكون عدداً صحيحاً موجباً.")
    original = config.read_text(encoding="utf-8")
    updated = original
    updated = _replace_key(updated, "project", "version", version)
    updated = _replace_key(updated, "tool.flet", "product", app_name)
    updated = _replace_key(updated, "tool.flet", "org", application_id)
    # The workflow consumes this value; keep it explicit and deterministic.
    workflow = root / ".github" / "workflows" / "build-apk.yml"
    if workflow.is_file():
        content = workflow.read_text(encoding="utf-8")
        content = re.sub(
            r"(?m)^(\s*build-version:\s*)['\"][^'\"]*['\"]\s*$",
            lambda m: m.group(1) + "'" + version + "'",
            content,
        )
        content = re.sub(
            r"(?m)^(\s*build-number:\s*).*$",
            lambda m: m.group(1) + build_number,
            content,
        )
        workflow.write_text(content, encoding="utf-8")
    config.write_text(updated, encoding="utf-8")
    return f"الإصدار {version} · البناء {build_number} · {application_id}"


def validate_flet_project(project_path: str | Path) -> list[str]:
    root = Path(project_path)
    issues: list[str] = []
    config = root / "pyproject.toml"
    if not config.is_file():
        return ["ملف pyproject.toml غير موجود."]
    content = config.read_text(encoding="utf-8")
    required = {
        "project": r"(?m)^\[project\]\s*$",
        "Flet configuration": r"(?m)^\[tool\.flet\]\s*$",
        "Flet app path": r"(?m)^\[tool\.flet\.app\]\s*$",
    }
    for label, pattern in required.items():
        if not re.search(pattern, content):
            issues.append(f"قسم {label} مفقود من pyproject.toml.")
    try:
        app_id_match = re.search(r'(?m)^org\s*=\s*"([^"]+)"', content)
        if not app_id_match:
            issues.append("معرّف تطبيق Android (org) غير موجود.")
        else:
            validate_application_id(app_id_match.group(1))
    except ValueError as exc:
        issues.append(str(exc))
    if not (root / "src" / "main.py").is_file():
        issues.append("ملف src/main.py غير موجود.")
    workflow = root / ".github" / "workflows" / "build-apk.yml"
    if not workflow.is_file():
        issues.append("ملف GitHub Actions لبناء APK غير موجود.")
    elif "flet-dev/flet-build-action" not in workflow.read_text(encoding="utf-8"):
        issues.append("إعداد بناء Flet غير موجود في workflow.")
    return issues
