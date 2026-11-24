const DB_NAME = "python-studio-mobile";
const DB_VERSION = 1;
const STORE_NAME = "projects";
export const MAX_FILE_BYTES = 512 * 1024;
export const MAX_PROJECT_FILES = 300;
export const MAX_PROJECT_BYTES = 12 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set([
  ".py", ".pyw", ".txt", ".json", ".csv", ".md", ".toml", ".ini",
  ".yaml", ".yml", ".html", ".css", ".js", ".xml", ".sql", ".sh",
  ".cfg", ".rst",
]);
let databasePromise;

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB request failed"));
  });
}
function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Storage transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("Storage transaction aborted"));
  });
}

export function openProjectDatabase() {
  if (databasePromise) return databasePromise;
  if (!("indexedDB" in globalThis)) {
    return Promise.reject(new Error("هذا المتصفح لا يدعم التخزين المحلي IndexedDB."));
  }
  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("updatedAt", "updatedAt", { unique: false });
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      database.onversionchange = () => {
        database.close();
        databasePromise = null;
      };
      resolve(database);
    };
    request.onerror = () => reject(request.error || new Error("تعذر فتح قاعدة بيانات المشاريع."));
    request.onblocked = () => reject(new Error("أغلق النسخة القديمة من التطبيق ثم أعد المحاولة."));
  }).catch((error) => {
    databasePromise = null;
    throw error;
  });
  return databasePromise;
}

export function normalizeProjectPath(rawPath) {
  if (typeof rawPath !== "string" || !rawPath.trim()) throw new Error("مسار الملف مطلوب.");
  const path = rawPath.trim();
  if (
    path.length > 220 ||
    path.startsWith("/") ||
    path.includes("\\") ||
    /[\u0000-\u001f\u007f]/.test(path) ||
    /^[A-Za-z]:/.test(path)
  ) {
    throw new Error("مسار الملف غير صالح.");
  }
  const parts = path.split("/");
  if (parts.some((part) => !part || part === "." || part === ".." || part.length > 100)) {
    throw new Error("المسار يحتوي على جزء غير مسموح.");
  }
  return parts.join("/");
}

export function validateTextFile(path, content) {
  const safePath = normalizeProjectPath(path);
  const filename = safePath.split("/").at(-1);
  const dot = filename.lastIndexOf(".");
  const extension = dot >= 0 ? filename.slice(dot).toLowerCase() : "";
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    throw new Error("امتداد الملف غير مدعوم: " + (extension || "بدون امتداد"));
  }
  if (typeof content !== "string") throw new Error("محتوى الملف يجب أن يكون نصاً.");
  if (new TextEncoder().encode(content).byteLength > MAX_FILE_BYTES) {
    throw new Error("حجم الملف يتجاوز 512 KB.");
  }
  return safePath;
}

export function validateProjectTree(files, folders = []) {
  if (!files || typeof files !== "object" || Array.isArray(files)) {
    throw new Error("قائمة ملفات المشروع غير صالحة.");
  }
  const entries = Object.entries(files);
  if (entries.length > MAX_PROJECT_FILES) throw new Error("عدد ملفات المشروع يتجاوز الحد المسموح.");

  const filePaths = new Set();
  let totalBytes = 0;
  for (const [path, content] of entries) {
    const safePath = validateTextFile(path, content);
    filePaths.add(safePath);
    totalBytes += new TextEncoder().encode(content).byteLength;
    if (totalBytes > MAX_PROJECT_BYTES) {
      throw new Error("حجم المشروع يتجاوز 12 MB.");
    }
  }

  const folderPaths = new Set();
  for (const rawFolder of folders || []) {
    const folder = normalizeProjectPath(rawFolder);
    folderPaths.add(folder);
  }

  for (const path of filePaths) {
    const parts = path.split("/");
    for (let index = 1; index < parts.length; index += 1) {
      const parent = parts.slice(0, index).join("/");
      if (filePaths.has(parent)) {
        throw new Error("تعارض في بنية المشروع: الملف " + parent + " مستخدم كمجلد أيضاً.");
      }
    }
    if (folderPaths.has(path)) {
      throw new Error("تعارض في بنية المشروع: " + path + " مسجل كملف ومجلد.");
    }
  }
  for (const folder of folderPaths) {
    const parts = folder.split("/");
    for (let index = 1; index < parts.length; index += 1) {
      const parent = parts.slice(0, index).join("/");
      if (filePaths.has(parent)) {
        throw new Error("تعارض في بنية المشروع: الملف " + parent + " مستخدم كمجلد أيضاً.");
      }
    }
  }
  return { totalBytes, fileCount: entries.length, folders: Array.from(folderPaths) };
}

export async function listProjects() {
  const database = await openProjectDatabase();
  const transaction = database.transaction(STORE_NAME, "readonly");
  const result = await requestResult(transaction.objectStore(STORE_NAME).getAll());
  await transactionDone(transaction);
  return result.sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function getProject(projectId) {
  const database = await openProjectDatabase();
  const transaction = database.transaction(STORE_NAME, "readonly");
  const result = await requestResult(transaction.objectStore(STORE_NAME).get(projectId));
  await transactionDone(transaction);
  return result || null;
}

export async function saveProject(project) {
  if (!project || typeof project.id !== "string" || !project.id) {
    throw new Error("بيانات المشروع غير صالحة.");
  }
  const files = project.files && typeof project.files === "object" ? project.files : {};
  const validation = validateProjectTree(files, project.folders || []);
  const database = await openProjectDatabase();
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).put({
    ...project,
    files,
    folders: validation.folders,
    updatedAt: Date.now(),
  });
  await transactionDone(transaction);
  return getProject(project.id);
}

export async function createProject(name = "مشروع جديد") {
  const cleanName = String(name || "").trim().slice(0, 48);
  if (!cleanName) throw new Error("اسم المشروع مطلوب.");
  const randomId = globalThis.crypto?.randomUUID?.() || (Date.now() + "-" + Math.random().toString(36).slice(2, 9));
  const project = {
    id: "project-" + randomId,
    name: cleanName,
    files: { "main.py": 'print("Hello, Python Studio!")\n' },
    folders: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  await saveProject(project);
  return project;
}

export async function ensureStarterProject() {
  const projects = await listProjects();
  if (projects.length) return projects[0];
  return createProject("مشروعي الأول");
}

export async function deleteProject(projectId) {
  const database = await openProjectDatabase();
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).delete(projectId);
  await transactionDone(transaction);
}

export async function renameProject(projectId, name) {
  const project = await getProject(projectId);
  if (!project) throw new Error("المشروع غير موجود.");
  const cleanName = String(name || "").trim().slice(0, 48);
  if (!cleanName) throw new Error("اسم المشروع مطلوب.");
  project.name = cleanName;
  return saveProject(project);
}

export async function saveProjectFile(project, path, content) {
  const safePath = validateTextFile(path, content);
  if (!project.files) project.files = {};
  if (!Object.hasOwn(project.files, safePath) && Object.keys(project.files).length >= MAX_PROJECT_FILES) {
    throw new Error("وصل المشروع إلى الحد الأقصى لعدد الملفات.");
  }
  project.files[safePath] = content;
  return saveProject(project);
}

export async function deleteProjectFile(project, path) {
  const safePath = normalizeProjectPath(path);
  if (!Object.hasOwn(project.files || {}, safePath)) throw new Error("الملف غير موجود.");
  delete project.files[safePath];
  return saveProject(project);
}

export const starterProjectText = 'print("Hello, Python Studio!")\n';