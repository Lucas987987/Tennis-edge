// 26/11/2026 (paquet 483, Lucas : « que les abonnés reçoivent des notifications quand un joueur ou un match est en
// favori et qu'il se passe quelque chose ») — NOTIFICATIONS DU TÉLÉPHONE (Web Push) POUR LES FAVORIS, abonnés Plus.
//
// Événements (choisis par Lucas) : le matin « joue aujourd'hui », le début du match, chaque break, la fin de chaque set,
// le résultat final (avec ce que l'algo avait annoncé). Seuls les matchs de la liste du site (site.json) sont suivis :
// un favori, c'est un joueur (nom du site) ou un match (uid du site).
//
// Comment :
//  • clés VAPID créées une fois par le worker et gardées dans le coffre R2 (notifs/vapid.json) : aucun secret à poser ;
//  • abonnement du téléphone (POST /compte/api/push) : gardé sur le compte et dans un index (notifs/index.json) qui ne
//    contient que les comptes ayant au moins un appareil — la tâche de chaque minute ne lit que cet index ;
//  • chaque minute (cron « * * * * * ») : s'il y a au moins un appareil, lecture du direct (live(), même cache et même
//    quota TennisApi que les visiteurs), rapprochement avec la liste du site (mêmes règles que la page), comparaison avec
//    l'état précédent (notifs/etat.json), envoi ;
//  • l'accès Plus est vérifié sur le compte au moment de l'envoi ; un appareil refusé (404/410) est retiré ;
//  • message chiffré (RFC 8291, aes128gcm) et signé (RFC 8292, VAPID), avec WebCrypto seulement ;
//  • garde-fous : 80 notifications par compte et par jour ; un break n'est annoncé que si exactement un jeu a été joué
//    depuis la minute précédente ET que le serveur a changé (sinon la donnée est douteuse : rien) ; jamais de break
//    dans un jeu décisif ; un match déjà avancé quand on le découvre n'a pas de « début ».
// Rien n'est envoyé hors abonnés Plus. Aucune cote. Le journal n'écrit ni adresse ni clé.
// Retrait : retirer le cron « * * * * * » de wrangler.toml (plus aucun envoi) ; les appareils restent enregistrés.
import { lire, ecrire, abonne } from './comptes.js';

const te = new TextEncoder();
export const VAPID_R2 = 'notifs/vapid.json', INDEX_R2 = 'notifs/index.json', ETAT_R2 = 'notifs/etat.json';
export const MAX_APPAREILS = 5, MAX_PAR_JOUR = 80, CONTACT = 'mailto:contact@gamesetalgo.com';
export const HOTES_PUSH = [/^fcm\.googleapis\.com$/, /(^|\.)push\.services\.mozilla\.com$/, /(^|\.)notify\.windows\.com$/,
  /(^|\.)push\.apple\.com$/, /^web\.push\.apple\.com$/];

// ------------------------------------------------------------------ outils
export const b64u = (u8) => btoa(String.fromCharCode(...new Uint8Array(u8))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export const deb64u = (s) => {
  s = String(s || '').replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(s + '='.repeat((4 - s.length % 4) % 4)), (c) => c.charCodeAt(0));
};
export const concat = (...L) => { const n = L.reduce((a, x) => a + x.length, 0), o = new Uint8Array(n); let i = 0; for (const x of L) { o.set(x, i); i += x.length; } return o; };
async function hkdf(sel, ikm, info, n) {
  const k = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt: sel, info }, k, n * 8));
}
async function lireJson(env, k) {
  try { const o = await env.COFFRE.get(k); return o ? { doc: JSON.parse(await o.text()), etag: o.etag } : { doc: null, etag: null }; }
  catch (e) { return { doc: null, etag: null }; }
}

