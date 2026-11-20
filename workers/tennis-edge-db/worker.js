// tennis-edge-db — Worker Cloudflare : page « Tennis Edge » des hypothèses gelées.
//
// VERSION DU 16/10/2026 — VERDICTS EN DIRECT.
// La page et /api/hypotheses lisent verdicts_direct.json, écrit dans le dépôt
// par scripts/suivi_direct.py à partir des ALERTES EN DIRECT
// (h*_signal_log.jsonl : données figées au moment de la détection, résultat
// ajouté après coup). Plus AUCUN calcul ici, plus de D1 :
//   - l'ancienne ingestion de moves_detail_hist.csv dans D1 (`mouvements`,
//     fenêtre de 14 jours, clé uid+detecte_le+side) laissait des lignes
//     fantômes quand la reconstruction changeait un côté ou une date ;
//   - les règles vivaient dans la table D1 `hypotheses` (`filtre_sql`), hors
//     du dépôt : impossible de les relire ou de les tester ;
//   - la CLV affichée était celle du MÊME book, pas Pinnacle ;
//   - `signaux` (journaux d'alertes) était ingérée mais jamais utilisée.
// archiverCourbes est supprimé : il cherchait parts/live_*.jsonl alors que les
// partitions sont en .jsonl.gz, et scripts/r2_parts.py / courbes_r2.py
// (GitHub Actions) copient déjà les partitions dans R2.
//
// Variables (Paramètres → Variables) : GH_OWNER, GH_REPO, GH_BRANCH (facultatives).
// Aucun binding requis (ni D1, ni R2), aucun déclencheur cron.

const DEFAUT = { owner: 'Lucas987987', repo: 'Tennis-edge', branch: 'main' };
const FICHIER = 'verdicts_direct.json';
const CACHE_S = 60;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api/hypotheses') {
      try {
        return json(await verdicts(env, ctx));
      } catch (e) {
        return json({ erreur: String(e).slice(0, 200), hypotheses: [] }, 502);
      }
    }
    if (url.pathname === '/api/verif') {
      return json(await verification(env, ctx));
    }
    if (url.pathname === '/' || url.pathname === '/index.html') {
      return new Response(page(), {
        headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' },
      });
    }
    return new Response('introuvable', { status: 404 });
  },
};

export function sourceUrl(env) {
  const o = (env && env.GH_OWNER) || DEFAUT.owner;
  const r = (env && env.GH_REPO) || DEFAUT.repo;
  const b = (env && env.GH_BRANCH) || DEFAUT.branch;
  return `https://raw.githubusercontent.com/${o}/${r}/${b}/${FICHIER}`;
}

function json(o, status = 200) {
  return new Response(JSON.stringify(o, null, 1), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': `public, max-age=${CACHE_S}`,
      'access-control-allow-origin': '*',
    },
  });
}

// Lecture de verdicts_direct.json, mise en cache ~60 s par Cloudflare.
export async function verdicts(env, ctx) {
  const src = sourceUrl(env);
  const r = await fetch(src, { cf: { cacheTtl: CACHE_S, cacheEverything: true } });
  if (!r.ok) throw new Error(`${FICHIER} : HTTP ${r.status}`);
  const doc = await r.json();
  return adapter(doc, src);
}

// Forme de /api/hypotheses conservée (genere_le, hypotheses[].code, gele_le,
// out_of_sample.n/roi/clv_moyen…) ; champs AJOUTÉS : n_detectees, n_envoyees,
// n_denouees, clv_pin_moyen, clv_pin_ic95, controle_reconstruction, source.
export function adapter(doc, src) {
  const hyps = Array.isArray(doc && doc.hypotheses) ? doc.hypotheses : [];
  return {
    genere_le: doc && doc.genere_le,
    source: 'alertes en direct — ' + (src || FICHIER),
    regles_de_comptage: (doc && doc.regles_de_comptage) || [],
    hypotheses: hyps.map((h) => ({
      ...h,
      out_of_sample: { n: 0, ...(h.out_of_sample || {}) },
      in_sample_recalcule: h.in_sample_recalcule || { n: 0 },
      replication: h.replication || [],
    })),
  };
}

