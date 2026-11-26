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
    delete: async (k) => { m.delete(k); v.delete(k); },
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


test('382 : changer de mot de passe, télécharger ses données, supprimer son compte', async () => {
  const { env, mails, C } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'g@exemple.fr', mdp: 'motdepasse1' }), env);
  let c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  assert.equal((await worker.fetch(post('/compte/api/mdp', { ancien: 'faux12345', nouveau: 'nouveau123' }, { Cookie: c }), env)).status, 403);
  let r = await worker.fetch(post('/compte/api/mdp', { ancien: 'motdepasse1', nouveau: 'nouveau123' }, { Cookie: c }), env);
  assert.equal(r.status, 200);
  const ancien = c; c = cookie(r);
  assert.equal((await (await worker.fetch(get('/compte/api/moi', { Cookie: ancien }), env)).json()).compte, null);   // autres sessions fermées
  const ex = await worker.fetch(get('/compte/api/export', { Cookie: c }), env);
  assert.match(ex.headers.get('Content-Disposition'), /attachment/);
  const d = await ex.json();
  assert.equal(d.email, 'g@exemple.fr');
  assert.ok(!JSON.stringify(d).includes('sel') || !('sel' in d));
  assert.ok(!('hash' in d) && !('sel' in d));
  assert.equal((await worker.fetch(post('/compte/api/supprimer', { mdp: 'motdepasse1' }, { Cookie: c }), env)).status, 403);
  r = await worker.fetch(post('/compte/api/supprimer', { mdp: 'nouveau123' }, { Cookie: c }), env);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Set-Cookie'), /Max-Age=0/);
  assert.ok(![...C.m.keys()].some((k) => k.startsWith('comptes/u/')));
  assert.equal((await worker.fetch(post('/compte/api/connexion', { email: 'g@exemple.fr', mdp: 'nouveau123' }), env)).status, 401);
});

test('382 : Turnstile exigé pour l’inscription et le mot de passe oublié quand il est configuré', async () => {
  const { env, mails } = monde();
  env.TURNSTILE_SECRET = 's'; env.TURNSTILE_SITEKEY = 'cle-publique';
  const brevo = globalThis.fetch, vus = [];
  globalThis.fetch = async (u, o) => {
    if (String(u).includes('turnstile/v0/siteverify')) { vus.push(o.body.get('response')); return new Response(JSON.stringify({ success: o.body.get('response') === 'bon' })); }
    return brevo(u, o);
  };
  assert.equal((await (await worker.fetch(get('/compte/api/moi'), env)).json()).turnstile, 'cle-publique');
  assert.equal((await worker.fetch(post('/compte/api/inscription', { email: 'h@exemple.fr', mdp: 'motdepasse1' }), env)).status, 403);
  assert.equal((await worker.fetch(post('/compte/api/inscription', { email: 'h@exemple.fr', mdp: 'motdepasse1', turnstile: 'mauvais' }), env)).status, 403);
  assert.equal(mails.length, 0);
  assert.equal((await worker.fetch(post('/compte/api/inscription', { email: 'h@exemple.fr', mdp: 'motdepasse1', turnstile: 'bon' }), env)).status, 200);
  assert.equal(mails.length, 1);
  assert.equal((await worker.fetch(post('/compte/api/oubli', { email: 'h@exemple.fr' }), env)).status, 403);
  assert.deepEqual(vus, ['mauvais', 'bon']);
  // la page autorise le script et le cadre de Turnstile, rien d'autre de nouveau
  globalThis.fetch = async () => new Response('<!doctype html>ok', { status: 200 });
  const csp = (await worker.fetch(get('/'), env)).headers.get('Content-Security-Policy');
  assert.match(csp, /script-src 'self' 'unsafe-inline' https:\/\/challenges\.cloudflare\.com;/);
  assert.match(csp, /frame-src https:\/\/challenges\.cloudflare\.com;/);
  assert.match(csp, /connect-src 'self' wss:\/\/gamesetalgo\.com wss:\/\/algo\.tennis-edge\.workers\.dev;/);   // 433 : direct en continu
});