// ------------------------------------------------------------------ clés VAPID (créées une fois, gardées dans R2)
let VAPID_MEMOIRE = null;
export const viderVapidMemoire = () => { VAPID_MEMOIRE = null; };
export async function clesVapid(env) {
  if (VAPID_MEMOIRE) return VAPID_MEMOIRE;
  let { doc } = await lireJson(env, VAPID_R2);
  if (!doc || !doc.jwk || !doc.publique) {
    const p = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
    const nouv = { publique: b64u(await crypto.subtle.exportKey('raw', p.publicKey)), jwk: await crypto.subtle.exportKey('jwk', p.privateKey),
      cree: new Date().toISOString() };
    await env.COFFRE.put(VAPID_R2, JSON.stringify(nouv));
    doc = (await lireJson(env, VAPID_R2)).doc || nouv;            // deux créations simultanées : la dernière écrite gagne pour tous
  }
  VAPID_MEMOIRE = doc;
  return doc;
}
export async function jetonVapid(env, endpoint, maintenant = Date.now()) {
  const v = await clesVapid(env);
  const aud = new URL(endpoint).origin;
  const tete = b64u(te.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const corps = b64u(te.encode(JSON.stringify({ aud, exp: Math.floor(maintenant / 1000) + 12 * 3600, sub: CONTACT })));
  const k = await crypto.subtle.importKey('jwk', v.jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, k, te.encode(tete + '.' + corps));
  return { jwt: `${tete}.${corps}.${b64u(sig)}`, k: v.publique };
}

// ------------------------------------------------------------------ chiffrement (RFC 8291, aes128gcm)
export async function chiffrer(texte, p256dh, auth) {
  const ua = deb64u(p256dh), secret = deb64u(auth);
  const eph = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', eph.publicKey));
  const uaCle = await crypto.subtle.importKey('raw', ua, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const partage = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaCle }, eph.privateKey, 256));
  const ikm = await hkdf(secret, partage, concat(te.encode('WebPush: info\0'), ua, asPub), 32);
  const sel = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(sel, ikm, te.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(sel, ikm, te.encode('Content-Encoding: nonce\0'), 12);
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const chiffre = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, aes, concat(te.encode(texte), new Uint8Array([2]))));
  return concat(sel, new Uint8Array([0, 0, 16, 0]), new Uint8Array([asPub.length]), asPub, chiffre);
}

export function appareilValide(a) {
  try {
    const u = new URL(String(a && a.endpoint));
    const k = a.keys || {};
    return u.protocol === 'https:' && HOTES_PUSH.some((r) => r.test(u.hostname)) && String(a.endpoint).length <= 1000
      && deb64u(k.p256dh).length === 65 && deb64u(k.auth).length === 16;
  } catch (e) { return false; }
}

// Un envoi : renvoie le code HTTP du service de notification (201 = accepté ; 404/410 = appareil à retirer).
export async function envoyerPush(env, appareil, message, ttl = 600) {
  const { jwt, k } = await jetonVapid(env, appareil.e);
  const corps = await chiffrer(JSON.stringify(message), appareil.k, appareil.s);
  try {
    const r = await fetch(appareil.e, { method: 'POST', body: corps, headers: { Authorization: `vapid t=${jwt}, k=${k}`,
      'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', TTL: String(ttl), Urgency: 'high' } });
    return r.status;
  } catch (e) { return 0; }
}

// ------------------------------------------------------------------ index des comptes qui ont un appareil
export function entreeIndex(u) {
  const f = (u && u.favoris) || {}, A = (u && u.push) || [];
  if (!A.length) return null;
  return { j: Array.isArray(f.joueurs) ? f.joueurs : [], m: Array.isArray(f.matchs) ? f.matchs : [], a: A, lang: u.lang === 'en' ? 'en' : 'fr' };
}
export async function majIndex(env, id, entree) {
  for (let i = 0; i < 4; i++) {
    const { doc, etag } = await lireJson(env, INDEX_R2);
    const I = doc && doc.u ? doc : { v: 1, u: {} };
    if (entree) I.u[id] = entree; else delete I.u[id];
    const r = await env.COFFRE.put(INDEX_R2, JSON.stringify(I), etag ? { onlyIf: { etagMatches: etag } } : {});
    if (r) return true;                                             // sinon : écrit entre-temps par un autre, on recommence
  }
  return false;
}
// Appelé quand les favoris ou les appareils d'un compte changent (et à sa suppression : u = null).
export async function suivreCompte(env, id, u) {
  try { const e = u ? entreeIndex(u) : null; const { doc } = await lireJson(env, INDEX_R2);
    if (!e && !(doc && doc.u && doc.u[id])) return; await majIndex(env, id, e); } catch (e) { /* jamais bloquant */ }
}

