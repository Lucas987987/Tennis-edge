// tennis-edge-db — Worker Cloudflare de l'ancienne page publique « Tennis Edge » (hypothèses gelées).
//
// FERMÉE LE 22/11/2026 (paquet 345, cotes en privé — étape 2). Cette page publique lisait verdicts_direct.json sur
// GitHub et affichait, pour chaque hypothèse, sa CLV contre la clôture : la comparaison avec les cotes de clôture est
// privée. verdicts_direct.json est désormais au coffre privé (R2) et sort du dépôt public ; les verdicts se lisent
// dans le Lab, derrière la connexion (worker « algo »).
// /api/hypotheses répond « prive » sans aucune donnée : la capture du Lab (fetch_worker_snapshot.py) garde alors sa
// capture précédente, comme pour toute panne. Aucun binding, aucun cron, aucune lecture extérieure.

const MESSAGE = 'Page fermée : les verdicts des hypothèses sont désormais privés.';

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/api/hypotheses' || url.pathname === '/api/verif') {
      return new Response(JSON.stringify({ status: 'prive', message: MESSAGE, hypotheses: [] }, null, 1), {
        status: 410,
        headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
      });
    }
    if (url.pathname === '/' || url.pathname === '/index.html') {
      return new Response(page(), {
        status: 410,
        headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex' },
      });
    }
    return new Response('introuvable', { status: 404 });
  },
};

export function page() {
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Page fermée</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0E0A24;color:#F4F1FF;font:16px/1.5 system-ui,sans-serif}main{max-width:32rem;padding:2rem;text-align:center}p{color:#ABA3D6}</style></head>
<body><main><h1>Page fermée</h1><p>${MESSAGE}</p></main></body></html>`;
}
