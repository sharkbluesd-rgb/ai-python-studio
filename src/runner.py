"""Local Python runner for trusted scripts, plus static syntax validation.

IMPORTANT: execution uses ``exec`` in the app process. This is not a sandbox,
not safe for untrusted code, and cannot reliably stop an infinite loop.
"""

from __future__ import annotations

import ast
import contextlib
import io
import sys
import threading
import traceback
from pathlib import Path


_RUN_LOCK = threading.RLock()


def check_python(code: str, file_path: str = "main.py") -> tuple[bool, str]:
    """Parse Python source without executing it."""
    if not isinstance(code, str):
        return False, "محتوى الكود غير صالح."
    try:
        ast.parse(code, filename=file_path)
        compile(code, file_path, "exec")
        return True, "لا توجد أخطاء نحوية في الكود."
    except SyntaxError as exc:
        location = f"السطر {exc.lineno or '?'}، العمود {exc.offset or '?'}"
        details = exc.msg or "SyntaxError"
        return False, f"خطأ نحوي في {location}: {details}"


def execute_python(
    code: str,
    file_path: str,
    project_root: str | None = None,
) -> tuple[str, bool]:
    """Run a trusted script and return ``(captured_output, succeeded)``.

    This serializes app executions because stdout/stderr redirection and
    ``sys.path`` are process-global. It does not sandbox or time-limit code.
    """
    valid, syntax_message = check_python(code, file_path)
    if not valid:
        return syntax_message, False

    stdout = io.StringIO()
    stderr = io.StringIO()
    script_path = Path(file_path).expanduser().resolve()
    script_dir = str(script_path.parent)
    project_dir = str(Path(project_root).expanduser().resolve()) if project_root else script_dir
    added_paths: list[str] = []
    namespace = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__package__": None,
    }

    with _RUN_LOCK:
        original_argv = sys.argv[:]
        original_sys_path = sys.path[:]
        try:
            for candidate in (project_dir, script_dir):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                    added_paths.append(candidate)
            sys.argv = [str(script_path)]
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compile(code, str(script_path), "exec"), namespace, namespace)
            output = stdout.getvalue()
            error_output = stderr.getvalue()
            if error_output:
                output += ("\n" if output else "") + error_output
            return output or "تم التنفيذ بنجاح — لا يوجد إخراج.", True
        except BaseException:
            output = stdout.getvalue()
            error_output = stderr.getvalue()
            details = traceback.format_exc()
            combined = output
            if error_output:
                combined += ("\n" if combined else "") + error_output
            combined += ("\n" if combined else "") + details
            return combined, False
        finally:
            sys.argv = original_argv
            sys.path[:] = original_sys_path