// POST /compte/api/push : { appareil: {endpoint, keys:{p256dh, auth}} } pour l'ajouter, { retirer: endpoint }, { essai: true }.
export async function routePush(env, u, b, rep) {
  u.push = Array.isArray(u.push) ? u.push : [];
  if (b.retirer) {
    u.push = u.push.filter((a) => a.e !== String(b.retirer));
    await ecrire(env, u); await suivreCompte(env, u.id, u);
    return rep({ ok: true, appareils: u.push.length });
  }
  if (!abonne(u)) return rep({ ok: false, erreur: 'plus' }, 403);
  if (b.appareil) {
    if (!appareilValide(b.appareil)) return rep({ ok: false, erreur: 'requete' }, 400);
    const a = { e: String(b.appareil.endpoint), k: b.appareil.keys.p256dh, s: b.appareil.keys.auth, le: new Date().toISOString() };
    u.push = [a, ...u.push.filter((x) => x.e !== a.e)].slice(0, MAX_APPAREILS);
    await ecrire(env, u); await suivreCompte(env, u.id, u);
    const code = await envoyerPush(env, a, { titre: TXT[u.lang === 'en' ? 'en' : 'fr'].pret_t, texte: TXT[u.lang === 'en' ? 'en' : 'fr'].pret, url: '/', tag: 'gsa-pret' });
    return rep({ ok: true, appareils: u.push.length, envoi: code });
  }
  if (b.essai) {
    let n = 0;
    for (const a of u.push) if ((await envoyerPush(env, a, { titre: TXT[u.lang === 'en' ? 'en' : 'fr'].pret_t, texte: TXT[u.lang === 'en' ? 'en' : 'fr'].essai, url: '/', tag: 'gsa-essai' })) < 300) n++;
    return rep({ ok: true, envoyes: n, appareils: u.push.length });
  }
  return rep({ ok: false, erreur: 'requete' }, 400);
}

// ------------------------------------------------------------------ textes
export const TXT = {
  fr: { pret_t: 'Game Set Algo', pret: 'Notifications activées : tu seras prévenu pour tes favoris.', essai: 'Test réussi : les notifications arrivent bien.',
    matin_t: '⭐ Tes favoris jouent aujourd\'hui', matin: (L) => L.join(' · ') + '. Le pronostic de l\'algo est en ligne.',
    ligne: (j, h, adv) => `${j} à ${h} contre ${adv}`,
    debut: (m) => `C'est parti : ${m.home} – ${m.away}`, debut_t: '▶️ Début du match',
    brk_t: (j) => `🎾 Break de ${j}`, brk: (j, sc, s) => `${sc} dans le ${s === 1 ? '1er' : s + 'e'} set`,
    set_t: (j, s) => `Set ${s} pour ${j}`, set: (sc) => `Sets : ${sc}`,
    fin_t: (g, p) => `🏁 ${g} bat ${p}`,
    fin: (sc, algo) => `${sc}. ${algo}`,
    algo_ok: (j, p) => `L'algo le donnait gagnant à ${p} % ✅`, algo_ko: (j, p) => `L'algo donnait ${j} à ${p} % ❌` },
  en: { pret_t: 'Game Set Algo', pret: 'Notifications on: you will hear about your favourites.', essai: 'Test passed: notifications arrive.',
    matin_t: '⭐ Your favourites play today', matin: (L) => L.join(' · ') + '. The algo\'s forecast is online.',
    ligne: (j, h, adv) => `${j} at ${h} vs ${adv}`,
    debut: (m) => `Under way: ${m.home} – ${m.away}`, debut_t: '▶️ Match started',
    brk_t: (j) => `🎾 Break for ${j}`, brk: (j, sc, s) => `${sc} in set ${s}`,
    set_t: (j, s) => `Set ${s} to ${j}`, set: (sc) => `Sets: ${sc}`,
    fin_t: (g, p) => `🏁 ${g} beats ${p}`,
    fin: (sc, algo) => `${sc}. ${algo}`,
    algo_ok: (j, p) => `The algo had them winning at ${p}% ✅`, algo_ko: (j, p) => `The algo had ${j} at ${p}% ❌` },
};

