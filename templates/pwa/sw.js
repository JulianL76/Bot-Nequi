// Service worker para Gestor Nequi (PWA instalable + notificaciones push).
//
// El nombre del caché lleva la versión del despliegue: al cambiar, el bloque
// "activate" borra los cachés viejos. Sin esto, un celular con la app ya
// instalada podía seguir sirviendo CSS/JS de una versión anterior para siempre.
const CACHE = "nequi-{{ cache_version }}";
const SHELL = ["/"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  // Red primero; si falla (offline), intentar caché.
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (req.url.includes("/static/")) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match("/")))
  );
});

// --- Notificaciones push -------------------------------------------------
// El navegador despierta este worker aunque la app esté cerrada. El servidor
// manda {titulo, mensaje, url} (ver comprobantes/notifications.py).
self.addEventListener("push", (e) => {
  let d = { titulo: "Gestor Nequi", mensaje: "", url: "/" };
  try { d = Object.assign(d, e.data.json()); } catch (err) {}
  e.waitUntil(
    self.registration.showNotification(d.titulo, {
      body: d.mensaje,
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
      data: { url: d.url },
      // Mismo tag => una notificación reemplaza a la anterior en vez de apilar.
      tag: "nequi",
      renotify: true,
    })
  );
});

// Al tocarla: enfocar la pestaña ya abierta si la hay, o abrir una nueva.
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const destino = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((lista) => {
      for (const c of lista) {
        if ("focus" in c) { c.navigate(destino); return c.focus(); }
      }
      return self.clients.openWindow(destino);
    })
  );
});
