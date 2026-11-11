const TILE_CACHE = 'watermap-tiles-v1';
const TILE_HOSTS = ['server.arcgisonline.com', 'tile.openstreetmap.org'];
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (!TILE_HOSTS.includes(url.hostname)) return;
  event.respondWith(caches.open(TILE_CACHE).then(async cache => {
    const cached = await cache.match(event.request);
    if (cached) return cached;
    try {
      const response = await fetch(event.request);
      if (response.ok || response.type === 'opaque') cache.put(event.request, response.clone());
      return response;
    } catch (error) {
      return cached || Response.error();
    }
  }));
});
