"""Local Python code runner for trusted scripts (not a security sandbox)."""

from __future__ import annotations

import contextlib
import io
import sys
import traceback
from pathlib import Path


def execute_python(code: str, file_path: str) -> tuple[str, bool]:
    """Run a script and return ``(captured_output, succeeded)``.

    This uses exec in the current app process. Output redirection is process-wide
    while the script runs, so the UI must allow only one script at a time. Do not
    use this for untrusted code; it is not isolated or time-limited.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    project_dir = str(Path(file_path).resolve().parent)
    added_to_path = project_dir not in sys.path
    if added_to_path:
        sys.path.insert(0, project_dir)

    namespace = {"__name__": "__main__", "__file__": file_path}
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compile(code, file_path, "exec"), namespace, namespace)
        result = stdout.getvalue()
        error_text = stderr.getvalue()
        if error_text:
            result += ("\n" if result else "") + error_text
        return (result or "تم التنفيذ بنجاح — لا يوجد إخراج."), True
    except BaseException:
        result = stdout.getvalue()
        error_text = stderr.getvalue()
        details = traceback.format_exc()
        combined = result
        if error_text:
            combined += ("\n" if combined else "") + error_text
        combined += ("\n" if combined else "") + details
        return combined, False
    finally:
        if added_to_path:
            try:
                sys.path.remove(project_dir)
            except ValueError:
                pass
