"""Local Python runner for trusted scripts, plus static syntax validation.

IMPORTANT: execution uses ``exec`` in the app process. This is not a sandbox
and is not safe for untrusted code. Cancellation is cooperative: Python line
events are checked, but native extensions and blocking calls may not stop.
"""

from __future__ import annotations

import ast
import contextlib
import io
import os
import sys
import threading
import traceback
import time
from collections.abc import Callable
from pathlib import Path


_RUN_LOCK = threading.RLock()


class ExecutionCancelled(Exception):
    """Raised when the user requests execution cancellation."""


class ExecutionTimedOut(Exception):
    """Raised when the execution time limit is reached."""


class ExecutionControl:
    """Cooperative cancellation and timeout for Python execution."""

    def __init__(self, timeout_seconds: float | None = 60):
        self._cancelled = threading.Event()
        self._deadline = (
            time.monotonic() + timeout_seconds
            if timeout_seconds is not None else None
        )

    def cancel(self) -> None:
        self._cancelled.set()

    def check(self) -> None:
        if self._cancelled.is_set():
            self._cancelled.clear()
            raise ExecutionCancelled()
        if self._deadline is not None and time.monotonic() >= self._deadline:
            self._deadline = None
            raise ExecutionTimedOut()


class _OutputCapture(io.StringIO):
    """Capture output and optionally forward each written chunk."""

    def __init__(self, callback: Callable[[str], None] | None = None):
        super().__init__()
        self.callback = callback

    def write(self, value: str) -> int:
        written = super().write(value)
        if value and self.callback is not None:
            try:
                self.callback(value)
            except Exception:
                pass
        return written




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


def execute_unittest_discovery(
    project_root: str,
    tests_dir: str = "tests",
    pattern: str = "test*.py",
    output_callback: Callable[[str], None] | None = None,
    control: ExecutionControl | None = None,
) -> tuple[str, bool]:
    """Discover and run a project's unittest suite from its project directory.

    Only relative test directories are accepted. Test code is still trusted
    code and runs in the app process through the same cooperative controls.
    """
    from pathlib import PurePath

    relative = PurePath(tests_dir)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        return "مسار مجلد الاختبارات غير صالح.", False
    if not isinstance(pattern, str) or not pattern or "/" in pattern or "\\\\" in pattern:
        return "نمط أسماء ملفات الاختبار غير صالح.", False

    root = Path(project_root).expanduser().resolve()
    test_root = (root / relative).resolve()
    try:
        test_root.relative_to(root)
    except ValueError:
        return "مجلد الاختبارات يجب أن يكون داخل المشروع.", False
    if not test_root.is_dir():
        return f"لم يتم العثور على مجلد الاختبارات: {tests_dir}", False

    script = (
        "import sys, unittest\\n"
        "from pathlib import Path\\n"
        f"test_root = Path({str(test_root)!r})\\n"
        f"project_root = Path({str(root)!r})\\n"
        f"pattern = {pattern!r}\\n"
        "suite = unittest.defaultTestLoader.discover(\\n"
        "    start_dir=str(test_root), pattern=pattern, top_level_dir=str(project_root)\\n"
        ")\\n"
        "count = suite.countTestCases()\\n"
        "if count == 0:\\n"
        "    print('لم يتم العثور على اختبارات مطابقة.')\\n"
        "    raise RuntimeError('No tests were discovered')\\n"
        "print(f'عدد الاختبارات المكتشفة: {count}')\\n"
        "result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)\\n"
        "print(f'النتيجة: {result.testsRun} اختبار، {len(result.failures)} فشل، "
        "{len(result.errors)} خطأ')\\n"
    )
    synthetic_file = root / "__ai_python_studio_test_runner__.py"
    output, executed = execute_python(
        script,
        str(synthetic_file),
        project_root=str(root),
        output_callback=output_callback,
        control=control,
    )
    if not executed:
        return output, False
    failed = "FAILED (" in output or "No tests were discovered" in output
    return output, not failed


def execute_python(
    code: str,
    file_path: str,
    project_root: str | None = None,
    output_callback: Callable[[str], None] | None = None,
    control: ExecutionControl | None = None,
) -> tuple[str, bool]:
    """Run a trusted script and return ``(captured_output, succeeded)``.

    This serializes app executions because stdout/stderr redirection,
    ``sys.path`` and the working directory are process-global. It does not
    sandbox code. Cancellation checks Python line events but may not interrupt
    native extensions or blocking third-party calls.
    """
    valid, syntax_message = check_python(code, file_path)
    if not valid:
        if output_callback is not None:
            output_callback(syntax_message + "\\n")
        return syntax_message, False

    stdout = _OutputCapture(output_callback)
    stderr = _OutputCapture(output_callback)
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
        original_trace = sys.gettrace()
        original_cwd = os.getcwd()

        def execution_trace(frame, event, arg):
            if control is not None and event == "line":
                control.check()
            return execution_trace

        try:
            os.chdir(project_dir)
            for candidate in (project_dir, script_dir):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                    added_paths.append(candidate)
            sys.argv = [str(script_path)]
            if control is not None:
                sys.settrace(execution_trace)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compile(code, str(script_path), "exec"), namespace, namespace)
            output = stdout.getvalue()
            error_output = stderr.getvalue()
            if error_output:
                output += ("\n" if output else "") + error_output
            return output or "تم التنفيذ بنجاح — لا يوجد إخراج.", True
        except ExecutionCancelled:
            return "تم إيقاف التنفيذ بطلب المستخدم.", False
        except ExecutionTimedOut:
            return "انتهت مهلة التنفيذ (60 ثانية).", False
        except BaseException:
            output = stdout.getvalue()
            error_output = stderr.getvalue()
            details = traceback.format_exc()
            if output_callback is not None:
                try:
                    output_callback(details)
                except Exception:
                    pass
            combined = output
            if error_output:
                combined += ("\n" if combined else "") + error_output
            combined += ("\n" if combined else "") + details
            return combined, False
        finally:
            try:
                os.chdir(original_cwd)
            except OSError:
                # Do not mask the original script result if the old folder
                # was removed by trusted project code while it was running.
                pass
            sys.settrace(original_trace)
            sys.argv = original_argv
            sys.path[:] = original_sys_path
