"""Service Worker JS servi depuis le backend."""
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

SW_JS = """
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Okeder';
  const options = {
    body:  data.body  || 'Your group outing update',
    icon:  data.icon  || '/icon-192.png',
    badge: '/icon-192.png',
    data:  { url: data.url || '/' },
    vibrate: [200, 100, 200],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});

self.addEventListener('install',  () => self.skipWaiting());
self.addEventListener('activate', () => clients.claim());
"""

@router.get("/sw.js")
async def service_worker():
    return Response(
        content=SW_JS,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )
