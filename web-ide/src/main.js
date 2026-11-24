import { basicSetup, EditorView } from "codemirror";
import { python, globalCompletion, localCompletionSource } from "@codemirror/lang-python";
import { autocompletion } from "@codemirror/autocomplete";
import { indentWithTab, undo, redo, insertNewlineAndIndent } from "@codemirror/commands";
import { Compartment } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { openSearchPanel } from "@codemirror/search";
import { oneDark } from "@codemirror/theme-one-dark";
import { zipSync, unzipSync, strToU8 } from "fflate";
import { inspectZipArchive } from "./zip-safety.js";
import {
  createProject, deleteProject, ensureStarterProject, getProject, listProjects,
  normalizeProjectPath, renameProject, saveProject, validateTextFile,
} from "./storage.js";
import { PyodideRuntimeAdapter } from "./runtime-adapter.js";
import "./style.css";

const $ = (id) => document.getElementById(id);
const state = {
  project: null, currentPath: "main.py", openTabs: [], saveTimer: null,
  lightTheme: false, virtualCtrl: false, virtualShift: false, collapsedFolders: new Set(),
  isRunning: false, activePanel: "output", runSequence: 0, runtimeReady: false,
};
const themeCompartment = new Compartment();
const runtime = new PyodideRuntimeAdapter(handleRuntimeMessage);
let editorView = null;
let toastTimer = null;
let lastRunError = "";