test('382 : un compte jamais confirmé est effacé après 30 jours (à l’ouverture de l’administration)', async () => {
  const { env, C } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'vieux@exemple.fr', mdp: 'motdepasse1' }), env);
  await worker.fetch(post('/compte/api/inscription', { email: 'recent@exemple.fr', mdp: 'motdepasse1' }), env);
  for (const [k, x] of C.m) if (k.startsWith('comptes/u/') && x.includes('vieux@'))
    C.m.set(k, JSON.stringify({ ...JSON.parse(x), cree: '2026-01-01T00:00:00Z' }));
  const l = await (await worker.fetch(get('/compte/admin/api/liste', { 'X-Cle': CLE }, DEV), env)).json();
  assert.deepEqual(l.comptes.map((c) => c.email), ['recent@exemple.fr']);
  assert.ok(![...C.m.values()].some((x) => x.includes('vieux@')));
});

test('474 : les 100 premiers comptes confirmés sont fondateurs, automatiquement ; place figée ; admin exclu', async () => {
  const { env, mails, C } = monde();
  // un compte administrateur ne prend pas de place
  const { idCompte } = await import('./comptes.js');
  const idA = await idCompte('admin@exemple.fr');
  C.m.set(`comptes/u/${idA}.json`, JSON.stringify({ id: idA, email: 'admin@exemple.fr', verifie: true, cree: '2026-01-01T00:00:00Z', acces: { formule: 'admin' } }));
  await worker.fetch(post('/compte/api/inscription', { email: 'g@exemple.fr', mdp: 'motdepasse1' }), env);
  const r = await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env);
  const c = cookie(r);
  const o = await r.json();
  assert.equal(o.compte.fondateur_place, 1);                    // rien à réserver
  assert.match(o.compte.fondateur, /^\d{4}-\d{2}-\d{2}T/);
  assert.match(o.compte.reference, /^GSA-[0-9A-F]{6}$/);
  assert.equal(mails.length, 1);                                // pas d'e-mail de réservation
  // un second compte prend la place 2 ; la place du premier ne bouge jamais
  await worker.fetch(post('/compte/api/inscription', { email: 'h2@exemple.fr', mdp: 'motdepasse1' }), env);
  const c2 = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[1], 'verifier') }), env));
  env.VIREMENT = JSON.stringify({ titulaire: 'Game Set Algo', iban: 'FR76 0000' });
  let moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c2 }), env)).json();
  assert.equal(moi.compte.fondateur_place, 2);
  assert.equal(moi.paiement.montant, 9.99);                     // le tarif fondateur est montré tout de suite
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json();
  assert.equal(moi.compte.fondateur_place, 1);
  const ex = await (await worker.fetch(get('/compte/api/export', { Cookie: c }), env)).json();
  assert.ok(ex.fondateur);
  // compte confirmé AVANT les places automatiques : place calculée à sa première visite
  const idV = await idCompte('vieux@exemple.fr');
  C.m.set(`comptes/u/${idV}.json`, JSON.stringify({ id: idV, email: 'vieux@exemple.fr', verifie: true, cree: '2026-11-20T00:00:00Z' }));
  const V = await import('./ventes.js');
  const uV = JSON.parse(C.m.get(`comptes/u/${idV}.json`));
  assert.equal(await V.attribuerFondateur(env, uV), true);
  assert.equal(uV.fondateur_place, 3);                          // places 1 et 2 déjà données : jamais reprises
});

test('384 : le script de la page d’administration est du JavaScript valide', async () => {
  const { pageAdmin } = await import('./comptes.js');
  const s = pageAdmin().split('<script>')[1].split('</script>')[0];
  assert.doesNotThrow(() => new Function(s));
});

