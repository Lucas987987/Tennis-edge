// Paquet 483 — notifications des favoris (Web Push) : chiffrement RFC 8291 vérifié en le déchiffrant, jeton VAPID
// vérifié avec la clé publique, abonnement réservé au Plus, index, événements du direct (début, break, set, résultat),
// garde-fous (break douteux, jeu décisif, match déjà avancé), matin, appareil refusé retiré, suppression du compte.
import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';
import { cookieSession } from './comptes.js';
import * as N from './notifs.js';

const CLE = 'k'.repeat(40), SITE = 'https://gamesetalgo.com';
const ID = 'a'.repeat(64), ID2 = 'b'.repeat(64);
function r2() {
  const m = new Map(), v = new Map();
  return {
    m,
    get: async (k) => (m.has(k) ? { body: m.get(k), etag: 'e' + (v.get(k) || 0), text: async () => m.get(k) } : null),
    put: async (k, x, o = {}) => {
      if (o.onlyIf && o.onlyIf.etagMatches && o.onlyIf.etagMatches !== 'e' + (v.get(k) || 0)) return null;
      m.set(k, String(x)); v.set(k, (v.get(k) || 0) + 1); return { key: k };
    },
    delete: async (k) => { m.delete(k); v.delete(k); },
    list: async ({ prefix }) => ({ objects: [...m.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })), truncated: false }),
  };
}
// Un « téléphone » : ses clés de réception, et le déchiffrement du message (RFC 8291) pour vérifier ce qui part.
async function telephone(n = 1) {
  const p = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const pub = new Uint8Array(await crypto.subtle.exportKey('raw', p.publicKey)), auth = crypto.getRandomValues(new Uint8Array(16));
  return { prive: p.privateKey, pub, auth, appareil: { endpoint: `https://fcm.googleapis.com/fcm/send/tel${n}`, keys: { p256dh: N.b64u(pub), auth: N.b64u(auth) } } };
}
async function hkdf(sel, ikm, info, n) {
  const k = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt: sel, info }, k, n * 8));
}
async function dechiffrer(tel, corps) {
  const te = new TextEncoder(), sel = corps.slice(0, 16), rs = new DataView(corps.buffer, corps.byteOffset + 16, 4).getUint32(0);
  const idlen = corps[20], asPub = corps.slice(21, 21 + idlen), ct = corps.slice(21 + idlen);
  assert.equal(rs, 4096); assert.equal(idlen, 65);
  const asCle = await crypto.subtle.importKey('raw', asPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const partage = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: asCle }, tel.prive, 256));
  const ikm = await hkdf(tel.auth, partage, N.concat(te.encode('WebPush: info\0'), tel.pub, asPub), 32);
  const cek = await hkdf(sel, ikm, te.encode('Content-Encoding: aes128gcm\0'), 16), nonce = await hkdf(sel, ikm, te.encode('Content-Encoding: nonce\0'), 12);
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['decrypt']);
  const clair = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce }, aes, ct));
  assert.equal(clair[clair.length - 1], 2);
  return JSON.parse(new TextDecoder().decode(clair.slice(0, -1)));
}
function monde() {
  N.viderVapidMemoire(); N.viderSiteMemoire();
  const C = r2(), envois = [], tels = new Map();
  let refus = new Set();
  globalThis.fetch = async (u, o) => {
    u = String(u);
    if (u.startsWith('https://fcm.googleapis.com/')) {
      envois.push({ u, o, corps: new Uint8Array(o.body) });
      return new Response('', { status: refus.has(u) ? 410 : 201 });
    }
    if (u.startsWith('https://api.brevo.com/')) return new Response('{}', { status: 201 });
    return new Response('x', { status: 404 });
  };
  return { env: { CLE_PRIVEE: CLE, COFFRE: C }, C, envois, tels, refuser: (u) => refus.add(u) };
}
async function compte(env, id, plus = true, extra = {}) {
  const u = { id, email: id.slice(0, 3) + '@x.fr', verifie: true, v: 0, lang: 'fr', acces: plus ? { formule: 'illimite', jusqu_au: null } : { formule: null, jusqu_au: null }, ...extra };
  await env.COFFRE.put(`comptes/u/${id}.json`, JSON.stringify(u));
  return (await cookieSession(env, u)).split(';')[0];
}
const post = (chemin, corps, c) => new Request(SITE + chemin, { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: SITE, Cookie: c }, body: JSON.stringify(corps) });
const lireR2 = async (C, k) => JSON.parse(C.m.get(k));