// ------------------------------------------------------------------ rapprochement direct ↔ liste du site (comme la page)
const motsNom = (n) => new Set(String(n || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((w) => w.length >= 2));
const memeJoueur = (a, b) => { const A = motsNom(a); for (const w of motsNom(b)) if (A.has(w)) return true; return false; };
const t0 = (m) => Date.parse(m.debut_utc || (m.debut && !/[zZ]|[+-]\d\d:?\d\d$/.test(m.debut) ? m.debut + 'Z' : m.debut));
export function relier(siteMatchs, x) {
  const commence = ((x.score_home && x.score_home.sets) || []).length > 0 || !!x.interrompu;
  for (const m of siteMatchs || []) {
    const t = t0(m);
    if (x.debut && Number.isFinite(t) && Math.abs(x.debut * 1000 - t) > (commence ? 40 : 8) * 3600e3) continue;
    if (memeJoueur(m.home, x.home) && memeJoueur(m.away, x.away)) return { m, inverse: false };
    if (memeJoueur(m.home, x.away) && memeJoueur(m.away, x.home)) return { m, inverse: true };
  }
  return null;
}
// Score orienté comme sur le site (home du site d'abord)
export function oriente(x, inverse) {
  const h = (inverse ? x.score_away : x.score_home) || {}, a = (inverse ? x.score_home : x.score_away) || {};
  const srv = x.serveur ? ((x.serveur === 'home') !== inverse ? 'h' : 'a') : null;
  return { h: (h.sets || []).map(Number), a: (a.sets || []).map(Number), srv };
}
export const setFini = (g, o) => (Math.max(g, o) >= 6 && Math.abs(g - o) >= 2) || (Math.max(g, o) === 7 && Math.min(g, o) >= 5);
export function setsGagnes(s) {
  let h = 0, a = 0;
  s.h.forEach((g, i) => { const o = s.a[i] || 0; if (setFini(g, o)) { if (g > o) h++; else a++; } });
  return { h, a };
}

// Événements entre deux états (p = avant, c = maintenant), pour le match du site m. Sans p : seulement le début.
export function evenements(m, p, c, meilleurDes = 3) {
  const E = [];
  const jeux = (s) => s.h.reduce((x, y) => x + y, 0) + s.a.reduce((x, y) => x + y, 0);
  if (!p) {
    if (jeux(c) <= 1 && c.h.length <= 1) E.push({ type: 'debut' });
    return E;
  }
  const gp = setsGagnes(p), gc = setsGagnes(c), aGagner = Math.ceil((meilleurDes || 3) / 2);
  const dh = c.h.reduce((x, y) => x + y, 0) - p.h.reduce((x, y) => x + y, 0), da = c.a.reduce((x, y) => x + y, 0) - p.a.reduce((x, y) => x + y, 0);
  // break : un seul jeu depuis la minute précédente, serveur connu avant et après, et changé ; pas un jeu décisif ;
  // pas le jeu qui finit un set (la fin du set le dira)
  if (dh + da === 1 && dh >= 0 && da >= 0 && p.srv && c.srv && p.srv !== c.srv) {
    let i = -1;
    for (let x = 0; x < c.h.length; x++) if ((c.h[x] || 0) !== (p.h[x] || 0) || (c.a[x] || 0) !== (p.a[x] || 0)) { i = x; break; }
    const gagnant = dh === 1 ? 'h' : 'a';
    const decisif = i >= 0 && (p.h[i] || 0) === 6 && (p.a[i] || 0) === 6;
    if (i >= 0 && !decisif && gagnant !== p.srv && !setFini(c.h[i] || 0, c.a[i] || 0))
      E.push({ type: 'break', qui: gagnant, set: i + 1, score: gagnant === 'h' ? `${c.h[i]}-${c.a[i] || 0}` : `${c.a[i] || 0}-${c.h[i]}` });
  }
  // fin de set (sauf le set qui finit le match : le résultat le dira)
  for (let n = gp.h + gp.a + 1; n <= gc.h + gc.a; n++) {
    const i = n - 1, g = c.h[i], o = c.a[i] || 0;
    if (g === undefined) continue;
    const qui = g > o ? 'h' : 'a';
    const apres = { h: c.h.slice(0, n), a: c.a.slice(0, n) }, w = setsGagnes(apres);
    if (w.h >= aGagner || w.a >= aGagner) continue;
    E.push({ type: 'set', qui, set: n, sets: `${w.h}-${w.a}`, score: qui === 'h' ? `${g}-${o}` : `${o}-${g}` });
  }
  return E;
}

export function message(e, m, lang, pct) {
  const T = TXT[lang] || TXT.fr, nom = (q) => (q === 'h' ? m.home : m.away);
  const url = '/#match=' + encodeURIComponent(m.uid), tag = 'gsa-' + m.uid;
  if (e.type === 'debut') return { titre: T.debut_t, texte: T.debut(m), url, tag };
  if (e.type === 'break') return { titre: T.brk_t(nom(e.qui)), texte: `${m.home} – ${m.away} · ${T.brk(nom(e.qui), e.score, e.set)}`, url, tag };
  if (e.type === 'set') return { titre: T.set_t(nom(e.qui), e.set), texte: `${m.home} – ${m.away} · ${e.score} · ${T.set(e.sets)}`, url, tag };
  if (e.type === 'fin') {
    const g = nom(e.qui), p = nom(e.qui === 'h' ? 'a' : 'h');
    let algo = '';
    if (Number.isFinite(pct)) {
      const fav = pct >= 0.5 ? 'h' : 'a', pf = Math.round((fav === 'h' ? pct : 1 - pct) * 100);
      algo = fav === e.qui ? T.algo_ok(g, pf) : T.algo_ko(nom(fav), pf);
    }
    return { titre: T.fin_t(g, p), texte: algo ? T.fin(e.score, algo) : e.score, url, tag };
  }
  return null;
}

// ------------------------------------------------------------------ qui reçoit quoi
export function interesses(I, m) {
  const out = [];
  for (const [id, e] of Object.entries((I && I.u) || {}))
    if ((e.m || []).includes(m.uid) || (e.j || []).includes(m.home) || (e.j || []).includes(m.away)) out.push(id);
  return out;
}

let SITE_MEMOIRE = null;
async function listeSite(env, maintenant) {
  if (SITE_MEMOIRE && maintenant - SITE_MEMOIRE.le < 5 * 60e3) return SITE_MEMOIRE.matchs;
  const { doc } = await lireJson(env, 'site/algo/site.json');
  SITE_MEMOIRE = { le: maintenant, matchs: (doc && doc.matchs) || [] };
  return SITE_MEMOIRE.matchs;
}
export const viderSiteMemoire = () => { SITE_MEMOIRE = null; };

// Envoie à chaque compte intéressé (accès Plus vérifié), au plus MAX_PAR_JOUR par jour ; retire les appareils refusés.
async function distribuer(env, I, etat, envois, ttl, journal) {
  const jour = new Date().toISOString().slice(0, 10);
  if (!etat.compte || etat.compte.jour !== jour) etat.compte = { jour, n: {} };
  const comptes = new Map();
  let n = 0;
  for (const { id, msg } of envois) {
    if ((etat.compte.n[id] || 0) >= MAX_PAR_JOUR) continue;
    if (!comptes.has(id)) comptes.set(id, await lire(env, id));
    const u = comptes.get(id);
    if (!u || !abonne(u) || !Array.isArray(u.push) || !u.push.length) continue;
    const morts = [];
    for (const a of u.push) {
      const code = await envoyerPush(env, a, msg, ttl);
      if (code === 404 || code === 410) morts.push(a.e);
      else if (code >= 200 && code < 300) n++;
    }
    etat.compte.n[id] = (etat.compte.n[id] || 0) + 1;
    if (morts.length) { u.push = u.push.filter((a) => !morts.includes(a.e)); await ecrire(env, u); await suivreCompte(env, id, u); }
  }
  if (journal) journal(`notifications : ${envois.length} prévues, ${n} envoyées`);
  return n;
}

// ------------------------------------------------------------------ chaque minute : le direct
export async function notifsDirect(env, lireDirect, maintenant = Date.now()) {
  if (!env.COFFRE) return { envoyes: 0 };
  const { doc: I } = await lireJson(env, INDEX_R2);
  if (!I || !I.u || !Object.keys(I.u).length) return { envoyes: 0, rien: true };   // aucun appareil : rien du tout
  const direct = await lireDirect();
  if (!direct || !direct.ok) return { envoyes: 0 };
  const site = await listeSite(env, maintenant);
  const { doc: e0 } = await lireJson(env, ETAT_R2);
  const avant = JSON.stringify(e0 || {}), etat = e0 || {};
  etat.matchs = etat.matchs || {}; etat.fini = etat.fini || {};
  const envois = [];
  const pour = (m, ev, pct) => { for (const id of interesses(I, m)) envois.push({ id, msg: message(ev, m, (I.u[id] || {}).lang, pct) }); };
  for (const x of [...(direct.matchs || []), ...(direct.interrompus || [])]) {
    if (!x || !x.id || etat.fini[x.id]) continue;
    const r = relier(site, x);
    if (!r || !interesses(I, r.m).length) continue;
    const c = oriente(x, r.inverse), k = String(x.id), p = etat.matchs[k];
    for (const ev of evenements(r.m, p ? p.s : null, c, r.m.meilleur_des)) pour(r.m, ev, r.m.p_home);
    if (!p || JSON.stringify(p.s) !== JSON.stringify(c) || maintenant - (p.vu || 0) > 30 * 60e3) etat.matchs[k] = { uid: r.m.uid, s: c, vu: maintenant };
  }
  for (const x of direct.termines || []) {
    if (!x || !x.id || etat.fini[x.id] || maintenant - (x.fin || 0) > 30 * 60e3) continue;
    const r = relier(site, x);
    if (!r || !interesses(I, r.m).length) continue;
    const c = oriente(x, r.inverse), gagnant = x.gagnant ? ((x.gagnant === 'home') !== r.inverse ? 'h' : 'a') : null;
    etat.fini[x.id] = maintenant; delete etat.matchs[String(x.id)];
    if (!gagnant) continue;
    const sc = c.h.map((g, i) => (gagnant === 'h' ? `${g}-${c.a[i] || 0}` : `${c.a[i] || 0}-${g}`)).join(' ');
    pour(r.m, { type: 'fin', qui: gagnant, score: sc }, r.m.p_home);
  }
  for (const [k, v] of Object.entries(etat.matchs)) if (maintenant - (v.vu || 0) > 6 * 3600e3) delete etat.matchs[k];
  for (const [k, v] of Object.entries(etat.fini)) if (maintenant - v > 48 * 3600e3) delete etat.fini[k];
  const n = envois.length ? await distribuer(env, I, etat, envois.filter((x) => x.msg), 600) : 0;
  const texte = JSON.stringify(etat);
  if (texte !== avant) await env.COFFRE.put(ETAT_R2, texte);   // rien de neuf : aucune écriture
  return { envoyes: n, prevus: envois.length };
}

// ------------------------------------------------------------------ le matin : « tes favoris jouent aujourd'hui »
export function heureParis(iso, lang) {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return '';
  return new Intl.DateTimeFormat(lang === 'en' ? 'en-GB' : 'fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' })
    .format(d).replace(':', lang === 'en' ? ':' : ' h ');
}
export async function notifsMatin(env, maintenant = Date.now()) {
  if (!env.COFFRE) return { envoyes: 0 };
  const { doc: I } = await lireJson(env, INDEX_R2);
  if (!I || !I.u || !Object.keys(I.u).length) return { envoyes: 0, rien: true };
  const { doc: e0 } = await lireJson(env, ETAT_R2);
  const etat = e0 || {};
  const jour = new Date(maintenant).toISOString().slice(0, 10);
  if (etat.matin === jour) return { envoyes: 0, deja: true };
  const site = await listeSite(env, maintenant);
  const fin = maintenant + 24 * 3600e3;
  const aVenir = site.filter((m) => { const t = t0(m); return Number.isFinite(t) && t >= maintenant - 3600e3 && t < fin; });
  const envois = [];
  for (const [id, e] of Object.entries(I.u)) {
    const T = TXT[e.lang] || TXT.fr, L = [];
    for (const m of aVenir.sort((a, b) => t0(a) - t0(b))) {
      const fj = (e.j || []).includes(m.home) ? m.home : (e.j || []).includes(m.away) ? m.away : (e.m || []).includes(m.uid) ? m.home : null;
      if (!fj) continue;
      L.push(T.ligne(fj, heureParis(m.debut_utc || t0(m), e.lang), fj === m.home ? m.away : m.home));
    }
    if (L.length) envois.push({ id, msg: { titre: T.matin_t, texte: T.matin(L.slice(0, 6)) + (L.length > 6 ? ` (+${L.length - 6})` : ''), url: '/', tag: 'gsa-matin' } });
  }
  etat.matin = jour;
  const n = envois.length ? await distribuer(env, I, etat, envois, 6 * 3600) : 0;
  await env.COFFRE.put(ETAT_R2, JSON.stringify(etat));
  return { envoyes: n, prevus: envois.length };
}

// GET /compte/api/push/cle : la clé publique VAPID (pour pushManager.subscribe)
export async function clePublique(env) { return (await clesVapid(env)).publique; }
