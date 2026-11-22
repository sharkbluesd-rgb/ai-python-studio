"""Python package management helpers."""
from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys

_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:\[[A-Za-z0-9_,.-]+\])?"
    r"(?:\s*(?:===|==|~=|!=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)?$"
)

class PackageManagerError(RuntimeError):
    pass

def parse_requirements(source: str) -> list[str]:
    packages = []
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].strip()
        if not _PACKAGE.fullmatch(line):
            raise PackageManagerError(
                f"صيغة غير مدعومة في requirements.txt عند السطر {number}: {line}"
            )
        packages.append(line)
    return packages

def list_installed() -> list[tuple[str, str]]:
    items = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name") or "unknown"
        items.append((name, dist.version or ""))
    return sorted(set(items), key=lambda item: item[0].casefold())

def install_packages(packages: list[str], timeout: int = 180) -> str:
    if not packages:
        raise PackageManagerError("لم يتم العثور على مكتبات للتثبيت.")
    for package in packages:
        if not isinstance(package, str) or not _PACKAGE.fullmatch(package.strip()):
            raise PackageManagerError(f"اسم مكتبة غير صالح: {package!r}")
    command = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--no-input", *packages,
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
    except (OSError, subprocess.SubprocessError) as exc:
        raise PackageManagerError(
            f"تعذر تشغيل pip في بيئة Python الحالية: {exc}"
        ) from exc

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode:
        raise PackageManagerError(
            output[-12000:] or f"فشل pip برمز {result.returncode}."
        )
    return output[-12000:] or "اكتمل التثبيت بنجاح."
