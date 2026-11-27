// Paquet 510 — notifications des favoris du tennis de table : le matin, le début, le résultat (verdict de l'algo) ;
// rien sans favori « tt: », rien au tout premier passage, rien pour un vieux match, rien deux fois, Plus seulement.
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

const T0 = Date.parse('2026-11-27T09:00:00Z');
const tt = (genere, matchs) => JSON.stringify({ genere_le: genere, acces: 'plus', matchs });
const M = (id, statut, t, extra = {}) => ({ id, ligue: 'Poland', t: Math.round(t / 1000), tournoi: 'TT Elite Series', h: 'Kowalski A.', a: 'Nowak B.',
  statut, p_h: 0.63, ...extra });

test('tennis de table : matin, début, résultat avec le verdict de l’algo ; une seule fois ; jamais au premier passage', async () => {
  const { env, C, envois } = monde();
  const tel = await telephone();
  const c = await compte(env, ID, true, { favoris: { joueurs: ['tt:Kowalski A.', 'Jannik Sinner'], matchs: [] } });
  await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  envois.length = 0;
  const recus = async () => { const L = []; for (const e of envois) L.push(await dechiffrer(tel, e.corps)); envois.length = 0; return L; };
  // premier passage, 6 h UTC : un match déjà en cours (noté, pas annoncé), pas encore le matin
  C.m.set(N.TT_R2, tt('2026-11-27T06:41:00Z', [M(1, 'en_cours', T0 - 4 * 3600e3 + 3600e3), M(2, 'a_venir', T0 + 3 * 3600e3)]));
  await N.notifsTT(env, T0 - 3 * 3600e3);
  assert.deepEqual(await recus(), []);
  // 9 h : le matin (le match 2 du favori), une seule fois
  await N.notifsTT(env, T0);
  let L = await recus();
  assert.equal(L.length, 1); assert.equal(L[0].titre, '🏓 Tes favoris jouent aujourd\'hui'); assert.equal(L[0].url, '/tennis-de-table');
  assert.match(L[0].texte, /Kowalski A\. à 13 h 00 contre Nowak B\./);
  await N.notifsTT(env, T0 + 60e3);
  assert.deepEqual(await recus(), []);                       // même page, matin déjà fait : rien
  // nouveau passage : le match 2 a commencé
  C.m.set(N.TT_R2, tt('2026-11-27T12:41:00Z', [M(2, 'en_cours', T0 + 3 * 3600e3, { manches: [[11, 5]] })]));
  await N.notifsTT(env, T0 + 3.7 * 3600e3);
  L = await recus();
  assert.equal(L.length, 1); assert.match(L[0].titre, /Début du match/); assert.equal(L[0].texte, "C'est parti : Kowalski A. – Nowak B.");
  // terminé : Nowak gagne 3-1, l'algo donnait Kowalski à 63 %
  C.m.set(N.TT_R2, tt('2026-11-27T13:41:00Z', [M(2, 'termine', T0 + 3 * 3600e3, { g: 2, manches: [[11, 5], [8, 11], [9, 11], [7, 11]] })]));
  await N.notifsTT(env, T0 + 4.7 * 3600e3);
  L = await recus();
  assert.equal(L.length, 1); assert.equal(L[0].titre, '🏁 Nowak B. bat Kowalski A.');
  assert.equal(L[0].texte, "3-1. L'algo donnait Kowalski A. à 63 % ❌");
  C.m.set(N.TT_R2, tt('2026-11-27T14:41:00Z', [M(2, 'termine', T0 + 3 * 3600e3, { g: 2, manches: [[11, 5], [8, 11], [9, 11], [7, 11]] })]));
  await N.notifsTT(env, T0 + 5.7 * 3600e3);
  assert.deepEqual(await recus(), []);                       // une seule fois
});

test('tennis de table : sans favori « tt: » la page n’est même pas lue ; un vieux match terminé ne part pas ; Plus seulement', async () => {
  const { env, C, envois } = monde();
  const tel = await telephone();
  const c = await compte(env, ID, true, { favoris: { joueurs: ['Jannik Sinner'], matchs: [] } });
  await worker.fetch(post('/compte/api/push', { appareil: tel.appareil }, c), env);
  assert.equal((await N.notifsTT(env, T0)).rien, true);
  const c2 = await compte(env, ID2, false, { favoris: { joueurs: [], matchs: ['tt:7'] } });   // pas Plus
  await worker.fetch(post('/compte/api/push', { appareil: (await telephone(2)).appareil }, c2), env);
  envois.length = 0;
  C.m.set(N.TT_R2, tt('a', [M(7, 'a_venir', T0 + 3600e3)]));
  await N.notifsTT(env, T0);
  C.m.set(N.TT_R2, tt('b', [M(7, 'termine', T0 - 10 * 3600e3, { g: 1, manches: [[11, 1], [11, 2], [11, 3]] })]));
  await N.notifsTT(env, T0 + 3600e3);
  assert.equal(envois.length, 0);
  assert.deepEqual(N.interessesTT({ u: { x: { j: ['tt:A'], m: [] }, y: { j: ['A'], m: ['tt:5'] } } }, { id: 5, h: 'A', a: 'B' }), ['x', 'y']);
});