function setStatus(message) { $("status-message").textContent = message; }
function toast(message, kind = "info") {
  const item = document.createElement("div");
  item.className = "toast " + kind;
  item.textContent = message;
  $("toast-region").append(item);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => item.remove(), 3200);
}
function setPanel(name) {
  state.activePanel = name;
  document.querySelectorAll(".panel-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.panel === name));
  document.querySelectorAll(".console-view").forEach((view) => view.classList.toggle("active", view.id === name + "-view"));
  $("bottom-panel").classList.remove("collapsed");
}
function appendText(element, text) {
  const maxChars = 250000;
  const next = element.textContent + String(text);
  element.textContent = next.length > maxChars
    ? "[تم اختصار المخرجات القديمة للحفاظ على أداء المحرر]\n" + next.slice(-maxChars)
    : next;
  element.scrollTop = element.scrollHeight;
}
function basename(path) { return path.split("/").at(-1) || path; }
function dirname(path) { const parts = path.split("/"); parts.pop(); return parts.join("/"); }

async function saveNow() {
  clearTimeout(state.saveTimer);
  state.saveTimer = null;
  if (!state.project || !editorView) return;
  if (state.currentPath) state.project.files[state.currentPath] = editorView.state.doc.toString();
  try {
    await saveProject(state.project);
    $("save-button").classList.remove("unsaved");
    setStatus("تم الحفظ محلياً في هذا المتصفح");
  } catch (error) {
    setStatus("تعذر الحفظ: " + error.message);
    toast(error.message, "error");
    throw error;
  }
}
function scheduleSave() {
  $("save-button").classList.add("unsaved");
  setStatus("تغييرات غير محفوظة…");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => { saveNow().catch(() => {}); }, 450);
}
function openFile(path) {
  const safePath = normalizeProjectPath(path);
  if (!Object.hasOwn(state.project.files, safePath)) throw new Error("الملف غير موجود.");
  if (editorView && state.currentPath) state.project.files[state.currentPath] = editorView.state.doc.toString();
  state.currentPath = safePath;
  if (!state.openTabs.includes(safePath)) state.openTabs.push(safePath);
  editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: state.project.files[safePath] } });
  renderFiles();
  renderTabs();
  updateFileHeading();
  editorView.focus();
}
function updateFileHeading() {
  $("active-filename").textContent = basename(state.currentPath);
  $("project-breadcrumb").textContent = state.project.name + " / " + state.currentPath;
}
function renderProjects(projects) {
  const select = $("project-select");
  select.replaceChildren();
  for (const project of projects) {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    select.append(option);
  }
  if (state.project) select.value = state.project.id;
}
function renderFiles() {
  const nav = $("file-list");
  nav.replaceChildren();
  const directories = new Set(state.project.folders || []);
  for (const path of Object.keys(state.project.files)) {
    const pieces = path.split("/");
    for (let i = 1; i < pieces.length; i += 1) directories.add(pieces.slice(0, i).join("/"));
  }
  const items = [
    ...Array.from(directories).map((path) => ({ path, folder: true })),
    ...Object.keys(state.project.files).map((path) => ({ path, folder: false })),
  ].sort((a, b) => a.path.localeCompare(b.path) || Number(b.folder) - Number(a.folder));

  $("file-count").textContent = Object.keys(state.project.files).length;
  for (const item of items) {
    const parts = item.path.split("/");
    const hiddenByAncestor = parts.slice(0, -1).some((_, index) =>
      state.collapsedFolders.has(parts.slice(0, index + 1).join("/"))
    );
    if (hiddenByAncestor) continue;

    const button = document.createElement("button");
    button.className = "tree-item " + (item.folder ? "folder-item" : "file-item")
      + (item.path === state.currentPath ? " active" : "");
    button.style.setProperty("--depth", String(parts.length - 1));
    button.dataset.path = item.path;
    const icon = document.createElement("span");
    icon.className = "tree-icon";
    icon.textContent = item.folder
      ? (state.collapsedFolders.has(item.path) ? "▸" : "▾")
      : item.path.toLowerCase().endsWith(".py") ? "Py" : "•";
    const label = document.createElement("span");
    label.textContent = basename(item.path);
    button.append(icon, label);

    if (item.folder) {
      button.setAttribute("aria-expanded", String(!state.collapsedFolders.has(item.path)));
      button.addEventListener("click", () => {
        if (state.collapsedFolders.has(item.path)) state.collapsedFolders.delete(item.path);
        else state.collapsedFolders.add(item.path);
        renderFiles();
      });
    } else {
      button.addEventListener("click", () => {
        try {
          openFile(item.path);
          closeSidebarOnMobile();
        } catch (error) {
          toast(error.message, "error");
        }
      });
    }
    nav.append(button);
  }
}
function renderTabs() {
  const tabs = $("editor-tabs");
  tabs.replaceChildren();
  for (const path of state.openTabs) {
    const tab = document.createElement("div");
    tab.className = "editor-tab" + (path === state.currentPath ? " active" : "");
    const open = document.createElement("button");
    open.className = "tab-open";
    open.textContent = basename(path);
    open.title = path;
    open.addEventListener("click", () => openFile(path));
    const close = document.createElement("button");
    close.className = "tab-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "إغلاق " + basename(path));
    close.addEventListener("click", () => closeTab(path));
    tab.append(open, close);
    tabs.append(tab);
  }
}
function closeTab(path) {
  const index = state.openTabs.indexOf(path);
  if (index < 0) return;
  state.openTabs.splice(index, 1);
  if (state.currentPath === path) {
    if (state.openTabs.length) {
      openFile(state.openTabs[Math.min(index, state.openTabs.length - 1)]);
    } else {
      state.currentPath = "";
      editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: "" },
        selection: { anchor: 0 },
      });
      $("active-filename").textContent = "لا يوجد ملف";
      $("project-breadcrumb").textContent = state.project.name;
    }
  }
  renderTabs();
  renderFiles();
}
function updateCursor() {
  if (!editorView) return;
  const position = editorView.state.selection.main.head;
  const line = editorView.state.doc.lineAt(position);
  $("cursor-position").textContent = "Ln " + line.number + ", Col " + (position - line.from + 1);
}
function setupEditor() {
  const lightTheme = EditorView.theme({
    "&": { backgroundColor: "#f6f7fb", color: "#1c2433" },
    ".cm-content": { caretColor: "#6554dc" },
    ".cm-gutters": { backgroundColor: "#eef0f6", color: "#738097", border: "none" },
    ".cm-activeLine": { backgroundColor: "#e9edfa" },
    ".cm-activeLineGutter": { backgroundColor: "#e2e7f5" },
    ".cm-cursor": { borderLeftColor: "#6554dc" },
    ".cm-selectionBackground": { backgroundColor: "#cbd5fa !important" },
  }, { dark: false });
  const theme = state.lightTheme ? lightTheme : oneDark;
  editorView = new EditorView({
    doc: state.project.files[state.currentPath] || "",
    parent: $("editor"),
    extensions: [
      basicSetup,
      python(),
      autocompletion({ override: [globalCompletion, localCompletionSource] }),
      keymap.of([
        indentWithTab,
        { key: "Mod-s", run: () => { saveNow(); return true; } },
        { key: "F5", run: () => { runCurrentFile(); return true; } },
        { key: "Escape", run: () => { runtime.stop(); return true; } },
      ]),
      themeCompartment.of(theme),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ autocapitalize: "off", autocorrect: "off", spellcheck: "false", "aria-label": "Python source editor" }),
      EditorView.theme({
        "&": { height: "100%", fontSize: "var(--editor-font-size, 15px)" },
        ".cm-scroller": { overflow: "auto", fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace", lineHeight: "1.7" },
        ".cm-content": { padding: "12px 0", minHeight: "100%" },
        ".cm-line": { padding: "0 12px" },
        ".cm-gutters": { minWidth: "42px" },
      }),
      EditorView.updateListener.of((update) => {
        if (update.docChanged && state.currentPath) {
          state.project.files[state.currentPath] = update.state.doc.toString();
          scheduleSave();
        }
        if (update.selectionSet) updateCursor();
      }),
    ],
  });
  updateCursor();
}
function closeSidebarOnMobile() {
  if (matchMedia("(max-width: 760px)").matches) {
    $("file-sidebar").classList.remove("open");
    $("mobile-scrim").classList.remove("visible");
  }
}
function showSidebar() {
  $("file-sidebar").classList.add("open");
  $("mobile-scrim").classList.add("visible");
}
async function refreshProjectList() {
  renderProjects(await listProjects());
}
async function switchProject(projectId) {
  await saveNow();
  const project = await getProject(projectId);
  if (!project) throw new Error("لم يتم العثور على المشروع.");
  state.project = project;
  state.currentPath = Object.keys(project.files)[0] || "";
  if (!state.currentPath) {
    state.currentPath = "main.py";
    project.files[state.currentPath] = "";
  }
  state.openTabs = [state.currentPath];
  editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: project.files[state.currentPath] } });
  updateFileHeading();
  renderFiles();
  renderTabs();
  await refreshProjectList();
  setStatus("تم فتح المشروع: " + project.name);
}
async function newProject() {
  const name = prompt("اسم المشروع الجديد:");
  if (!name) return;
  await saveNow();
  const project = await createProject(name);
  state.project = project;
  state.currentPath = "main.py";
  state.openTabs = ["main.py"];
  editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: project.files["main.py"] } });
  updateFileHeading();
  renderFiles();
  renderTabs();
  await refreshProjectList();
  toast("تم إنشاء المشروع وحفظه محلياً.", "success");
}
async function newFile() {
  const path = prompt("مسار الملف الجديد، مثال: main.py أو utils/helpers.py");
  if (!path) return;
  await saveNow();
  const safe = validateTextFile(path, "");
  if (Object.hasOwn(state.project.files, safe)) throw new Error("يوجد ملف بهذا المسار بالفعل.");
  const nextFiles = { ...state.project.files, [safe]: "" };
  const nextFolders = new Set(state.project.folders || []);
  const parentParts = safe.split("/");
  parentParts.pop();
  for (let i = 1; i <= parentParts.length; i += 1) nextFolders.add(parentParts.slice(0, i).join("/"));
  state.project = await saveProject({ ...state.project, files: nextFiles, folders: Array.from(nextFolders) });
  openFile(safe);
}
async function newFolder() {
  const path = prompt("اسم المجلد أو مساره:");
  if (!path) return;
  await saveNow();
  const safe = normalizeProjectPath(path);
  if ((state.project.folders || []).includes(safe)) throw new Error("المجلد موجود بالفعل.");
  const nextFolders = new Set(state.project.folders || []);
  const parts = safe.split("/");
  for (let i = 1; i <= parts.length; i += 1) nextFolders.add(parts.slice(0, i).join("/"));
  state.project = await saveProject({ ...state.project, folders: Array.from(nextFolders) });
  renderFiles();
  toast("تم إنشاء المجلد.", "success");
}
async function renameCurrentFile() {
  if (!state.currentPath) return;
  const newPath = prompt("المسار الجديد للملف:", state.currentPath);
  if (!newPath || newPath === state.currentPath) return;
  await saveNow();
  const safe = validateTextFile(newPath, state.project.files[state.currentPath]);
  if (Object.hasOwn(state.project.files, safe)) throw new Error("المسار الجديد مستخدم بالفعل.");
  const nextFiles = { ...state.project.files, [safe]: state.project.files[state.currentPath] };
  delete nextFiles[state.currentPath];
  const nextFolders = new Set(state.project.folders || []);
  const parentParts = safe.split("/");
  parentParts.pop();
  for (let i = 1; i <= parentParts.length; i += 1) nextFolders.add(parentParts.slice(0, i).join("/"));
  state.project = await saveProject({ ...state.project, files: nextFiles, folders: Array.from(nextFolders) });
  state.openTabs = state.openTabs.map((path) => path === state.currentPath ? safe : path);
  state.currentPath = safe;
  renderFiles(); renderTabs(); updateFileHeading();
}
async function duplicateCurrentFile() {
  if (!state.currentPath) return;
  const suggested = state.currentPath.replace(/(\\.[^./]+)?$/, "_copy$1");
  const target = prompt("مسار النسخة الجديدة:", suggested);
  if (!target) return;
  await saveNow();
  const safe = validateTextFile(target, state.project.files[state.currentPath]);
  if (Object.hasOwn(state.project.files, safe)) throw new Error("المسار مستخدم بالفعل.");
  const nextFiles = { ...state.project.files, [safe]: state.project.files[state.currentPath] };
  const nextFolders = new Set(state.project.folders || []);
  const parentParts = safe.split("/");
  parentParts.pop();
  for (let i = 1; i <= parentParts.length; i += 1) nextFolders.add(parentParts.slice(0, i).join("/"));
  state.project = await saveProject({ ...state.project, files: nextFiles, folders: Array.from(nextFolders) });
  renderFiles();
  openFile(safe);
}
async function renameProjectAction() {
  const name = prompt("اسم المشروع:", state.project.name);
  if (!name || name === state.project.name) return;
  state.project = await renameProject(state.project.id, name);
  updateFileHeading();
  await refreshProjectList();
  toast("تم تغيير اسم المشروع.", "success");
}
async function deleteProjectAction() {
  if (!confirm("حذف المشروع «" + state.project.name + "» وجميع ملفاته من هذا المتصفح؟")) return;
  await deleteProject(state.project.id);
  const remaining = await listProjects();
  state.project = remaining[0] || await createProject("مشروعي الأول");
  state.currentPath = Object.keys(state.project.files)[0] || "main.py";
  state.openTabs = [state.currentPath];
  editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: state.project.files[state.currentPath] || "" } });
  await refreshProjectList();
  updateFileHeading();
  renderFiles();
  renderTabs();
  toast("تم حذف المشروع.", "success");
}
async function deleteCurrentFile() {
  if (!state.currentPath) return;
  if (!confirm("حذف الملف " + state.currentPath + "؟ لا يمكن التراجع عن الحذف.")) return;
  await saveNow();
  const deletedPath = state.currentPath;
  const nextFiles = { ...state.project.files };
  delete nextFiles[deletedPath];
  if (!Object.keys(nextFiles).length) nextFiles["main.py"] = "";
  state.project = await saveProject({ ...state.project, files: nextFiles });
  state.openTabs = state.openTabs.filter((path) => path !== deletedPath);
  state.currentPath = state.openTabs.find((path) => Object.hasOwn(nextFiles, path))
    || Object.keys(nextFiles)[0];
  if (!state.openTabs.includes(state.currentPath)) state.openTabs.push(state.currentPath);
  editorView.dispatch({
    changes: { from: 0, to: editorView.state.doc.length, insert: nextFiles[state.currentPath] || "" },
    selection: { anchor: 0 },
  });
  renderFiles();
  renderTabs();
  updateFileHeading();
}
async function importFiles(fileList) {
  await saveNow();
  const additions = [];
  const nextFolders = new Set(state.project.folders || []);

  for (const file of Array.from(fileList)) {
    const path = file.webkitRelativePath || file.name;
    const safe = validateTextFile(path, "");
    if (file.size > 512 * 1024) throw new Error("حجم الملف يتجاوز 512 KB: " + safe);
    const text = await file.text();
    validateTextFile(safe, text);
    if (Object.hasOwn(state.project.files, safe) && !confirm("استبدال الملف " + safe + "؟")) continue;
    additions.push([safe, text]);
    const parentParts = safe.split("/");
    parentParts.pop();
    for (let i = 1; i <= parentParts.length; i += 1) {
      nextFolders.add(parentParts.slice(0, i).join("/"));
    }
  }
  if (!additions.length) return;

  const nextFiles = { ...state.project.files };
  for (const [path, text] of additions) nextFiles[path] = text;
  state.project = await saveProject({
    ...state.project,
    files: nextFiles,
    folders: Array.from(nextFolders),
  });
  renderFiles();
  if (additions.some(([path]) => path === state.currentPath)) openFile(state.currentPath);
  toast("تم استيراد " + additions.length + " ملف.", "success");
}
async function importZip(file) {
  if (!file) return;
  await saveNow();
  if (file.size > 10 * 1024 * 1024) throw new Error("حجم ZIP يتجاوز 10 MB.");
  const archiveBytes = new Uint8Array(await file.arrayBuffer());
  const manifest = inspectZipArchive(archiveBytes);
  const manifestByPath = new Map(manifest.map((entry) => [entry.path, entry]));
  const archive = unzipSync(archiveBytes);
  const imported = {};
  const folders = new Set();
  let totalBytes = 0;

  for (const [rawPath, bytes] of Object.entries(archive)) {
    const isFolder = rawPath.endsWith("/");
    const trimmed = isFolder ? rawPath.slice(0, -1) : rawPath;
    if (!trimmed || trimmed === "__MACOSX" || trimmed.startsWith("__MACOSX/")) continue;
    const safe = normalizeProjectPath(trimmed);
    const metadata = manifestByPath.get(safe);
    if (!metadata || metadata.isDirectory !== isFolder) {
      throw new Error("محتوى ZIP لا يطابق دليل الملفات: " + safe);
    }
    if (isFolder) {
      folders.add(safe);
      continue;
    }
    if (bytes.byteLength !== metadata.uncompressedSize) {
      throw new Error("حجم الملف بعد فك الضغط لا يطابق بيانات ZIP: " + safe);
    }
    totalBytes += bytes.byteLength;
    if (totalBytes > 12 * 1024 * 1024) throw new Error("حجم الملفات بعد فك الضغط يتجاوز 12 MB.");
    let text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      throw new Error("الملف ليس نص UTF-8 صالحاً: " + safe);
    }
    validateTextFile(safe, text);
    imported[safe] = text;
  }

  if (!Object.keys(imported).length) throw new Error("لم يتم العثور على ملفات نصية مدعومة داخل ZIP.");
  const replace = Object.keys(imported).some((path) => Object.hasOwn(state.project.files, path));
  if (replace && !confirm("توجد ملفات بنفس الأسماء. هل تريد استبدالها؟")) return;
  const nextFiles = { ...state.project.files, ...imported };
  const nextFolders = Array.from(new Set([...(state.project.folders || []), ...folders]));
  state.project = await saveProject({ ...state.project, files: nextFiles, folders: nextFolders });
  renderFiles();
  const firstPython = Object.keys(imported).find((path) => path.endsWith(".py")) || Object.keys(imported)[0];
  openFile(firstPython);
  toast("تم استيراد " + Object.keys(imported).length + " ملف من ZIP.", "success");
}
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
function exportZip() {
  const files = {};
  for (const [path, content] of Object.entries(state.project.files)) files[path] = strToU8(content);
  for (const folder of state.project.folders || []) files[folder + "/"] = new Uint8Array(0);
  const archive = zipSync(files, { level: 6 });
  downloadBlob(new Blob([archive], { type: "application/zip" }), state.project.name.replace(/[^a-z0-9_-]/gi, "_") + ".zip");
  toast("تم تجهيز ملف ZIP للتنزيل.", "success");
}
async function persistRuntimeSnapshot(message) {
  if (!message.filesSnapshot || !message.projectId) return;
  const project = await getProject(message.projectId);
  if (!project) return;
  const files = { ...message.filesSnapshot.files };
  if (!Object.keys(files).length) files["main.py"] = "";
  const saved = await saveProject({
    ...project,
    files,
    folders: message.filesSnapshot.folders || [],
  });

  if (state.project?.id === message.projectId) {
    state.project = saved;
    state.openTabs = state.openTabs.filter((path) => Object.hasOwn(saved.files, path));
    if (!Object.hasOwn(saved.files, state.currentPath)) {
      state.currentPath = state.openTabs[0] || Object.keys(saved.files)[0] || "main.py";
      if (!state.openTabs.includes(state.currentPath)) state.openTabs.push(state.currentPath);
    }
    const nextText = saved.files[state.currentPath] || "";
    if (editorView.state.doc.toString() !== nextText) {
      editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: nextText },
        selection: { anchor: 0 },
      });
    }
    renderFiles();
    renderTabs();
    updateFileHeading();
  }
  if (message.filesSnapshot.ignoredFiles > 0) {
    appendText($("output-text"), "\n[تنبيه] تم تجاهل " + message.filesSnapshot.ignoredFiles
      + " ملفاً غير مدعوم أو تجاوز حدود التخزين.\n");
  }
}
function setRunning(running) {
  state.isRunning = running;
  $("run-button").disabled = running;
  $("stop-button").disabled = !running;
  $("runtime-state").classList.toggle("busy", running);
  $("project-select").disabled = running;
  for (const id of [
    "new-project", "rename-project", "delete-project", "new-file", "new-folder",
    "import-files", "rename-file", "duplicate-file", "delete-file", "import-zip",
    "export-zip", "package-install-button", "package-input",
  ]) {
    const control = $(id);
    if (control) control.disabled = running;
  }
  $("file-list").querySelectorAll("button").forEach((button) => { button.disabled = running; });
  $("editor-tabs").querySelectorAll("button").forEach((button) => { button.disabled = running; });
  if (editorView) editorView.contentDOM.contentEditable = String(!running);
}
async function runCurrentFile() {
  if (!state.currentPath) { toast("أنشئ ملف Python أولاً.", "error"); return; }
  if (!/\\.pyw?$/i.test(state.currentPath)) {
    toast("يمكن تشغيل ملفات Python فقط (.py أو .pyw).", "error");
    return;
  }
  await saveNow();
  $("output-text").textContent = "";
  $("error-text").textContent = "لا توجد أخطاء في هذا التشغيل.";
  $("error-count").textContent = "0";
  $("run-duration").textContent = "قيد التشغيل…";
  lastRunError = "";
  setPanel("output");
  setRunning(true);
  const code = editorView.state.doc.toString();
  const id = ++state.runSequence;
  try {
    await runtime.run({
      id,
      projectId: state.project.id,
      code,
      files: { ...state.project.files },
      activeFile: state.currentPath,
    });
  } catch (error) {
    setRunning(false);
    $("run-duration").textContent = "تعذر التشغيل";
    appendText($("error-text"), error.message + "\n");
    setPanel("errors");
    toast(error.message, "error");
  }
}
function addRuntimeError(text) {
  lastRunError += String(text);
  $("error-text").textContent = lastRunError;
  const count = (lastRunError.match(/Traceback|Error:|Exception:/g) || []).length;
  $("error-count").textContent = String(Math.max(1, count));
}
function handleRuntimeMessage(message) {
  if (message.type === "status") {
    $("runtime-state").querySelector("span").textContent = message.text;
  } else if (message.type === "ready") {
    state.runtimeReady = true;
    $("runtime-state").classList.add("ready");
    $("runtime-state").querySelector("span").textContent = "Python جاهز";
    $("python-version").textContent = "Python " + message.version;
    if (!message.inputSupported) {
      $("stdin-label").textContent = "input() يحتاج استضافة COOP/COEP؛ الإيقاف يعمل بإنهاء Worker.";
    }
    if (!message.interruptSupported) {
      $("runtime-state").title = "الإيقاف يعمل بإنهاء عامل التشغيل لأن الاستضافة لا توفر SharedArrayBuffer.";
    }
    runtime.refreshPackages("initial");
  } else if (message.type === "stdout") {
    appendText($("output-text"), message.text);
  } else if (message.type === "stderr") {
    appendText($("error-text"), message.text);
    lastRunError += message.text;
    $("error-count").textContent = "1";
  } else if (message.type === "run-started") {
    setRunning(true);
  } else if (message.type === "run-finished") {
    runtime.markRunFinished();
    $("stdin-form").classList.add("hidden");
    $("run-duration").textContent = message.durationMs + " ms";
    if (!message.success) {
      addRuntimeError("");
      setPanel("errors");
    }
    const finishRun = () => {
      setRunning(false);
      setStatus(message.success ? "اكتمل التنفيذ وحُفظت تغييرات الملفات" : "انتهى التنفيذ مع خطأ");
    };
    if (message.filesSnapshot && message.projectId) {
      persistRuntimeSnapshot(message)
        .catch((error) => {
          appendText($("error-text"), "\nتعذر حفظ ملفات Python: " + error.message + "\n");
          toast("تعذر حفظ تغييرات ملفات Python: " + error.message, "error");
        })
        .finally(finishRun);
    } else {
      finishRun();
    }
  } else if (message.type === "stdin-request") {
    setPanel("terminal");
    $("stdin-form").classList.remove("hidden");
    $("stdin-input").focus();
  } else if (message.type === "package-progress") {
    $("package-status").textContent = message.text;
  } else if (message.type === "packages") {
    renderPackages(message.packages || []);
  } else if (message.type === "runtime-error" || message.type === "init-failed") {
    state.runtimeReady = false;
    $("runtime-state").classList.remove("ready", "busy");
    $("runtime-state").classList.add("error");
    $("runtime-state").querySelector("span").textContent = "خطأ في Python";
    setRunning(false);
    $("stdin-form").classList.add("hidden");
    addRuntimeError(message.message || "خطأ في بيئة التشغيل.");
  } else if (message.type === "worker-terminated") {
    $("run-duration").textContent = "تم الإيقاف";
    setRunning(false);
    $("stdin-form").classList.add("hidden");
    setStatus(message.text);
  }
}
async function restartPythonRuntime() {
  if (state.isRunning && !confirm("إعادة التشغيل ستوقف البرنامج الجاري وتعيد تحميل بيئة Python. متابعة؟")) return;
  const button = $("restart-runtime");
  button.disabled = true;
  state.runtimeReady = false;
  $("runtime-state").classList.remove("ready", "error", "busy");
  $("runtime-state").querySelector("span").textContent = "إعادة تشغيل Python…";
  try {
    const result = await runtime.restart();
    state.runtimeReady = true;
    $("python-version").textContent = "Python " + result.version;
    $("output-text").textContent = "تمت إعادة تشغيل بيئة Python بنجاح.\n";
    setStatus("بيئة Python جاهزة من جديد");
    toast("تمت إعادة تشغيل بيئة Python.", "success");
  } catch (error) {
    state.runtimeReady = false;
    $("runtime-state").classList.add("error");
    $("runtime-state").querySelector("span").textContent = "تعذر تحميل Python";
    $("python-version").textContent = "Python غير متاح";
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}
function renderPackages(packages) {
  const list = $("package-list");
  list.replaceChildren();
  $("package-status").textContent = packages.length + " حزمة مثبتة في جلسة Pyodide الحالية.";
  for (const item of packages) {
    const row = document.createElement("div");
    row.className = "package-row";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const version = document.createElement("span");
    version.textContent = item.version;
    row.append(name, version);
    list.append(row);
  }
}
async function installPackage() {
  const packageName = $("package-input").value.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,80}(?:==[A-Za-z0-9.+*-]{1,30})?$/.test(packageName)) {
    toast("اكتب اسم مكتبة صحيحاً، ويمكن تحديد الإصدار بصيغة name==version.", "error");
    return;
  }
  const button = $("package-install-button");
  button.disabled = true;
  try {
    await runtime.installPackage(packageName, "install-" + Date.now());
    $("package-input").value = "";
  } catch (error) {
    $("package-status").textContent = error.message;
    toast(error.message, "error");
  } finally { button.disabled = false; }
}
async function runTerminalCommand(command) {
  const output = $("terminal-text");
  appendText(output, "\n$ " + command + "\n");
  const [verb, ...rest] = command.trim().split(/\s+/);
  const argument = rest.join(" ");
  if (!verb) return;
  if (verb === "help") {
    appendText(output, "الأوامر المدعومة: help, clear, ls, pwd, python --version, run [file.py], cat [file], pip list, pip install [package]\n");
  } else if (verb === "clear") {
    output.textContent = "";
  } else if (verb === "ls") {
    appendText(output, Object.keys(state.project.files).join("\n") + "\n");
  } else if (verb === "pwd") {
    appendText(output, "/home/pyodide/project\n");
  } else if (verb === "python" && ["--version", "-V"].includes(argument)) {
    appendText(output, $("python-version").textContent + "\n");
  } else if (verb === "run") {
    if (argument) {
      const safe = normalizeProjectPath(argument);
      if (!Object.hasOwn(state.project.files, safe)) throw new Error("الملف غير موجود.");
      openFile(safe);
    }
    if (!state.currentPath.endsWith(".py")) throw new Error("اختر ملف Python لتشغيله.");
    await runCurrentFile();
  } else if (verb === "cat") {
    const safe = normalizeProjectPath(argument);
    if (!Object.hasOwn(state.project.files, safe)) throw new Error("الملف غير موجود.");
    appendText(output, state.project.files[safe] + "\n");
  } else if (verb === "pip" && argument === "list") {
    await runtime.refreshPackages("terminal");
    appendText(output, "تم طلب قائمة الحزم من بيئة Python.\n");
  } else if (verb === "pip" && argument.startsWith("install ")) {
    $("package-input").value = argument.slice(8).trim();
    await installPackage();
    setPanel("packages");
  } else {
    appendText(output, "أمر غير معروف. اكتب help.\n");
  }
}
function insertAtCursor(value) {
  const selection = editorView.state.selection.main;
  editorView.dispatch({ changes: { from: selection.from, to: selection.to, insert: value }, selection: { anchor: selection.from + value.length } });
  editorView.focus();
}
function handleProgrammerKey(key) {
  if (key === "CTRL") {
    state.virtualCtrl = !state.virtualCtrl;
    document.querySelector('[data-key="CTRL"]').classList.toggle("modifier-active", state.virtualCtrl);
    return;
  }
  if (key === "SHIFT") {
    state.virtualShift = !state.virtualShift;
    document.querySelector('[data-key="SHIFT"]').classList.toggle("modifier-active", state.virtualShift);
    return;
  }
  if (key === "ESC") { runtime.stop(); return; }
  if (state.virtualCtrl) {
    state.virtualCtrl = false;
    document.querySelector('[data-key="CTRL"]').classList.remove("modifier-active");
    const shortcut = key.toLowerCase();
    const selection = editorView.state.selection.main;
    if (shortcut === "s") saveNow();
    else if (shortcut === "f") openSearchPanel(editorView);
    else if (shortcut === "a") editorView.dispatch({ selection: { anchor: 0, head: editorView.state.doc.length } });
    else if (shortcut === "z") undo(editorView);
    else if (shortcut === "y") redo(editorView);
    else if (shortcut === "c" || shortcut === "x") {
      navigator.clipboard?.writeText(editorView.state.sliceDoc(selection.from, selection.to)).catch(() => toast("تعذر الوصول إلى الحافظة."));
      if (shortcut === "x" && !selection.empty) editorView.dispatch({ changes: { from: selection.from, to: selection.to, insert: "" } });
    } else if (shortcut === "v") {
      navigator.clipboard?.readText().then((text) => insertAtCursor(text)).catch(() => toast("تعذر قراءة الحافظة."));
    } else toast("اختصار غير مدعوم.");
    editorView.focus();
    return;
  }
  const arrows = { ARROWLEFT: "left", ARROWRIGHT: "right", ARROWUP: "up", ARROWDOWN: "down" };
  if (arrows[key]) {
    const head = editorView.state.selection.main.head;
    const movement = { left: -1, right: 1, up: -1, down: 1 }[arrows[key]];
    let position = head + movement;
    if (arrows[key] === "up" || arrows[key] === "down") {
      const line = editorView.state.doc.lineAt(head);
      const targetNumber = Math.max(1, Math.min(editorView.state.doc.lines, line.number + movement));
      const targetLine = editorView.state.doc.line(targetNumber);
      position = Math.min(targetLine.to, targetLine.from + head - line.from);
    }
    const nextPosition = Math.max(0, Math.min(editorView.state.doc.length, position));
    const current = editorView.state.selection.main;
    editorView.dispatch({ selection: state.virtualShift ? { anchor: current.anchor, head: nextPosition } : { anchor: nextPosition } });
    state.virtualShift = false;
    document.querySelector('[data-key="SHIFT"]').classList.remove("modifier-active");
    editorView.focus();
    return;
  }
  if (key === "TAB" || key === "INDENT") insertAtCursor("    ");
  else if (key === "ENTER") insertNewlineAndIndent(editorView);
  else insertAtCursor(state.virtualShift ? key.toUpperCase() : key);
  state.virtualShift = false;
  document.querySelector('[data-key="SHIFT"]').classList.remove("modifier-active");
}
function goToLine() {
  const number = Number(prompt("اذهب إلى رقم السطر:"));
  if (!Number.isInteger(number) || number < 1 || number > editorView.state.doc.lines) return;
  const line = editorView.state.doc.line(number);
  editorView.dispatch({ selection: { anchor: line.from }, scrollIntoView: true });
  editorView.focus();
}
function toggleTheme() {
  state.lightTheme = !state.lightTheme;
  const light = EditorView.theme({
    "&": { backgroundColor: "#f6f7fb", color: "#1c2433" }, ".cm-content": { caretColor: "#6554dc" },
    ".cm-gutters": { backgroundColor: "#eef0f6", color: "#738097", border: "none" },
    ".cm-activeLine": { backgroundColor: "#e9edfa" }, ".cm-cursor": { borderLeftColor: "#6554dc" },
  }, { dark: false });
  editorView.dispatch({ effects: themeCompartment.reconfigure(state.lightTheme ? light : oneDark) });
  document.body.classList.toggle("light", state.lightTheme);
}
function bindEvents() {
  $("sidebar-toggle").addEventListener("click", showSidebar);
  $("sidebar-close").addEventListener("click", closeSidebarOnMobile);
  $("mobile-scrim").addEventListener("click", closeSidebarOnMobile);
  $("new-project").addEventListener("click", () => newProject().catch((error) => toast(error.message, "error")));
  $("rename-project").addEventListener("click", () => renameProjectAction().catch((error) => toast(error.message, "error")));
  $("delete-project").addEventListener("click", () => deleteProjectAction().catch((error) => toast(error.message, "error")));
  $("rename-file").addEventListener("click", () => renameCurrentFile().catch((error) => toast(error.message, "error")));
  $("duplicate-file").addEventListener("click", () => duplicateCurrentFile().catch((error) => toast(error.message, "error")));
  $("delete-file").addEventListener("click", () => deleteCurrentFile().catch((error) => toast(error.message, "error")));
  $("project-select").addEventListener("change", (event) => switchProject(event.target.value).catch((error) => toast(error.message, "error")));
  $("new-file").addEventListener("click", () => newFile().catch((error) => toast(error.message, "error")));
  $("new-folder").addEventListener("click", () => newFolder().catch((error) => toast(error.message, "error")));
  $("import-files").addEventListener("click", () => $("file-picker").click());
  $("file-picker").addEventListener("change", (event) => importFiles(event.target.files).catch((error) => toast(error.message, "error")).finally(() => { event.target.value = ""; }));
  $("import-zip").addEventListener("click", () => $("zip-picker").click());
  $("zip-picker").addEventListener("change", (event) => importZip(event.target.files[0]).catch((error) => toast(error.message, "error")).finally(() => { event.target.value = ""; }));
  $("export-zip").addEventListener("click", () => exportZip());
  $("save-button").addEventListener("click", () => saveNow().catch(() => {}));
  $("restart-runtime").addEventListener("click", () => restartPythonRuntime());
  $("run-button").addEventListener("click", () => runCurrentFile().catch((error) => toast(error.message, "error")));
  $("stop-button").addEventListener("click", () => runtime.stop());
  $("search-button").addEventListener("click", () => openSearchPanel(editorView));
  $("goto-button").addEventListener("click", goToLine);
  $("theme-button").addEventListener("click", toggleTheme);
  $("font-size").addEventListener("input", (event) => $("editor").style.setProperty("--editor-font-size", event.target.value + "px"));
  $("programmer-keyboard").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-key]");
    if (button) handleProgrammerKey(button.dataset.key);
  });
  document.querySelectorAll(".panel-tab").forEach((tab) => tab.addEventListener("click", () => {
    setPanel(tab.dataset.panel);
    if (tab.dataset.panel === "packages" && state.runtimeReady) runtime.refreshPackages("packages");
  }));
  $("panel-toggle").addEventListener("click", () => $("bottom-panel").classList.toggle("collapsed"));
  $("clear-output").addEventListener("click", () => {
    $("output-text").textContent = "";
    $("error-text").textContent = "";
    lastRunError = "";
    $("error-count").textContent = "0";
  });
  $("terminal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = $("terminal-input");
    const command = input.value.trim(); input.value = "";
    try { await runTerminalCommand(command); } catch (error) { appendText($("terminal-text"), error.message + "\n"); }
  });
  $("stdin-form").addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      const value = $("stdin-input").value;
      runtime.submitInput(value);
      appendText($("terminal-text"), value + "\n");
      $("stdin-input").value = "";
      $("stdin-form").classList.add("hidden");
      editorView.focus();
    } catch (error) { toast(error.message, "error"); }
  });
  $("package-install-button").addEventListener("click", () => installPackage());
  $("package-input").addEventListener("keydown", (event) => { if (event.key === "Enter") installPackage(); });
  $("package-list").addEventListener("click", (event) => {
    const row = event.target.closest(".package-row");
    if (row) { $("package-input").value = row.querySelector("strong").textContent; }
  });
  $("active-filename").addEventListener("dblclick", () => renameCurrentFile().catch((error) => toast(error.message, "error")));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) saveNow().catch(() => {});
  });
  window.addEventListener("beforeunload", () => runtime.dispose());
}

