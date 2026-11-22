"""Offline project inspection helpers for AI Python Studio.

These checks are heuristic and intentionally dependency-free. They do not
execute project code and must not be presented as a full security audit.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from workspace import WorkspaceError, WorkspaceStore

_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?token)\b\s*[:=]\s*(['\"])(.{8,}?)\2"
)
_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX)\b", re.IGNORECASE)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class _QualityDiagnostics(ast.NodeVisitor):
    """Focused maintainability checks that require no third-party linter."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.diagnostics: list[dict[str, Any]] = []
        self.branch_points = 0

    def add(self, severity: str, code: str, node: ast.AST, message: str) -> None:
        self.diagnostics.append({
            "severity": severity, "code": code, "file": self.filename,
            "line": getattr(node, "lineno", 1), "message": message,
        })

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        defaults = [None] * (len(node.args.args) - len(node.args.defaults))
        defaults.extend(node.args.defaults)
        defaults.extend(item for item in node.args.kw_defaults if item is not None)
        for value in defaults:
            if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                self.add(
                    "warning", "MUTABLE_DEFAULT", value,
                    "القيمة الافتراضية قابلة للتغيير؛ استخدم None وأنشئ القيمة داخل الدالة.",
                )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(
                "warning", "BARE_EXCEPT", node,
                "استخدم نوع استثناء محدداً بدلاً من except المجرد.",
            )
        body = [item for item in node.body if not (
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
        )]
        if len(body) == 1 and isinstance(body[0], ast.Pass):
            self.add(
                "warning", "SILENT_EXCEPTION", node,
                "يتم تجاهل الاستثناء بصمت؛ سجّل الخطأ أو عالجه صراحة.",
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == "*" for alias in node.names):
            self.add(
                "info", "WILDCARD_IMPORT", node,
                "الاستيراد الشامل (*) يجعل مصدر الأسماء أقل وضوحاً.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        http_methods = {
            "requests.get", "requests.post", "requests.put", "requests.delete",
            "requests.patch", "httpx.get", "httpx.post", "httpx.put",
            "httpx.delete", "httpx.patch",
        }
        if name in http_methods and not any(
            keyword.arg == "timeout" for keyword in node.keywords
        ):
            self.add(
                "warning", "HTTP_NO_TIMEOUT", node,
                "أضف timeout لطلبات HTTP حتى لا يظل التطبيق منتظراً بلا حد زمني.",
            )
        self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (
            ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.IfExp,
        )):
            self.branch_points += 1
        super().generic_visit(node)


