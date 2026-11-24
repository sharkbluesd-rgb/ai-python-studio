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

test("ZIP preflight rejects a file used as a parent directory", () => {
  const archive = zipSync({
    "src": strToU8("not a folder"),
    "src/main.py": strToU8("print(1)"),
  });
  assert.throws(() => inspectZipArchive(archive), /تعارض/);
});

test("ZIP preflight verifies local filenames match central directory names", () => {
  const archive = zipSync({ "main.py": strToU8("print(1)") });
  const bytes = new Uint8Array(archive);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let centralOffset = -1;
  let localNameOffset = -1;
  for (let index = 0; index <= bytes.length - 4; index += 1) {
    const signature = view.getUint32(index, true);
    if (signature === 0x04034b50 && localNameOffset < 0) {
      localNameOffset = index + 30;
    }
    if (signature === 0x02014b50) {
      centralOffset = index;
      break;
    }
  }
  assert.ok(localNameOffset > 0 && centralOffset > 0);
  bytes[localNameOffset] ^= 1;
  assert.throws(() => inspectZipArchive(bytes), /اسم الملف المحلي/);
});