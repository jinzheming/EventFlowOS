/* EventFlowOS Service Worker: static shell cache-first, /api always network (no data cache). */
const SHELL_CACHE = 'pa-shell-v2';
const SHELL_ASSETS = ['/manifest.webmanifest', '/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== SHELL_CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  if (url.pathname.startsWith('/assets/')) {
    // vite hashed assets: cache-first，内容寻址天然安全
    event.respondWith(
      caches.open(SHELL_CACHE).then((cache) =>
        cache.match(event.request).then(
          (hit) =>
            hit ??
            fetch(event.request).then((response) => {
              cache.put(event.request, response.clone());
              return response;
            }),
        ),
      ),
    );
    return;
  }
  // 导航请求: network-first，离线回退缓存壳
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // 成功导航后刷新缓存副本，离线时回退到最新见过的壳
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put('/index.html', copy));
          return response;
        })
        .catch(() => caches.match('/index.html')),
    );
  }
});

self.addEventListener('push', (event) => {
  let data = { title: '事项提醒', body: '' };
  try {
    data = { ...data, ...(event.data ? event.data.json() : {}) };
  } catch {
    /* 非 JSON 负载使用默认值 */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, { body: data.body, icon: '/icon.svg', tag: 'pa-reminder' }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((client) => 'focus' in client);
      if (existing) return existing.focus();
      return self.clients.openWindow('/');
    }),
  );
});
