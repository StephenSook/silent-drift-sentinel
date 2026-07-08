// Minimal service worker: a network pass-through whose presence (with the
// manifest) makes the app installable to the home screen. No offline caching.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {
  // intentionally pass-through to the network
});
