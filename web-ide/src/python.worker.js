import { loadPyodide, version as pyodideVersion } from "pyodide";

let pyodide = null;
let inputControl = null;
let inputBytes = null;
let interruptView = null;
let pendingInput = new Uint8Array(0);
let pendingOffset = 0;
let inputEnabled = false;
let activeRunId = null;
let outputChars = 0;
let outputTruncated = false;
const MAX_OUTPUT_CHARS_PER_RUN = 250000;

function send(type, payload = {}) { self.postMessage({ type, ...payload }); }
function sendLimitedOutput(type, text) {
  const value = String(text);
  const remaining = Math.max(0, MAX_OUTPUT_CHARS_PER_RUN - outputChars);
  if (remaining > 0) {
    const chunk = value.slice(0, remaining);
    if (chunk) send(type, { text: chunk });
    outputChars += chunk.length;
  }
  if (value.length > remaining && !outputTruncated) {
    outputTruncated = true;
    send(type, { text: "\n[تم اختصار مخرجات Python بعد بلوغ الحد الآمن]\n" });
  }
}

function setProjectFiles(files, activeFile) {
  const root = "/home/pyodide/project";
  pyodide.runPython("import os, shutil\nos.chdir('/home/pyodide')\nshutil.rmtree('project', ignore_errors=True)\nos.makedirs('project', exist_ok=True)\nos.chdir('project')\n");
  for (const [relativePath, content] of Object.entries(files || {})) {
    const path = String(relativePath);
    if (path.startsWith("/") || path.includes("\\") || path.split("/").some((part) => part === ".." || !part)) {
      throw new Error("رفض مسار ملف غير آمن: " + path);
    }
    const target = root + "/" + path;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, content, { encoding: "utf8" });
  }
  pyodide.runPython("import os, sys\nos.chdir('/home/pyodide/project')\nsys.path.insert(0, '/home/pyodide/project')\n");
  pyodide.globals.set("__file__", root + "/" + activeFile);
}

const TEXT_EXTENSIONS = new Set([
  ".py", ".pyw", ".txt", ".json", ".csv", ".md", ".toml", ".ini",
  ".yaml", ".yml", ".html", ".css", ".js", ".xml", ".sql", ".sh",
  ".cfg", ".rst", ".lock",
]);
const TEXT_FILENAMES = new Set([
  ".gitignore", ".dockerignore", ".editorconfig", ".python-version",
  ".flake8", "dockerfile", "makefile", "procfile", "pipfile",
]);
const MAX_SNAPSHOT_FILES = 300;
const MAX_SNAPSHOT_FILE_BYTES = 512 * 1024;
const MAX_SNAPSHOT_BYTES = 12 * 1024 * 1024;
const SKIPPED_DIRECTORIES = new Set([".git", ".venv", "venv", "node_modules", "__pycache__"]);

function collectProjectSnapshot() {
  const root = "/home/pyodide/project";
  const files = {};
  const folders = [];
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let totalBytes = 0;
  let ignoredFiles = 0;

  function walk(absoluteDirectory, relativeDirectory) {
    for (const name of pyodide.FS.readdir(absoluteDirectory)) {
      if (name === "." || name === ".." || SKIPPED_DIRECTORIES.has(name.toLowerCase())) continue;
      const relativePath = relativeDirectory ? relativeDirectory + "/" + name : name;
      if (relativePath.startsWith("/") || relativePath.includes("\\")
        || relativePath.split("/").some((part) => !part || part === "." || part === "..")) {
        ignoredFiles += 1;
        continue;
      }
      const absolutePath = absoluteDirectory + "/" + name;
      const stat = pyodide.FS.lstat(absolutePath);
      if (pyodide.FS.isLink(stat.mode)) {
        ignoredFiles += 1;
        continue;
      }
      if (pyodide.FS.isDir(stat.mode)) {
        folders.push(relativePath);
        walk(absolutePath, relativePath);
        continue;
      }

      const dot = name.lastIndexOf(".");
      const extension = dot >= 0 ? name.slice(dot).toLowerCase() : "";
      if ((!TEXT_EXTENSIONS.has(extension) && !TEXT_FILENAMES.has(name.toLowerCase()))
        || stat.size > MAX_SNAPSHOT_FILE_BYTES
        || Object.keys(files).length >= MAX_SNAPSHOT_FILES
        || totalBytes + stat.size > MAX_SNAPSHOT_BYTES) {
        ignoredFiles += 1;
        continue;
      }
      try {
        const content = decoder.decode(pyodide.FS.readFile(absolutePath));
        files[relativePath] = content;
        totalBytes += stat.size;
      } catch {
        ignoredFiles += 1;
      }
    }
  }

  walk(root, "");
  return { files, folders, ignoredFiles, totalBytes };
}

