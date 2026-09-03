const CACHE_NAME = "aquarappel-cache-v5";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./css/style.css",
  "./js/vendor/supabase.js",
  "./js/config.js",
  "./js/supabaseClient.js",
  "./js/auth.js",
  "./js/app.js",
  "./js/chat.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-512-maskable.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  // Ne jamais mettre en cache les appels vers Supabase (données live : tâches,
  // authentification, assistant). Seuls les fichiers de l'appli elle-même
  // (même origine) passent par le cache pour le fonctionnement hors-ligne.
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Réseau en priorité, pour toujours servir la dernière version déployée
  // quand l'appareil est en ligne. Le cache ne sert qu'en secours (hors-ligne
  // ou réseau en échec) — jamais comme réponse "par défaut" qui retarderait
  // la prise en compte d'une mise à jour.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Reçoit les notifications push envoyées par la fonction serveur "send-reminders",
// même quand l'appli n'est pas ouverte.
self.addEventListener("push", (event) => {
  let payload = { title: "AquaRappel", body: "Tu as des tâches à faire." };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch {
    // Corps non-JSON : on garde le message par défaut.
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "./icons/icon-192.png",
      badge: "./icons/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsList) => {
      for (const client of clientsList) {
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow("./");
    })
  );
});
