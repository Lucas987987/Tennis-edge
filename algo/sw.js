// Game Set Algo — service worker (23/11/2026, paquet 391, Lucas : « installer le site comme une appli »).
// Règles, par prudence :
//  • la PAGE (navigation) : le réseau d'abord, toujours ; la copie gardée ne sert que hors connexion ;
//  • les fichiers à empreinte (app-….js, style-….css), polices et icônes : gardés (ils ne changent jamais sous le même nom) ;
//  • TOUT LE RESTE passe sans être touché : données (site*.json, donnees.json), direct (/live…), comptes (/compte/…),
//    vidéo, Lab. Rien de personnel ni de réservé n'est jamais mis en cache ici.
// Arrêt d'urgence : publier un sw.js qui contient seulement « self.registration.unregister() ».
const CACHE = 'gsa-v1';
const FIXES = /\/(app-[0-9a-f]{12}\.js|style-[0-9a-f]{12}\.css|polices\/[a-z0-9-]+\.woff2|icone-[a-z0-9-]+\.png|apple-touch-icon\.png|manifest\.webmanifest)$/;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function page(req) {
  const c = await caches.open(CACHE);
  try {
    const r = await fetch(req);
    if (r.ok) {
      const html = await r.clone().text();
      await c.put('page', new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
      // ne garder que les fichiers à empreinte que la nouvelle page utilise
      const utiles = new Set((html.match(/(app|style)-[0-9a-f]{12}\.(js|css)/g) || []));
      for (const k of await c.keys()) {
        const m = k.url.match(/(app|style)-[0-9a-f]{12}\.(js|css)$/);
        if (m && !utiles.has(m[0])) await c.delete(k);
      }
    }
    return r;
  } catch (e) {
    const g = await c.match('page');
    if (g) return g;
    throw e;
  }
}

async function fixe(req) {
  const c = await caches.open(CACHE);
  const g = await c.match(req);
  if (g) return g;
  const r = await fetch(req);
  if (r.ok) await c.put(req, r.clone());
  return r;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.mode === 'navigate' && /\/(index\.html)?$/.test(url.pathname) && !url.search.match(/[?&](video|carte|bilan|semaine|projections)=/)) {
    e.respondWith(page(req));
    return;
  }
  if (FIXES.test(url.pathname)) e.respondWith(fixe(req));
});
