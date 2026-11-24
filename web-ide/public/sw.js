const CACHE_NAME = "python-studio-mobile-v3";
const PYODIDE_PREFIX = "/pyodide/v314.0.8/full/";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith("python-studio-") && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;
  const pyodideCdn = url.hostname === "cdn.jsdelivr.net" && url.pathname.includes(PYODIDE_PREFIX);
  if (!sameOrigin && !pyodideCdn) return;

  const isNavigation = sameOrigin && (
    request.mode === "navigate" || /\\.html?$/i.test(url.pathname)
  );

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);

    // Always revalidate the app shell so a deployment cannot remain stuck on
    // an old HTML entry point and old hashed JavaScript bundles.
    if (isNavigation) {
      try {
        const response = await fetch(request, { cache: "no-cache" });
        if (response.ok) {
          try { await cache.put(request, response.clone()); } catch {}
        }
        return response;
      } catch (error) {
        const cached = await cache.match(request);
        if (cached) return cached;
        const appShell = await cache.match(new URL("./", self.registration.scope).href);
        if (appShell) return appShell;
        throw error;
      }
    }

    // Hashed local assets and versioned Pyodide files are safe to cache-first.
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
      const response = await fetch(request);
      if (response.ok || response.type === "opaque") {
        try { await cache.put(request, response.clone()); } catch {}
      }
      return response;
    } catch (error) {
      if (sameOrigin) {
        const fallback = await cache.match(new URL("./", self.registration.scope).href);
        if (fallback) return fallback;
      }
      throw error;
    }
  })());
});