async function bootstrap() {
  const project = await ensureStarterProject();
  state.project = await getProject(project.id);
  state.currentPath = Object.keys(state.project.files)[0] || "main.py";
  if (!state.project.files[state.currentPath]) state.project.files[state.currentPath] = "";
  state.openTabs = [state.currentPath];
  renderProjects(await listProjects());
  setupEditor();
  renderFiles(); renderTabs(); updateFileHeading();
  bindEvents();
  setStatus("المشاريع محفوظة محلياً في المتصفح باستخدام IndexedDB.");
  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    const workerUrl = new URL("sw.js", new URL(import.meta.env.BASE_URL, location.origin)).href;
    navigator.serviceWorker.register(workerUrl, { scope: new URL(import.meta.env.BASE_URL, location.origin).pathname })
      .catch((error) => console.warn("Offline cache is unavailable:", error));
  }
  try {
    const ready = await runtime.start();
    $("runtime-state").querySelector("span").textContent = "Python جاهز";
    $("python-version").textContent = "Python " + ready.version;
  } catch (error) {
    $("runtime-state").querySelector("span").textContent = "تعذر تحميل Python";
    $("runtime-state").classList.add("error");
    $("python-version").textContent = "Python غير متاح";
    toast("المحرر يعمل، لكن تعذر تحميل بيئة Python: " + error.message, "error");
  }
}

bootstrap().catch((error) => {
  console.error(error);
  toast("تعذر بدء التطبيق: " + error.message, "error");
  setStatus(error.message);
});