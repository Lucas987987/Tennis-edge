// worker-joueurs.js - fiches joueurs publiques, servies par tennis-edge-index.
//
// A FUSIONNER avec worker-public.js : ce fichier ajoute les routes /j,
// rien d'autre. La route / de l'indice des operateurs reste intacte.
//
//   /j                page d'accueil : le classement marche
//   /j/<slug>         fiche d'un joueur
//   /j/<a>/<b>        comparaison, les deux sur la meme echelle
//   /api/joueur/<s>   la fiche en JSON
//
// LE SLUG
// -------
// Le meme que la cle de players_profile.json : tokens du nom, minuscules,
// accents retires, TRIES, joints par un tiret. « Mattia Bellucci » et
// « bellucci mattia » donnent donc tous deux `bellucci-mattia`.
//
// Le tri est ce qui rend le lien calculable depuis les scripts d'alerte
// sans table de correspondance : player_form ecrit les noms dans les deux
// ordres selon les entrees, et un slug non trie aurait casse une fois sur
// deux.
//
// L'ECHELLE DE PRIX
// -----------------
// Logarithmique, de 1,01 a 6,00. Les cotes sont multiplicatives : l'ecart
// entre 1,20 et 1,40 vaut bien plus que celui entre 4,00 et 4,20. En
// lineaire, 1,15 et 1,40 se chevauchent (2,8 % contre 7,8 % de l'axe) ;
// en log ils sont separes de 9 points. C'est la difference entre un axe
// lisible et un axe decoratif.

// TOUT EST ENFERME DANS `FICHES`
// -----------------------------
// Un seul nom entre dans la portee du worker. worker-public.js definit
// deja esc(), html(), slug() et CSS ; un `const` redeclare n'est pas une
// erreur a l'execution mais une SyntaxError au chargement : le worker
// entier refuse de demarrer, y compris la route / qui marchait. Le cout
// d'une collision est donc la panne totale, pas une fiche cassee.
//
// A COLLER tel quel dans worker-public.js, n'importe ou au premier niveau,
// puis deux lignes au debut de fetch() :
//
//     const f = await FICHES.route(url, env);
//     if (f) return f;
//
// `url` est le `new URL(request.url)` deja present. route() rend null
// pour toute adresse qui ne commence pas par /j ou /api/joueur : la route
// de l'indice des operateurs n'est pas touchee.

