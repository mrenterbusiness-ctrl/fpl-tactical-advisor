// أسمع مني — Service Worker للعمل أوفلاين مع استراتيجية Network-First
const CACHE_NAME = 'asma3-meny-v3';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            console.log('[SW] مسح الكاش القديم:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  
  // لطلبات الـ API لا نلجأ للكاش ونمررها مباشرة للسيرفر
  if (event.request.url.includes('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // استراتيجية Network-First للأصول الثابتة وصفحات HTML
  event.respondWith(
    fetch(event.request).then(networkResp => {
      if (networkResp && networkResp.status === 200) {
        const respClone = networkResp.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, respClone);
        });
      }
      return networkResp;
    }).catch(() => {
      // في حالة انقطاع الاتصال (Offline) نلجأ للكاش
      return caches.match(event.request).then(cachedResp => {
        if (cachedResp) return cachedResp;
        if (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html')) {
          return caches.match('/index.html');
        }
      });
    })
  );
});
