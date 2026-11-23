"""Validated Python package management helpers.

The manager intentionally accepts package names and version constraints only.
It does not accept pip options, URLs, editable installs or requirements includes.
"""
from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys

MAX_REQUIREMENTS_CHARS = 64 * 1024
MAX_REQUIREMENTS_LINES = 100
MAX_PACKAGE_SPEC_CHARS = 200
MIN_INSTALL_TIMEOUT = 5
MAX_INSTALL_TIMEOUT = 600

_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:\[[A-Za-z0-9_,.-]+\])?"
    r"(?:\s*(?:===|==|~=|!=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)?$"
)


class PackageManagerError(RuntimeError):
    """A safe, user-displayable package manager failure."""


def _validate_package(package: str, *, line_number: int | None = None) -> str:
    if not isinstance(package, str):
        raise PackageManagerError("اسم المكتبة يجب أن يكون نصاً.")
    value = package.strip()
    location = f" عند السطر {line_number}" if line_number is not None else ""
    if (
        not value
        or len(value) > MAX_PACKAGE_SPEC_CHARS
        or not _PACKAGE.fullmatch(value)
    ):
        raise PackageManagerError(
            f"صيغة اسم المكتبة غير مدعومة{location}."
        )
    return value


def parse_requirements(source: str) -> list[str]:
    """Parse a deliberately small, safe subset of requirements.txt."""
    if not isinstance(source, str):
        raise PackageManagerError("محتوى requirements.txt غير صالح.")
    if len(source) > MAX_REQUIREMENTS_CHARS:
        raise PackageManagerError("ملف requirements.txt أكبر من 64 كيلوبايت.")
    packages: list[str] = []
    for number, raw in enumerate(source.splitlines(), 1):
        if number > MAX_REQUIREMENTS_LINES:
            raise PackageManagerError("ملف requirements.txt يتجاوز 100 سطر.")
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].strip()
        packages.append(_validate_package(line, line_number=number))
    if len(packages) > MAX_REQUIREMENTS_LINES:
        raise PackageManagerError("عدد المكتبات يتجاوز الحد المسموح.")
    return packages


def list_installed() -> list[tuple[str, str]]:
    items = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name") or "unknown"
        items.append((name, dist.version or ""))
    return sorted(set(items), key=lambda item: item[0].casefold())


def install_packages(packages: list[str], timeout: int = 180) -> str:
    """Install a bounded list of validated package specs using the active Python."""
    if not isinstance(packages, list) or not packages:
        raise PackageManagerError("لم يتم العثور على مكتبات للتثبيت.")
    if len(packages) > MAX_REQUIREMENTS_LINES:
        raise PackageManagerError("عدد المكتبات يتجاوز 100 مكتبة.")
    validated = [_validate_package(item) for item in packages]

    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise PackageManagerError("مهلة التثبيت يجب أن تكون عدداً صحيحاً.")
    timeout = max(MIN_INSTALL_TIMEOUT, min(timeout, MAX_INSTALL_TIMEOUT))

    command = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--no-input", *validated,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PackageManagerError(
            f"انتهت مهلة التثبيت بعد {timeout} ثانية."
        ) from exc
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise PackageManagerError(
            "تعذر تشغيل pip في بيئة Python الحالية."
        ) from exc

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode:
        raise PackageManagerError(
            output[-12000:] or f"فشل pip برمز {result.returncode}."
        )
    return output[-12000:] or "اكتمل التثبيت بنجاح."
