/* HostTalk service worker.
   Install and offline use need a secure context, so this runs on localhost or
   behind an HTTPS proxy. Plain LAN HTTP browsers skip registration. */
const CACHE = "hosttalk-shell-2.1.0-room";
const SHELL = [
  "/room",
  "/static/css/tokens.css",
  "/static/css/base.css",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/core.js",
  "/static/js/render.js",
  "/static/fonts/archivo-var.woff2",
  "/static/fonts/public-sans-400.woff2",
  "/static/fonts/public-sans-500.woff2",
  "/static/fonts/public-sans-600.woff2",
  "/static/icons/icon-192.png",
  "/static/icons/favicon.ico"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/healthz") return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (url.pathname === "/room") {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put("/room", copy));
          }
          return response;
        })
        .catch(() => caches.match("/room"))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
            return response;
          })
      )
    );
  }
});