test('385 : alerte Telegram à la création, à la confirmation et à la place fondateur, adresse masquée', async () => {
  const { env, mails } = monde();
  const tg = [], brevo = globalThis.fetch;
  globalThis.fetch = async (u, o) => {
    if (String(u).startsWith('https://api.telegram.org/')) { tg.push(JSON.parse(o.body)); return new Response('{}'); }
    return brevo(u, o);
  };
  env.TELEGRAM_TOKEN = 't'; env.TELEGRAM_CHAT_ID = '42';
  await worker.fetch(post('/compte/api/inscription', { email: 'lucie.martin@exemple.fr', mdp: 'motdepasse1' }), env);
  assert.equal(tg.length, 1);
  assert.match(tg[0].text, /nouveau compte : lu\*\*\*@exemple\.fr/);
  assert.ok(!tg[0].text.includes('lucie.martin'));
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  assert.match(tg[1].text, /adresse confirmée : lu\*\*\*@exemple\.fr · fondateur n° 1/);   // 474 : place automatique
  void c;
  // Telegram en panne : le compte se crée quand même
  globalThis.fetch = async (u, o) => { if (String(u).includes('telegram')) throw new Error('panne'); return brevo(u, o); };
  const r = await worker.fetch(post('/compte/api/inscription', { email: 'x@exemple.fr', mdp: 'motdepasse1' }), env);
  assert.equal(r.status, 200);
});

test('471 : test sans facture — seulement sans FACTURE_VENDEUR, accès ouvert, aucun numéro consommé', async () => {
  const { env, mails } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 't@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }, { Cookie: c }), env);
  const vir = (b) => worker.fetch(post('/compte/admin/api/virement', b, { 'X-Cle': CLE }, DEV), env).then((r) => r.json());
  assert.equal((await vir({ compte: 't@exemple.fr', formule: 'mois', montant: '14,99' })).erreur, 'vendeur_absent');
  let o = await vir({ compte: 't@exemple.fr', formule: 'mois', montant: '14,99', test_sans_facture: true });
  assert.equal(o.ok, true); assert.equal(o.sans_facture, true); assert.equal(o.numero, null);
  const moi = (await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json()).compte;
  assert.equal(moi.paye, true);
  assert.ok(Date.parse(moi.jusqu_au) > Date.now() + 25 * 86400e3);
  assert.match(mails.at(-1).subject, /accès Plus est ouvert/);
  // dès que le vendeur existe, la case est ignorée : facture obligatoire, et la numérotation démarre à 0001
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'Lucas Test EI', adresse: '1 rue du Court', siret: '123 456 789 00012' });
  // 474 : une 2e validation en moins de 10 minutes est refusée (double appui), sauf confirmation explicite
  o = await vir({ compte: 't@exemple.fr', formule: 'mois', montant: '14,99', test_sans_facture: true });
  assert.equal(o.ok, false); assert.equal(o.erreur, 'doublon'); assert.ok(o.le);
  o = await vir({ compte: 't@exemple.fr', formule: 'mois', montant: '14,99', test_sans_facture: true, confirmer_doublon: true });
  assert.equal(o.ok, true); assert.equal(o.numero, `F${new Date().getUTCFullYear()}-0001`);
});