const FICHES = (() => {
  const RAW = (o, r, f) =>
    `https://raw.githubusercontent.com/${o}/${r}/main/${f}`;

  const LO = 1.01, HI = 6.0;
  const LOG_LO = Math.log(LO), ETENDUE = Math.log(HI) - LOG_LO;

  // Position sur l'axe, bornee : une cote a 12,00 reste visible au bout
  // plutot que de sortir du cadre.
  const pos = (c) => Math.max(0, Math.min(1, (Math.log(c) - LOG_LO) / ETENDUE));

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const fr = (n, d = 2) => (n == null ? '—' : Number(n).toFixed(d).replace('.', ','));

  // Accord en nombre. « 1 matchs » sur une fiche publique, c'est le detail
  // qui fait douter de tout le reste.
  const pl = (n, mot, plur) => `${n} ${n > 1 ? (plur || mot + 's') : mot}`;

  const SURF = { dur: 'dur', terre: 'terre', gazon: 'gazon' };

  // L'Elo publie par tennisabstract.com, rafraichi chaque lundi par
  // elo_fetch.py. C'est le SEUL avis de la page qui ne vienne pas du
  // marche : quand il diverge de la cote mediane, c'est l'information la
  // plus interessante de la fiche.
  //
  // L'Elo maison du depot n'y figure pas, volontairement : il s'auto-evalue
  // a brier 0,235 quand les books sont a 0,209 — il predit moins bien que
  // le marche.
  function elo_surfaces(e) {
    if (!e || !e.surfaces) return '';
    return Object.keys(SURF).filter((n) => e.surfaces[n] != null).map((n) => {
      const c = n === e.meilleure_surface ? ' mieux'
        : (n === e.pire_surface ? ' moins' : '');
      return `<span class="su${c}">${SURF[n]} <b>${e.surfaces[n]}</b></span>`;
    }).join('');
  }

  // Deux faits independants : une surface de predilection, et une surface
  // ou le joueur decroche. Il peut n'avoir ni l'une ni l'autre, ou les deux.
  function elo_phrase(e) {
    const p = [];
    if (e.meilleure_surface) p.push(`nettement meilleur sur ${SURF[e.meilleure_surface]}`);
    if (e.pire_surface) p.push(`nettement moins bon sur ${SURF[e.pire_surface]}`);
    if (!p.length) return 'Aucune surface ne se détache.';
    return p.join(', ').replace(/^./, (c) => c.toUpperCase()) + '.';
  }

  // L'ECART ENTRE LE PRIX DU JOUR ET LA MEDIANE DU JOUEUR
  //
  // La fiche dit ce que le marche pense du joueur EN GENERAL (sa cote
  // mediane a l'ouverture). Le bandeau dit ce qu'il pense de lui CE SOIR.
  // L'ecart entre les deux est l'information la plus directe de la page :
  // ce match est-il plus dur ou plus facile que son ordinaire ?
  //
  // Mesure en POINTS DE PROBABILITE, pas en pourcentage de cote. Les cotes
  // sont multiplicatives : passer de 1,20 a 1,30 et de 3,00 a 3,25 est le
  // meme +8 % de cote, mais le premier coute 6 points de probabilite et le
  // second seulement 2,6. Le point de probabilite se compare d'un joueur a
  // l'autre, le pourcentage de cote non.
  // Le classement marché (depuis le 10/10) : la cote face à un joueur moyen
  // du circuit, ajustée à la force des adversaires (build_profiles,
  // notes_marche). La médiane brute reste pour « plus facile / plus dur que
  // son ordinaire ». Repli sur la médiane si le fichier est d'avant le 10/10.
  const CL = (p) => (p && p.cote_classement != null) ? p.cote_classement
    : (p ? p.cote_mediane : null);

  // Classement OFFICIEL ATP/WTA (fichiers tennis-data, depuis le 10/10) :
  // celui du dernier match du joueur dans le fichier, avec sa date — ce
  // n'est pas un classement en direct, la date le dit.
  const jjmm = (iso) => iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) : '';
  const officiel = (p) => p && p.rang_officiel
    ? `${ord(p.rang_officiel.rang, FEM(p))}` : null;

  function ecart_mediane(cote, mediane) {
    if (!cote || !mediane || cote <= 1 || mediane <= 1) return null;
    return (1 / cote - 1 / mediane) * 100;
  }

  function ecart_html(e) {
    if (e === null || Math.abs(e) < 2) return '';
    // Sous 2 points, l'ecart n'est pas une information : c'est la marge.
    return `<span class="ec${e < 0 ? ' dur' : ''}">${e > 0 ? '+' : ''}`
         + `${fr(e, 0)} pts</span>`;
  }

  // 1er, 2e, 3e — pas « 1e ».
  // « 1er » au masculin, « 1re » au féminin : le classement WTA est un
  // classement de joueuses et « 1er sur 65 joueuses » se lit mal. Au-dela
  // de 1 les deux formes se confondent en « e », d'ou le seul cas special.
  const ord = (n, fem) => `${n}<sup>${n === 1 ? (fem ? 're' : 'er') : 'e'}</sup>`;

  // Le circuit sert partout : titre, légende du rang, tableau du duo. Il
  // vient du champ `circuit` de la fiche, que build_profiles.py remplit
  // par l'Elo publié puis par le graphe des adversaires (un homme ne joue
  // pas contre une femme, donc le circuit se propage de match en match).
  const FEM = (p) => (p || {}).circuit === 'wta';
  const CIRC = (p) => ((p || {}).circuit || '').toUpperCase();
  const joueurs = (p, n) => `${FEM(p) ? 'joueuse' : 'joueur'}${n > 1 ? 's' : ''}`;
  const classes = (p, n) => `class${FEM(p) ? 'ée' : 'é'}${n > 1 ? 's' : ''}`;

  // Les jours s'arrondissent : « il y a 3,7 j » affiche une precision que la
  // donnee n'a pas, et personne ne compte en dixiemes de journee.
  function depuis(j) {
    if (j == null) return null;
    const n = Math.round(j);
    if (n <= 0) return 'aujourd’hui';
    if (n === 1) return 'hier';
    return `il y a ${n} jours`;
  }

  function slug(nom) {
    return String(nom)
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .split(/[^a-z]+/).filter((t) => t.length > 1)
      .sort()
      .join('-');
  }

  // La cle de players_profile.json : memes tokens tries, separes par une
  // espace. slug() et cleNom() doivent rester l'image l'un de l'autre, sinon
  // les liens pointent dans le vide.
  const cleNom = (n) => slug(n).split('-').join(' ');

  let _cache = null;
  async function profils(env) {
    if (_cache && Date.now() - _cache.t < 900000) return _cache.d;
    // Valeurs par defaut pour que le worker marche sans aucune variable a
    // regler : un reglage oublie dans un tableau de bord est une panne qui
    // n'apparait nulle part. Les variables restent prioritaires.
    const o = (env && env.GH_OWNER) || 'Lucas987987';
    const dep = (env && env.GH_REPO) || 'tennis-edge';
    const r = await fetch(RAW(o, dep, 'players_profile.json'),
      { cf: { cacheTtl: 900 } });
    if (!r.ok) throw new Error(`players_profile.json : HTTP ${r.status}`);
    const d = await r.json();
    _cache = { t: Date.now(), d };
    return d;
  }

  // ── LES MATCHS A VENIR ───────────────────────────────────────────────────
  //
  // matches_oddspapi.json est reecrit par la capture, plusieurs fois par
  // heure. C'est la seule source du depot qui regarde DEVANT ; la fiche,
  // elle, ne regarde que derriere. Les deux ensemble transforment un
  // historique en page qu'on rouvre.
  //
  // Cache 5 minutes et non 15 : une fiche qui annonce encore un match
  // commence depuis un quart d'heure est pire que pas d'annonce du tout.
  //
  // Toute panne ici est AVALEE : le bloc disparait, la fiche s'affiche. Ce
  // fichier n'est pas celui qui porte la page.
  let _cacheAv = null;
  async function aVenir(env) {
    if (_cacheAv && Date.now() - _cacheAv.t < 300000) return _cacheAv.d;
    const o = (env && env.GH_OWNER) || 'Lucas987987';
    const dep = (env && env.GH_REPO) || 'tennis-edge';
    const par = new Map();
    try {
      const r = await fetch(RAW(o, dep, 'matches_oddspapi.json'),
        { cf: { cacheTtl: 300 } });
      if (r.ok) {
        const j = await r.json();
        const liste = Array.isArray(j) ? j : (j && j.matches) || [];
        for (const m of liste) {
          const t = Date.parse(m.commence_time || '');
          // Un match deja commence n'interesse plus personne ici, et la
          // capture garde les entrees quelques heures apres le debut.
          if (!t || t < Date.now() - 1800000) continue;
          const h = m.home_team, a = m.away_team;
          if (!h || !a) continue;
          for (const [moi, adv] of [[h, a], [a, h]]) {
            const k = cleNom(moi);
            const prec = par.get(k);
            // Un joueur peut figurer sur deux lignes (marches differents) :
            // on garde la plus proche.
            if (!prec || t < prec.t) {
              par.set(k, {
                t, adv, tour: m.sport_title || null, ...prix(m, moi),
              });
            }
          }
        }
      }
    } catch (e) { /* la fiche vit tres bien sans */ }
    _cacheAv = { t: Date.now(), d: par };
    return par;
  }

  // Le prix VIVANT du joueur sur ce match : la reference Pinnacle, et le
  // meilleur prix du marche avec le book qui le sert.
  //
  // C'est la seule chose de la page qui ait une valeur maintenant plutot
  // qu'un interet documentaire — et elle ne coute aucune requete de plus,
  // le fichier etant deja charge pour l'horaire.
  //
  // Les noms viennent du fournisseur et ne sont pas toujours ecrits comme
  // dans la fiche : on passe par cleNom, qui absorbe l'ordre et les accents.
  // Le « meilleur prix » est cherche parmi CES books-la et aucun autre :
  // H14_SOFTS, la liste gelee du depot. Deux raisons, mesurees.
  //
  // Les exchanges d'abord : leur cote est AVANT commission. Annoncer 1,40
  // chez betfair-ex a cote de 1,37 chez Pinnacle ferait croire a un gain de
  // 1,9 % qui n'existe plus une fois 2 a 5 % de commission retires.
  //
  // Les books asiatiques ensuite. Sur les 114 matchs a venir, en prenant
  // tout le marche, 4casters servait le meilleur prix 44 fois sur 61 — un
  // book inaccessible depuis la France. Un « meilleur prix » qu'on ne peut
  // pas jouer n'est pas un meilleur prix.
  //
  // Restreint aux sept, l'ecart median tombe a -0,47 % et seuls 21 % des
  // cas depassent 1 %. C'est moins spectaculaire, et c'est le vrai chiffre.
  const JOUABLES = new Set(['unibet', 'bwin', 'betsson', 'bet365',
                            '888sport', 'betway', 'leovegas']);

  function prix(m, joueur) {
    const k = cleNom(joueur);
    let pin = null, pinJuste = null, best = null, bestBook = null;
    // Repli quand Pinnacle ne cote pas le match (51 matchs sur 82 le 09/10,
    // surtout en Challenger et ITF) : la MEDIANE des books qui le cotent,
    // prix affiché tel quel, prix juste (marge retirée book par book) pour
    // l'écart à la médiane du joueur. Une médiane plutôt qu'une moyenne :
    // un book en retard ou une cote d'exchange isolée ne la déplace pas.
    const bruts = [], justes = [];
    for (const b of m.bookmakers || []) {
      const h2h = (b.markets || []).find((x) => x.key === 'h2h');
      if (!h2h) continue;
      const o = (h2h.outcomes || []).find((x) => cleNom(x.name) === k);
      const c = o && Number(o.price);
      if (!c || c <= 1) continue;
      const cle_ = (b.key || '').toLowerCase();
      {
        const autre = (h2h.outcomes || []).find((x) => cleNom(x.name) !== k);
        const ca = autre && Number(autre.price);
        if (ca && ca > 1) { bruts.push(c); justes.push((1 / c + 1 / ca) / (1 / c)); }
      }
      if (cle_ === 'pinnacle') {
        pin = c;
        // Cote JUSTE : la marge retirée, comme dans la médiane du joueur
        // (build_profiles, depuis le 09/10). Comparer un prix avec marge à
        // une médiane sans marge décalerait tous les écarts d'un point.
        const autre = (h2h.outcomes || []).find((x) => cleNom(x.name) !== k);
        const ca = autre && Number(autre.price);
        if (ca && ca > 1) pinJuste = (1 / c + 1 / ca) / (1 / c);
      }
      if (!JOUABLES.has(cle_)) continue;
      if (best === null || c > best) { best = c; bestBook = b.title || b.key; }
    }
    const med = (v) => {
      if (!v.length) return null;
      const t = [...v].sort((x, y) => x - y), i = t.length >> 1;
      return t.length % 2 ? t[i] : (t[i - 1] + t[i]) / 2;
    };
    // ref / refJuste : ce qu'on affiche comme « cote du match ». Pinnacle
    // quand il cote, sinon la médiane du marché — et on dit laquelle.
    const nBooks = bruts.length;
    const ref = pin || (nBooks >= 3 ? med(bruts) : null);
    const refJuste = pin ? pinJuste : (nBooks >= 3 ? med(justes) : null);
    const source = pin ? 'Pinnacle' : (ref ? `Marché (${nBooks} books)` : null);
    return { pin, pinJuste, best, bestBook, ref, refJuste, source };
  }

  // ── ROUTAGE ──────────────────────────────────────────────────────────────

  async function routeJoueurs(url, env) {
    const seg = url.pathname.split('/').filter(Boolean);   // ['j', a, b?]

    if (seg[0] === 'api' && seg[1] === 'joueur') {
      const d = await profils(env);
      const p = d.joueurs[(seg[2] || '').replace(/-/g, ' ')];
      return new Response(JSON.stringify(p || { erreur: 'inconnu' }, null, 1), {
        status: p ? 200 : 404,
        headers: {
          'content-type': 'application/json; charset=utf-8',
          'access-control-allow-origin': '*',
          'cache-control': 'public, max-age=60',
        },
      });
    }

    if (seg[0] !== 'j') return null;

    let d;
    try {
      d = await profils(env);
    } catch (e) {
      return html(pageErreur(String(e)), 503);
    }

    const cle = (s) => (s || '').replace(/-/g, ' ');
    const a = d.joueurs[cle(seg[1])];
    const b = d.joueurs[cle(seg[2])];

    if (seg[1] && !a) return html(pageInconnu(seg[1], d), 404);
    if (seg[2] && !b) return html(pageInconnu(seg[2], d), 404);
    // Les matchs a venir ne conditionnent jamais l'affichage : aVenir()
    // avale ses propres pannes et rend une Map vide.
    if (a && b) return html(pageDuo(a, b, d, await aVenir(env)));
    if (a) return html(pageSolo(a, d, await aVenir(env)));
    return html(pageIndex(d));
  }

  const html = (s, st = 200) => new Response(s, {
    status: st,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=60',
    },
  });

  // ── STYLE ────────────────────────────────────────────────────────────────
  //
  // Sombre par defaut : la page s'ouvre depuis Telegram, ou l'ecran est
  // presque toujours sombre, et un tableau de cotes se lit comme un tableau
  // d'affichage - chiffres lumineux sur fond eteint. Le clair existe pour
  // qui a regle son telephone ainsi.
  //
  // Un seul accent, l'ambre des anciens tableaux d'affichage, reserve au
  // marqueur de prix. Tout le reste est neutre : la cote est la seule chose
  // qui doit attirer l'oeil.

  const CSS = `
  :root{
    --fond:#0E1116; --relief:#161A21; --trait:#242A34;
    --texte:#E9ECF1; --faible:#8B94A3; --accent:#E0A94A; --vif:#F2F5F9;
  }
  @media (prefers-color-scheme: light){
    :root{
      --fond:#FFFFFF; --relief:#F4F6F8; --trait:#DDE2E8;
      --texte:#161A21; --faible:#5E6775; --accent:#B07B14; --vif:#000;
    }
  }
  *{box-sizing:border-box}
  body{
    margin:0;padding:22px 16px 56px;background:var(--fond);color:var(--texte);
    font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
    font-variant-numeric:tabular-nums;
    max-width:620px;margin-inline:auto;-webkit-text-size-adjust:100%;
  }
  a{color:inherit}
  .retour{display:inline-block;color:var(--faible);text-decoration:none;
    font-size:13.5px;margin-bottom:26px}
  .retour:hover{color:var(--texte)}

  h1{font-size:28px;line-height:1.15;margin:0;font-weight:600;letter-spacing:-.01em}
  a.nomlien{color:inherit;text-decoration:underline;text-decoration-thickness:1px;
    text-underline-offset:4px;text-decoration-color:var(--accent)}
  .sous{color:var(--faible);font-size:13.5px;margin-top:5px}

  /* La cote : le seul endroit ou la page hausse la voix. */
  .prix{font-size:62px;line-height:1;font-weight:300;letter-spacing:-.035em;
    margin:26px 0 2px}
  .rang{color:var(--faible);font-size:13.5px}

  /* L'echelle. Elle porte l'information : ou se situe ce joueur parmi les
     autres. Les graduations sont des cotes reelles, pas un decor. */
  .axe{margin:26px 0 30px;position:relative;height:50px}
  .rail{position:absolute;top:17px;left:0;right:0;height:2px;background:var(--trait)}
  .grad{position:absolute;top:13px;width:1px;height:10px;background:var(--trait)}
  .glab{position:absolute;top:28px;transform:translateX(-50%);
    font-size:11.5px;color:var(--faible)}
  .mark{position:absolute;top:10px;width:3px;height:16px;background:var(--accent);
    transform:translateX(-1px)}
  .mlab{position:absolute;top:-8px;transform:translateX(-50%);font-size:12px;
    white-space:nowrap;font-weight:600}

  /* Les lignes de donnees : pas de cartes. Des reglures, comme un releve. */
  .bloc{border-top:1px solid var(--trait);padding-top:16px;margin-top:28px}
  .bloc h2{font-size:13.5px;color:var(--faible);font-weight:500;margin:0 0 12px}
  table{width:100%;border-collapse:collapse;font-size:15px}
  td{padding:7px 0;vertical-align:baseline}
  td:first-child{color:var(--faible);width:46%}
  td.n{text-align:right;font-variant-numeric:tabular-nums}
  .v{color:var(--vif);font-weight:600}
  .m{display:flex;gap:10px;padding:7px 0;align-items:baseline;font-size:15px}
  .m .d{color:var(--faible);font-size:13px;min-width:52px}
  .m .r{min-width:16px;font-weight:600}
  .m .r.gagne{color:var(--accent)}
  .m .r.perdu{color:var(--faible)}
  .m .a{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .m .sc{min-width:30px;color:var(--faible);font-size:13px;
    font-variant-numeric:tabular-nums}
  .m .ct{font-size:13px;color:var(--faible);font-variant-numeric:tabular-nums}
  .m .ct.contre{color:var(--texte, inherit);text-decoration:underline;
    text-decoration-color:var(--accent);text-underline-offset:3px}
  .m .a a{text-decoration:none;border-bottom:1px solid var(--trait)}
  .m .a a:hover{border-bottom-color:var(--accent)}

  /* Comparaison : deux colonnes, memes lignes, lecture horizontale. */
  .duo{width:100%;border-collapse:collapse;font-size:15px}
  .duo th{font-size:15px;font-weight:600;text-align:right;padding:0 0 14px;
    vertical-align:bottom;line-height:1.25}
  .duo th:first-child{text-align:left;font-weight:400;color:var(--faible);
    font-size:13.5px}
  .duo td{padding:8px 0;text-align:right;font-variant-numeric:tabular-nums}
  /* Les deux colonnes de valeurs se touchaient : « il y a 31 joursil y a
     8 jours ». Un espace fixe entre elles, et le texte peut passer à la
     ligne plutôt que déborder sur la voisine. */
  .duo td+td,.duo th+th{padding-left:14px}
  .nw{white-space:nowrap}
  .rec{font-size:13px;font-weight:600}
  .tdc{font-size:12.5px;font-weight:600;color:var(--faible);white-space:nowrap}
  .tdc.h{color:var(--accent)}
  .tdc.b{color:#b4483c}
  .att{font-size:12px;color:var(--faible);font-weight:400}
  .duo td:first-child{text-align:left;color:var(--faible)}
  .duo tr+tr td{border-top:1px solid var(--trait)}

  /* Le bandeau du match a venir : le seul endroit ou l'accent sert a
   autre chose qu'un prix, parce que c'est la seule information de la
   page qui perime. */
.avenir{border-left:3px solid var(--accent);padding:10px 0 10px 13px;
  margin:22px 0 4px;font-size:15px;line-height:1.5}
.avenir b{font-weight:600}
.avenir a{text-decoration:none;border-bottom:1px solid var(--trait)}
.avenir .px{margin-top:7px;font-size:14px;color:var(--faible)}
.avenir .px b{color:var(--texte);font-weight:600}
.avenir .ec{color:var(--accent);font-weight:600}
/* L'ecart au prix habituel. L'accent signale un prix PLUS GENEREUX que
   d'ordinaire ; un match plus dur reste en gris, pour ne pas suggerer
   qu'un outsider est une occasion. */
.ec{font-size:13px;font-weight:600;color:var(--accent);margin-left:7px;
  white-space:nowrap}
.ec.dur{color:var(--faible)}

/* Les trois surfaces, sur une ligne. La meilleure prend l'accent — c'est
   la seule chose a retenir quand on compare deux joueurs. */
.surf{display:flex;gap:18px;flex-wrap:wrap;font-size:15px}
.surf .su{color:var(--faible)}
.surf .su b{color:var(--texte);font-weight:600;font-variant-numeric:tabular-nums}
.surf .su.mieux{color:var(--accent)}
.surf .su.mieux b{color:var(--accent)}
.surf .su.moins b{opacity:.55}

.note{color:var(--faible);font-size:12.5px;line-height:1.6;
    border-top:1px solid var(--trait);margin-top:34px;padding-top:16px}
  .liste a{display:flex;justify-content:space-between;gap:12px;
    padding:9px 0;border-bottom:1px solid var(--trait);text-decoration:none}
  .liste a:last-child{border-bottom:0}
  .liste .c{color:var(--accent);font-weight:600;white-space:nowrap}
  .liste .n{color:var(--faible);font-size:12.5px;font-weight:400;margin-left:8px}
  /* Le rang en chiffre devant le nom : deux classements cote a cote se
     relisent mal sans lui, l'ordre seul ne suffit plus a le porter. */
  .liste .r{display:inline-block;min-width:22px;color:var(--faible);
    font-size:12.5px;font-variant-numeric:tabular-nums}
  input{width:100%;padding:11px 13px;font:inherit;color:inherit;
    background:var(--relief);border:1px solid var(--trait);border-radius:7px;
    margin-bottom:14px}
  input:focus{outline:2px solid var(--accent);outline-offset:1px}
  `;

  // `partage` alimente la carte affichee quand le lien est colle sur X ou
  // envoye dans Telegram. Sans elle, le lien s'affiche nu : c'est la moitie
  // de l'interet d'une page publique qui disparait.
  function enveloppe(titre, corps, extra = '', partage = '') {
    return `<!doctype html><html lang="fr"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${esc(titre)}</title>
  <meta property="og:title" content="${esc(titre)}">
  <meta property="og:type" content="website">
  ${partage ? `<meta property="og:description" content="${esc(partage)}">
  <meta name="description" content="${esc(partage)}">` : ''}
  <meta name="twitter:card" content="summary">
  <style>${CSS}</style></head><body>
  <a class="retour" href="/j">Tennis Edge · classement marché</a>
  ${corps}
  <p class="note">Le classement marché est la cote que Pinnacle donnerait au
  joueur face à un joueur moyen de son circuit. Il est calculé sur tous ses
  matchs cotés, marge retirée, en tenant compte de la force de chaque
  adversaire : battre le marché contre un 300e compte moins que contre un
  20e. C’est une mesure de ce que le marché pense de lui, pas une prévision.<br><br>
  18+ · Jouer comporte des risques ·
  <a href="https://www.joueurs-info-service.fr">joueurs-info-service.fr</a></p>
  ${extra}</body></html>`;
  }

  // ── L'ECHELLE ────────────────────────────────────────────────────────────

  function axe(joueurs) {
    const grads = [1.1, 1.5, 2, 3, 4.5];
    const g = grads.map((c) => {
      const x = (100 * pos(c)).toFixed(1);
      return `<i class="grad" style="left:${x}%"></i>`
           + `<i class="glab" style="left:${x}%">${fr(c, c < 2 ? 2 : 1)}</i>`;
    }).join('');
    const m = joueurs.filter((j) => j.cote != null).map((j, i) => {
      const x = (100 * pos(j.cote)).toFixed(1);
      // Deux marqueurs proches se chevaucheraient : on decale l'etiquette
      // du second au-dessus plutot que de la laisser illisible.
      const haut = i === 1 ? 'top:-26px;' : '';
      return `<i class="mark" style="left:${x}%"></i>`
           + `<i class="mlab" style="left:${x}%;${haut}">${esc(j.court)}</i>`;
    }).join('');
    return `<div class="axe"><i class="rail"></i>${g}${m}</div>`;
  }

  const court = (nom) => {
    const t = String(nom).trim().split(/\s+/);
    return t.length > 1 ? `${t[0][0]}. ${t[t.length - 1]}` : nom;
  };

  // ── FICHE ────────────────────────────────────────────────────────────────

  function ligne(lib, val, fort) {
    if (val == null || val === '') return '';
    return `<tr><td>${lib}</td><td class="n${fort ? ' v' : ''}">${val}</td></tr>`;
  }

  // BILAN EN FAVORI / OUTSIDER (format du 09/10, historique tennis-data) :
  //   67 % · 99 sur 148          <- tous ses matchs cotés depuis « depuis »
  //   marché 64 % · depuis 2017  <- ce que les cotes annonçaient
  //   20 derniers : 75 % (marché 67 %) → stable
  // Le pourcentage du marché à côté de chaque pourcentage : 75 % ne veut rien
  // dire seul, il veut dire quelque chose à côté de 67 %.
  const pctS = (b) => Math.round(100 * b.victoires / b.n);
  const pctM = (b) => Math.round(100 * b.attendu / b.n);
  const TEND = {
    hausse: '<span class="tdc h">↗ en hausse</span>',
    baisse: '<span class="tdc b">↘ en baisse</span>',
    stable: '<span class="tdc">→ stable</span>',
  };
  // MÊME STRUCTURE POUR TOUS LES JOUEURS (09/10). Avant, un joueur avec
  // moins de 20 matchs dans un statut (souvent en Challenger, sans
  // historique tennis-data) n'avait ni ligne « derniers » ni tendance :
  // deux fiches côte à côte ne se ressemblaient pas. Désormais la ligne
  // existe toujours (« 7 derniers » s'il n'y en a que 7) et la tendance dit
  // « trop peu de matchs » au lieu de disparaître.
  const recentDe = (b) => b.recent || b;
  const tendance = (b) => (b.tendance && TEND[b.tendance])
    ? TEND[b.tendance] : '<span class="tdc">tendance : trop peu de matchs</span>';
  const tendanceCourte = (b) => (b.tendance && TEND[b.tendance])
    ? TEND[b.tendance] : '<span class="tdc">trop tôt</span>';
  function bilanStatut(b) {
    const r = recentDe(b);
    return `${pctS(b)}&nbsp;% · ${b.victoires} sur ${b.n}`
      + `<br><span class="att">le marché prévoyait ${pctM(b)}&nbsp;%</span>`
      + (b.depuis ? `<br><span class="att">depuis ${esc(b.depuis)}</span>` : '')
      + `<br><span class="rec nw">${r.n} derniers : ${pctS(r)}&nbsp;%</span>`
      + `<br><span class="att nw">le marché prévoyait ${pctM(r)}&nbsp;%</span>`
      + `<br>${tendance(b)}`;
  }
  function bilanStatutCourt(b) {
    if (!b) return null;
    const r = recentDe(b);
    return `<span class="nw">${pctS(b)}&nbsp;% · ${b.victoires}/${b.n}</span>`
      + `<br><span class="att nw">prévu ${pctM(b)}&nbsp;%</span>`
      + `<br><span class="rec nw">${r.n} derniers ${pctS(r)}&nbsp;%</span>`
      + `<br><span class="att nw">prévu ${pctM(r)}&nbsp;%</span>`
      + `<br>${tendanceCourte(b)}`;
  }

  function corpsFiche(p, d) {
    const L = [];
    if (p.rang_officiel)
      L.push(ligne(`Classement ${CIRC(p) || 'officiel'}`,
        `${officiel(p)}<br><span class="att">au ${jjmm(p.rang_officiel.date)}</span>`, true));
    if (p.cote_adversaires != null)
      L.push(ligne('Cote de ses adversaires', fr(p.cote_adversaires)));
    if (p.pct_favori != null)
      L.push(ligne('Favori avant le match', `${p.pct_favori} %`));
    // Ce qu'il fait de ce statut, sur tous ses matchs cotés, à côté de ce
    // que le marché attendait (somme des probabilités d'avant-match).
    if (p.en_favori)
      L.push(ligne('Gagne quand favori', bilanStatut(p.en_favori), true));
    if (p.en_outsider)
      L.push(ligne('Gagne quand outsider', bilanStatut(p.en_outsider), true));
    // UNE seule ligne de bilan depuis le 09/10, calculée par build_profiles
    // sur les mêmes matchs que la liste « Derniers matchs ». L'ancienne
    // fiche affichait « Matchs gagnés 0/2 » (alertes seules) à côté de
    // « Sur ses 10 derniers 5/10 » (tous les matchs) : deux chiffres pour
    // la même question, qui se contredisaient.
    if (p.recent) {
      L.push(ligne('Sur ses 10 derniers',
        `${p.recent.victoires} sur ${p.recent.n}`, true));
      if (p.recent.set1_n)
        L.push(ligne('1ers sets gagnés',
          `${p.recent.set1_gagnes} sur ${p.recent.set1_n}`, true));
    } else if (p.bilan) {
      L.push(ligne('Matchs gagnés', `${p.bilan.victoires} sur ${p.bilan.n}`, true));
    }
    // DATES CALCULEES AU RENDU, jamais lues toutes faites.
    //
    // player_form.json portait `jours_depuis_dernier`, fige a l'instant ou
    // le fichier a ete produit. Le 05/10 il valait 1 et c'etait juste ; la
    // page l'affichait encore « hier » le 08/10, trois jours plus tard, pour
    // un match du 04/10 visible deux lignes plus bas.
    //
    // Une duree relative ne se stocke pas. On garde la DATE, qui ne perime
    // pas, et on calcule l'ecart a l'ouverture de la page.
    const dates = (p.derniers || []).map((m) => m.date).filter(Boolean).sort();
    if (dates.length) {
      const d0 = Date.parse(dates[dates.length - 1] + 'T12:00:00Z');
      const j7 = dates.filter(
        (x) => Date.now() - Date.parse(x + 'T12:00:00Z') < 7 * 86400000).length;
      if (j7) L.push(ligne('Joués sur 7 jours', pl(j7, 'match', 'matchs')));
      L.push(ligne('Dernier match', depuis((Date.now() - d0) / 86400000)));
    }
    if (p.meilleur_prix)
      L.push(ligne('Meilleur prix le plus souvent', esc(p.meilleur_prix)));
    if (p.elo)
      L.push(ligne('Elo', `<b>${p.elo.valeur}</b>`, true));

    const tbl = L.filter(Boolean).join('');

    // Chaque adversaire deja vu renvoie vers la comparaison des deux : c'est
    // le chemin le plus court entre « il a battu X » et « que vaut X ».
    // Chaque ligne : date, résultat, score en sets, adversaire, et la cote
    // JUSTE qu'il avait avant le match. C'est elle qui donne son sens au
    // résultat : « battu à 1,30 » et « battu à 3,50 » ne racontent pas la
    // même chose. Le résultat est souligné quand il contredit la cote —
    // un favori battu, un outsider vainqueur.
    const der = (p.derniers || []).map((m) => {
      const r = m.gagne === true ? 'V' : (m.gagne === false ? 'D' : '·');
      const c = m.gagne === true ? ' gagne' : (m.gagne === false ? ' perdu' : '');
      const dd = m.date ? m.date.slice(8, 10) + '/' + m.date.slice(5, 7) : '';
      const fiche = d && d.joueurs[m.adv_cle];
      const nom = esc(m.adv || '');
      const a = fiche
        ? `<a href="/j/${slug(p.nom)}/${slug(m.adv)}">${nom}</a>` : nom;
      const sc = score(m);
      const contre = m.cote != null && m.gagne != null
        && ((m.gagne && m.cote >= 2) || (!m.gagne && m.cote < 2));
      const ct = m.cote != null
        ? `<span class="ct${contre ? ' contre' : ''}">${fr(m.cote)}</span>` : '';
      return `<div class="m"><span class="d">${dd}</span>`
           + `<span class="r${c}">${r}</span>`
           + (sc ? `<span class="sc">${sc}</span>` : '')
           + `<span class="a">${a}</span>${ct}</div>`;
    }).join('');
    const legendeDer = (p.derniers || []).some((m) => m.cote != null)
      ? `<p class="note" style="border:0;margin-top:10px;padding-top:0">`
        + `À droite, sa cote avant le match, marge retirée. Soulignée quand`
        + ` le résultat l’a contredite : battu en favori, vainqueur en`
        + ` outsider.</p>`
      : '';


    // Les trois surfaces, la meilleure mise en avant quand elle devance
    // nettement la deuxieme — sinon les trois chiffres parlent d'eux-memes.
    const su = elo_surfaces(p.elo);
    const blocSu = su
      ? `<div class="bloc"><h2>Elo par surface</h2><div class="surf">${su}</div>`
        + `<p class="note" style="border:0;margin-top:10px;padding-top:0">`
        + `${esc(elo_phrase(p.elo))}</p>`
        + `</div>`
      : '';

    const legendeStatut = (p.en_favori || p.en_outsider)
      ? `<p class="note" style="border:0;margin-top:10px;padding-top:0">`
        + `Favori / outsider : tous ses matchs cotés par Pinnacle depuis l’année`
        + ` indiquée (circuit principal jusqu’en janvier 2026, puis nos relevés),`
        + ` comparés à ce que les cotes annonçaient. « En hausse » ou « en baisse »`
        + ` seulement quand ses derniers matchs s’écartent de son passé plus que le`
        + ` hasard ne l’explique. Ce n’est pas une prévision.</p>`
      : '';
    return (tbl ? `<div class="bloc"><h2>Repères</h2><table>${tbl}</table>${legendeStatut}</div>` : '')
      + blocSu
      + (der ? `<div class="bloc"><h2>Derniers matchs</h2>${der}${legendeDer}</div>` : '')
      ;
  }

  // ── CE QUI ARRIVE ──────────────────────────────────────────────────────
  //
  // Le seul bloc de la page qui regarde devant, et il est tout en haut :
  // quelqu'un qui ouvre la fiche depuis une alerte veut d'abord savoir si
  // le match est encore a jouer.
  function bandeau(av, nom, d) {
    const m = av && av.get(cleNom(nom));
    if (!m) return '';
    const dt = new Date(m.t);
    const mn = Math.round((m.t - Date.now()) / 60000);
    const h2 = (x) => String(x).padStart(2, '0');
    const quand = mn <= 0 ? 'en ce moment'
      : mn < 60 ? `dans ${pl(mn, 'minute')}`
        : mn < 1440 ? `à ${h2(dt.getUTCHours())}h${h2(dt.getUTCMinutes())} UTC`
          : `le ${h2(dt.getUTCDate())}/${h2(dt.getUTCMonth() + 1)}`;
    const adv = d.joueurs[cleNom(m.adv)]
      ? `<a href="/j/${slug(nom)}/${slug(m.adv)}">${esc(m.adv)}</a>`
      : esc(m.adv);
    // Le meilleur prix n'est signale que s'il bat vraiment Pinnacle : un
    // ecart d'un centieme n'est pas une information, c'est du bruit
    // d'arrondi qui donnerait l'air de recommander quelque chose.
    const ecart = (m.ref && m.best) ? (m.best / m.ref - 1) * 100 : 0;
    const ec = m.ref ? ecart_mediane(m.refJuste || m.ref,
      (d.joueurs[cleNom(nom)] || {}).cote_mediane) : null;
    const px = m.ref
      ? `<div class="px">${esc(m.source)} <b>${fr(m.ref)}</b>${ecart_html(ec)}`
        + (ecart >= 1
          ? ` · meilleur prix <b>${fr(m.best)}</b> chez ${esc(m.bestBook)}`
            + ` <span class="ec">+${fr(ecart, 1)} %</span>`
          : '')
        + `</div>`
      : '';
    const cmp = (ec !== null && Math.abs(ec) >= 2)
      ? `<div class="px">${ec < 0 ? 'Match plus dur' : 'Match plus facile'}`
        + ` que son ordinaire — il est coté ${fr(m.ref)} contre`
        + ` ${fr(d.joueurs[cleNom(nom)].cote_mediane)} en médiane.</div>`
      : '';
    return `<div class="avenir"><b>Joue ${esc(quand)}</b>`
         + (m.tour ? ` · ${esc(m.tour)}` : '')
         + `<br>contre ${adv}${px}${cmp}</div>`;
  }

  // ── CONFRONTATION DIRECTE ────────────────────────────────────────────────
  //
  // Les deux fiches portent chacune la liste de leurs matchs avec la cle du
  // adversaire : l'intersection se lit sans rien recharger. On part de la
  // fiche de `a`, donc `gagne` est deja de son point de vue.
  // Score en sets, vu du joueur. Un score sans vainqueur net (« 0-1 »,
  // « 0-0 ») vient d'un abandon ou d'un règlement partiel : on le dit
  // plutôt que d'afficher un score qui n'existe pas.
  function score(m) {
    if (!m.sets) return '';
    const [x, y] = m.sets.split('-').map(Number);
    if (!(x >= 2 || y >= 2)) return 'ab.';
    return m.sets;
  }

  function confrontations(a, b) {
    const cleB = cleNom(b.nom);
    return (a.derniers || [])
      .filter((m) => m.adv_cle === cleB)
      .sort((x, y) => (y.date || '').localeCompare(x.date || ''));
  }

  function pageSolo(p, d, av) {
    const sousTitre = [
      `${p.n_matchs_vus} match${p.n_matchs_vus > 1 ? 's' : ''} suivi${p.n_matchs_vus > 1 ? 's' : ''}`,
      p.periode ? `depuis le ${p.periode[0].slice(8, 10)}/${p.periode[0].slice(5, 7)}` : '',
    ].filter(Boolean).join(', ')
      // Le circuit vient de `circuit`, pas de `elo.tour` : l'Elo n'en
      // couvre que 701 fiches, le graphe des adversaires en porte 886.
      + (p.circuit ? ` · ${CIRC(p)}` : '');

    // Un rang n'est publie qu'au-dela du seuil : en dessous, la mediane
    // reste juste mais la place qu'elle donne ne l'est pas. Le rang est
    // celui de SON circuit — nommé, sans quoi « 12e sur 86 » ne dit pas
    // de quoi.
    const legende = p.rang_marche
      ? `Rang marché opérateur : ${ord(p.rang_marche, FEM(p))} sur ${p.rang_sur}`
        + ` ${joueurs(p, p.rang_sur)} ${classes(p, p.rang_sur)}`
        + ` · ${pl(p.n_cotes, 'cote')} relevée${p.n_cotes > 1 ? 's' : ''}`
      : `${pl(p.n_cotes, 'cote')} relevée${p.n_cotes > 1 ? 's' : ''}`
        + (p.circuit
          ? ` · trop peu pour un rang`
          // Sans circuit il n'y a aucun classement où le placer : le dire,
          // plutôt que laisser croire au seuil de cotes.
          : ` · circuit inconnu, pas de classement`);

    const prix = CL(p) != null
      ? `<div class="prix">${fr(CL(p))}</div>`
        + `<div class="rang">${legende}</div>`
        + axe([{ cote: CL(p), court: court(p.nom) }])
      : `<div class="bloc"><h2>Classement marché</h2>`
        + `<p style="margin:0;color:var(--faible)">Moins de ${d.meta.min_cotes}`
        + ` cotes relevées : pas encore de classement.</p></div>`;

    const circ = (p.circuits || []).length
      // Pas « où il joue » : la base melange ATP et WTA, et rien dans les
      // donnees ne dit lequel. Un titre neutre evite de se tromper une fois
      // sur deux.
      ? `<div class="bloc"><h2>Tournois</h2><p style="margin:0">`
        + p.circuits.map(esc).join('<br>') + `</p></div>`
      : '';

    return enveloppe(`${p.nom} — Tennis Edge`,
      `<h1>${esc(p.nom)}</h1><div class="sous">${esc(sousTitre)}</div>`
      + bandeau(av, p.nom, d) + prix + corpsFiche(p, d) + circ
      + `<div class="bloc"><h2>Comparer</h2>`
      + `<input id="q" placeholder="Nom d’un autre joueur" autocomplete="off">`
      + `<div class="liste" id="res"></div></div>`,
      scriptRecherche(d, p.nom),
      [CL(p) != null ? `Classement marché ${fr(CL(p))}` : null,
       p.rang_marche
         ? `${p.rang_marche}/${p.rang_sur} au classement ${CIRC(p)}` : null,
       p.recent ? `${p.recent.victoires} victoires sur ses ${p.recent.n} derniers matchs`
         : (p.bilan ? `${p.bilan.victoires} victoires sur ${p.bilan.n} matchs suivis` : null),
      ].filter(Boolean).join(' · '));
  }

  function pageDuo(a, b, d, av) {
    const marq = [a, b].filter((p) => CL(p) != null)
      .map((p) => ({ cote: CL(p), court: court(p.nom) }));

    const L = [];
    const r = (lib, fa, fb) => {
      const va = fa(a), vb = fb ? fb(b) : fa(b);
      if (va == null && vb == null) return;
      L.push(`<tr><td>${lib}</td><td>${va == null ? '—' : va}</td>`
           + `<td>${vb == null ? '—' : vb}</td></tr>`);
    };
    r('Classement marché', (p) => CL(p) == null ? null
      : `<span class="v">${fr(CL(p))}</span>`);
    // Deux circuits différents en vis-à-vis n'arrive que si on compare la
    // main : les rangs ne se comparent alors pas, donc on les nomme.
    r(a.circuit && a.circuit === b.circuit
      ? `Classement ${CIRC(a)}` : 'Classement officiel',
      (p) => p.rang_officiel
        ? `${officiel(p)}<br><span class="att">au ${jjmm(p.rang_officiel.date)}</span>`
        : null);
    // « Rang marché opérateur » (10/10) : NOTRE rang, tiré des cotes — pas
    // le classement ATP/WTA, affiché sur la ligne du dessus.
    r('Rang marché opérateur',
      (p) => p.rang_marche
        ? ord(p.rang_marche, FEM(p))
          + (a.circuit === b.circuit ? '' : ` <span class="n">${CIRC(p)}</span>`)
        : null);
    r('Cote de ses adversaires', (p) => p.cote_adversaires == null ? null
      : fr(p.cote_adversaires));
    // On ne montre le prix du jour QUE si ces deux-la jouent l'un contre
    // l'autre. Deux joueurs qui jouent chacun de leur cote le meme soir
    // ont des prix qui ne se comparent pas — les afficher cote a cote
    // ferait croire a une confrontation qui n'existe pas.
    const ma = av && av.get(cleNom(a.nom));
    const mb = av && av.get(cleNom(b.nom));
    const memeMatch = ma && mb && cleNom(ma.adv) === cleNom(b.nom);
    if (memeMatch) {
      r('Coté pour ce match', (p) => {
        const m = (p === a) ? ma : mb;
        if (!m || !m.ref) return null;
        return `<span class="v">${fr(m.ref)}</span>`
             + ecart_html(ecart_mediane(m.refJuste || m.ref, p.cote_mediane))
             + (m.pin ? '' : '<br><span class="att nw">sans Pinnacle</span>');
      });
    }
    r('Elo', (p) => p.elo ? `<span class="v">${p.elo.valeur}</span>` : null);
    for (const n of Object.keys(SURF)) {
      r(`Elo ${SURF[n]}`, (p) => (p.elo && p.elo.surfaces
        && p.elo.surfaces[n] != null)
        ? (p.elo.meilleure_surface === n
          ? `<b>${p.elo.surfaces[n]}</b>` : `${p.elo.surfaces[n]}`)
        : null);
    }
    r('Favori avant le match', (p) => p.pct_favori == null ? null : `${p.pct_favori} %`);
    r('Gagne quand favori', (p) => bilanStatutCourt(p.en_favori));
    r('Gagne quand outsider', (p) => bilanStatutCourt(p.en_outsider));
    r('Sur ses 10 derniers', (p) => p.recent
      ? `${p.recent.victoires}/${p.recent.n}`
      : (p.bilan ? `${p.bilan.victoires}/${p.bilan.n}` : null));
    r('1ers sets gagnés', (p) => (p.recent && p.recent.set1_n)
      ? `${p.recent.set1_gagnes}/${p.recent.set1_n}` : null);
    // Memes dates calculees au rendu que sur la fiche solo : une duree lue
    // toute faite dans le fichier perime des le lendemain.
    const dmax = (p) => {
      const d = (p.derniers || []).map((m) => m.date).filter(Boolean).sort();
      return d.length ? Date.parse(d[d.length - 1] + 'T12:00:00Z') : null;
    };
    const n7 = (p) => (p.derniers || []).filter(
      (m) => m.date
        && Date.now() - Date.parse(m.date + 'T12:00:00Z') < 7 * 86400000).length;
    r('Joués sur 7 jours', (p) => n7(p) || null);
    r('Depuis le dernier match', (p) => {
      const t = dmax(p);
      return t === null ? null : depuis((Date.now() - t) / 86400000);
    });

    // ── Ce qu'ils se sont fait ────────────────────────────────────────────
    //
    // Le seul chiffre de la page qui ne soit ni une cote ni une moyenne :
    // ce qui s'est passe quand ces deux-la se sont trouves en face.
    const h2h = confrontations(a, b);
    const blocH2H = h2h.length
      ? `<div class="bloc"><h2>Quand ils se sont croisés</h2>`
        + h2h.map((m) => {
          const dd = m.date ? m.date.slice(8, 10) + '/' + m.date.slice(5, 7)
            + '/' + m.date.slice(2, 4) : '';
          const gagnant = m.gagne === true ? a.nom
            : (m.gagne === false ? b.nom : null);
          // Le premier set n'est signale que s'il contredit le resultat :
          // « il a gagne, et il avait gagne le 1er set » n'apprend rien.
          const retourne = m.gagne != null && m.set1 != null && m.set1 !== m.gagne;
          const s1 = retourne
            ? ` après avoir perdu le 1<sup>er</sup> set` : '';
          const sc = score(m);
          const scVu = sc && sc !== 'ab.' && m.gagne === false
            ? sc.split('-').reverse().join('-') : sc;
          return `<div class="m"><span class="d">${dd}</span>`
               + `<span class="a">${gagnant
                 ? `<b>${esc(gagnant)}</b> l’emporte${scVu
                   ? (scVu === 'ab.' ? ' (abandon)' : ` ${scVu}`) : ''}${s1}`
                 : 'résultat inconnu'}</span></div>`;
        }).join('')
        + `</div>`
      : `<div class="bloc"><h2>Quand ils se sont croisés</h2>`
        + `<p style="margin:0;color:var(--faible)">Jamais, dans les matchs`
        + ` suivis ici.</p></div>`;

    return enveloppe(`${a.nom} / ${b.nom} — Tennis Edge`,
      // Chaque nom mène à la fiche individuelle du joueur (10/10) : depuis
      // une alerte on arrive ici, et c'est d'ici qu'on va voir l'un ou l'autre.
      `<h1><a class="nomlien" href="/j/${slug(a.nom)}">${esc(a.nom)}</a><br>`
      + `<a class="nomlien" href="/j/${slug(b.nom)}">${esc(b.nom)}</a></h1>`
      + `<div class="sous">Les deux sur la même échelle de prix</div>`
      + bandeau(av, a.nom, d)
      + (marq.length ? axe(marq) : '')
      + `<table class="duo"><tr><th>&nbsp;</th>`
      + `<th><a class="nomlien" href="/j/${slug(a.nom)}">${esc(a.nom)}</a></th>`
      + `<th><a class="nomlien" href="/j/${slug(b.nom)}">${esc(b.nom)}</a></th></tr>`
      + `${L.join('')}</table>`
      + ((a.en_favori || b.en_favori || a.en_outsider || b.en_outsider)
        ? `<p class="note" style="border:0;margin-top:10px">Gagne quand favori /`
          + ` outsider : son pourcentage de victoires, sur tous ses matchs cotés`
          + ` puis sur ses 20 derniers. « Prévu » : ce que les cotes lui donnaient.`
          + ` Au-dessus, il fait mieux que le marché ne l’attendait.</p>`
        : '')
      + blocH2H
      + `<div class="bloc"><h2>Fiches complètes</h2><div class="liste">`
      + `<a href="/j/${slug(a.nom)}"><span>${esc(a.nom)}</span>`
      + `<span class="c">${fr(CL(a))}</span></a>`
      + `<a href="/j/${slug(b.nom)}"><span>${esc(b.nom)}</span>`
      + `<span class="c">${fr(CL(b))}</span></a></div></div>`,
      '',
      `${a.nom} ${fr(CL(a))} contre ${b.nom} ${fr(CL(b))}`
      + ` — classement marché, cote face à un joueur moyen du circuit`);
  }

  function pageIndex(d) {
    // Le classement ne liste que les joueurs qui ont un rang. Les autres
    // restent cherchables : leur fiche existe, c'est leur place qui n'existe
    // pas. Le nombre de cotes est affiche a cote du prix pour que le lecteur
    // pese lui-meme : 1,40 sur huit cotes et 1,40 sur seize ne se valent pas.
    //
    // DEUX CLASSEMENTS. Les circuits ne se croisent jamais : aucun match
    // ne relie un homme et une femme, donc aucune cote ne les compare. Un
    // rang commun ne mesurait pas qui est le meilleur, il mesurait de quel
    // côté le marché cote le plus serré.
    const tous = Object.values(d.joueurs);
    const par = (cir) => tous
      .filter((p) => p.rang_marche && p.circuit === cir)
      .sort((x, y) => x.rang_marche - y.rang_marche);

    const liste = (cl) => cl.slice(0, 25).map((p) =>
      `<a href="/j/${slug(p.nom)}">`
      + `<span><span class="r">${p.rang_marche}</span>${esc(p.nom)}</span>`
      + `<span><span class="c">${fr(CL(p))}</span>`
      + `<span class="n">${p.n_cotes}</span></span></a>`).join('');

    const bloc = (cir, titre) => {
      const cl = par(cir);
      if (!cl.length) return '';
      return `<div class="bloc"><h2>${titre} · ${cl.length} ${
        cir === 'wta' ? 'joueuses' : 'joueurs'}</h2>`
        + `<div class="liste">${liste(cl)}</div></div>`;
    };

    const na = (d.meta.n_classes_atp || par('atp').length);
    const nw = (d.meta.n_classes_wta || par('wta').length);

    return enveloppe('Classement marché — Tennis Edge',
      `<h1>Classement marché</h1>`
      + `<div class="sous">${na} joueurs et ${nw} joueuses classés par la`
      + ` cote que Pinnacle leur donnerait face à un joueur moyen de leur`
      + ` circuit, en tenant compte de la force de leurs adversaires, sur`
      + ` ${d.meta.n_joueurs} fiches.`
      + ` Mis à jour le ${esc((d.meta.genere_le || '').slice(0, 10))}.</div>`
      + `<div class="bloc"><h2>Chercher</h2>`
      + `<input id="q" placeholder="Nom d’un joueur" autocomplete="off">`
      + `<div class="liste" id="res"></div></div>`
      + bloc('atp', 'Hommes') + bloc('wta', 'Femmes')
      + `<p class="note">Le second chiffre est le nombre de cotes relevées.`
      + ` Un rang demande au moins ${d.meta.min_rang || 8} cotes et un`
      + ` circuit connu ; sans l’un des deux la fiche existe, le rang non.`
      + ` Les deux classements ne se comparent pas : rien ne fait jouer un`
      + ` circuit contre l’autre, donc rien ne met les cotes sur la même`
      + ` échelle.</p>`,
      scriptRecherche(d),
      `${na} joueurs et ${nw} joueuses classés par le marché : la cote`
      + ` Pinnacle face à un joueur moyen du circuit, ajustée à la force des`
      + ` adversaires — le classement que fait le marché, pas la fédération.`);
  }

  function pageInconnu(s, d) {
    return enveloppe('Joueur inconnu — Tennis Edge',
      `<h1>Joueur inconnu</h1>`
      + `<div class="sous">Aucune fiche pour « ${esc(s.replace(/-/g, ' '))} ».`
      + ` Un joueur apparaît ici dès qu’un mouvement de marché a été détecté`
      + ` sur l’un de ses matchs.</div>`
      + `<div class="bloc"><h2>Chercher</h2>`
      + `<input id="q" placeholder="Nom d’un joueur" autocomplete="off">`
      + `<div class="liste" id="res"></div></div>`,
      scriptRecherche(d));
  }

  function pageErreur(e) {
    return enveloppe('Indisponible — Tennis Edge',
      `<h1>Fiches indisponibles</h1>`
      + `<div class="sous">Les données n’ont pas pu être chargées.`
      + ` Réessayez dans quelques minutes.</div>`
      + `<p class="note" style="border:0">${esc(e)}</p>`);
  }

  // La recherche tient dans la page : l'index fait quelques dizaines de ko,
  // contre un aller-retour reseau par frappe. Sur mobile en 4G, c'est la
  // difference entre instantane et poussif.
  function scriptRecherche(d, exclu) {
    const idx = Object.values(d.joueurs)
      .filter((p) => CL(p) != null && p.nom !== exclu)
      .sort((a, b) => CL(a) - CL(b))
      .map((p) => [p.nom, CL(p)]);
    const base = exclu ? `/j/${slug(exclu)}/` : '/j/';
    return `<script>
  const IDX=${JSON.stringify(idx)},BASE=${JSON.stringify(base)};
  const sl=n=>n.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase()
    .split(/[^a-z]+/).filter(t=>t.length>1).sort().join('-');
  const nn=s=>s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
  const q=document.getElementById('q'),res=document.getElementById('res');
  q.addEventListener('input',()=>{
    const v=nn(q.value.trim());
    if(v.length<2){res.innerHTML='';return}
    res.innerHTML=IDX.filter(([n])=>nn(n).includes(v)).slice(0,12)
      .map(([n,c])=>'<a href="'+BASE+sl(n)+'"><span>'+n+
        '</span><span class="c">'+c.toFixed(2).replace('.',',')+'</span></a>').join('')
      ||'<p style="color:var(--faible);padding:9px 0;margin:0">Aucun joueur de ce nom.</p>';
  });
  </script>`;
  }

  return { route: routeJoueurs, slug };
})();

