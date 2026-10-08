const CACHE_NAME = 'cathealth-v1.0.0';
const urlsToCache = [
  '/',
  '/index.html',
  '/dashboard.html',
  '/auth.js',
  '/hospital-map.js',
  '/manifest.json',
  '/service-worker.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// 安装Service Worker
self.addEventListener('install', function(event) {
  console.log('Service Worker 安装中...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('缓存打开成功');
        return cache.addAll(urlsToCache);
      })
      .then(function() {
        console.log('所有资源缓存成功');
        return self.skipWaiting();
      })
  );
});

// 激活Service Worker
self.addEventListener('activate', function(event) {
  console.log('Service Worker 激活中...');
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            console.log('删除旧缓存:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(function() {
      console.log('Service Worker 激活完成');
      return self.clients.claim();
    })
  );
});

// 拦截请求
self.addEventListener('fetch', function(event) {
  // 只缓存GET请求
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // 如果缓存中有，返回缓存内容
        if (response) {
          return response;
        }

        // 否则从网络获取
        return fetch(event.request).then(function(response) {
          // 检查是否有效响应
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // 克隆响应
          var responseToCache = response.clone();

          caches.open(CACHE_NAME)
            .then(function(cache) {
              cache.put(event.request, responseToCache);
            });

          return response;
        });
      }).catch(function() {
        // 网络请求失败时的处理
        if (event.request.destination === 'document') {
          return caches.match('/index.html');
        }
      })
  );
});
