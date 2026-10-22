// tennis-edge-closing — Worker Cloudflare : le SEUL déclencheur des collectes.
//
// Cron */3 * * * * : capture des cotes (capture_closing), Polymarket, Kalshi,
// courbes live + alertes. Toute la chaîne en dépend.
//
// RANGÉ DANS LE DÉPÔT LE 22/10/2026 (jusque-là, il n'existait que dans le
// tableau de bord Cloudflare). Déployé par .github/workflows/deploy_closing.yml
// à chaque modification de ce dossier. Ne plus modifier le code dans le
// tableau de bord : le prochain déploiement l'écraserait.
//
// Variables (tableau de bord, gardées au déploiement) : GH_OWNER, GH_REPO,
// GH_TOKEN (secret), et facultatives DAY_CADENCE_MIN, NIGHT_*, *_WORKFLOW_FILE,
// *_CADENCE_MIN, KALSHI_ENABLED.

const RAW = (owner, repo, file) =>
`https://raw.githubusercontent.com/${owner}/${repo}/main/${file}`;

// Période du cron Cloudflare, en minutes.
// DOIT correspondre à l'expression configurée dans
// Settings > Triggers > Cron Triggers (actuellement */3 * * * *).
// Si tu changes l'une, change l'autre : l'alignement de la cadence de nuit
// plus bas se ferait sinon sur une grille qui n'existe pas.
const CRON_MIN = 3;

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env).then((msg) => { console.log(msg); return msg; }));
  },

  async fetch(request, env, ctx) {
    const msg = await run(env);
    return new Response(msg, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
  },
};

function parseTs(s) {
  if (typeof s !== 'string' || !s) return NaN;
  const hasTz = /(?:Z|[+-]\d\d:?\d\d)$/.test(s);
  return Date.parse(hasTz ? s : s + 'Z');
}

