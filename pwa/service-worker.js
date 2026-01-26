/**
 * RealAgent Progressive Web App Service Worker
 * Handles offline functionality, caching, background sync, and push notifications
 * Version: 1.0.0
 */

// Cache versioning - increment to force cache update
const CACHE_VERSION = 'realagent-v1.0.0';
const DYNAMIC_CACHE = 'realagent-dynamic-v1.0.0';
const IMAGE_CACHE = 'realagent-images-v1.0.0';

// Assets to cache immediately on install
const STATIC_ASSETS = [
  '/pwa/offline.html',
  '/pwa/assets/icon-192.png',
  '/pwa/assets/icon-512.png',
  '/pwa/pwa-init.js',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400&display=swap'
];

// Cache strategies for different resource types
const CACHE_STRATEGIES = {
  'cache-first': [
    /\.webp$/,
    /\.jpg$/,
    /\.jpeg$/,
    /\.png$/,
    /\.gif$/,
    /fonts\.(googleapis|gstatic)\.com/
  ],
  'network-first': [
    /\/index\.html$/,
    /\/manifest\.json$/,
    /\/999-.*\/$/
  ],
  'stale-while-revalidate': [
    /\.css$/,
    /\.js$/,
    /tile\.openstreetmap\.org/
  ]
};

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing...');
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      console.log('[ServiceWorker] Caching static assets');
      return cache.addAll(STATIC_ASSETS.map(url => {
        return new Request(url, { mode: 'cors' });
      })).catch(err => {
        console.warn('[ServiceWorker] Failed to cache some static assets:', err);
      });
    })
  );
  // Force immediate activation
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter(name => name.startsWith('realagent-') && name !== CACHE_VERSION && name !== DYNAMIC_CACHE && name !== IMAGE_CACHE)
          .map(name => {
            console.log('[ServiceWorker] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    })
  );
  // Take control of all pages immediately
  self.clients.claim();
});

// Fetch event - implement caching strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Determine caching strategy
  let strategy = 'network-first'; // default
  
  for (const [strategyName, patterns] of Object.entries(CACHE_STRATEGIES)) {
    if (patterns.some(pattern => pattern.test(url.href))) {
      strategy = strategyName;
      break;
    }
  }

  event.respondWith(handleRequest(request, strategy));
});

// Request handler with different strategies
async function handleRequest(request, strategy) {
  const url = new URL(request.url);
  
  switch (strategy) {
    case 'cache-first':
      return cacheFirst(request);
    case 'network-first':
      return networkFirst(request);
    case 'stale-while-revalidate':
      return staleWhileRevalidate(request);
    default:
      return fetch(request);
  }
}

// Cache-first strategy (images, fonts)
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(IMAGE_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Return offline page if available
    const offline = await caches.match('/pwa/offline.html');
    return offline || new Response('Offline', { status: 503 });
  }
}

// Network-first strategy (HTML pages)
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    
    // For HTML requests, return offline page
    if (request.headers.get('accept').includes('text/html')) {
      const offline = await caches.match('/pwa/offline.html');
      return offline || new Response('Offline', { status: 503 });
    }
    
    return new Response('Network error', { status: 503 });
  }
}

// Stale-while-revalidate strategy (CSS, JS, map tiles)
async function staleWhileRevalidate(request) {
  const cached = await caches.match(request);
  
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      const cache = caches.open(DYNAMIC_CACHE);
      cache.then(c => c.put(request, response.clone()));
    }
    return response;
  }).catch(() => cached);
  
  return cached || fetchPromise;
}

// Push notification handling removed for clean PWA experience

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Background sync:', event.tag);
  
  if (event.tag === 'sync-favorites') {
    event.waitUntil(syncFavorites());
  } else if (event.tag === 'sync-inquiries') {
    event.waitUntil(syncInquiries());
  }
});

// Sync favorites to server when online
async function syncFavorites() {
  try {
    const cache = await caches.open('realagent-data');
    const requests = await cache.keys();
    const favorites = requests
      .filter(req => req.url.includes('/api/favorites'))
      .map(req => cache.match(req).then(res => res.json()));
    
    const data = await Promise.all(favorites);
    
    if (data.length > 0) {
      await fetch('/api/sync/favorites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      // Clear synced data
      for (const req of requests.filter(r => r.url.includes('/api/favorites'))) {
        await cache.delete(req);
      }
    }
  } catch (error) {
    console.error('[ServiceWorker] Sync failed:', error);
    throw error; // Retry later
  }
}

// Sync property inquiries when online
async function syncInquiries() {
  try {
    const cache = await caches.open('realagent-data');
    const requests = await cache.keys();
    const inquiries = requests
      .filter(req => req.url.includes('/api/inquiries'))
      .map(req => cache.match(req).then(res => res.json()));
    
    const data = await Promise.all(inquiries);
    
    if (data.length > 0) {
      await fetch('/api/sync/inquiries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      // Clear synced data
      for (const req of requests.filter(r => r.url.includes('/api/inquiries'))) {
        await cache.delete(req);
      }
    }
  } catch (error) {
    console.error('[ServiceWorker] Inquiry sync failed:', error);
    throw error;
  }
}

// Notification handlers removed for clean PWA experience

// Message handling for client-service worker communication
self.addEventListener('message', (event) => {
  console.log('[ServiceWorker] Message received:', event.data);
  
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then(names => Promise.all(
        names.map(name => caches.delete(name))
      ))
    );
  } else if (event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(DYNAMIC_CACHE).then(cache => 
        cache.addAll(event.data.urls)
      )
    );
  }
});