async function verification(env, ctx) {
  const src = sourceUrl(env);
  try {
    const d = await verdicts(env, ctx);
    const age = d.genere_le ? Math.round((Date.now() - Date.parse(d.genere_le)) / 60000) : null;
    return { source: src, genere_le: d.genere_le, age_minutes: age,
      hypotheses: d.hypotheses.map((h) => ({ code: h.code, n_detectees: h.out_of_sample.n_detectees,
        n_envoyees: h.out_of_sample.n_envoyees, n_denouees: h.out_of_sample.n })),
      rappel: 'verdicts calculés dans GitHub Actions (scripts/suivi_direct.py), page en lecture seule' };
  } catch (e) {
    return { source: src, erreur: String(e).slice(0, 200) };
  }
}

// PAGE
export function page() {
  return `<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tennis Edge</title>
<style>
:root{--f:#111;--g:#666;--b:#e5e5e5;--z:#fafafa;--ok:#2d6a4f;--no:#a32d2d;--bg:#fff}
@media(prefers-color-scheme:dark){:root{--f:#eee;--g:#999;--b:#333;--z:#1a1a1a;--bg:#111;--ok:#74c69d;--no:#f08080}}
body{font:15px/1.5 system-ui,sans-serif;margin:0 auto;padding:14px;color:var(--f);background:var(--bg);max-width:780px}
h1{font-size:19px;margin:0 0 2px}
.s{color:var(--g);font-size:13px;margin-bottom:16px}
.h{border:1px solid var(--b);border-radius:8px;margin-bottom:10px;overflow:hidden}
summary{padding:12px;cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.t{font-weight:600}.n{color:var(--g);font-size:12.5px}
.r{display:flex;gap:14px;margin-top:6px;font-size:13px;flex-wrap:wrap}
.r b{font-weight:600}
.c{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;font-size:12px}
.c span{border:1px solid var(--b);border-radius:6px;padding:1px 6px;color:var(--g)}
.d{padding:0 12px 12px}
h3{font-size:12.5px;color:var(--g);margin:14px 0 4px;font-weight:600;text-transform:uppercase;letter-spacing:.3px}
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:3px 0;vertical-align:top}
td:first-child{color:var(--g);width:46%}
.v{font-weight:600}.ok{color:var(--ok)}.no{color:var(--no)}
.bar{height:4px;background:var(--b);border-radius:2px;margin:8px 0 4px}
.bar>i{display:block;height:100%;background:var(--f);border-radius:2px}
.w{background:var(--z);padding:8px 10px;border-radius:6px;font-size:12.5px;color:var(--g);margin-top:10px}
</style></head><body>
<h1>Tennis Edge</h1>
<div class="s" id="s">chargement…</div>
<div id="o"></div>
<script>
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const fr = (x, d=1) => x==null || !Number.isFinite(+x) ? '—' : (+x).toLocaleString('fr-FR', {maximumFractionDigits:d});
const sg = (x,u) => x==null ? '—' : (x>0?'+':'') + fr(x) + (u||'');
const cl = v => v==='SURVIT'?'ok':(v==='REJET'?'no':'');
const ic = a => Array.isArray(a) ? '[' + fr(a[0]) + ' ; ' + fr(a[1]) + ']' : '—';
function carte(h){
  const o=h.out_of_sample||{}, R=h.reference_in_sample||{}, K=h.controle_reconstruction;
  const c=cl(o.verdict);
  const compte = \`<div class="c"><span>\${fr(o.n_detectees||0,0)} détectées</span><span>\${fr(o.n_envoyees||0,0)} envoyées</span><span>\${fr(o.n||0,0)} dénouées</span></div>\`;
  if(!o.n) return \`<details class="h"><summary><div class="t">\${esc(h.code)} — \${esc(h.libelle)}</div>
    <div class="n">gelée le \${esc(h.gele_le)} · aucun pari dénoué en direct\${h.debut_direct?' · 1re détection '+esc(h.debut_direct):''}</div>\${compte}</summary>
    <div class="d">\${h.note?\`<div class="w">\${esc(h.note)}</div>\`:''}</div></details>\`;
  const tete = \`<div class="t">\${esc(h.code)} — \${esc(h.libelle)}</div>
    <div class="n">gelée le \${esc(h.gele_le)} · en direct</div>
    <div class="r"><span>\${fr(o.n,0)} paris</span><span class="\${c}"><b>\${sg(o.ecart)} pts</b></span>
    <span><b>\${sg(o.roi,' %')}</b></span><span>CLV Pin <b>\${sg(o.clv_pin_moyen,' %')}</b></span></div>\${compte}
    <div class="bar"><i style="width:\${Math.min(h.avancement||0,100)}%"></i></div>
    <div class="n">\${fr(o.n,0)}/\${fr(h.cible,0)} — \${fr(h.avancement,0)} % · reste \${fr(h.restant,0)}</div>
    \${o.verrouillable===false?\`<div class="n">⏳ \${esc(o.statut)}</div>\`:''}\`;
  const rep = h.replication && h.replication.length===2 ? \`<h3>Réplication</h3><table>
    \${h.replication.map(m=>\`<tr><td>\${m.moitie===1?'1re':'2e'} moitié (n=\${fr(m.n,0)})</td><td>écart \${sg(m.ecart)} · ROI \${sg(m.roi,' %')} · CLV \${sg(m.clv_pin,' %')}</td></tr>\`).join('')}
    </table><div class="w">Un effet qui tient sur deux périodes sans recouvrement vaut mieux qu'un p significatif obtenu sur un balayage. À ce volume, c'est indicatif.</div>\` : '';
  const conc = h.concentration_5_meilleurs!=null ? \`<tr><td>5 meilleurs paris</td><td>\${fr(h.concentration_5_meilleurs)} % du P&L</td></tr>\` : '';
  return \`<details class="h"><summary>\${tete}</summary><div class="d">
    <h3>En direct (hors échantillon)</h3><table>
    <tr><td>gains</td><td class="v">\${fr(o.gains,0)}/\${fr(o.n,0)} = \${fr(o.taux)} % <span class="n">(seuil \${fr(o.seuil)} %)</span></td></tr>
    <tr><td>écart au seuil</td><td class="v \${c}">\${sg(o.ecart)} pts</td></tr>
    <tr><td>IC95 du taux</td><td>\${ic(o.ic95)}</td></tr>
    <tr><td>verdict (indicatif)</td><td class="v \${c}">\${esc(o.verdict)}</td></tr>
    <tr><td>CLV Pinnacle</td><td class="v">\${sg(o.clv_pin_moyen,' %')} <span class="n">IC95 \${ic(o.clv_pin_ic95)} · n=\${fr(o.clv_n,0)} · positif \${fr(o.clv_positif)} %</span></td></tr>
    <tr><td>ROI</td><td class="v">\${sg(o.roi,' %')} · P&L \${sg(o.pnl,' u')}</td></tr>
    \${conc}
    <tr><td>cote moyenne</td><td>\${fr(o.cote_moyenne,2)}</td></tr>
    \${o.lead_moyen_h!=null?\`<tr><td>délai moyen</td><td>\${fr(o.lead_moyen_h)} h avant le match</td></tr>\`:''}
    \${o.periode?\`<tr><td>période</td><td>\${esc(o.periode)}</td></tr>\`:''}
    </table>\${rep}
    <h3>Référence au gel</h3><table>
    <tr><td>in-sample</td><td>\${fr(R.n,0)} paris · \${fr(R.taux)} % <span class="n">(seuil \${fr(R.seuil)} %)</span> · ROI \${sg(R.roi,' %')}</td></tr>
    \${K&&K.n?\`<tr><td>contrôle (reconstruction)</td><td>\${fr(K.gains,0)}/\${fr(K.n,0)} · écart \${sg(K.ecart)} pts <span class="n">— ne juge pas</span></td></tr>\`:''}
    </table>
    <div class="w"><b>NON confirmatoire</b> : la référence in-sample a servi à trouver l'hypothèse. Seules les alertes en direct après le gel jugent.</div>
    \${h.note?\`<div class="w">\${esc(h.note)}</div>\`:''}
  </div></details>\`;
}
fetch('/api/hypotheses').then(r=>r.json()).then(d=>{
  if(d.erreur) throw new Error(d.erreur);
  document.getElementById('s').textContent = 'verdicts en direct · mis à jour ' + new Date(d.genere_le).toLocaleString('fr-FR');
  document.getElementById('o').innerHTML = d.hypotheses.map(carte).join('');
}).catch(e=>{document.getElementById('s').textContent='erreur : '+e});
</script></body></html>`;
}
