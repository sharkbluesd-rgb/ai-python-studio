import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = fileURLToPath(new URL("..", import.meta.url));
const viteBin = resolve(root, "node_modules/vite/bin/vite.js");
const baseUrl = "http://127.0.0.1:4173/ai-python-studio/";
const server = spawn(process.execPath, [viteBin, "preview", "--host", "127.0.0.1", "--port", "4173", "--strictPort"], {
  cwd: root,
  env: { ...process.env, GITHUB_PAGES: "true" },
  stdio: ["ignore", "pipe", "pipe"],
});

let serverOutput = "";
server.stdout.on("data", (chunk) => { serverOutput += chunk.toString(); });
server.stderr.on("data", (chunk) => { serverOutput += chunk.toString(); });

async function waitForServer() {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {}
    await delay(250);
  }
  throw new Error("Vite preview did not start.\n" + serverOutput);
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  const pageErrors = [];
  const consoleErrors = [];
  const interruptPageErrors = [];
  let stoppingPython = false;
  page.on("pageerror", (error) => {
    if (stoppingPython && /KeyboardInterrupt/.test(error.message)) {
      interruptPageErrors.push(error.message);
    } else {
      pageErrors.push(error.message);
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.querySelector("#runtime-state")?.classList.contains("ready"), undefined, { timeout: 120000 });
  const isolated = await page.evaluate(() => window.crossOriginIsolated);
  assert.equal(isolated, true, "COOP/COEP headers must enable cross-origin isolation for interactive stdin and interrupts.");

  const editor = page.locator("#editor .cm-content");
  await editor.fill("with open('result.txt', 'w', encoding='utf-8') as file:\n    file.write('persisted from Python')\nprint('BROWSER_SMOKE_OK')");
  await page.locator("#save-button").click();
  await page.locator("#run-button").click();
  await page.waitForFunction(() => {
    const output = document.querySelector("#output-text")?.textContent || "";
    const errors = document.querySelector("#error-text")?.textContent || "";
    return output.includes("BROWSER_SMOKE_OK") || errors.includes("Traceback") || errors.includes("Error:");
  }, undefined, { timeout: 60000 });
  const firstRunOutput = await page.locator("#output-text").innerText();
  const firstRunError = await page.locator("#error-text").innerText();
  assert.match(
    firstRunOutput,
    /BROWSER_SMOKE_OK/,
    "Python execution failed. Output: " + firstRunOutput + " | Errors: " + firstRunError
      + " | Status: " + await page.locator("#status-message").innerText()
      + " | Runtime: " + await page.locator("#runtime-state").getAttribute("class")
      + " | Page errors: " + pageErrors.join(" || ")
      + " | Console errors: " + consoleErrors.join(" || "),
  );
  await page.waitForFunction(() => document.querySelector("#stop-button").disabled);

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.querySelector("#runtime-state")?.classList.contains("ready"), undefined, { timeout: 120000 });
  const restoredCode = await page.locator("#editor .cm-content").innerText();
  assert.match(restoredCode, /BROWSER_SMOKE_OK/, "IndexedDB should restore the last saved source after reload.");
  assert.ok(await page.locator("#file-list").getByText("result.txt").count(), "Python-created files should be saved back into the local project.");

  await page.locator("#editor .cm-content").fill('name = input("Your name: ")\nprint("HELLO " + name)');
  await page.locator("#save-button").click();
  await page.locator("#run-button").click();
  await page.locator("#stdin-form").waitFor({ state: "visible" });
  await page.locator("#stdin-input").fill("Python Studio");
  await page.locator("#stdin-form button").click();
  await page.waitForFunction(() => document.querySelector("#output-text").textContent.includes("HELLO Python Studio"));

  await page.locator("#editor .cm-content").fill("def broken(:\n    pass");
  await page.locator("#run-button").click();
  await page.waitForFunction(() => document.querySelector("#error-text").textContent.includes("SyntaxError"));

  await page.locator("#editor .cm-content").fill("while True:\n    pass");
  await page.locator("#run-button").click();
  await page.waitForFunction(() => !document.querySelector("#stop-button").disabled);
  stoppingPython = true;
  await page.locator("#stop-button").click();
  await page.waitForFunction(() => document.querySelector("#stop-button").disabled, undefined, { timeout: 15000 });
  assert.match(await page.locator("#error-text").innerText(), /KeyboardInterrupt|تم إيقاف|Execution interrupted/i);

  await page.locator("#sidebar-toggle").click();
  await page.locator("#file-sidebar.open").waitFor({ state: "visible" });
  await page.locator("#mobile-scrim").click();
  assert.equal(await page.locator("#file-sidebar").evaluate((element) => element.classList.contains("open")), false);

  // Exercise the controls on a real mobile viewport rather than merely checking
  // that the page bundles successfully.
  const lightBefore = await page.locator("body").evaluate((element) => element.classList.contains("light"));
  await page.locator("#theme-button").click();
  assert.notEqual(await page.locator("body").evaluate((element) => element.classList.contains("light")), lightBefore);
  await page.locator("#theme-button").click();

  await page.locator("#search-button").click();
  await page.locator(".cm-search").waitFor({ state: "visible" });
  await page.once("dialog", (dialog) => dialog.accept("1"));
  await page.locator("#goto-button").click();

  await page.locator(".panel-tab[data-panel='terminal']").click();
  await page.locator("#terminal-input").fill("help");
  await page.locator("#terminal-form button").click();
  await page.waitForFunction(() => document.querySelector("#terminal-text").textContent.includes("الأوامر المدعومة"));

  await page.locator("#panel-toggle").click();
  assert.equal(await page.locator("#bottom-panel").evaluate((element) => element.classList.contains("collapsed")), true);
  await page.locator("#panel-toggle").click();
  assert.equal(await page.locator("#bottom-panel").evaluate((element) => element.classList.contains("collapsed")), false);

  await page.locator("#editor .cm-content").fill("value = 10");
  await page.locator('[data-key="("]').click();
  assert.match(await page.locator("#editor .cm-content").innerText(), /\(/, "Programmer keyboard buttons should insert characters into the editor.");
  await page.locator("#font-size").evaluate((element) => {
    element.value = "18";
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });

  const promptQueue = [];
  page.on("dialog", async (dialog) => {
    if (dialog.type() === "prompt") await dialog.accept(promptQueue.shift() ?? "");
    else await dialog.accept();
  });
  await page.locator("#sidebar-toggle").click();
  promptQueue.push("UI Controls Project");
  await page.locator("#new-project").click();
  await page.waitForFunction(() => Array.from(document.querySelector("#project-select").options).some((option) => option.textContent === "UI Controls Project"));

  promptQueue.push("tools/demo.py");
  await page.locator("#new-file").click();
  await page.locator('#file-list button[data-path="tools/demo.py"]').waitFor({ state: "visible" });
  await page.locator('#file-list button[data-path="tools/demo.py"]').click();
  await page.locator("#sidebar-toggle").click();
  await page.locator("#file-sidebar.open").waitFor({ state: "visible" });
  await page.locator("#editor .cm-content").fill("print('FILE_BUTTON_OK')");
  await page.locator("#save-button").click();

  promptQueue.push("tools/renamed.py");
  await page.locator("#rename-file").click();
  await page.locator('#file-list button[data-path="tools/renamed.py"]').waitFor({ state: "visible" });

  promptQueue.push("tools/copy.py");
  await page.locator("#duplicate-file").click();
  await page.locator('#file-list button[data-path="tools/copy.py"]').waitFor({ state: "visible" });
  await page.locator("#delete-file").click();
  await page.locator('#file-list button[data-path="tools/copy.py"]').waitFor({ state: "detached" });

  promptQueue.push("assets/icons");
  await page.locator("#new-folder").click();
  await page.locator('#file-list button[data-path="assets/icons"]').waitFor({ state: "visible" });

  promptQueue.push("Renamed UI Controls Project");
  await page.locator("#rename-project").click();
  await page.waitForFunction(() => Array.from(document.querySelector("#project-select").options).some((option) => option.textContent === "Renamed UI Controls Project"));

  await page.locator("#file-picker").setInputFiles({
    name: "imported.py",
    mimeType: "text/x-python",
    buffer: Buffer.from("print('IMPORTED_OK')\n"),
  });
  await page.waitForFunction(() => Boolean(document.querySelector('#file-list button[data-path="imported.py"]')));

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export-zip").click();
  const download = await downloadPromise;
  assert.match(download.suggestedFilename(), /\.zip$/);

  assert.deepEqual(pageErrors, [], "The browser page should not throw unexpected JavaScript errors.");
  assert.deepEqual(consoleErrors, [], "The browser console should not report unexpected errors.");
  assert.ok(
    interruptPageErrors.every((message) => message.includes("KeyboardInterrupt")),
    "Only the expected Python KeyboardInterrupt may surface while cancelling a running program.",
  );
  console.log("Browser smoke passed: Python execution, persistence, input(), errors, Stop, mobile navigation and editor/project controls.");
  await context.close();
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
}