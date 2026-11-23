// Paquet 377 — comptes des abonnés : inscription, e-mail de confirmation, connexion, accès Plus, données réservées.
import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';
import { hacher, normaliser, abonne } from './comptes.js';

const CLE = 'k'.repeat(40);
function r2() {
  const m = new Map(), v = new Map();
  return {
    m,
    get: async (k) => (m.has(k) ? { body: m.get(k), size: m.get(k).length, etag: 'e' + (v.get(k) || 0), text: async () => m.get(k) } : null),
    put: async (k, x, o = {}) => {
      if (o.onlyIf && o.onlyIf.etagMatches && o.onlyIf.etagMatches !== 'e' + (v.get(k) || 0)) return null;
      m.set(k, String(x)); v.set(k, (v.get(k) || 0) + 1); return { key: k };
    },
    list: async ({ prefix }) => ({ objects: [...m.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })), truncated: false }),
  };
}
function monde() {
  const C = r2();
  C.m.set('site/algo/site.json', '{"plein":true}');
  C.m.set('site/algo/donnees.json', '{"plein":true,"tout":1}');
  C.m.set('site/algo/site_libre.json', '{"libre":true}');
  C.m.set('site/algo/site_admin.json', '{"interne":true}');
  const mails = [];
  globalThis.fetch = async (u, o) => {
    if (String(u).startsWith('https://api.brevo.com/')) { mails.push(JSON.parse(o.body)); return new Response('{}', { status: 201 }); }
    return new Response('x', { status: 404 });
  };
  return { env: { CLE_PRIVEE: CLE, COFFRE: C, BREVO_API_KEY: 'b' }, mails, C };
}
const SITE = 'https://gamesetalgo.com', DEV = 'https://algo.tennis-edge.workers.dev';
const post = (chemin, corps, h = {}, base = SITE) => new Request(base + chemin, { method: 'POST',
  headers: { 'Content-Type': 'application/json', Origin: base, ...h }, body: JSON.stringify(corps) });
const get = (chemin, h = {}, base = SITE) => new Request(base + chemin, { headers: h });
const cookie = (r) => (r.headers.get('Set-Cookie') || '').split(';')[0];
const lienDe = (mail, cle) => new URL(mail.htmlContent.match(/href="([^"]+)"/)[1].replace(/&amp;/g, '&')).searchParams.get(cle);

test('inscription → e-mail de confirmation → connexion → données libres, puis accès Plus donné à la main', async () => {
  const { env, mails } = monde();
  let r = await worker.fetch(post('/compte/api/inscription', { email: 'Ana@Exemple.fr', mdp: 'motdepasse1' }), env);
  assert.equal(r.status, 200);
  assert.equal(mails.length, 1);
  assert.equal(mails[0].to[0].email, 'ana@exemple.fr');
  assert.equal(mails[0].sender.email, 'noreply@gamesetalgo.com');
  // pas encore confirmé
  r = await worker.fetch(post('/compte/api/connexion', { email: 'ana@exemple.fr', mdp: 'motdepasse1' }), env);
  assert.equal(r.status, 403);
  const jeton = lienDe(mails[0], 'verifier');
  r = await worker.fetch(post('/compte/api/verifier', { jeton }), env);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Set-Cookie'), /HttpOnly; Secure; SameSite=Lax/);
  // le lien ne sert qu'une fois
  assert.equal((await worker.fetch(post('/compte/api/verifier', { jeton }), env)).status, 400);
  r = await worker.fetch(post('/compte/api/connexion', { email: 'ana@exemple.fr', mdp: 'motdepasse1' }), env);
  assert.equal(r.status, 200);
  const c = cookie(r);
  const moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json();
  assert.equal(moi.compte.email, 'ana@exemple.fr');
  assert.equal(moi.compte.abonne, false);
  // sans accès Plus : version libre, jamais le fichier complet
  for (const f of ['/site.json', '/donnees.json']) {
    const x = await worker.fetch(get(f, { Cookie: c }), env);
    assert.equal(await x.text(), '{"libre":true}', f);
    assert.equal(x.headers.get('Cache-Control'), 'private, no-store');
  }
  assert.equal(await (await worker.fetch(get('/site.json'), env)).text(), '{"libre":true}');
  // l'administration : pas sur gamesetalgo.com, et seulement avec la clé
  assert.equal((await worker.fetch(get('/compte/admin'), env)).status, 404);
  assert.equal((await worker.fetch(get('/compte/admin', {}, DEV), env)).status, 303);
  r = await worker.fetch(post('/compte/admin/api/acces', { email: 'ana@exemple.fr', formule: 'mois' }, { 'X-Cle': CLE }, DEV), env);
  assert.equal(r.status, 200);
  const acc = (await r.json()).compte;
  assert.equal(acc.abonne, true);
  assert.ok(Date.parse(acc.jusqu_au) - Date.now() > 30 * 86400e3);
  assert.equal(await (await worker.fetch(get('/site.json', { Cookie: c }), env)).text(), '{"plein":true}');
  // 380 : un abonné reçoit site.json pour /donnees.json (les sections internes restent à l'administrateur)
  assert.equal(await (await worker.fetch(get('/donnees.json', { Cookie: c }), env)).text(), '{"plein":true}');
  const liste = await (await worker.fetch(get('/compte/admin/api/liste', { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(liste.comptes.length, 1);
  assert.ok(!JSON.stringify(liste).includes('hash'));
  // retrait
  await worker.fetch(post('/compte/admin/api/acces', { email: 'ana@exemple.fr', formule: 'retirer' }, { 'X-Cle': CLE }, DEV), env);
  assert.equal(await (await worker.fetch(get('/site.json', { Cookie: c }), env)).text(), '{"libre":true}');
});

test('mot de passe oublié : lien d’une heure, à usage unique, ferme les anciennes sessions', async () => {
  const { env, mails, C } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'bob@exemple.fr', mdp: 'ancienmdp1' }), env);
  let r = await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env);
  const ancien = cookie(r);
  // l'envoi suivant attend 2 minutes : on recule l'horloge du compte
  for (const [k, v] of C.m) if (k.startsWith('comptes/u/')) C.m.set(k, JSON.stringify({ ...JSON.parse(v), dernier_mail: 0 }));
  await worker.fetch(post('/compte/api/oubli', { email: 'bob@exemple.fr' }), env);
  assert.equal(mails.length, 2);
  const jeton = lienDe(mails[1], 'reinit');
  assert.equal((await worker.fetch(post('/compte/api/reinit', { jeton, mdp: 'court' }), env)).status, 400);
  r = await worker.fetch(post('/compte/api/reinit', { jeton, mdp: 'nouveaumdp1' }), env);
  assert.equal(r.status, 200);
  assert.equal((await worker.fetch(post('/compte/api/reinit', { jeton, mdp: 'encoreautre1' }), env)).status, 400);
  assert.equal((await (await worker.fetch(get('/compte/api/moi', { Cookie: ancien }), env)).json()).compte, null);
  assert.equal((await worker.fetch(post('/compte/api/connexion', { email: 'bob@exemple.fr', mdp: 'ancienmdp1' }), env)).status, 401);
  assert.equal((await worker.fetch(post('/compte/api/connexion', { email: 'bob@exemple.fr', mdp: 'nouveaumdp1' }), env)).status, 200);
});

