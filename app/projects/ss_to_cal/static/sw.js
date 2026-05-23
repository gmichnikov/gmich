/* SS to Cal — cache app shell only; extraction/share always uses network */
const CACHE_NAME = "ss-to-cal-shell-v1";
const SHELL_ASSETS = [
  "/ss-to-cal/static/ss_to_cal.css",
  "/ss-to-cal/static/ss_to_cal.js",
  "/ss-to-cal/static/icons/icon-192.png",
  "/ss-to-cal/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        SHELL_ASSETS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn("SS to Cal SW: failed to cache", url, err);
          })
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);

  if (url.pathname.startsWith("/ss-to-cal/share")) {
    return;
  }

  if (url.pathname.startsWith("/ss-to-cal/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const network = fetch(event.request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        });
        return cached || network;
      })
    );
  }
});