async function fetchJson(url) {
  const r = await fetch(`${url}?t=${Date.now()}`, {
      headers: { 'User-Agent': 'tennis-edge-worker' },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export function countTournaments(active) {
  if (!active || typeof active !== 'object') return null;
  return Object.keys(active).filter(k => !k.startsWith('_')).length;
}

export function isNight(hourUTC, start, end) {
  return start <= end
    ? (hourUTC >= start && hourUTC < end)
    : (hourUTC >= start || hourUTC < end);
}

export function decide(state, nTournois, nowMs, cfg, enCoursCapture) {
  const { DAY_CADENCE_MIN, NIGHT_CADENCE_MIN, NIGHT_START_UTC, NIGHT_END_UTC } = cfg;

  // MULTIPLICATEUR PAR NOMBRE DE TOURNOIS RETIRÉ (03/09/2026).
  // Avant : R = Math.max(1, Math.ceil(nTournois / 5)) et cadence = base * R.
  // Ce facteur divisait la fréquence de capture au moment précis où il y a le
  // plus à capturer : R montait à 6 pendant une grosse semaine (30 tournois),
  // faisant passer une cadence de 5 min à 30 min. Le budget mesuré ne le
  // justifiait pas.
  //
  // GARDE API AU LIEU DU TEST TEMPOREL (05/09/2026).
  // Observé : 6 captures/heure et 10 min d'écart, alors que le cron tournait
  // toutes les 5 min sans une seule erreur. Une exécution sur deux disait
  //   « rien a faire (mode jour, cadence 5min, derniere capture il y a 5min) »
  // Cause : `minsSince >= cadence` avec cadence == période du cron est un
  // TEST DE BORD. last_capture_at est écrit à la FIN du run capture_closing
  // et n'est lisible qu'une fois le commit poussé : au réveil suivant l'écart
  // mesuré vaut (période du cron − durée du run), jamais la période entière.
  // Le test échoue, on attend un tour, l'écart double. Simulé : cron 5 /
  // cadence 5 -> 6,0 captures/h, écart 10,0 min. Exactement les chiffres
  // observés. Passer le cron à 3 min sans corriger ceci donnerait 6 min.
  //
  // Le bon garde-fou était déjà dans ce fichier : planifierCollecteur()
  // explique en commentaire pourquoi elle interroge l'API plutôt qu'un
  // fichier d'état poussé en fin de run. Le raisonnement vaut mot pour mot
  // pour last_capture_at ; il n'avait juste jamais été appliqué ici.
  //
  // DE JOUR : la seule question utile est « un run de capture est-il déjà en
  // cours ou en file ? ». Sinon on déclenche. La cadence devient bornée par
  // la durée réelle d'un run, ce qui est la bonne borne : simulé à cron 3 min,
  // un run de 2 min donne 20 captures/h, un run de 5 min en donne 10. Le
  // système s'auto-régule au lieu de se bloquer sur une comparaison.
  //
  // DE NUIT : on garde un test temporel — il n'y a rien à capturer et le
  // budget d'appels est mieux dépensé de jour. Mais avec une TOLÉRANCE, sans
  // quoi la nuit reproduirait exactement le même bug de bord.

  const night = isNight(new Date(nowMs).getUTCHours(), NIGHT_START_UTC, NIGHT_END_UTC);
  const lastCap = state && state.last_capture_at ? parseTs(state.last_capture_at) : NaN;
  const minsSince = isNaN(lastCap) ? Infinity : (nowMs - lastCap) / 60000;

  // enCoursCapture vaut null/undefined quand l'API GitHub est injoignable.
  // Repli temporel : dégradé mais jamais bloquant, mieux vaut une capture en
  // trop qu'un arrêt silencieux. Même parti pris que planifierCollecteur().
  const apiConnue = (enCoursCapture === true || enCoursCapture === false);

  // Une cadence qui n'est pas un multiple de CRON_MIN est INATTEIGNABLE : le
  // Worker ne se réveille que sur la grille. On arrondit à l'inférieur, avec
  // un plancher d'un tick.
  const aligner = (v) => Math.max(CRON_MIN, Math.floor(v / CRON_MIN) * CRON_MIN);
  const TOLERANCE_MIN = CRON_MIN / 2;

  if (night) {
    const cadence = aligner(NIGHT_CADENCE_MIN);
    return {
      fire: (apiConnue ? !enCoursCapture : true) && minsSince >= cadence - TOLERANCE_MIN,
      mode: 'nuit',
      R: 1,               // conservé à 1 : d'anciens tests le référencent.
      cadence,
      garde: apiConnue ? 'api+temps' : 'repli temporel',
      minsSince: minsSince === Infinity ? null : Math.round(minsSince),
    };
  }

  const cadence = aligner(DAY_CADENCE_MIN);
  return {
    fire: apiConnue ? !enCoursCapture : (minsSince >= cadence - TOLERANCE_MIN),
    mode: 'jour',
    R: 1,
    cadence,
    garde: apiConnue ? 'api' : 'repli temporel',
    minsSince: minsSince === Infinity ? null : Math.round(minsSince),
  };
}

// Un run Polymarket est-il DÉJÀ en cours ou en file d'attente ?
//
// Pourquoi passer par l'API et non par polymarket_collector_state.json :
// le collecteur écrit running:true sur le RUNNER, mais le fichier n'est
// commité et poussé qu'à la toute fin du workflow. raw.githubusercontent ne
// voit donc JAMAIS running:true -- le garde basé sur ce champ était du code
// mort. Constaté : avec un run de 18 min et une cadence de 5 min, le Worker
// déclenchait 4 fois pendant un seul run. La contrainte de concurrence côté
// GitHub évite le chevauchement réel, mais chaque déclenchement excédentaire
// crée un run qui sera annulé, ce qui pollue l'historique Actions et masque
// les vrais échecs.
// L'API, elle, connaît l'état réel. Coût : un appel, mis en cache 30 s.
// Planifie UN collecteur : même logique pour Polymarket et Kalshi.
//
// Factorisé volontairement. Dupliquer ces 50 lignes pour chaque nouveau
// collecteur, c'est garantir qu'elles divergeront : côté Python, trois copies
// de player_match() avaient dérivé au point qu'une seule était correcte.
// Ici, un correctif de garde s'applique aux deux collecteurs d'un coup.
//
// cadenceMin doit refléter la DURÉE RÉELLE d'un run, pas un intervalle
// souhaité. Déclencher plus souvent ne collecte pas davantage : la contrainte
// de concurrence côté GitHub met les runs en file, et les excédentaires sont
// annulés — ce qui pollue l'historique Actions et masque les vrais échecs.
async function planifierCollecteur(cfg) {
  const { owner, repo, token, ts, nom, evenement, workflowFile,
    stateFile, cadenceMin, messages } = cfg;

  let etat = null;
  try {
    etat = await fetchJson(RAW(owner, repo, stateFile));
  } catch (e) {
    etat = null;
  }

  const dernier = etat && etat.last_run_at ? parseTs(etat.last_run_at) : NaN;
  const minsDepuis = isNaN(dernier) ? Infinity : (Date.now() - dernier) / 60000;

  // Garde principal : l'API GitHub, seule à connaître l'état réel. Le fichier
  // d'état ne peut PAS servir : le collecteur y écrit running:true sur le
  // runner, mais le fichier n'est poussé qu'à la fin du run — raw.github ne
  // voit donc jamais running:true.
  // Si l'API est injoignable, repli temporel : dégradé mais jamais bloquant,
  // mieux vaut un run en trop qu'un arrêt silencieux de la collecte.
  let enCours = false;
  let garde = 'api';
  try {
    enCours = await runEnCours(owner, repo, token, workflowFile);
  } catch (e) {
    garde = `repli temporel (API: ${e})`;
    enCours = minsDepuis < cadenceMin;
  }

  if (enCours) {
    messages.push(`${nom}: run deja en cours ou en file [garde ${garde}] `
        + `(derniere execution il y a ${isFinite(minsDepuis) ? Math.round(minsDepuis) : '∞'}min).`);
    return;
  }
  // CORRIGÉ LE 05/09/2026 : ce test temporel reproduisait EXACTEMENT le bug
  // de bord corrigé dans decide() le matin même — et je ne l'avais pas
  // appliqué ici, dans la fonction sœur du même fichier.
  //
  // `last_run_at` est écrit à la FIN du run et n'est lisible qu'une fois le
  // commit poussé. Au réveil suivant, minsDepuis vaut donc
  // (période du cron − durée du run), jamais la période entière :
  //     courbes_alertes, run de 1 min 40, cron 3 min
  //     -> minsDepuis = 1,3 min < cadenceMin = 3  -> on saute un tour
  //     -> cadence réelle 6 min au lieu de 3.
  // Mesuré sur les runs #38 à #43 : écarts de 5, 6, 6, 6, 6 min pour des
  // runs de 1 min 34 à 1 min 45.
  //
  // Quand l'API a répondu (garde === 'api'), elle sait DÉJÀ si un run est en
  // cours — c'est le seul fait qui compte, et il a été testé juste au-dessus.
  // Le test temporel n'apporte alors rien qu'une soustraction fausse.
  // Il reste utile en repli, quand l'API est muette : là on n'a que le temps,
  // et une tolérance évite le même effet de bord.
  // `reposMin` : minutes de REPOS exigées APRÈS la fin du run précédent.
  // Sémantique volontairement différente de « cadence » : minsDepuis se
  // mesure depuis last_run_at, écrit à la FIN du run. Parler de cadence sur
  // cette base était précisément la source de la confusion — une « cadence
  // de 3 min » donnait en réalité un cycle de 6.
  //   courbes_alertes  -> 0  : repartir dès que possible, c'est le but
  //   Polymarket/Kalshi -> 5 : ~20 min de run + 5 de repos = cycle de ~25,
  //                            la valeur visée avant ce correctif (le bug
  //                            de bord la portait à 47).
  const reposMin = (cfg.reposMin != null) ? cfg.reposMin : 0;
  const TOLERANCE_MIN = 0.75;
  const seuil = (garde === 'api') ? reposMin : Math.max(reposMin, cadenceMin) - TOLERANCE_MIN;
  if (minsDepuis < seuil) {
    messages.push(`${nom}: rien a faire [${garde}] `
        + `(fin du run precedent il y a ${Math.round(minsDepuis)}min, repos ${seuil}min).`);
    return;
  }
  try {
    messages.push(await dispatch(owner, repo, token, evenement, {
          cadence_min: cadenceMin,
          mins_since_last: isFinite(minsDepuis) ? Math.round(minsDepuis) : null,
          garde,
          triggered_at: ts,
    }));
  } catch (e) {
    messages.push(`Erreur dispatch ${evenement}: ${e}`);
  }
}


// Un run du workflow est-il DÉJÀ en cours ou en file ? — avec une DATE LIMITE.
//
// 08/10/2026 : un run resté coincé « queued » ou « in_progress » bloquait le
// worker indéfiniment (trois collecteurs arrêtés, aucune erreur nulle part).
// D'où un plafond : au-delà, le run est un fantôme et on l'ignore. Ce plafond
// était d'abord un bloc collé en fin de fichier qui redéfinissait la fonction ;
// il est maintenant ici, à sa place.
//
// 22/10/2026 — PLAFOND PAR WORKFLOW. GitHub a laissé « in_progress » des runs
// capture_closing dont le job avait fini en 22 s : clos au bout de 44 min et
// 12 min 47. Avec le plafond unique de 45 min, la capture des cotes restait
// arrêtée jusqu'à 45 min. Le plafond doit dépasser le run réel le plus long de
// CHAQUE workflow, pas de tous :
//     capture_closing    ~20 s (timeout 12)  -> 6 min
//     courbes_alertes    ~50 s à 1 min 40    -> 10 min
//     Polymarket, Kalshi ~15-20 min          -> 45 min (inchangé)
// Lancer un run par-dessus un fantôme est sans risque : capture_closing n'a
// pas de groupe de concurrence et son commit supporte deux runs en parallèle.
//
// En cas d'échec de l'API, l'exception remonte : les appelants basculent sur le
// repli temporel — « dégradé mais jamais bloquant ».
export const GARDE_PLAFOND_MIN = 45;
export const PLAFOND_PAR_WORKFLOW = { 'capture_closing.yml': 6, 'courbes_alertes.yml': 10 };
const ACTIFS = new Set(['queued', 'in_progress', 'waiting', 'requested', 'pending']);
const _gardeCache = new Map();

export function plafondMin(workflowFile) {
  return PLAFOND_PAR_WORKFLOW[workflowFile] || GARDE_PLAFOND_MIN;
}

// Décision pure (testable) : `runs` = workflow_runs de l'API GitHub.
export function runsBloquants(runs, workflowFile, nowMs) {
  const limite = nowMs - plafondMin(workflowFile) * 60000;
  let bloquant = false;
  let fantomes = 0;
  for (const run of runs || []) {
    if (!ACTIFS.has(run.status)) continue;
    const ne = Date.parse(run.created_at || '');
    if (isNaN(ne) || ne >= limite) {
      bloquant = true;        // run récent : garde légitime, on s'abstient
    } else {
      fantomes++;             // plus vieux que le plafond : on l'ignore
    }
  }
  return { bloquant, fantomes };
}

async function runEnCours(owner, repo, token, workflowFile) {
  const cle = `${owner}/${repo}/${workflowFile}`;
  const vu = _gardeCache.get(cle);
  if (vu && Date.now() - vu.t < 30000) return vu.v;

  // Pas de filtre `status` dans l'URL : l'API ne sait pas combiner `queued`
  // et `in_progress` en une requête.
  const url = `https://api.github.com/repos/${owner}/${repo}`
    + `/actions/workflows/${encodeURIComponent(workflowFile)}`
    + `/runs?per_page=20`;
  const r = await fetch(url, {
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'tennis-edge-worker',
    },
  });
  if (!r.ok) throw new Error(`API runs HTTP ${r.status}`);
  const data = await r.json();
  const { bloquant, fantomes } = runsBloquants((data && data.workflow_runs) || [], workflowFile, Date.now());
  if (fantomes && !bloquant) {
    console.log(`[garde] ${workflowFile} : ${fantomes} run(s) actif(s) `
      + `depuis plus de ${plafondMin(workflowFile)} min, ignoré(s).`);
  }
  _gardeCache.set(cle, { t: Date.now(), v: bloquant });
  return bloquant;
}

async function dispatch(owner, repo, token, eventType, clientPayload) {
  const resp = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/dispatches`,
    {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${token}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'tennis-edge-worker',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
          event_type: eventType,
          client_payload: clientPayload,
      }),
    }
  );

  if (resp.status === 204) return `OK - ${eventType} declenche.`;
  const body = await resp.text();
  return `ECHEC ${eventType} (HTTP ${resp.status}): ${body}`;
}

async function run(env) {
  const owner = env.GH_OWNER;
  const repo = env.GH_REPO;
  const token = env.GH_TOKEN;

  if (!owner || !repo || !token) {
    return 'ERREUR: GH_OWNER, GH_REPO ou GH_TOKEN manquant dans la config.';
  }

  const cfg = {
    // Sert de repli quand l'API GitHub est injoignable ; de jour, la décision
    // passe normalement par le garde API et non par cette valeur. Alignée sur
    // CRON_MIN dans decide(). Laisser 3 (ou la variable d'environnement
    // DAY_CADENCE_MIN si elle est définie côté Cloudflare — vérifier qu'elle
    // n'y est pas restée à 5, elle écraserait ce défaut).
    DAY_CADENCE_MIN: Number(env.DAY_CADENCE_MIN) || 3,
    NIGHT_CADENCE_MIN: Number(env.NIGHT_CADENCE_MIN) || 15,
    NIGHT_START_UTC: env.NIGHT_START_UTC != null ? Number(env.NIGHT_START_UTC) : 23,
    NIGHT_END_UTC: env.NIGHT_END_UTC != null ? Number(env.NIGHT_END_UTC) : 6,
  };

  let state = null;
  let nTournois = null;

  try {
    state = await fetchJson(RAW(owner, repo, 'capture_state.json'));
  } catch (e) {
    state = null;
  }

  try {
    nTournois = countTournaments(
      await fetchJson(RAW(owner, repo, 'active_tournaments.json'))
    );
  } catch (e) {
    nTournois = null;
  }

  // AJOUTÉ LE 05/09/2026 : capture_closing bénéficie enfin du même garde que
  // Polymarket et Kalshi. runEnCours() est réutilisée telle quelle — un
  // correctif de garde profite ainsi aux trois d'un coup, ce qui est la
  // raison d'être de la factorisation de planifierCollecteur().
  // null = API injoignable, decide() bascule alors en repli temporel.
  let enCoursCapture = null;
  try {
    enCoursCapture = await runEnCours(
      owner, repo, token, env.CAPTURE_WORKFLOW_FILE || 'capture_closing.yml');
  } catch (e) {
    enCoursCapture = null;
  }

  const d = decide(state, nTournois, Date.now(), cfg, enCoursCapture);
  const ts = new Date().toISOString();
  // `(x${d.R})` retiré de cette ligne le 03/09 avec le multiplicateur.
  // `garde` ajouté le 05/09 : sans lui, un repli temporel permanent (jeton
  // expiré, API en panne) ferait retomber la cadence à 6 min SANS AUCUN
  // signal. C'est le mot à chercher dans les logs pour vérifier que le
  // correctif est réellement actif.
  const info = `mode ${d.mode}, ${nTournois ?? '?'} tournois, cadence ${d.cadence}min, ` +
  `garde ${d.garde}, derniere capture il y a ${d.minsSince ?? '∞'}min`;

  let messages = [];

  if (!d.fire) {
    messages.push(`${ts} - capture_closing: rien a faire (${info}).`);
  } else {
    try {
      messages.push(await dispatch(owner, repo, token, 'capture_closing', {
            reason: d.mode,
            cadence_min: d.cadence,
            tournois: nTournois,
            mins_since_last: d.minsSince,
            triggered_at: ts,
      }));
    } catch (e) {
      messages.push(`Erreur dispatch capture_closing: ${e}`);
    }
  }

  // Polymarket : cadence indépendante du nombre de tournois.
  // Le Worker reste le scheduler ; GitHub Actions ne contient aucun cron.
  //
  // Polymarket : run d'environ 18 min (checkout ~3 min + collecte 15 min).
  await planifierCollecteur({
      owner, repo, token, ts, messages,
      nom: 'Polymarket',
      evenement: 'polymarket_collector',
      workflowFile: env.PM_WORKFLOW_FILE || 'polymarket_collector.yml',
      stateFile: 'polymarket_collector_state.json',
      // 5 min de repos entre deux runs : rétablit le cycle de ~25 min visé,
      // que le bug de bord portait à ~47. Sans ce plancher, la garde API
      // seule relancerait dès la fin du run précédent (~21 min) et
      // doublerait volume de ticks et commits — le dépôt vient d'être purgé
      // de 3,4 Go, autant ne pas le regonfler pour rien.
      reposMin: 5,
      cadenceMin: Math.max(1, Number(env.PM_CADENCE_MIN) || 16),
  });

  // Courbes live + alertes : workflow créé le 05/09/2026 en découpant
  // Capture Closing Lines. Il contient les 130-160 s de recalcul LOCAL qui
  // bloquaient la capture des cotes à 5 min alors qu'elle prend 1,9 s.
  // Ces scripts travaillent sur des données déjà capturées : les retarder de
  // quelques minutes ne fait rien perdre, une cote captée en retard est
  // perdue pour toujours. D'où une cadence propre, plus lâche.
  // cadenceMin reflète la DURÉE RÉELLE d'un run (~2 min 40) plus une marge,
  // comme pour Polymarket et Kalshi.
  await planifierCollecteur({
      owner, repo, token, ts, messages,
      nom: 'Courbes',
      evenement: 'courbes_alertes',
      workflowFile: env.CURVES_WORKFLOW_FILE || 'courbes_alertes.yml',
      stateFile: 'courbes_alertes_state.json',
      // 9 -> 3 le 05/09/2026, après l'ajout du cache de calibration
      // (actions/cache sur calib_cache.json). Le run passe de ~150 s à ~50 s :
      // la garde API ne bloque donc plus sur une grille de 3 min, et les
      // alertes tombent dans la MÊME fenêtre que la capture au lieu d'avoir
      // jusqu'à 9 min de retard sur elle.
      // Coût : 0 requête OddsPapi (ce workflow n'en fait aucune), seulement
      // des minutes Actions et des commits.
      cadenceMin: Math.max(1, Number(env.CURVES_CADENCE_MIN) || 3),
  });

  // Kalshi : run plus court que Polymarket -- checkout allégé (filter
  // blob:none, ~25 s), aucune dépendance pip à installer, et 900 s de
  // collecte. Mesuré : 15 min 30 au total. Cadence 17 min pour laisser une
  // marge sans empiler de runs annulés.
  // Activable/désactivable sans redéploiement : KALSHI_ENABLED=0.
  if ((env.KALSHI_ENABLED || '1') !== '0') {
    await planifierCollecteur({
        owner, repo, token, ts, messages,
        nom: 'Kalshi',
        evenement: 'kalshi_collector',
        workflowFile: env.KX_WORKFLOW_FILE || 'kalshi_collector.yml',
        stateFile: 'kalshi_collector_state.json',
        // 5 min de repos entre deux runs : rétablit le cycle de ~25 min visé,
        // que le bug de bord portait à ~47. Sans ce plancher, la garde API
        // seule relancerait dès la fin du run précédent (~21 min) et
        // doublerait volume de ticks et commits — le dépôt vient d'être purgé
        // de 3,4 Go, autant ne pas le regonfler pour rien.
        reposMin: 5,
        cadenceMin: Math.max(1, Number(env.KX_CADENCE_MIN) || 17),
    });
  } else {
    messages.push('Kalshi: desactive (KALSHI_ENABLED=0).');
  }

  return messages.join('\n');
}
