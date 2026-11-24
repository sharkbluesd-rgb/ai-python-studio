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
    this.pendingPackage = null;
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
        } else if (message.type === "package-installed" || message.type === "package-failed") {
          if (this.pendingPackage && this.pendingPackage.id === message.id) {
            clearTimeout(this.pendingPackage.timer);
            const pending = this.pendingPackage;
            this.pendingPackage = null;
            if (message.type === "package-installed") pending.resolve(message);
            else pending.reject(new Error(message.message || "فشل تثبيت المكتبة."));
          }
        }
        this.onMessage(message);
      };
      this.worker.onerror = (event) => {
        clearTimeout(timeout);
        const error = new Error(event.message || "تعطل عامل تشغيل Python.");
        const failedWorker = this.worker;
        this.worker = null;
        this.ready = false;
        this.running = false;
        this.readyPromise = null;
        if (this.pendingPackage) {
          clearTimeout(this.pendingPackage.timer);
          this.pendingPackage.reject(error);
          this.pendingPackage = null;
        }
        failedWorker?.terminate();
        reject(error);
        this.onMessage({ type: "runtime-error", message: error.message });
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
    if (this.pendingPackage) throw new Error("انتظر حتى يكتمل تثبيت المكتبة الحالية.");
    this.running = true;
    if (this.interruptBuffer) Atomics.store(new Int32Array(this.interruptBuffer), 0, 0);
    this.worker.postMessage({ type: "run", id, code, files, activeFile });
  }
  async installPackage(packageName, id) {
    await this.start();
    if (this.running) throw new Error("أوقف البرنامج قبل تثبيت مكتبة.");
    if (this.pendingPackage) throw new Error("هناك عملية تثبيت أخرى قيد التنفيذ.");
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pendingPackage?.id === id) {
          const error = new Error("انتهت مهلة تثبيت المكتبة. أُعيد تشغيل بيئة Python لإيقاف العملية المعلّقة.");
          const stalledWorker = this.worker;
          this.pendingPackage = null;
          this.worker = null;
          this.ready = false;
          this.running = false;
          this.readyPromise = null;
          stalledWorker?.terminate();
          reject(error);
          this.onMessage({ type: "worker-terminated", text: error.message });
        }
      }, 300000);
      this.pendingPackage = { id, resolve, reject, timer };
      this.worker.postMessage({ type: "install-package", packageName, id });
    });
  }
  async refreshPackages(id) {
    await this.start();
    if (this.running || this.pendingPackage) return;
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
      if (this.pendingPackage) {
        clearTimeout(this.pendingPackage.timer);
        this.pendingPackage.reject(new Error("توقفت بيئة Python قبل اكتمال تثبيت المكتبة."));
        this.pendingPackage = null;
      }
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
    if (this.pendingPackage) {
      clearTimeout(this.pendingPackage.timer);
      this.pendingPackage.reject(new Error("أُعيد تشغيل بيئة Python."));
      this.pendingPackage = null;
    }
    return this.start();
  }
  dispose() {
    this.worker?.terminate();
    this.worker = null;
    this.ready = false;
    this.running = false;
    this.readyPromise = null;
    if (this.pendingPackage) {
      clearTimeout(this.pendingPackage.timer);
      this.pendingPackage.reject(new Error("أُغلقت بيئة Python."));
      this.pendingPackage = null;
    }
  }
}