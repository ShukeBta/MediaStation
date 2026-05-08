/* Service Worker - MediaStation PWA
 * 缓存策略：
 * - 静态资源（JS/CSS/字体）：Cache First，长期缓存
 * - API 请求：Network Only，不缓存
 * - 图标/图片：Stale While Revalidate
 * - HTML：Network First，回退到缓存
 */

const CACHE_NAME = 'mediastation-v1';
const STATIC_CACHE = 'mediastation-static-v1';

// 需要预缓存的关键资源（安装时缓存）
const PRECACHE_URLS = [
  '/',
  '/index.html',
];

// 安装：预缓存关键资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key !== STATIC_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// 请求拦截
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 非同源请求不处理（API 等）
  if (url.origin !== location.origin) return;

  // API 请求直接走网络
  if (url.pathname.startsWith('/api/')) return;

  // 静态资源：Cache First
  if (
    url.pathname.match(/\.(js|css|woff2?|ttf|eot|svg)$/) ||
    url.pathname.includes('/assets/')
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // 图片/图标：Stale While Revalidate
  if (url.pathname.match(/\.(png|jpg|jpeg|gif|webp|avif|ico)$/)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const fetchPromise = fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // HTML 页面：Network First，回退缓存
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then((cached) => {
          // 必须返回非 null 的 Response，否则抛 TypeError
          if (cached) return cached;
          // 离线且无缓存：返回根路由缓存（SPA fallback）
          return caches.match('/') || new Response('Offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' },
          });
        })
      )
  );
});
