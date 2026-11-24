import test from "node:test";
import assert from "node:assert/strict";
import { strToU8, zipSync } from "fflate";
import { inspectZipArchive } from "../src/zip-safety.js";

test("ZIP preflight accepts a normal nested Python project", () => {
  const archive = zipSync({
    "src/main.py": strToU8("print('hello')\n"),
    "src/helpers.py": strToU8("VALUE = 42\n"),
  });
  const entries = inspectZipArchive(archive);
  assert.deepEqual(entries.map((entry) => entry.path).sort(), ["src/helpers.py", "src/main.py"]);
  assert.ok(entries.every((entry) => !entry.isDirectory));
});

test("ZIP preflight rejects path traversal before extraction", () => {
  const archive = zipSync({ "../outside.py": strToU8("print('bad')") });
  assert.throws(() => inspectZipArchive(archive), /مسار|غير صالح|غير مسموح/);
});

test("ZIP preflight rejects oversized expanded files", () => {
  const archive = zipSync({ "large.py": strToU8("x".repeat(512 * 1024 + 1)) });
  assert.throws(() => inspectZipArchive(archive), /512 KB/);
});

test("ZIP preflight rejects encrypted members", () => {
  const archive = zipSync({ "main.py": strToU8("print(1)") });
  const bytes = new Uint8Array(archive);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let index = 0; index < bytes.length - 4; index += 1) {
    if (view.getUint32(index, true) === 0x02014b50) {
      view.setUint16(index + 8, view.getUint16(index + 8, true) | 1, true);
      break;
    }
  }
  assert.throws(() => inspectZipArchive(bytes), /مشفرة/);
});