// ── LE WORKER LUI-MEME ───────────────────────────────────────────────────
//
// Ce fichier est un worker COMPLET et autonome : a deployer dans un worker
// NEUF, pas dans tennis-edge-closing.
//
// tennis-edge-closing porte les crons qui declenchent capture_closing,
// Polymarket, Kalshi et les courbes. Toute la chaine en depend. Y ajouter
// des pages publiques, c'est mettre la collecte en jeu a chaque retouche
// d'affichage — pour une page qui n'a aucun besoin d'y etre.
//
// Les deux workers lisent le meme players_profile.json sur GitHub : ils
// n'ont rien a se dire.
//
// SI UN JOUR CE BLOC DOIT ALLER DANS UN WORKER EXISTANT : supprimer le
// `export default` ci-dessous, garder le reste, et appeler
// FICHES.route(url, env) au debut du fetch() de ce worker-la. C'est la
// raison du passage par `FICHES` : aucun nom ne fuit, donc aucune
// collision possible avec les helpers deja definis la-bas.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const r = await FICHES.route(url, env);
    if (r) return r;
    // Toute autre adresse retombe sur le classement plutot que sur un 404 :
    // c'est la racine du worker qu'on tapera depuis un telephone.
    return Response.redirect(new URL('/j', url).toString(), 302);
  },
};
