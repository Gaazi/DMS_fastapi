const CACHE_NAME = 'dms-premium-cache-v3';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/css/fonts.css',
  '/static/css/main.css',
  '/static/offline.html',
  '/static/icons/logo.webp',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/js/vendors/tailwindcss.js',
  '/static/js/vendors/htmx.min.js',
  '/static/js/vendors/alpine.min.js',
  '/static/js/vendors/chart.umd.min.js',
  '/static/css/fontawesome.all.min.css',
  '/static/webfonts/fa-solid-900.woff2',
  '/static/fonts/mehr.woff2',
  '/static/fonts/google/Amiri-Regular.ttf'
];

// 1. Install Event: High-Priority Cache
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
});

// 2. Activate Event: Clean old junk
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
    })
  );
  self.clients.claim();
});

// 3. Fetch Event: Ultra-Smart Routing
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // --- BUGFIX 1: Ignore non-HTTP/HTTPS requests (like chrome-extension://) to prevent fatal crashes ---
  if (!url.protocol.startsWith('http')) {
    return;
  }

  const isHTMX = request.headers.has('HX-Request') || request.headers.has('hx-request');

  // --- BUGFIX 2: Prevent caching for non-GET requests (POST, PUT, DELETE) ---
  if (request.method !== 'GET') {
    event.respondWith(
      fetch(request).catch(error => {
        // If offline during a POST navigation (rare but possible), show offline page
        if (request.mode === 'navigate') {
          return caches.match('/static/offline.html');
        }

        // If it's an HTMX POST/PUT/DELETE, return an elegant offline message snippet!
        if (isHTMX) {
          return new Response(
            '<div class="p-3 mb-4 bg-red-50 text-red-600 rounded-lg text-sm text-center border border-red-200 shadow-sm"><i class="fa-solid fa-wifi mr-2"></i> No Internet Connection. Action failed.</div>',
            { status: 200, headers: { 'Content-Type': 'text/html' } }
          );
        }

        throw error;
      })
    );
    return;
  }

  // --- HANDLER 1: Navigation Requests (Offline Fallback Support) ---
  // Applies to ALL navigation requests (Dynamic or Static)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(networkResponse => {
          // BUGFIX 3: Only cache valid/successful responses (Do not cache 404s or 500s)
          if (networkResponse.ok) {
            const resClone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, resClone));
          }
          return networkResponse;
        })
        .catch(() => {
          return caches.match(request).then(cachedResponse => {
            if (cachedResponse) return cachedResponse;
            return caches.match('/static/offline.html');
          });
        })
    );
    return;
  }

  // --- HANDLER 2: HTMX / Dynamic Data (Network Only -> Cache Fallback) ---
  const isDynamicRoute =
    url.pathname.includes('/in/') ||
    url.pathname.includes('/out/') ||
    url.pathname.includes('/balance/') ||
    url.pathname.includes('/fees/') ||
    url.pathname.includes('/donor/');

  if (isHTMX || isDynamicRoute) {
    event.respondWith(
      fetch(request)
        .then(res => {
          // BUGFIX 4: Do NOT cache HTMX responses! 
          // If we cache HTMX partials, they will overwrite the full-page cache for the same URL, ruining the offline navigation experience.
          if (res.ok && !isHTMX) {
            const resClone = res.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, resClone));
          }
          return res;
        })
        .catch(() => {
          // For HTMX GET requests when offline, show a nice inline alert
          if (isHTMX) {
            return new Response(
              '<div class="p-3 mb-4 bg-red-50 text-red-600 rounded-lg text-sm text-center border border-red-200 shadow-sm"><i class="fa-solid fa-wifi mr-2"></i> No Internet Connection. Data could not be loaded.</div>',
              { status: 200, headers: { 'Content-Type': 'text/html' } }
            );
          }
          return caches.match(request);
        })
    );
    return;
  }

  // --- HANDLER 3: Static Assets (Cache First -> Network Fallback) ---
  if (request.destination === 'font' || request.destination === 'image' || url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cachedResponse => {
        return cachedResponse || fetch(request).then(networkResponse => {
          if (networkResponse.ok) {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, networkResponse.clone()); // Update cache dynamically
            });
          }
          return networkResponse;
        }).catch(() => {
          // Silently fail network block for static assets if offline
        });
      })
    );
    return;
  }

  // --- HANDLER 4: Default Fallback ---
  event.respondWith(fetch(request).catch(() => caches.match(request)));
});