test('386 : virement reçu → accès payé, facture numérotée sans trou, e-mail, page du client, rappel avant la fin', async () => {
  const { env, mails, C } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'h@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  const ref = (await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json()).compte.reference;
  const vir = (b) => worker.fetch(post('/compte/admin/api/virement', b, { 'X-Cle': CLE }, DEV), env).then((r) => r.json());
  // sans vendeur : refus
  assert.equal((await vir({ compte: ref, formule: 'mois', montant: '9,99' })).erreur, 'vendeur_absent');
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'Lucas Test EI', adresse: '1 rue du Court\n75000 Paris', siret: '123 456 789 00012' });
  assert.equal((await vir({ compte: ref, formule: 'mois', montant: '0' })).erreur, 'montant');
  // 403 : sans demande d'accès immédiat, refus ; le client coche les deux cases
  assert.equal((await vir({ compte: ref, formule: 'mois', montant: '9,99' })).erreur, 'sans_renonciation');
  assert.equal((await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }, { Cookie: c }), env)).status, 200);
  let o = await vir({ compte: ref, formule: 'mois', montant: '9,99', fondateur: true });
  assert.equal(o.renonciation, true);
  assert.equal(o.ok, true);
  assert.equal(o.numero, `F${new Date().getUTCFullYear()}-0001`);
  o = await vir({ compte: 'h@exemple.fr', formule: 'mois', montant: '9,99', confirmer_doublon: true });   // par e-mail, prolonge l'accès
  assert.equal(o.numero, `F${new Date().getUTCFullYear()}-0002`);
  const moi = (await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json()).compte;
  assert.equal(moi.paye, true);
  assert.equal(moi.factures.length, 2);
  assert.ok(Date.parse(moi.jusqu_au) > Date.now() + 60 * 86400e3);
  assert.match(mails.at(-1).subject, /facture F\d{4}-0002/);
  assert.match(mails.at(-1).htmlContent, /TVA non applicable, art\. 293 B du CGI/);
  assert.match(mails.at(-1).htmlContent, /SIRET 123 456 789 00012/);
  // le client voit sa facture, pas celle d'un autre ; l'administration voit tout
  let r = await worker.fetch(get('/compte/api/facture?n=' + moi.factures[0], { Cookie: c }), env);
  assert.equal(r.status, 200);
  const page = await r.text();
  assert.match(page, /Accès Plus Game Set Algo, 1 mois \(tarif fondateur\)/);
  assert.match(page, /avec renonciation au droit de rétractation/);
  assert.equal((await worker.fetch(get('/compte/api/facture?n=F1999-0001', { Cookie: c }), env)).status, 404);
  assert.equal((await worker.fetch(get('/compte/api/facture?n=' + moi.factures[0]), env)).status, 401);
  const l = await (await worker.fetch(get('/compte/admin/api/factures', { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(l.factures.length, 2);
  // suppression du compte : les factures restent
  await worker.fetch(post('/compte/api/supprimer', { mdp: 'motdepasse1' }, { Cookie: c }), env);
  assert.ok(C.m.has(`factures/${moi.factures[0]}.json`));
});

test('386 : rappel de fin d’accès payé, une seule fois par échéance, avec la référence de virement', async () => {
  const { env, mails, C } = monde();
  const V = await import('./ventes.js');
  await worker.fetch(post('/compte/api/inscription', { email: 'i@exemple.fr', mdp: 'motdepasse1' }), env);
  await worker.fetch(post('/compte/api/inscription', { email: 'j@exemple.fr', mdp: 'motdepasse1' }), env);
  const fin = new Date(Date.now() + 2 * 86400e3).toISOString();
  for (const [k, x] of C.m) if (k.startsWith('comptes/u/')) {
    const u = JSON.parse(x);
    u.acces = { formule: 'mois', jusqu_au: fin, paye: u.email === 'i@exemple.fr', montant: 9.99 };
    C.m.set(k, JSON.stringify(u));
  }
  env.VIREMENT = JSON.stringify({ titulaire: 'Lucas Test', iban: 'FR76 0000 0000 0000', bic: 'TESTFRPP' });
  const avant = mails.length;
  assert.equal(await V.rappels(env), 1);                         // seulement l'accès payé
  assert.equal(mails.length, avant + 1);
  assert.match(mails.at(-1).textContent, /Libellé \(important\) : GSA-[0-9A-F]{6}/);
  assert.match(mails.at(-1).textContent, /9,99 €/);
  assert.equal(await V.rappels(env), 0);                         // pas deux fois pour la même échéance
});

test('386 : entonnoir — visites sans cookie comptées une fois par jour, robots ignorés, empreintes effacées le lendemain', async () => {
  const { env, C } = monde();
  const V = await import('./ventes.js');
  const att = [];
  const ctx = { waitUntil: (p) => att.push(p) };
  const vue = (ip, ua = 'Mozilla/5.0') => worker.fetch(new Request(SITE + '/site.json', { headers: { 'CF-Connecting-IP': ip, 'User-Agent': ua } }), env, ctx);
  await vue('1.1.1.1'); await Promise.all(att);
  await vue('1.1.1.1'); await Promise.all(att);
  await vue('2.2.2.2'); await Promise.all(att);
  await vue('3.3.3.3', 'Googlebot/2.1'); await Promise.all(att);
  await worker.fetch(new Request(DEV + '/site.json', { headers: { 'CF-Connecting-IP': '4.4.4.4' } }), env, ctx); await Promise.all(att);
  const jour = new Date().toISOString().slice(0, 10);
  const x = JSON.parse(C.m.get(`stats/visites/${jour}.json`));
  assert.equal(x.vues, 3);
  assert.equal(x.uniques, 2);
  assert.ok(!JSON.stringify(x).includes('1.1.1.1'));
  const e = await (await worker.fetch(get('/compte/admin/api/entonnoir', { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(e.fenetres[7].visiteurs, 2);
  C.m.set('stats/visites/2026-01-01.json', JSON.stringify({ jour: '2026-01-01', vues: 5, u: ['a', 'b'] }));
  await V.compacterVisites(env);
  assert.deepEqual(JSON.parse(C.m.get('stats/visites/2026-01-01.json')), { jour: '2026-01-01', vues: 5, uniques: 2 });
  assert.ok(Array.isArray(JSON.parse(C.m.get(`stats/visites/${jour}.json`)).u));   // aujourd'hui : gardées jusqu'à demain
});

test('403 : accès immédiat — deux cases exigées, textes gardés, e-mail de confirmation, retrait avant paiement, virement sans renonciation', async () => {
  const { env, mails } = monde();
  const { TEXTES_RENONCIATION, RENONCIATION_VERSION } = await import('./comptes.js');
  assert.equal((await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }), env)).status, 401);
  await worker.fetch(post('/compte/api/inscription', { email: 'k@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  let r = await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: false }, { Cookie: c }), env);
  assert.equal(r.status, 400);
  assert.equal((await r.json()).erreur, 'deux_cases');
  const n0 = mails.length;
  let o = await (await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }, { Cookie: c }), env)).json();
  assert.match(o.compte.acces_immediat, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(mails.length, n0 + 1);
  assert.match(mails.at(-1).subject, /accès immédiat/);
  assert.ok(mails.at(-1).htmlContent.includes(TEXTES_RENONCIATION.fr[1].replace(/'/g, "'")) || mails.at(-1).textContent.includes(TEXTES_RENONCIATION.fr[1]));
  const ex = await (await worker.fetch(get('/compte/api/export', { Cookie: c }), env)).json();
  assert.deepEqual(ex.acces_immediat.textes, [...TEXTES_RENONCIATION.fr]);
  assert.equal(ex.acces_immediat.version, RENONCIATION_VERSION);
  // deux fois : la première date reste, pas de second e-mail
  const d = o.compte.acces_immediat;
  o = await (await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }, { Cookie: c }), env)).json();
  assert.equal(o.compte.acces_immediat, d);
  assert.equal(mails.length, n0 + 1);
  // retrait avant paiement
  o = await (await worker.fetch(post('/compte/api/acces_immediat', { retirer: true }, { Cookie: c }), env)).json();
  assert.equal(o.compte.acces_immediat, null);
  // virement sans renonciation : seulement avec la case de l'admin ; la facture rappelle les 14 jours
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'Lucas Test EI', adresse: '1 rue du Court', siret: '123' });
  const vir = (b) => worker.fetch(post('/compte/admin/api/virement', b, { 'X-Cle': CLE }, DEV), env).then((x) => x.json());
  assert.equal((await vir({ compte: 'k@exemple.fr', formule: 'mois', montant: '9,99' })).erreur, 'sans_renonciation');
  o = await vir({ compte: 'k@exemple.fr', formule: 'mois', montant: '9,99', sans_renonciation: true });
  assert.equal(o.ok, true);
  assert.equal(o.renonciation, false);
  assert.match(mails.at(-1).htmlContent, /Droit de rétractation : 14 jours à compter du paiement/);
  // accès payé ouvert avec une demande : plus de retrait possible
  await worker.fetch(post('/compte/api/acces_immediat', { demande: true, renonce: true }, { Cookie: c }), env);
  r = await worker.fetch(post('/compte/api/acces_immediat', { retirer: true }, { Cookie: c }), env);
  assert.equal(r.status, 409);
});

test('403 : les textes des deux cases du site sont exactement ceux gardés comme preuve', async () => {
  const fs = await import('node:fs');
  const { TEXTES_RENONCIATION } = await import('./comptes.js');
  const html = fs.readFileSync(new URL('../../algo/index.html', import.meta.url), 'utf-8');
  for (const t of [...TEXTES_RENONCIATION.fr, ...TEXTES_RENONCIATION.en]) assert.ok(html.includes(JSON.stringify(t).slice(1, -1)) || html.includes(t), t);
});

test('405 : ouverture fondateurs — aperçu, refus sans coordonnées, envoi par lots aux 100 premières places, une seule fois, paiement visible', async () => {
  const { env, mails, C } = monde();
  const V = await import('./ventes.js');
  const cookies = [];
  for (let i = 0; i < 3; i++) {
    const n0 = mails.length;
    await worker.fetch(post('/compte/api/inscription', { email: `f${i}@exemple.fr`, mdp: 'motdepasse1' }), env);
    const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[n0], 'verifier') }), env));
    cookies.push(c);
    await new Promise((r) => setTimeout(r, 5));
  }
  const ouv = (b) => worker.fetch(post('/compte/admin/api/ouverture', b, { 'X-Cle': CLE }, DEV), env).then((r) => r.json());
  assert.equal((await ouv({ mode: 'apercu' })).erreur, 'vendeur_absent');
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'Lucas Test EI', adresse: '1 rue du Court', siret: '123' });
  assert.equal((await ouv({ mode: 'apercu' })).erreur, 'coordonnees_absentes');
  env.VIREMENT = JSON.stringify({ titulaire: 'Lucas Test', iban: 'FR76 0000 0000 0000', bic: 'TESTFRPP' });
  // 474 : la place est connue dès la confirmation, le tarif fondateur et les coordonnées sont visibles tout de suite
  let moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cookies[0] }), env)).json();
  assert.equal(moi.compte.fondateur_place, 1);
  assert.equal(moi.paiement.montant, 9.99);
  const a = await ouv({ mode: 'apercu' });
  assert.equal(a.places, 3);
  assert.match(a.sujet, /place fondateur n° 1/);
  assert.match(a.html, /IBAN : FR76 0000 0000 0000/);
  assert.match(a.html, /Libellé \(important\) : GSA-[0-9A-F]{6}/);
  assert.match(a.html, /https:\/\/gamesetalgo\.com\/#plus/);                 // liens vers le site, jamais vers workers.dev
  assert.match(a.html, /#cgv/);
  const n0 = mails.length;
  const o = await ouv({ mode: 'envoyer' });
  assert.deepEqual([o.envoyes, o.restants, o.places], [3, 0, 3]);
  assert.equal(mails.length, n0 + 3);
  assert.match(mails[n0].subject, /n° 1/);
  assert.equal(mails[n0].to[0].email, 'f0@exemple.fr');                        // ordre des comptes
  assert.match(mails[n0 + 2].subject, /n° 3/);
  assert.equal((await ouv({ mode: 'envoyer' })).envoyes, 0);                    // jamais deux fois
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cookies[1] }), env)).json();
  assert.equal(moi.compte.fondateur_place, 2);
  assert.equal(moi.paiement.montant, 9.99);
  assert.equal(moi.paiement.reference, moi.compte.reference);
  assert.equal(V.PLACES_FONDATEUR, 100);
});

