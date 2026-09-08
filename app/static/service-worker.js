// Offline-first support for the SIF Precursor Detection portal.
// Caches the static app shell so the login/report screens still open
// without a connection (critical for remote sites like Baghjan), and
// falls back to offline.html for uncached page navigations.

const CACHE_NAME = "sif-shell-v1";
const SHELL_ASSETS = [
  "/static/manifest.json",
  "/static/offline.html",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Never intercept POSTs (report submissions) — let the app's own
  // offline-queue JS (offline-sync.js) handle those.
  if (req.method !== "GET") return;

  if (req.mode === "navigate") {
    // Network-first for pages, fall back to cached offline page.
    event.respondWith(
      fetch(req).catch(() => caches.match("/static/offline.html"))
    );
    return;
  }

  // Cache-first for static assets.
  event.respondWith(
    caches.match(req).then((cached) => cached || fetch(req))
  );
});