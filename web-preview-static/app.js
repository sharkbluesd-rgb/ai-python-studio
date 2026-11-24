"use strict";
const $ = (id) => document.getElementById(id);
const state = { csrf: "", project: null, authenticated: false, polling: false, pollTimer: null };
const input = $("project-zip");
const zone = $("upload-zone");
const fileState = $("file-state");
const message = $("preview-message");

function announce(text, kind = "info") {
  message.textContent = text;
  message.dataset.kind = kind;
}
function setConnection(text, connected = false) {
  const badge = document.querySelector(".connection-state");
  badge.textContent = text;
  badge.classList.toggle("connected", connected);
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.csrf && options.method && options.method !== "GET") {
    headers.set("X-CSRF-Token", state.csrf);
  }
  const response = await fetch(path, {
    ...options, headers, credentials: "same-origin",
  });
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = payload && payload.detail;
    const text = typeof detail === "string" ? detail : detail?.message || JSON.stringify(detail || "تعذر تنفيذ الطلب.");
    throw new Error(text || "تعذر تنفيذ الطلب.");
  }
  return payload;
}
async function initialize() {
  try {
    let session;
    try {
      session = await api("/api/session");
    } catch (error) {
      if (!String(error.message).includes("الجلسة") && !String(error.message).includes("انتهت")) throw error;
      const created = await api("/api/session", { method: "POST" });
      state.csrf = created.csrf_token;
      session = await api("/api/session");
    }
    state.csrf = session.csrf_token || state.csrf;
    state.authenticated = session.authenticated;
    if (session.project) {
      state.project = session.project;
      fileState.textContent = "المشروع الحالي: " + session.project.name;
      await refreshProject();
    }
    if (state.authenticated) {
      const user = await api("/api/github/me");
      setConnection("متصل: @" + user.login, true);
    }
    document.querySelector(".header-state").innerHTML = "<i></i> خدمة الويب متصلة";
    announce("اتصلت المنصة بالخادم. يمكنك رفع مشروع Flet أو إنشاء قالب.");
  } catch (error) {
    announce("تعذر الاتصال بالخادم: " + error.message, "error");
  }
}
async function refreshProject() {
  const current = await api("/api/projects/current");
  state.project = current.project;
  const summary = current.ready
    ? "المشروع جاهز مبدئياً للبناء · " + current.files.length + " ملف"
    : "المشروع يحتاج معالجة: " + current.issues.join("، ");
  fileState.textContent = current.project.name + " — " + summary;
  announce(summary, current.ready ? "success" : "warning");
}
$("choose-zip").addEventListener("click", () => input.click());
input.addEventListener("change", async () => {
  const file = input.files && input.files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip") || file.size > 12 * 1024 * 1024) {
    fileState.textContent = "اختر ZIP لا يتجاوز 12 MB";
    announce("لم يتم قبول الملف. تحقق من النوع والحجم.", "error");
    input.value = "";
    return;
  }
  const data = new FormData();
  data.append("file", file, file.name);
  announce("جارٍ رفع المشروع وفحص محتويات ZIP...");
  try {
    const result = await api("/api/projects/import", { method: "POST", body: data });
    state.project = result.project;
    fileState.textContent = "تم رفع: " + result.project.name;
    announce(result.issues.length ? "تم استيراد المشروع، لكن توجد متطلبات: " + result.issues.join("، ") : "تم استيراد المشروع واجتاز الفحص الأولي.", result.issues.length ? "warning" : "success");
  } catch (error) {
    announce(error.message, "error");
  }
});
["dragenter", "dragover"].forEach(type => zone.addEventListener(type, event => {
  event.preventDefault(); zone.classList.add("drag");
}));
["dragleave", "drop"].forEach(type => zone.addEventListener(type, event => {
  event.preventDefault(); zone.classList.remove("drag");
}));
zone.addEventListener("drop", event => {
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
  input.dispatchEvent(new Event("change"));
});
$("starter-btn").addEventListener("click", async () => {
  try {
    announce("جارٍ إنشاء قالب Flet Android...");
    const result = await api("/api/projects/starter", { method: "POST" });
    state.project = result.project;
    fileState.textContent = "تم إنشاء: " + result.project.name;
    await refreshProject();
  } catch (error) { announce(error.message, "error"); }
});
$("connect-btn").addEventListener("click", async () => {
  const clientId = $("oauth-client-id").value.trim();
  if (!clientId) { announce("أدخل GitHub OAuth Client ID أولاً.", "warning"); return; }
  try {
    const result = await api("/api/auth/github/device/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId }),
    });
    $("device-info").hidden = false;
    $("device-code").textContent = result.user_code;
    $("device-link").href = result.verification_uri;
    $("device-link").textContent = "افتح GitHub لإدخال الرمز";
    announce("أدخل رمز التحقق في GitHub، ثم اترك الصفحة مفتوحة. جارٍ انتظار الموافقة...");
    if (state.pollTimer) clearInterval(state.pollTimer);
    const poll = async () => {
      try {
        const status = await api("/api/auth/github/device/poll", { method: "POST" });
        if (status.authorized) {
          clearInterval(state.pollTimer); state.pollTimer = null;
          state.authenticated = true;
          setConnection("متصل: @" + status.user.login, true);
          $("device-info").hidden = true;
          announce("تم ربط حساب GitHub بنجاح.", "success");
        }
      } catch (error) {
        clearInterval(state.pollTimer); state.pollTimer = null;
        announce(error.message, "error");
      }
    };
    state.pollTimer = setInterval(poll, Math.max(5, result.interval) * 1000);
  } catch (error) { announce(error.message, "error"); }
});
$("repos-btn").addEventListener("click", async () => {
  try {
    const result = await api("/api/github/repos");
    const names = result.repositories.map(item => item.full_name);
    if (!names.length) { announce("لا توجد مستودعات متاحة في الحساب.", "warning"); return; }
    const chosen = window.prompt("مستودعات GitHub المتاحة:\n" + names.join("\n") + "\n\nاكتب اسم المستودع owner/repository:");
    if (chosen && names.includes(chosen.trim())) {
      $("repository").value = chosen.trim();
      const found = result.repositories.find(item => item.full_name === chosen.trim());
      if (found?.default_branch) $("branch").value = found.default_branch;
      announce("تم اختيار " + chosen.trim(), "success");
    }
  } catch (error) { announce(error.message, "error"); }
});
$("new-repo-btn").addEventListener("click", async () => {
  const name = window.prompt("اكتب اسم المستودع الجديد:");
  if (!name) return;
  try {
    const result = await api("/api/github/repos", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), private: true }),
    });
    $("repository").value = result.full_name;
    $("branch").value = result.default_branch || "main";
    announce("تم إنشاء المستودع الخاص: " + result.full_name, "success");
  } catch (error) { announce(error.message, "error"); }
});
async function configure() {
  return api("/api/projects/configure", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      app_name: $("app-name").value.trim(),
      application_id: $("application-id").value.trim(),
      version: $("app-version").value.trim(),
      build_number: $("build-number").value.trim(),
    }),
  });
}
$("build-btn").addEventListener("click", async () => {
  if (!state.project) { announce("ارفع مشروع Flet أو أنشئ قالباً أولاً.", "warning"); return; }
  const fullName = $("repository").value.trim().split("/");
  if (fullName.length !== 2 || !fullName[0] || !fullName[1]) {
    announce("اكتب اسم المستودع بالصيغة owner/repository.", "warning"); return;
  }
  try {
    announce("جارٍ حفظ إعدادات Android وفحص المشروع...");
    const configured = await configure();
    if (!configured.ready) {
      announce("المشروع غير جاهز: " + configured.issues.join("، "), "warning"); return;
    }
    announce("جارٍ رفع المشروع إلى GitHub وتشغيل البناء السحابي...");
    const result = await api("/api/build/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner: fullName[0], repository: fullName[1], branch: $("branch").value.trim() || "main" }),
    });
    $("download-btn").hidden = true;
    announce(result.message, "success");
    await refreshBuild();
  } catch (error) { announce(error.message, "error"); }
});
async function refreshBuild() {
  try {
    const result = await api("/api/build/status");
    if (!result.found) { announce(result.message); return; }
    const summary = (result.jobs || []).map(job => {
      const steps = (job.steps || []).map(step => step.name + ": " + (step.conclusion || step.status)).join(" · ");
      return job.name + ": " + (job.conclusion || job.status) + (steps ? "\n" + steps : "");
    }).join("\n");
    announce("حالة البناء: " + result.status + (result.conclusion ? " — " + result.conclusion : "") + (summary ? "\n" + summary : ""), result.conclusion === "success" ? "success" : result.conclusion === "failure" ? "error" : "info");
    if (result.html_url) $("actions-link").href = result.html_url;
    if (result.status === "completed") {
      if (result.conclusion === "success") $("download-btn").hidden = false;
      if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
    } else if (!state.pollTimer) {
      state.pollTimer = setInterval(refreshBuild, 8000);
    }
  } catch (error) { announce(error.message, "error"); }
}
$("refresh-btn").addEventListener("click", refreshBuild);
$("download-btn").addEventListener("click", async event => {
  event.preventDefault();
  try {
    const response = await fetch("/api/build/download", { credentials: "same-origin" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "تعذر تنزيل APK.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "flet-app.apk";
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    URL.revokeObjectURL(url);
    announce("تم تجهيز تنزيل ملف APK.", "success");
  } catch (error) { announce(error.message, "error"); }
});
initialize();
