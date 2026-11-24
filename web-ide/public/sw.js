const CACHE_NAME = "python-studio-mobile-v1";
const PYODIDE_PREFIX = "/pyodide/v314.0.7/full/";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith("python-studio-") && name !== CACHE_NAME).map((name) => caches.delete(name)));
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

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
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