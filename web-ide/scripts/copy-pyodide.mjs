import { cp, mkdir, stat } from "node:fs/promises";
import { resolve } from "node:path";

const source = resolve("node_modules/pyodide");
const destination = resolve("dist/pyodide");
try {
  await stat(source);
} catch {
  throw new Error("Pyodide npm package was not installed.");
}
await mkdir(destination, { recursive: true });
await cp(source, destination, { recursive: true });
for (const required of ["pyodide.js", "pyodide.asm.wasm", "pyodide-lock.json", "python_stdlib.zip"]) {
  try {
    await stat(resolve(destination, required));
  } catch {
    throw new Error("Required Pyodide runtime file is missing: " + required);
  }
}
console.log("Copied the pinned Pyodide runtime into dist/pyodide.");