test('protections : mauvaise origine, adresse déjà inscrite (même réponse), blocage après 10 échecs, cookie falsifié', async () => {
  const { env, mails } = monde();
  assert.equal((await worker.fetch(post('/compte/api/inscription', { email: 'x@exemple.fr', mdp: 'motdepasse1' },
    { Origin: 'https://pirate.example' }), env)).status, 403);
  const a = await (await worker.fetch(post('/compte/api/inscription', { email: 'c@exemple.fr', mdp: 'motdepasse1' }), env)).json();
  const b = await (await worker.fetch(post('/compte/api/inscription', { email: 'c@exemple.fr', mdp: 'autre12345' }), env)).json();
  assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort());
  assert.equal(mails.length, 1);                                   // pas de second e-mail avant 2 minutes
  await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env);
  for (let i = 0; i < 10; i++) await worker.fetch(post('/compte/api/connexion', { email: 'c@exemple.fr', mdp: 'faux' + i }), env);
  assert.equal((await worker.fetch(post('/compte/api/connexion', { email: 'c@exemple.fr', mdp: 'motdepasse1' }), env)).status, 429);
  const faux = 'gsa_compte=' + 'a'.repeat(64) + '.9999999999999.0.' + 'Z'.repeat(43);
  assert.equal((await (await worker.fetch(get('/compte/api/moi', { Cookie: faux }), env)).json()).compte, null);
  assert.equal(await (await worker.fetch(get('/site.json', { Cookie: faux }), env)).text(), '{"libre":true}');
  assert.equal((await worker.fetch(post('/compte/api/inscription', { email: 'pas-un-email', mdp: 'motdepasse1' }), env)).status, 400);
});

test('sans Brevo : le compte est créé, l’e-mail est signalé non envoyé ; outils', async () => {
  const { env } = monde();
  delete env.BREVO_API_KEY;
  const o = await (await worker.fetch(post('/compte/api/inscription', { email: 'd@exemple.fr', mdp: 'motdepasse1' }), env)).json();
  assert.equal(o.envoye, false);
  assert.equal(o.raison, 'mail_non_configure');
  assert.equal(normaliser('  A@B.CO '), 'a@b.co');
  assert.equal(normaliser('a@b'), null);
  const h1 = await hacher('x'.repeat(10)), h2 = await hacher('x'.repeat(10), h1.sel);
  assert.equal(h1.hash, h2.hash);
  assert.equal(abonne({ acces: { formule: 'illimite' } }), true);
  assert.equal(abonne({ acces: { formule: 'mois', jusqu_au: '2000-01-01T00:00:00Z' } }), false);
});