test('chiffrement RFC 8291 : le téléphone retrouve le message ; jeton VAPID signé et vérifiable', async () => {
  const { env, C } = monde();
  const tel = await telephone();
  const corps = await N.chiffrer(JSON.stringify({ titre: 'Été', texte: 'Sinner – Alcaraz' }), tel.appareil.keys.p256dh, tel.appareil.keys.auth);
  assert.deepEqual(await dechiffrer(tel, corps), { titre: 'Été', texte: 'Sinner – Alcaraz' });
  const { jwt, k } = await N.jetonVapid(env, tel.appareil.endpoint);
  const [h, p, s] = jwt.split('.');
  const pub = await crypto.subtle.importKey('raw', N.deb64u(k), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  assert.ok(await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, pub, N.deb64u(s), new TextEncoder().encode(h + '.' + p)));
  const charge = JSON.parse(new TextDecoder().decode(N.deb64u(p)));
  assert.equal(charge.aud, 'https://fcm.googleapis.com');
  assert.match(charge.sub, /^mailto:/);
  // clés créées une fois, gardées dans le coffre
  N.viderVapidMemoire();
  assert.equal((await N.jetonVapid(env, tel.appareil.endpoint)).k, k);
  assert.ok(C.m.has(N.VAPID_R2));
});

test('abonnement : Plus seulement, adresse vérifiée, index tenu, message de bienvenue, retrait, suppression du compte', async () => {
  const { env, C, envois } = monde();
  const tel = await telephone();
  const libre = await compte(env, ID2, false);
  let r = await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, libre), env);
  assert.equal(r.status, 403);
  const c = await compte(env, ID, true, { favoris: { joueurs: ['Jannik Sinner'], matchs: [] } });
  r = await worker.fetch(post('/compte/api/push', { appareil: { ...tel.appareil, endpoint: 'https://evil.example/x' } }, c), env);
  assert.equal(r.status, 400);
  r = await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  assert.equal(r.status, 200);
  assert.equal(envois.length, 1);
  assert.equal((await dechiffrer(tel, envois[0].corps)).tag, 'gsa-pret');
  assert.match(envois[0].o.headers.Authorization, /^vapid t=.+, k=/);
  let I = await lireR2(C, N.INDEX_R2);
  assert.deepEqual(I.u[ID].j, ['Jannik Sinner']);
  // la clé publique est servie à tous
  const cle = await (await worker.fetch(new Request(SITE + '/compte/api/push/cle'), env)).json();
  assert.equal(N.deb64u(cle.cle).length, 65);
  // favoris modifiés → index suivi
  await worker.fetch(post('/compte/api/favoris', { type: 'joueur', cle: 'Carlos Alcaraz', actif: true }, c), env);
  I = await lireR2(C, N.INDEX_R2);
  assert.deepEqual(I.u[ID].j, ['Carlos Alcaraz', 'Jannik Sinner']);
  // la vue du compte dit combien d'appareils
  const moi = await (await worker.fetch(new Request(SITE + '/compte/api/moi', { headers: { Cookie: c } }), env)).json();
  assert.equal(moi.compte.appareils, 1);
  // retrait de l'appareil → sorti de l'index
  r = await worker.fetch(post('/compte/api/push', { retirer: tel.appareil.endpoint }, c), env);
  assert.equal((await r.json()).appareils, 0);
  I = await lireR2(C, N.INDEX_R2);
  assert.equal(I.u[ID], undefined);
});