test('405 : au-delà des 100 places, pas d’e-mail d’ouverture', async () => {
  const { env, C } = monde();
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'X', adresse: 'Y', siret: '1' });
  env.VIREMENT = JSON.stringify({ titulaire: 'L', iban: 'FR76' });
  const { idCompte } = await import('./comptes.js');
  for (let i = 0; i < 102; i++) {
    const email = `z${String(i).padStart(3, '0')}@exemple.fr`, id = await idCompte(email);
    C.m.set(`comptes/u/${id}.json`, JSON.stringify({ id, email, verifie: true, cree: new Date(Date.UTC(2026, 10, 1, 0, i)).toISOString() }));
  }
  const V = await import('./ventes.js');
  const L = (await V.fondateursOrdonnes(env)).slice(0, V.PLACES_FONDATEUR);
  assert.equal(L.length, 100);
  assert.equal(L[0].email, 'z000@exemple.fr');
  assert.ok(!L.some((u) => u.email === 'z100@exemple.fr' || u.email === 'z101@exemple.fr'));
  const r = await worker.fetch(post('/compte/admin/api/ouverture', { mode: 'envoyer' }, { 'X-Cle': CLE }, DEV), env).then((x) => x.json());
  assert.equal(r.envoyes, 25);                                                  // un lot à la fois
  assert.equal(r.restants, 75);
});