def inspect_python_source(source: str, filename: str) -> dict[str, Any]:
    """Return syntax, structure and heuristic security diagnostics for Python."""
    diagnostics: list[dict[str, Any]] = []
    lines = source.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if len(line) > 120:
            diagnostics.append({
                "severity": "info", "code": "LONG_LINE", "file": filename,
                "line": line_number, "message": "السطر أطول من 120 حرفاً.",
            })
        if _SECRET_PATTERN.search(line):
            diagnostics.append({
                "severity": "warning", "code": "POSSIBLE_SECRET", "file": filename,
                "line": line_number,
                "message": "قد يحتوي هذا السطر على كلمة مرور أو مفتاح سري مكتوب مباشرة.",
            })
        todo = _TODO_PATTERN.search(line)
        if todo:
            diagnostics.append({
                "severity": "info", "code": todo.group(1).upper(), "file": filename,
                "line": line_number,
                "message": f"عنصر عمل معلّق: {line.strip()[:100]}",
            })

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        diagnostics.append({
            "severity": "error", "code": "SYNTAX_ERROR", "file": filename,
            "line": exc.lineno or 1,
            "message": f"خطأ نحوي: {exc.msg or 'صياغة غير صحيحة'}.",
        })
        return {
            "diagnostics": diagnostics,
            "functions": 0,
            "classes": 0,
            "imports": 0,
            "valid_syntax": False,
        }

    functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    imports = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        severity = None
        code = ""
        message = ""
        if name in {"eval", "exec"}:
            severity, code = "warning", "DYNAMIC_EXECUTION"
            message = "تنفيذ نص ديناميكي قد يسمح بتشغيل تعليمات غير موثوقة."
        elif name in {"os.system", "os.popen"}:
            severity, code = "warning", "SHELL_COMMAND"
            message = "استدعاء أوامر النظام مباشرة يحتاج إلى تحقق صارم من المدخلات."
        elif name in {"subprocess.run", "subprocess.call", "subprocess.Popen"}:
            shell_true = any(
                keyword.arg == "shell" and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
            if shell_true:
                severity, code = "warning", "SHELL_TRUE"
                message = "استخدام shell=True قد يسبب حقن أوامر عند تمرير مدخلات خارجية."
        elif name in {"pickle.load", "pickle.loads"}:
            severity, code = "warning", "UNSAFE_PICKLE"
            message = "لا تحمّل بيانات pickle من مصدر غير موثوق؛ قد تنفذ شيفرة."
        elif name == "yaml.load":
            has_loader = any(keyword.arg == "Loader" for keyword in node.keywords)
            if not has_loader:
                severity, code = "warning", "YAML_LOADER"
                message = "حدد Loader آمناً عند استخدام yaml.load أو استخدم safe_load."
        if severity:
            diagnostics.append({
                "severity": severity, "code": code, "file": filename,
                "line": getattr(node, "lineno", 1), "message": message,
            })

    quality = _QualityDiagnostics(filename)
    quality.visit(tree)
    diagnostics.extend(quality.diagnostics)

    return {
        "diagnostics": diagnostics,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "branch_points": quality.branch_points,
        "valid_syntax": True,
    }


def analyze_project(store: WorkspaceStore, project_id: str) -> dict[str, Any]:
    """Analyze the project without importing or executing any project files."""
    files = store.list_files(project_id)
    assets = store.list_assets(project_id)
    folders = store.list_folders(project_id)
    python_files = [name for name in files if Path(name).suffix.lower() in {".py", ".pyw"}]
    diagnostics: list[dict[str, Any]] = []
    total_lines = total_bytes = functions = classes = imports = todo_count = 0
    branch_points = 0

    for filename in python_files:
        try:
            source = store.read_file(project_id, filename)
        except WorkspaceError:
            continue
        total_lines += len(source.splitlines())
        total_bytes += len(source.encode("utf-8"))
        todo_count += len(_TODO_PATTERN.findall(source))
        result = inspect_python_source(source, filename)
        diagnostics.extend(result["diagnostics"])
        functions += result["functions"]
        classes += result["classes"]
        imports += result["imports"]
        branch_points += result.get("branch_points", 0)

    requirement_files = [name for name in files if Path(name).name.lower() == "requirements.txt"]
    dependency_count = 0
    for filename in requirement_files:
        try:
            dependency_count += sum(
                1 for line in store.read_file(project_id, filename).splitlines()
                if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("-")
            )
        except WorkspaceError:
            pass

    diagnostics.sort(key=lambda item: (
        {"error": 0, "warning": 1, "info": 2}.get(item["severity"], 3),
        item["file"].casefold(), item["line"],
    ))
    severity_counts = {
        level: sum(item["severity"] == level for item in diagnostics)
        for level in ("error", "warning", "info")
    }
    quality_score = max(
        0,
        100
        - severity_counts["error"] * 20
        - severity_counts["warning"] * 8
        - severity_counts["info"] * 2,
    )

    recommendations: list[str] = []
    if not any(Path(name).name.lower() in {"readme.md", "readme"} for name in files):
        recommendations.append("أضف README.md لوصف المشروع وطريقة تشغيله.")
    if python_files and not any("test" in Path(name).parts for name in python_files):
        recommendations.append("أضف مجلد tests واكتب اختبارات للوظائف الأساسية.")
    if any(item["severity"] == "error" for item in diagnostics):
        recommendations.append("أصلح الأخطاء النحوية قبل تشغيل المشروع.")
    if not requirement_files:
        recommendations.append("أنشئ requirements.txt عند استخدام مكتبات خارجية.")
    if severity_counts["warning"]:
        recommendations.append("راجع التحذيرات الأمنية وجودة الكود قبل مشاركة المشروع.")

    return {
        "metrics": {
            "files": len(files), "python_files": len(python_files),
            "folders": len(folders), "assets": len(assets),
            "python_lines": total_lines, "python_bytes": total_bytes,
            "functions": functions, "classes": classes, "imports": imports,
            "branch_points": branch_points,
            "todos": todo_count, "dependencies": dependency_count,
        },
        "diagnostics": diagnostics,
        "severity_counts": severity_counts,
        "quality_score": quality_score,
        "recommendations": recommendations,
        "valid_syntax": not any(item["severity"] == "error" for item in diagnostics),
    }


def format_analysis_report(project_name: str, report: dict[str, Any]) -> str:
    """Build a readable plain-text report suitable for the output panel."""
    metrics = report["metrics"]
    lines = [
        f"تقرير فحص المشروع: {project_name}",
        "=" * 42,
        f"الملفات: {metrics['files']} | ملفات Python: {metrics['python_files']} | المجلدات: {metrics['folders']}",
        f"أسطر Python: {metrics['python_lines']} | الدوال: {metrics['functions']} | الأصناف: {metrics['classes']}",
        f"عمليات الاستيراد: {metrics['imports']} | نقاط التفرع: {metrics.get('branch_points', 0)}",
        f"المهام TODO/FIXME: {metrics['todos']} | الاعتماديات: {metrics['dependencies']}",
        f"مؤشر جودة إرشادي: {report.get('quality_score', 'غير متاح')}/100",
        "",
        f"نتيجة الصياغة: {'سليمة' if report['valid_syntax'] else 'تحتاج إلى إصلاح'}",
        (
            f"الأخطاء: {report.get('severity_counts', {}).get('error', 0)} | "
            f"التحذيرات: {report.get('severity_counts', {}).get('warning', 0)} | "
            f"المعلومات: {report.get('severity_counts', {}).get('info', 0)}"
        ),
    ]
    for item in report["diagnostics"]:
        lines.append(
            f"[{item['severity'].upper()}] {item['file']}:{item['line']} — {item['message']}"
        )
    if report["recommendations"]:
        lines.extend(["", "اقتراحات التحسين:"])
        lines.extend(f"- {item}" for item in report["recommendations"])
    lines.extend([
        "", "ملاحظة: هذا فحص ثابت مبدئي، وليس تدقيقاً أمنياً كاملاً، ولا يشغّل ملفات المشروع."
    ])
    return "\n".join(lines)