test('380 : sections internes réservées à l’administrateur ; un abonné reçoit site.json pour /donnees.json', async () => {
  const { env, mails } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'e@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  assert.equal((await worker.fetch(get('/site_admin.json', { Cookie: c }), env)).status, 404);
  assert.equal((await worker.fetch(get('/site_admin.json'), env)).status, 404);
  await worker.fetch(post('/compte/admin/api/acces', { email: 'e@exemple.fr', formule: 'mois' }, { 'X-Cle': CLE }, DEV), env);
  assert.equal((await worker.fetch(get('/site_admin.json', { Cookie: c }), env)).status, 404);
  assert.equal(await (await worker.fetch(get('/donnees.json', { Cookie: c }), env)).text(), '{"plein":true}');   // site.json
  let moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json();
  assert.equal(moi.admin, false);
  await worker.fetch(post('/compte/admin/api/acces', { email: 'e@exemple.fr', formule: 'admin' }, { 'X-Cle': CLE }, DEV), env);
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json();
  assert.equal(moi.admin, true);
  assert.equal(moi.compte.abonne, true);
  assert.equal(await (await worker.fetch(get('/site_admin.json', { Cookie: c }), env)).text(), '{"interne":true}');
  assert.equal(await (await worker.fetch(get('/donnees.json', { Cookie: c }), env)).text(), '{"plein":true,"tout":1}');
  // la clé privée (Lab) suffit aussi
  assert.equal((await worker.fetch(get('/site_admin.json', { 'X-Cle': CLE }, DEV), env)).status, 200);
  assert.equal((await (await worker.fetch(get('/compte/api/moi', { 'X-Cle': CLE }, DEV), env)).json()).admin, true);
});


test('381 : code d’accès à usage unique, durée limitée, réservé à un compte connecté', async () => {
  const { env, mails, C } = monde();
  const r = await (await worker.fetch(post('/compte/admin/api/codes', { formule: 'offert', jours: 10, validite: 5, nombre: 2, note: 'test' },
    { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(r.ok, true);
  assert.equal(r.codes.length, 2);
  assert.match(r.codes[0], /^GSA-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/);
  // au coffre : l'empreinte, jamais le code en clair
  assert.ok(![...C.m.values()].some((x) => x.includes(r.codes[0])));
  // sans connexion : refusé
  assert.equal((await worker.fetch(post('/compte/api/code', { code: r.codes[0] }), env)).status, 401);
  await worker.fetch(post('/compte/api/inscription', { email: 'f@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  // saisie souple (minuscules, sans tirets)
  let o = await (await worker.fetch(post('/compte/api/code', { code: r.codes[0].toLowerCase().replace(/-/g, ' ') }, { Cookie: c }), env)).json();
  assert.equal(o.ok, true);
  assert.equal(o.compte.abonne, true);
  const fin = Date.parse(o.compte.jusqu_au) - Date.now();
  assert.ok(fin > 9.9 * 86400e3 && fin < 10.1 * 86400e3);
  assert.equal(await (await worker.fetch(get('/site.json', { Cookie: c }), env)).text(), '{"plein":true}');
  // une seule utilisation
  o = await (await worker.fetch(post('/compte/api/code', { code: r.codes[0] }, { Cookie: c }), env)).json();
  assert.equal(o.erreur, 'code_utilise');
  // code expiré
  for (const [k, x] of C.m) if (k.startsWith('comptes/codes/') && !JSON.parse(x).utilise_par)
    C.m.set(k, JSON.stringify({ ...JSON.parse(x), expire: '2000-01-01T00:00:00Z' }));
  o = await (await worker.fetch(post('/compte/api/code', { code: r.codes[1] }, { Cookie: c }), env)).json();
  assert.equal(o.erreur, 'code_expire');
  // liste de l'administration : indice, état, jamais le code entier
  const l = await (await worker.fetch(get('/compte/admin/api/codes', { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(l.codes.length, 2);
  assert.ok(l.codes.some((x) => x.utilise_par === 'f@exemple.fr'));
  assert.ok(!JSON.stringify(l).includes(r.codes[0]));
  // pas de création de code sans la clé, ni de code « admin »
  assert.equal((await worker.fetch(post('/compte/admin/api/codes', { formule: 'mois' }, {}, DEV), env)).status, 303);
  assert.equal((await worker.fetch(post('/compte/admin/api/codes', { formule: 'admin' }, { 'X-Cle': CLE }, DEV), env)).status, 400);
  // 10 essais ratés par heure au plus
  for (let i = 0; i < 10; i++) await worker.fetch(post('/compte/api/code', { code: 'GSA-AAAA-AAAA-AAA' + 'B' }, { Cookie: c }), env);
  assert.equal((await worker.fetch(post('/compte/api/code', { code: r.codes[0] }, { Cookie: c }), env)).status, 429);
});