test('407 : demande d’abonnement — montant fixé par le serveur, tarif fondateur au mois, e-mail, paiement visible, annulation, effacée au virement', async () => {
  const { env, mails } = monde();
  const V = await import('./ventes.js');
  assert.equal((await worker.fetch(post('/compte/api/abonnement', { formule: 'mois' }), env)).status, 401);
  const comptes = [];
  for (const e of ['a1@exemple.fr', 'a2@exemple.fr']) {
    const n0 = mails.length;
    await worker.fetch(post('/compte/api/inscription', { email: e, mdp: 'motdepasse1' }), env);
    comptes.push(cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[n0], 'verifier') }), env)));
  }
  const [cA, cB] = comptes;
  // 474 : A et B sont fondateurs n° 1 et 2, automatiquement
  let r = await worker.fetch(post('/compte/api/abonnement', { formule: 'decennie' }, { Cookie: cB }), env);
  assert.equal((await r.json()).erreur, 'formule');
  // sans coordonnées bancaires : la demande est notée, l'e-mail annonce les coordonnées plus tard
  let n0 = mails.length;
  r = await (await worker.fetch(post('/compte/api/abonnement', { formule: 'trimestre', montant: 0.01 }, { Cookie: cB }), env)).json();
  assert.equal(r.ok, true);
  assert.equal(mails.length, n0 + 1);
  assert.match(mails.at(-1).subject, /3 mois, 49,99 €/);
  assert.match(mails.at(-1).textContent, /Ta référence : GSA-[0-9A-F]{6}/);
  let moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cB }), env)).json();
  assert.equal(moi.compte.demande.montant, V.TARIFS.trimestre);                 // jamais le montant du navigateur
  assert.deepEqual(moi.tarifs, { ...V.TARIFS });
  assert.equal(moi.paiement.iban, null);
  assert.equal(moi.paiement.montant, 49.99);
  // fondateur parmi les 100 premiers : 9,99 € au mois
  env.VIREMENT = JSON.stringify({ titulaire: 'Lucas Test', iban: 'FR76 0000', bic: 'TESTFRPP' });
  r = await (await worker.fetch(post('/compte/api/abonnement', { formule: 'mois' }, { Cookie: cA }), env)).json();
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cA }), env)).json();
  assert.equal(moi.compte.demande.montant, 9.99);
  assert.equal(moi.compte.demande.fondateur, true);
  assert.equal(moi.paiement.iban, 'FR76 0000');
  assert.match(mails.at(-1).htmlContent, /IBAN : FR76 0000/);
  assert.match(mails.at(-1).htmlContent, /tarif fondateur/);
  // le même fondateur à l'année : prix normal
  await worker.fetch(post('/compte/api/abonnement', { formule: 'annee' }, { Cookie: cA }), env);
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cA }), env)).json();
  assert.equal(moi.compte.demande.montant, 169.99);
  // l'administration voit les demandes
  const l = await (await worker.fetch(get('/compte/admin/api/liste', { 'X-Cle': CLE }, DEV), env)).json();
  assert.equal(l.comptes.filter((c) => c.demande).length, 2);
  // annulation
  await worker.fetch(post('/compte/api/abonnement', { annuler: true }, { Cookie: cA }), env);
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cA }), env)).json();
  assert.equal(moi.compte.demande, null);
  assert.equal(moi.paiement.montant, 9.99);                     // 474 : le tarif fondateur reste proposé
  // virement reçu : la demande de B est effacée
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'Lucas Test EI', adresse: '1 rue', siret: '1' });
  const o = await worker.fetch(post('/compte/admin/api/virement', { compte: 'a2@exemple.fr', formule: 'trimestre', montant: '49,99', sans_renonciation: true },
    { 'X-Cle': CLE }, DEV), env).then((x) => x.json());
  assert.equal(o.ok, true);
  moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: cB }), env)).json();
  assert.equal(moi.compte.demande, null);
  assert.equal(moi.compte.paye, true);
});

