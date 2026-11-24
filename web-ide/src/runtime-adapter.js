export class PyodideRuntimeAdapter {
  constructor(onMessage) {
    this.onMessage = typeof onMessage === "function" ? onMessage : () => {};
    this.worker = null;
    this.readyPromise = null;
    this.ready = false;
    this.running = false;
    this.inputControlBuffer = null;
    this.inputBytesBuffer = null;
    this.interruptBuffer = null;
    this.inputSupported = false;
    this.interruptSupported = false;
  }
  start() {
    if (this.ready) return Promise.resolve();
    if (this.readyPromise) return this.readyPromise;
    this.worker = new Worker(new URL("./python.worker.js", import.meta.url), { type: "module", name: "python-studio-runtime" });
    const isolated = globalThis.crossOriginIsolated === true && typeof SharedArrayBuffer !== "undefined";
    const shared = isolated ? {
      control: new SharedArrayBuffer(Int32Array.BYTES_PER_ELEMENT * 2),
      bytes: new SharedArrayBuffer(8192),
      interrupt: new SharedArrayBuffer(Int32Array.BYTES_PER_ELEMENT),
    } : null;
    this.inputControlBuffer = shared?.control || null;
    this.inputBytesBuffer = shared?.bytes || null;
    this.interruptBuffer = shared?.interrupt || null;

    this.readyPromise = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("انتهت مهلة تحميل بيئة Python.")), 90000);
      this.worker.onmessage = (event) => {
        const message = event.data || {};
        if (message.type === "ready") {
          clearTimeout(timeout);
          this.ready = true;
          this.inputSupported = message.inputSupported === true;
          this.interruptSupported = message.interruptSupported === true;
          resolve(message);
        } else if (message.type === "init-failed") {
          clearTimeout(timeout);
          reject(new Error(message.message || "تعذر تحميل Pyodide."));
        }
        this.onMessage(message);
      };
      this.worker.onerror = (event) => {
        clearTimeout(timeout);
        reject(new Error(event.message || "تعطل عامل تشغيل Python."));
      };
      const baseUrl = new URL(import.meta.env.BASE_URL, globalThis.location.origin).href;
      this.worker.postMessage({ type: "init", baseUrl, shared });
    }).catch((error) => {
      this.ready = false;
      this.worker?.terminate();
      this.worker = null;
      this.readyPromise = null;
      throw error;
    });
    return this.readyPromise;
  }
  async run({ id, code, files, activeFile }) {
    await this.start();
    if (this.running) throw new Error("هناك برنامج قيد التشغيل بالفعل.");
    this.running = true;
    this.worker.postMessage({ type: "run", id, code, files, activeFile });
  }
  async installPackage(packageName, id) {
    await this.start();
    if (this.running) throw new Error("أوقف البرنامج قبل تثبيت مكتبة.");
    this.worker.postMessage({ type: "install-package", packageName, id });
  }
  async refreshPackages(id) {
    await this.start();
    this.worker.postMessage({ type: "list-packages", id });
  }
  submitInput(value) {
    if (!this.inputSupported || !this.inputControlBuffer || !this.inputBytesBuffer) {
      throw new Error("الإدخال التفاعلي يحتاج إلى استضافة تدعم Cross-Origin Isolation.");
    }
    const bytes = new TextEncoder().encode(String(value) + "\n");
    const control = new Int32Array(this.inputControlBuffer);
    const buffer = new Uint8Array(this.inputBytesBuffer);
    if (bytes.length > buffer.length) throw new Error("الإدخال طويل جداً.");
    buffer.set(bytes);
    Atomics.store(control, 1, bytes.length);
    Atomics.store(control, 0, 1);
    Atomics.notify(control, 0);
  }
  stop() {
    if (!this.worker || !this.running) return;
    if (this.interruptSupported && this.interruptBuffer) {
      Atomics.store(new Int32Array(this.interruptBuffer), 0, 2);
    } else {
      this.worker.terminate();
      this.worker = null;
      this.ready = false;
      this.readyPromise = null;
      this.running = false;
      this.onMessage({ type: "worker-terminated", text: "أُوقف التنفيذ بإنهاء عامل Python." });
    }
  }
  markRunFinished() { this.running = false; }
  async restart() {
    this.worker?.terminate();
    this.worker = null;
    this.ready = false;
    this.running = false;
    this.readyPromise = null;
    this.inputControlBuffer = null;
    this.inputBytesBuffer = null;
    this.interruptBuffer = null;
    this.inputSupported = false;
    this.interruptSupported = false;
    return this.start();
  }
  dispose() {
    this.worker?.terminate();
    this.worker = null;
    this.ready = false;
    this.running = false;
    this.readyPromise = null;
  }
}