const CACHE = 'ranger-intel-banner-refresh-v4';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('ranger-intel-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  // The report is always network-only, including on an offline launch.
  if (url.pathname.includes('/data/')) {
    event.respondWith(fetch(new Request(event.request, {cache:'no-store'})));
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(new Request(event.request, {cache:'no-cache'})).then(response => {
      if (response.ok) {const copy = response.clone(); event.waitUntil(caches.open(CACHE).then(cache => cache.put('./index.html', copy)));}
      return response;
    }).catch(() => caches.match('./index.html')));
    return;
  }
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