test('407 : prix du mois pour un fondateur au-delà des 100 places : prix normal', async () => {
  const V = await import('./ventes.js');
  assert.equal(V.montantDemande('mois', 100), 9.99);
  assert.equal(V.montantDemande('mois', 101), 19.99);
  assert.equal(V.montantDemande('mois', null), 19.99);
  assert.equal(V.montantDemande('semaine', 1), 5.99);
  assert.equal(V.montantDemande('decennie', 1), null);
});

test('412 : tarif fondateur perdu après 7 jours de retard ; rappel avec la date limite ; virement fondateur refusé', async () => {
  const V = await import('./ventes.js');
  const now = Date.parse('2026-12-20T12:00:00Z');
  const u = (jusqu, extra = {}) => ({ acces: { paye: true, fondateur_tarif: true, jusqu_au: jusqu }, ...extra });
  assert.equal(V.fondateurPerdu(u('2026-12-15T00:00:00Z'), now), false);          // 5 jours : gardé
  assert.equal(V.fondateurPerdu(u('2026-12-10T00:00:00Z'), now), true);           // 10 jours : perdu
  assert.equal(V.fondateurPerdu({ acces: {} }, now), false);                      // jamais payé : pas de délai
  assert.equal(V.fondateurPerdu(u('2027-01-30T00:00:00Z', { fondateur_perdu: '2026-11-01' }), now), true);   // définitif
  const m = V.messageRappel({ id: 'abcdef', acces: { paye: true, fondateur_tarif: true, jusqu_au: '2026-12-15T00:00:00Z', montant: 9.99 } }, {}, 'https://gamesetalgo.com');
  assert.match(m.texte, /garder ton tarif fondateur, paie au plus tard le 22\/12\/2026/);
  // demande d'un fondateur en retard : prix normal, perte notée
  const { env, mails, C } = monde();
  await worker.fetch(post('/compte/api/inscription', { email: 'r@exemple.fr', mdp: 'motdepasse1' }), env);
  const c = cookie(await worker.fetch(post('/compte/api/verifier', { jeton: lienDe(mails[0], 'verifier') }), env));
  await worker.fetch(post('/compte/api/fondateur', { reserver: true }, { Cookie: c }), env);
  for (const [k, x] of C.m) if (k.startsWith('comptes/u/')) {
    const v = JSON.parse(x); v.acces = { formule: 'mois', paye: true, fondateur_tarif: true, jusqu_au: new Date(Date.now() - 20 * 86400e3).toISOString() };
    C.m.set(k, JSON.stringify(v));
  }
  await worker.fetch(post('/compte/api/abonnement', { formule: 'mois' }, { Cookie: c }), env);
  const moi = await (await worker.fetch(get('/compte/api/moi', { Cookie: c }), env)).json();
  assert.equal(moi.compte.demande.montant, 19.99);
  assert.equal(moi.compte.fondateur_perdu, true);
  env.FACTURE_VENDEUR = JSON.stringify({ nom: 'X', adresse: 'Y', siret: '1' });
  const o = await worker.fetch(post('/compte/admin/api/virement', { compte: 'r@exemple.fr', formule: 'mois', montant: '9,99', fondateur: true, sans_renonciation: true },
    { 'X-Cle': CLE }, DEV), env).then((x) => x.json());
  assert.equal(o.erreur, 'fondateur_perdu');
});
