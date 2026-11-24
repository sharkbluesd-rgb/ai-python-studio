import "fake-indexeddb/auto";
import test from "node:test";
import assert from "node:assert/strict";
import {
  createProject, deleteProject, getProject, normalizeProjectPath,
  saveProject, validateTextFile,
} from "../src/storage.js";

test("IndexedDB stores project files and restores them after a fresh read", async () => {
  const project = await createProject("Persistence test");
  project.files["src/app.py"] = "print('saved')\n";
  await saveProject(project);

  const restored = await getProject(project.id);
  assert.equal(restored.name, "Persistence test");
  assert.equal(restored.files["src/app.py"], "print('saved')\n");
  await deleteProject(project.id);
  assert.equal(await getProject(project.id), null);
});

test("project paths reject traversal, absolute paths and unsupported extensions", () => {
  assert.equal(normalizeProjectPath("src/main.py"), "src/main.py");
  assert.throws(() => normalizeProjectPath("../outside.py"), /غير مسموح/);
  assert.throws(() => normalizeProjectPath("/etc/passwd"), /غير صالح/);
  assert.throws(() => validateTextFile("payload.exe", "bad"), /غير مدعوم/);
  assert.throws(() => validateTextFile("large.py", "x".repeat(512 * 1024 + 1)), /512 KB/);
});