const SITEJ = { matchs: [{ uid: '2026-11-26_sinner_alcaraz', home: 'Jannik Sinner', away: 'Carlos Alcaraz', debut_utc: '2026-11-26T14:00:00+00:00', meilleur_des: 3, p_home: 0.62 },
  { uid: '2026-11-26_x_y', home: 'Xavier Un', away: 'Yann Deux', debut_utc: '2026-11-26T15:00:00+00:00', meilleur_des: 3, p_home: 0.5 }] };
const T0 = Date.parse('2026-11-26T14:05:00Z');
const lv = (sh, sa, srv, extra = {}) => ({ id: 77, debut: Date.parse('2026-11-26T14:00:00Z') / 1000, home: 'Alcaraz C.', away: 'Sinner J.',   // inversé par rapport au site
  serveur: srv, statut: { type: 'inprogress' }, score_home: { sets: sa }, score_away: { sets: sh }, ...extra });

test('direct : début, break, set, résultat avec le verdict de l\'algo ; rien pour les autres matchs', async () => {
  const { env, C, envois } = monde();
  C.m.set('site/algo/site.json', JSON.stringify(SITEJ));
  const tel = await telephone();
  const c = await compte(env, ID, true, { favoris: { joueurs: ['Jannik Sinner'], matchs: [] } });
  await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  envois.length = 0;
  // les messages du téléphone, déchiffrés
  const recus = async () => { const L = []; for (const e of envois) L.push(await dechiffrer(tel, e.corps)); envois.length = 0; return L; };
  let D = { ok: true, matchs: [lv([0], [0], 'away')], termines: [] };       // Sinner (site home = live away) au service
  await N.notifsDirect(env, async () => D, T0);
  let L = await recus();
  assert.equal(L.length, 1); assert.match(L[0].titre, /Début/); assert.equal(L[0].url, '/#match=2026-11-26_sinner_alcaraz');
  // Sinner sert et perd le jeu : break d'Alcaraz (le serveur a changé, un seul jeu)
  D = { ok: true, matchs: [lv([0], [1], 'home')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 60e3);
  L = await recus();
  assert.equal(L.length, 1); assert.equal(L[0].titre, '🎾 Break de Carlos Alcaraz'); assert.match(L[0].texte, /1-0 dans le 1er set/);
  // deux jeux d'un coup (minute manquée) : pas de break annoncé
  D = { ok: true, matchs: [lv([1], [2], 'away')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 120e3);
  assert.deepEqual(await recus(), []);
  // jeu gagné au service : rien
  D = { ok: true, matchs: [lv([2], [2], 'home')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 180e3);
  assert.equal((await recus()).length, 0);
  // fin du 1er set : Sinner 6-4
  D = { ok: true, matchs: [lv([6, 0], [4, 0], 'away')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 240e3);
  L = await recus();
  assert.equal(L.length, 1); assert.equal(L[0].titre, 'Set 1 pour Jannik Sinner'); assert.match(L[0].texte, /6-4 · Sets : 1-0/);
  // jeu décisif à 6-6 gagné par le relanceur : pas un break
  D = { ok: true, matchs: [lv([6, 6], [4, 6], 'home')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 300e3);
  await recus();
  D = { ok: true, matchs: [lv([6, 6], [4, 7], 'away')], termines: [] };
  await N.notifsDirect(env, async () => D, T0 + 360e3);
  L = await recus();
  assert.ok(L.every((m) => !/Break/.test(m.titre)));
  // résultat : Sinner gagne, l'algo le donnait à 62 %
  D = { ok: true, matchs: [], termines: [{ ...lv([6, 6, 6], [4, 7, 3], null), gagnant: 'away', fin: T0 + 400e3 }] };
  await N.notifsDirect(env, async () => D, T0 + 420e3);
  L = await recus();
  assert.equal(L.length, 1); assert.equal(L[0].titre, '🏁 Jannik Sinner bat Carlos Alcaraz');
  assert.match(L[0].texte, /6-4 6-7 6-3\. L'algo le donnait gagnant à 62 % ✅/);
  // une seule fois
  await N.notifsDirect(env, async () => D, T0 + 480e3);
  assert.equal((await recus()).length, 0);
});

test('garde-fous : match déjà avancé sans « début », pas d\'abonné → aucune lecture du direct, Plus expiré → rien, appareil refusé retiré', async () => {
  const { env, C, envois, refuser } = monde();
  C.m.set('site/algo/site.json', JSON.stringify(SITEJ));
  let lu = 0;
  assert.equal((await N.notifsDirect(env, async () => { lu++; return { ok: true, matchs: [] }; }, T0)).rien, true);
  assert.equal(lu, 0);
  const tel = await telephone();
  const c = await compte(env, ID, true, { favoris: { joueurs: [], matchs: ['2026-11-26_sinner_alcaraz'] } });
  await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  envois.length = 0;
  await N.notifsDirect(env, async () => ({ ok: true, matchs: [lv([3], [2], 'home')], termines: [] }), T0);
  assert.equal(envois.length, 0);                                     // découvert à 3-2 : pas de « début »
  // accès Plus terminé : plus rien, même si l'index le connaît encore
  const u = await lireR2(C, `comptes/u/${ID}.json`);
  u.acces = { formule: 'mois', jusqu_au: '2026-01-01T00:00:00Z' };
  await C.put(`comptes/u/${ID}.json`, JSON.stringify(u));
  await N.notifsDirect(env, async () => ({ ok: true, matchs: [lv([6, 0], [3, 0], 'away')], termines: [] }), T0 + 60e3);
  assert.equal(envois.length, 0);
  // de nouveau Plus, mais le téléphone a désinstallé : 410 → appareil retiré du compte et de l'index
  u.acces = { formule: 'illimite' };
  await C.put(`comptes/u/${ID}.json`, JSON.stringify(u));
  refuser(tel.appareil.endpoint);
  await N.notifsDirect(env, async () => ({ ok: true, matchs: [lv([6, 0], [3, 1], 'home')], termines: [] }), T0 + 120e3);   // break d'Alcaraz
  assert.equal(envois.length, 1);
  assert.deepEqual((await lireR2(C, `comptes/u/${ID}.json`)).push, []);
  assert.equal((await lireR2(C, N.INDEX_R2)).u[ID], undefined);
});

test('le matin : un seul message par compte avec ses favoris du jour, une seule fois par jour', async () => {
  const { env, C, envois } = monde();
  C.m.set('site/algo/site.json', JSON.stringify(SITEJ));
  const tel = await telephone();
  const c = await compte(env, ID, true, { favoris: { joueurs: ['Carlos Alcaraz'], matchs: ['2026-11-26_x_y'] } });
  await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  envois.length = 0;
  const matin = Date.parse('2026-11-26T07:17:00Z');
  await N.notifsMatin(env, matin);
  assert.equal(envois.length, 1);
  const m = await dechiffrer(tel, envois[0].corps);
  assert.equal(m.titre, '⭐ Tes favoris jouent aujourd\'hui');
  assert.equal(m.texte, 'Carlos Alcaraz à 15 h 00 contre Jannik Sinner · Xavier Un à 16 h 00 contre Yann Deux. Le pronostic de l\'algo est en ligne.');
  await N.notifsMatin(env, matin + 3600e3);
  assert.equal(envois.length, 1);
});

test('événements : la fin du set qui gagne le match n\'est pas annoncée (le résultat le dira)', () => {
  const m = { home: 'A', away: 'B', uid: 'u' };
  const p = { h: [6, 5], a: [4, 4], srv: 'h' }, c = { h: [6, 6], a: [4, 4], srv: 'a' };
  assert.deepEqual(N.evenements(m, p, c, 3).filter((e) => e.type === 'set'), []);
  const c5 = { h: [6, 6], a: [4, 4], srv: 'a' };
  assert.equal(N.evenements(m, p, c5, 5).filter((e) => e.type === 'set').length, 1);
});
