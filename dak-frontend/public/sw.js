// Dak Sahayak AI — PWA Service Worker
const CACHE_NAME = 'dak-sahayak-v1';
const PRECACHE_URLS = [
  '/chat',
  '/manifest.webmanifest',
  '/manifest.json',
  '/icon-192x192.png',
  '/icon-512x512.png'
];

// 1. Install event: Skip waiting immediately to activate fresh SW
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn('[SW] Pre-caching warning:', err);
      });
    })
  );
});

// 2. Activate event: Claim existing clients and remove old cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            console.log('[SW] Deleting legacy cache:', name);
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Fetch event: Bypass /api/ routes to keep Flask streaming & real-time calls untouched
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Critical: Never intercept or buffer API routes (streaming LLM tokens, SSE, TTS audio, calculators)
  if (url.pathname.startsWith('/api') || request.method !== 'GET') {
    return;
  }

  // Bypass cross-origin requests
  if (url.origin !== self.location.origin) {
    return;
  }

  // Network-first strategy with cache fallback for app shell and assets
  event.respondWith(
    fetch(request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
        }
        return networkResponse;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) {
          return cached;
        }
        if (request.mode === 'navigate') {
          return caches.match('/chat');
        }
      })
  );
});