function configureInput(shared) {
  if (!shared?.control || !shared?.bytes || !shared?.interrupt) {
    pyodide.setStdin({ error: true });
    inputEnabled = false;
    return;
  }
  inputControl = new Int32Array(shared.control);
  inputBytes = new Uint8Array(shared.bytes);
  interruptView = new Int32Array(shared.interrupt);
  pyodide.setInterruptBuffer(interruptView);
  inputEnabled = true;
  pyodide.setStdin({
    isatty: true,
    read(buffer) {
      send("stdin-request");
      while (pendingOffset >= pendingInput.length) {
        while (Atomics.load(inputControl, 0) === 0) {
          Atomics.wait(inputControl, 0, 0, 120);
          pyodide.checkInterrupt();
        }
        const state = Atomics.load(inputControl, 0);
        if (state === 2) return 0;
        const length = Math.min(Atomics.load(inputControl, 1), inputBytes.length);
        pendingInput = inputBytes.slice(0, length);
        pendingOffset = 0;
        Atomics.store(inputControl, 0, 0);
        Atomics.store(inputControl, 1, 0);
      }
      const count = Math.min(buffer.length, pendingInput.length - pendingOffset);
      buffer.set(pendingInput.subarray(pendingOffset, pendingOffset + count));
      pendingOffset += count;
      return count;
    },
  });
}

async function initialize(message) {
  send("status", { text: "تحميل بيئة Python WebAssembly..." });
  pyodide = await loadPyodide({
    indexURL: new URL("pyodide/", message.baseUrl).href,
    packageBaseUrl: "https://cdn.jsdelivr.net/pyodide/v" + pyodideVersion + "/full/",
    stdout: (text) => sendLimitedOutput("stdout", text),
    stderr: (text) => sendLimitedOutput("stderr", text),
  });
  configureInput(message.shared);
  send("ready", { version: pyodide.version || pyodideVersion, inputSupported: inputEnabled, interruptSupported: Boolean(interruptView) });
}

async function execute(message) {
  activeRunId = message.id;
  outputChars = 0;
  outputTruncated = false;
  const start = performance.now();
  let success = true;
  let errorText = "";
  let filesSnapshot = null;
  send("run-started", { id: activeRunId });
  try {
    setProjectFiles(message.files, message.activeFile);
    pyodide.globals.set("__name__", "__main__");
    await pyodide.runPythonAsync(message.code);
  } catch (error) {
    success = false;
    errorText = String(error?.message || error);
    send("stderr", { text: errorText.endsWith("\n") ? errorText : errorText + "\n" });
  }

  try {
    filesSnapshot = collectProjectSnapshot();
  } catch (error) {
    send("stderr", { text: "تعذر حفظ تغييرات ملفات Python: " + String(error?.message || error) + "\n" });
  }

  send("run-finished", {
    id: activeRunId,
    projectId: message.projectId,
    success,
    durationMs: Math.round(performance.now() - start),
    error: errorText || undefined,
    filesSnapshot,
  });
  try { pyodide.globals.delete("__file__"); } catch {}
  activeRunId = null;
}
async function installPackage(message) {
  try {
    send("package-progress", { id: message.id, text: "تحميل micropip..." });
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    try {
      send("package-progress", { id: message.id, text: "جارٍ تنزيل " + message.packageName });
      await micropip.install(message.packageName);
      send("package-progress", { id: message.id, text: "تم تثبيت " + message.packageName });
    } finally {
      micropip.destroy();
    }
    await listPackages(message.id);
    send("package-installed", { id: message.id, packageName: message.packageName });
  } catch (error) {
    send("package-failed", {
      id: message.id,
      message: String(error?.message || error),
    });
  }
}
async function listPackages(id) {
  const json = pyodide.runPython(
    "import importlib.metadata, json\n"
    + "json.dumps(sorted([{ 'name': d.metadata.get('Name', d.name), 'version': d.version } "
    + "for d in importlib.metadata.distributions()], key=lambda x: x['name'].lower()))"
  );
  send("packages", { id, packages: JSON.parse(json) });
}

self.onmessage = async (event) => {
  const message = event.data || {};
  try {
    if (message.type === "init") await initialize(message);
    else if (message.type === "run" && pyodide) await execute(message);
    else if (message.type === "install-package" && pyodide) await installPackage(message);
    else if (message.type === "list-packages" && pyodide) await listPackages(message.id);
    else if (message.type === "reset") send("reset-requested");
  } catch (error) {
    send("runtime-error", { message: String(error?.stack || error) });
    if (message.type === "init") send("init-failed", { message: String(error?.message || error) });
  }
};