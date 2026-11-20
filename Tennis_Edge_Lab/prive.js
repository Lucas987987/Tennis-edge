/* Coffre privé du Lab (23/10/2026).
 * Les fichiers des canaux privés (H19 : valeur.json, H20 : h20.json) et le pronostic complet du jour
 * (pronostics.json) ne sont plus publiés sur GitHub Pages : ils sont dans R2, servis par le worker « algo »
 * uniquement avec la clé privée. Ce script, chargé AVANT les autres, redirige leurs lectures vers le worker.
 *
 * Clé : ouvrir UNE fois le Lab avec ?cle=VOTRE_CLE dans l'adresse (le secret CLE_PRIVEE). Elle est gardée dans
 * ce navigateur seulement, puis retirée de l'adresse. Sans clé, ces sections restent vides — rien d'autre ne change.
 * Oublier la clé sur cet appareil : ?cle=oublier
 */
(function () {
  'use strict';
  var COFFRE = 'https://algo.tennis-edge.workers.dev/prive/';
  var PRIVES = /(?:^|\/)live\/(valeur\.json|h20\.json|pronostics\.json)(?:[?#].*)?$/;
  var cle = null;
  try {
    var u = new URL(location.href), q = u.searchParams.get('cle');
    if (q === 'oublier') { localStorage.removeItem('te_cle_coffre'); }
    else if (q) { localStorage.setItem('te_cle_coffre', q); }
    if (q) { u.searchParams.delete('cle'); history.replaceState(null, '', u.pathname + u.search + u.hash); }
    cle = localStorage.getItem('te_cle_coffre');
  } catch (e) { /* stockage indisponible : pas de coffre */ }
  if (!window.fetch) return;
  var origine = window.fetch.bind(window);
  window.fetch = function (entree, init) {
    var url = typeof entree === 'string' ? entree : (entree && entree.url) || '';
    var m = PRIVES.exec(url);
    if (!m) return origine(entree, init);
    if (!cle) return Promise.resolve(new Response('Coffre : clé absente sur cet appareil.', { status: 401 }));
    return origine(COFFRE + m[1], { headers: { 'X-Cle': cle }, cache: 'no-store' });
  };
})();
