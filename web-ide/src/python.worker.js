import { loadPyodide, version as pyodideVersion } from "pyodide";

let pyodide = null;
let inputControl = null;
let inputBytes = null;
let interruptView = null;
let pendingInput = new Uint8Array(0);
let pendingOffset = 0;
let inputEnabled = false;
let activeRunId = null;

function send(type, payload = {}) { self.postMessage({ type, ...payload }); }

function setProjectFiles(files, activeFile) {
  const root = "/home/pyodide/project";
  pyodide.runPython("import os, shutil\nshutil.rmtree('/home/pyodide/project', ignore_errors=True)\nos.makedirs('/home/pyodide/project', exist_ok=True)\n");
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
    stdout: (text) => send("stdout", { text }),
    stderr: (text) => send("stderr", { text }),
  });
  configureInput(message.shared);
  send("ready", { version: pyodide.version || pyodideVersion, inputSupported: inputEnabled, interruptSupported: Boolean(interruptView) });
}

async function execute(message) {
  activeRunId = message.id;
  const start = performance.now();
  send("run-started", { id: activeRunId });
  try {
    setProjectFiles(message.files, message.activeFile);
    await pyodide.runPythonAsync(message.code);
    send("run-finished", { id: activeRunId, success: true, durationMs: Math.round(performance.now() - start) });
  } catch (error) {
    const text = String(error?.message || error);
    send("stderr", { text: text.endsWith("\n") ? text : text + "\n" });
    send("run-finished", { id: activeRunId, success: false, durationMs: Math.round(performance.now() - start), error: text });
  } finally {
    try { pyodide.globals.delete("__file__"); } catch {}
    activeRunId = null;
  }
}

async function installPackage(message) {
  send("package-progress", { id: message.id, text: "تحميل micropip..." });
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");
  try {
    send("package-progress", { id: message.id, text: "جارٍ تنزيل " + message.packageName });
    await micropip.install(message.packageName);
    send("package-progress", { id: message.id, text: "تم تثبيت " + message.packageName });
  } finally { micropip.destroy(); }
  await listPackages(message.id);
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