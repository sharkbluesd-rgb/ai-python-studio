import test from "node:test";
import assert from "node:assert/strict";
import { isPythonSourcePath, suggestedDuplicatePath } from "../src/file-utils.js";

test("Python file detection accepts .py and .pyw case-insensitively", () => {
  for (const path of ["main.py", "main.pyw", "src/app.PY", "src/app.PyW"]) {
    assert.equal(isPythonSourcePath(path), true, path);
  }
  for (const path of ["main.txt", "mainpy", "main.py.txt", "", null]) {
    assert.equal(isPythonSourcePath(path), false, String(path));
  }
});

test("duplicate suggestions preserve parent directories and extensions", () => {
  assert.equal(suggestedDuplicatePath("main.py"), "main_copy.py");
  assert.equal(suggestedDuplicatePath("src/helpers.pyw"), "src/helpers_copy.pyw");
  assert.equal(suggestedDuplicatePath("notes.txt"), "notes_copy.txt");
  assert.equal(suggestedDuplicatePath("main.py.backup"), "main.py.backup_copy");
});
