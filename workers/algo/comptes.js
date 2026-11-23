// Comptes des abonnés Game Set Algo (23/11/2026, paquet 377).
//
// Décisions de Lucas : le site reste ouvert, UN match offert par jour (le match du jour), tout le reste réservé à
// l'accès Plus ; un seul accès, payé à la semaine, au mois, au trimestre ou à l'année ; pas encore de paiement
// (l'accès est donné à la main depuis /compte/admin) ; un compte utilisateur avec e-mail et mot de passe ; les
// e-mails partent par Brevo (secret BREVO_API_KEY du worker).
//
// Stockage : R2 (bucket du coffre), préfixe comptes/ — jamais servi par le site (publique ne lit que site/algo/,
// prive que prive/). Un objet par compte : comptes/u/<sha256 de l'e-mail>.json. Aucune donnée de paiement.
// Mots de passe : PBKDF2-SHA256, 100 000 tours, sel de 16 octets. Session : cookie signé (HMAC, clé tirée de
// CLE_PRIVEE), HttpOnly, Secure, SameSite=Lax, 90 jours ; un changement de mot de passe ferme toutes les sessions.
// Liens envoyés par e-mail (vérification, nouveau mot de passe) : signés, valables 48 h / 1 h, à usage unique.

export const COOKIE_COMPTE = 'gsa_compte';
export const FORMULES = Object.freeze({ semaine: 7, mois: 31, trimestre: 92, annee: 366, offert: null, illimite: null,
  admin: null });                     // 380 : admin = accès Plus illimité + sections internes du site
const SESSION_J = 90, VERIF_H = 48, REINIT_H = 1, ITER = 100000;
const MAX_ECHECS = 10, BLOCAGE_MIN = 15, ENVOI_MIN_S = 120, ENVOIS_JOUR = 250;

const te = new TextEncoder();
const b64u = (u8) => btoa(String.fromCharCode(...u8)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const deb64u = (s) => Uint8Array.from(atob(String(s).replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
const hex = (u8) => [...u8].map((x) => x.toString(16).padStart(2, '0')).join('');

export function normaliser(email) {
  const e = String(email || '').trim().toLowerCase();
  return /^[^\s@<>"']{1,64}@[^\s@<>"']{1,190}\.[a-z]{2,24}$/.test(e) ? e : null;
}
export async function idCompte(email) {
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', te.encode('gsa:' + email))));
}
function egal(a, b) {
  const x = te.encode(String(a || '')), y = te.encode(String(b || ''));
  let d = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) d |= (x[i] || 0) ^ (y[i] || 0);
  return d === 0;
}
async function cleHmac(env) {
  const base = await crypto.subtle.importKey('raw', te.encode(String(env.CLE_PRIVEE)), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const brut = new Uint8Array(await crypto.subtle.sign('HMAC', base, te.encode('comptes-gamesetalgo-v1')));
  return crypto.subtle.importKey('raw', brut, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
}
async function signer(env, texte) {
  return b64u(new Uint8Array(await crypto.subtle.sign('HMAC', await cleHmac(env), te.encode(texte))));
}
export async function hacher(mdp, selB64, iter = ITER) {
  // iter : tours PBKDF2 (variable PBKDF2_TOURS du worker pour les nouveaux mots de passe ; chaque compte garde les siens)
  iter = Math.max(10000, Math.min(100000, Number(iter) || ITER));
  const sel = selB64 ? deb64u(selB64) : crypto.getRandomValues(new Uint8Array(16));
  const k = await crypto.subtle.importKey('raw', te.encode(String(mdp)), 'PBKDF2', false, ['deriveBits']);
  const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: sel, iterations: iter }, k, 256));
  return { sel: b64u(sel), hash: b64u(bits), iter };
}

// --------------------------------------------------------------------------------------------- stockage
const chemin = (id) => `comptes/u/${id}.json`;
async function lire(env, id) {
  try {
    const o = await env.COFFRE.get(chemin(id));
    return o ? JSON.parse(await o.text()) : null;
  } catch (e) { return null; }
}
async function ecrire(env, u) {
  await env.COFFRE.put(chemin(u.id), JSON.stringify(u), { httpMetadata: { contentType: 'application/json' } });
}

export function abonne(u, maintenant = Date.now()) {
  const a = (u && u.acces) || {};
  if (a.formule === 'illimite' || a.formule === 'admin') return true;
  return !!a.jusqu_au && Date.parse(a.jusqu_au) > maintenant;
}
export const estAdmin = (u) => !!u && (u.acces || {}).formule === 'admin';
function vueCompte(u) {
  return { email: u.email, verifie: !!u.verifie, abonne: abonne(u), admin: estAdmin(u), formule: (u.acces || {}).formule || null,
    jusqu_au: (u.acces || {}).jusqu_au || null, cree: u.cree };
}

// --------------------------------------------------------------------------------------------- session
export async function cookieSession(env, u) {
  const exp = Date.now() + SESSION_J * 86400e3, corps = `${u.id}.${exp}.${u.v || 0}`;
  const val = `${corps}.${await signer(env, 's|' + corps)}`;
  return `${COOKIE_COMPTE}=${val}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_J * 86400}`;
}
function lireCookie(req, nom) {
  for (const p of (req.headers.get('Cookie') || '').split(';')) {
    const i = p.indexOf('=');
    if (i > 0 && p.slice(0, i).trim() === nom) return p.slice(i + 1).trim();
  }
  return '';
}
export async function utilisateur(req, env) {
  if (!env || !env.COFFRE || !env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return null;
  const c = lireCookie(req, COOKIE_COMPTE), m = /^([0-9a-f]{64})\.(\d{10,15})\.(\d{1,9})\.([A-Za-z0-9_-]{20,})$/.exec(c);
  if (!m || Number(m[2]) < Date.now()) return null;
  if (!egal(m[4], await signer(env, `s|${m[1]}.${m[2]}.${m[3]}`))) return null;
  const u = await lire(env, m[1]);
  return u && String(u.v || 0) === m[3] ? u : null;
}

// --------------------------------------------------------------------------------------------- liens par e-mail
async function lien(env, u, but, heures) {
  const exp = Date.now() + heures * 3600e3, empreinte = but === 'reinit' ? String(u.hash || '').slice(0, 12) : String(u.v || 0);
  const corps = `${u.id}.${exp}.${but}`;
  return `${corps}.${await signer(env, `l|${corps}|${empreinte}`)}`;
}
async function lireLien(env, jeton, but) {
  const m = /^([0-9a-f]{64})\.(\d{10,15})\.(verif|reinit)\.([A-Za-z0-9_-]{20,})$/.exec(String(jeton || ''));
  if (!m || m[3] !== but || Number(m[2]) < Date.now()) return null;
  const u = await lire(env, m[1]);
  if (!u) return null;
  const empreinte = but === 'reinit' ? String(u.hash || '').slice(0, 12) : String(u.v || 0);
  return egal(m[4], await signer(env, `l|${m[1]}.${m[2]}.${m[3]}|${empreinte}`)) ? u : null;
}

// --------------------------------------------------------------------------------------------- e-mails (Brevo)
const ESC = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export function messageMail(but, url, lang) {
  const fr = lang !== 'en';
  const T = {
    verif: fr ? ['Confirme ton adresse e-mail', 'Bienvenue sur Game Set Algo. Confirme ton adresse pour activer ton compte :', 'Confirmer mon adresse', 'Ce lien est valable 48 heures.']
      : ['Confirm your email address', 'Welcome to Game Set Algo. Confirm your address to activate your account:', 'Confirm my address', 'This link is valid for 48 hours.'],
    reinit: fr ? ['Nouveau mot de passe', 'Tu as demandé à changer ton mot de passe :', 'Choisir un nouveau mot de passe', "Ce lien est valable 1 heure. Si tu n'as rien demandé, ignore cet e-mail."]
      : ['New password', 'You asked to change your password:', 'Choose a new password', "This link is valid for 1 hour. If you didn't ask, ignore this email."],
    existe: fr ? ['Ton compte Game Set Algo', 'Un compte existe déjà avec cette adresse. Si tu as oublié ton mot de passe :', 'Choisir un nouveau mot de passe', "Si tu n'as rien demandé, ignore cet e-mail."]
      : ['Your Game Set Algo account', 'An account already exists with this address. If you forgot your password:', 'Choose a new password', "If you didn't ask, ignore this email."],
  }[but];
  const html = `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:24px;color:#14102e">
<h2 style="margin:0 0 12px">${ESC(T[0])}</h2><p>${ESC(T[1])}</p>
<p style="margin:24px 0"><a href="${ESC(url)}" style="background:#2ee6ff;color:#0e0a24;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:bold">${ESC(T[2])}</a></p>
<p style="color:#666;font-size:13px">${ESC(T[3])}</p><p style="color:#666;font-size:13px">Game Set Algo · gamesetalgo.com</p></div>`;
  return { sujet: T[0], html, texte: `${T[1]}\n${url}\n\n${T[3]}` };
}
async function quotaJour(env) {
  const cle = `comptes/envois/${new Date().toISOString().slice(0, 10)}.json`;
  let n = 0;
  try { const o = await env.COFFRE.get(cle); if (o) n = Number(JSON.parse(await o.text()).n) || 0; } catch (e) { /* 0 */ }
  if (n >= ENVOIS_JOUR) return false;
  await env.COFFRE.put(cle, JSON.stringify({ n: n + 1 }));
  return true;
}
export async function envoyerMail(env, a, m) {
  if (!env.BREVO_API_KEY) return { ok: false, raison: 'mail_non_configure' };
  if (!(await quotaJour(env))) return { ok: false, raison: 'quota' };
  const exp = String(env.MAIL_EXPEDITEUR || 'Game Set Algo <noreply@gamesetalgo.com>');
  const mm = /^(.*)<([^>]+)>$/.exec(exp);
  const r = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: { 'api-key': env.BREVO_API_KEY, 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ sender: mm ? { name: mm[1].trim(), email: mm[2].trim() } : { email: exp }, to: [{ email: a }],
      subject: m.sujet, htmlContent: m.html, textContent: m.texte }),
  });
  return { ok: r.ok, raison: r.ok ? null : 'brevo_' + r.status };
}
function base(req, env) {
  return String(env.SITE_URL || new URL(req.url).origin).replace(/\/+$/, '');
}

// --------------------------------------------------------------------------------------------- API
const H = { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'private, no-store',
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' };
const rep = (o, status = 200, extra = {}) => new Response(JSON.stringify(o), { status, headers: { ...H, ...extra } });

function memeOrigine(req) {
  const o = req.headers.get('Origin');
  return !o || o === new URL(req.url).origin;
}
async function corps(req) {
  if (!(req.headers.get('Content-Type') || '').includes('application/json')) return null;
  try { const t = await req.text(); return t.length > 4000 ? null : JSON.parse(t); } catch (e) { return null; }
}
const mdpValide = (m) => typeof m === 'string' && m.length >= 8 && m.length <= 200;

// 23/11/2026 (paquet 382) — ANTI-ROBOTS : Cloudflare Turnstile sur l'inscription et le mot de passe oublié (les deux
// envoient un e-mail : sans lui, un robot viderait les 300 envois Brevo du jour). Actif seulement si les secrets
// TURNSTILE_SITEKEY et TURNSTILE_SECRET du worker existent ; sinon tout marche comme avant.
export async function humain(req, env, jeton) {
  if (!env.TURNSTILE_SECRET) return true;
  if (!jeton || String(jeton).length > 4000) return false;
  try {
    const f = new FormData();
    f.append('secret', env.TURNSTILE_SECRET);
    f.append('response', String(jeton));
    const ip = req.headers.get('CF-Connecting-IP');
    if (ip) f.append('remoteip', ip);
    const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: f });
    const o = await r.json();
    return !!(o && o.success);
  } catch (e) { return false; }
}
const LANG = (b) => (b && b.lang === 'en' ? 'en' : 'fr');

async function inscription(req, env, b) {
  if (!(await humain(req, env, b.turnstile))) return rep({ ok: false, erreur: 'robot' }, 403);
  const email = normaliser(b.email);
  if (!email) return rep({ ok: false, erreur: 'email_invalide' }, 400);
  if (!mdpValide(b.mdp)) return rep({ ok: false, erreur: 'mdp_court' }, 400);
  const id = await idCompte(email);
  const deja = await lire(env, id);
  const maintenant = Date.now();
  if (deja) {                                                   // réponse identique : on ne révèle pas qui est inscrit
    if (!deja.dernier_mail || maintenant - deja.dernier_mail > ENVOI_MIN_S * 1000) {
      deja.dernier_mail = maintenant;
      await ecrire(env, deja);
      const but = deja.verifie ? 'existe' : 'verif';
      const t = await lien(env, deja, but === 'verif' ? 'verif' : 'reinit', but === 'verif' ? VERIF_H : REINIT_H);
      await envoyerMail(env, email, messageMail(but, `${base(req, env)}/?${but === 'verif' ? 'verifier' : 'reinit'}=${t}`, LANG(b)));
    }
    return rep({ ok: true, envoye: true });
  }
  const u = { id, email, ...(await hacher(b.mdp, null, env.PBKDF2_TOURS)), v: 0, verifie: false, cree: new Date(maintenant).toISOString(),
    acces: { formule: null, jusqu_au: null }, echecs: 0, dernier_mail: maintenant, lang: LANG(b) };
  await ecrire(env, u);
  const m = await envoyerMail(env, email, messageMail('verif', `${base(req, env)}/?verifier=${await lien(env, u, 'verif', VERIF_H)}`, LANG(b)));
  return rep({ ok: true, envoye: m.ok, raison: m.raison || undefined });
}
async function connexionCompte(req, env, b) {
  const email = normaliser(b.email);
  if (!email || typeof b.mdp !== 'string') return rep({ ok: false, erreur: 'identifiants' }, 401);
  const u = await lire(env, await idCompte(email));
  if (!u) { await hacher(b.mdp, null, env.PBKDF2_TOURS); return rep({ ok: false, erreur: 'identifiants' }, 401); }   // même durée
  if (u.bloque_jusqu && u.bloque_jusqu > Date.now()) return rep({ ok: false, erreur: 'bloque' }, 429);
  const h = await hacher(b.mdp, u.sel, u.iter);
  if (!egal(h.hash, u.hash)) {
    u.echecs = (u.echecs || 0) + 1;
    if (u.echecs >= MAX_ECHECS) { u.bloque_jusqu = Date.now() + BLOCAGE_MIN * 60e3; u.echecs = 0; }
    await ecrire(env, u);
    return rep({ ok: false, erreur: 'identifiants' }, 401);
  }
  if (!u.verifie) return rep({ ok: false, erreur: 'non_verifie' }, 403);
  u.echecs = 0; u.bloque_jusqu = null; u.vu = new Date().toISOString();
  await ecrire(env, u);
  return rep({ ok: true, compte: vueCompte(u) }, 200, { 'Set-Cookie': await cookieSession(env, u) });
}
async function verifier(req, env, b) {
  const u = await lireLien(env, b.jeton, 'verif');
  if (!u) return rep({ ok: false, erreur: 'lien_invalide' }, 400);
  if (!u.verifie) { u.verifie = true; u.verifie_le = new Date().toISOString(); }
  u.v = (u.v || 0) + 1;                                         // le lien ne sert qu'une fois
  await ecrire(env, u);
  return rep({ ok: true, compte: vueCompte(u) }, 200, { 'Set-Cookie': await cookieSession(env, u) });
}
async function oubli(req, env, b) {
  if (!(await humain(req, env, b.turnstile))) return rep({ ok: false, erreur: 'robot' }, 403);
  const email = normaliser(b.email);
  if (email) {
    const u = await lire(env, await idCompte(email));
    if (u && (!u.dernier_mail || Date.now() - u.dernier_mail > ENVOI_MIN_S * 1000)) {
      u.dernier_mail = Date.now();
      await ecrire(env, u);
      await envoyerMail(env, email, messageMail('reinit', `${base(req, env)}/?reinit=${await lien(env, u, 'reinit', REINIT_H)}`, LANG(b)));
    }
  }
  return rep({ ok: true, envoye: true });
}
async function reinit(req, env, b) {
  if (!mdpValide(b.mdp)) return rep({ ok: false, erreur: 'mdp_court' }, 400);
  const u = await lireLien(env, b.jeton, 'reinit');
  if (!u) return rep({ ok: false, erreur: 'lien_invalide' }, 400);
  Object.assign(u, await hacher(b.mdp, null, env.PBKDF2_TOURS));
  u.v = (u.v || 0) + 1; u.verifie = true; u.echecs = 0; u.bloque_jusqu = null;   // toutes les sessions fermées
  await ecrire(env, u);
  return rep({ ok: true, compte: vueCompte(u) }, 200, { 'Set-Cookie': await cookieSession(env, u) });
}

// 23/11/2026 (paquet 382) — RGPD : changer de mot de passe, supprimer son compte (effacement immédiat), télécharger ses
// données. Les deux premiers demandent le mot de passe actuel.
async function verifierMdp(u, mdp) {
  if (!u || typeof mdp !== 'string') return false;
  return egal((await hacher(mdp, u.sel, u.iter)).hash, u.hash);
}
async function changerMdp(req, env, b) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  if (!mdpValide(b.nouveau)) return rep({ ok: false, erreur: 'mdp_court' }, 400);
  if (!(await verifierMdp(u, b.ancien))) return rep({ ok: false, erreur: 'mdp_faux' }, 403);
  Object.assign(u, await hacher(b.nouveau, null, env.PBKDF2_TOURS));
  u.v = (u.v || 0) + 1;                                          // les autres sessions sont fermées
  await ecrire(env, u);
  return rep({ ok: true, compte: vueCompte(u) }, 200, { 'Set-Cookie': await cookieSession(env, u) });
}
async function supprimer(req, env, b) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  if (!(await verifierMdp(u, b.mdp))) return rep({ ok: false, erreur: 'mdp_faux' }, 403);
  await env.COFFRE.delete(chemin(u.id));
  return rep({ ok: true }, 200, { 'Set-Cookie': `${COOKIE_COMPTE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0` });
}
async function exporter(req, env) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  const garde = ['email', 'cree', 'verifie', 'verifie_le', 'vu', 'acces', 'historique', 'lang'];
  const d = Object.fromEntries(garde.filter((k) => k in u).map((k) => [k, u[k]]));
  d.mot_de_passe = 'jamais stocké en clair : seulement une empreinte (PBKDF2-SHA256)';
  return new Response(JSON.stringify(d, null, 1), { headers: { ...H, 'Content-Disposition': 'attachment; filename="mes-donnees-gamesetalgo.json"' } });
}

export async function apiCompte(req, env, url, cle = false) {
  const p = url.pathname.slice('/compte/api/'.length);
  if (!env.COFFRE || !env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return rep({ ok: false, erreur: 'ferme' }, 503);
  if (p === 'moi' && req.method === 'GET') {
    const u = await utilisateur(req, env);
    return rep({ ok: true, compte: u ? vueCompte(u) : null, admin: !!cle || estAdmin(u),
      turnstile: env.TURNSTILE_SECRET && env.TURNSTILE_SITEKEY ? String(env.TURNSTILE_SITEKEY) : null });
  }
  if (p === 'export' && req.method === 'GET') return exporter(req, env);
  if (req.method !== 'POST') return rep({ ok: false, erreur: 'methode' }, 405);
  if (!memeOrigine(req)) return rep({ ok: false, erreur: 'origine' }, 403);
  if (p === 'deconnexion') return rep({ ok: true }, 200, { 'Set-Cookie': `${COOKIE_COMPTE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0` });
  const b = await corps(req);
  if (!b) return rep({ ok: false, erreur: 'requete' }, 400);
  if (p === 'inscription') return inscription(req, env, b);
  if (p === 'connexion') return connexionCompte(req, env, b);
  if (p === 'verifier') return verifier(req, env, b);
  if (p === 'oubli') return oubli(req, env, b);
  if (p === 'reinit') return reinit(req, env, b);
  if (p === 'code') return utiliserCode(req, env, b);
  if (p === 'mdp') return changerMdp(req, env, b);
  if (p === 'supprimer') return supprimer(req, env, b);
  return rep({ ok: false, erreur: 'inconnu' }, 404);
}

// --------------------------------------------------------------------------------------------- codes d'accès
// 23/11/2026 (paquet 381, Lucas) : un CODE À USAGE UNIQUE active l'accès Plus d'un compte, sans paiement. Créé depuis
// /compte/admin : formule (semaine, mois, trimestre, année, ou un nombre de jours), validité du code (il ne marche plus
// après cette date même jamais utilisé). Au coffre, seule l'empreinte du code (SHA-256) : la liste ne montre que ses
// 4 derniers caractères. Utilisation : un compte connecté et confirmé le saisit dans « Mon compte » ; le code est marqué
// utilisé par une écriture conditionnelle (deux comptes en même temps : un seul gagne). 10 essais ratés par heure au plus.
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';           // sans 0/O ni 1/I : se dicte et se recopie sans erreur
const MAX_ESSAIS_CODE = 10;
const PURGE_J = 30;
export function nouveauCode() {
  const r = crypto.getRandomValues(new Uint8Array(12));
  const c = [...r].map((x) => ALPHABET[x % ALPHABET.length]).join('');
  return `GSA-${c.slice(0, 4)}-${c.slice(4, 8)}-${c.slice(8, 12)}`;
}
export function normaliserCode(c) {
  const s = String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const corps = s.startsWith('GSA') ? s.slice(3) : s;
  return corps.length === 12 ? `GSA-${corps.slice(0, 4)}-${corps.slice(4, 8)}-${corps.slice(8, 12)}` : null;
}
const cheminCode = async (code) => `comptes/codes/${hex(new Uint8Array(await crypto.subtle.digest('SHA-256', te.encode('gsa-code:' + code))))}.json`;
export async function creerCodes(env, formule, jours, validiteJours, nombre = 1, note = '') {
  if (!(formule in FORMULES) || formule === 'admin' || formule === 'illimite') return { ok: false, erreur: 'formule' };
  const j = Number(jours) > 0 ? Math.min(Number(jours), 3660) : FORMULES[formule];
  if (!j) return { ok: false, erreur: 'jours' };
  const v = Math.max(1, Math.min(Number(validiteJours) || 30, 365));
  const n = Math.max(1, Math.min(Number(nombre) || 1, 50));
  const codes = [];
  for (let i = 0; i < n; i++) {
    const code = nouveauCode(), maintenant = Date.now();
    await env.COFFRE.put(await cheminCode(code), JSON.stringify({ indice: code.slice(-4), formule, jours: j,
      cree: new Date(maintenant).toISOString(), expire: new Date(maintenant + v * 86400e3).toISOString(),
      note: String(note || '').slice(0, 80), utilise_par: null, utilise_le: null }));
    codes.push(code);
  }
  return { ok: true, codes, formule, jours: j, valide_jours: v };
}
export async function listeCodes(env) {
  const out = [];
  let curseur;
  do {
    const l = await env.COFFRE.list({ prefix: 'comptes/codes/', cursor: curseur, limit: 1000 });
    for (const o of l.objects || []) {
      try { const x = JSON.parse(await (await env.COFFRE.get(o.key)).text()); out.push(x); } catch (e) { /* ignoré */ }
    }
    curseur = l.truncated ? l.cursor : undefined;
  } while (curseur);
  return out.sort((a, b) => String(b.cree).localeCompare(String(a.cree))).slice(0, 200);
}
async function utiliserCode(req, env, b) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  if (!u.verifie) return rep({ ok: false, erreur: 'non_verifie' }, 403);
  const heure = Math.floor(Date.now() / 3600e3);
  if (u.essais_code && u.essais_code.h === heure && u.essais_code.n >= MAX_ESSAIS_CODE) return rep({ ok: false, erreur: 'bloque' }, 429);
  const code = normaliserCode(b.code), cle = code ? await cheminCode(code) : null;
  const o = cle ? await env.COFFRE.get(cle) : null;
  let x = null;
  try { x = o ? JSON.parse(await o.text()) : null; } catch (e) { x = null; }
  const raison = !x ? 'code_invalide' : x.utilise_par ? 'code_utilise' : Date.parse(x.expire) < Date.now() ? 'code_expire' : null;
  if (raison) {
    u.essais_code = { h: heure, n: (u.essais_code && u.essais_code.h === heure ? u.essais_code.n : 0) + 1 };
    await ecrire(env, u);
    return rep({ ok: false, erreur: raison }, 400);
  }
  x.utilise_par = u.email; x.utilise_le = new Date().toISOString();
  const pose = await env.COFFRE.put(cle, JSON.stringify(x), { onlyIf: { etagMatches: o.etag } });
  if (!pose) return rep({ ok: false, erreur: 'code_utilise' }, 400);           // un autre compte l'a pris à l'instant
  const r = await donnerAcces(env, u.email, x.formule, x.jours, 'code ' + x.indice);
  return rep(r.ok ? { ok: true, compte: r.compte, jours: x.jours } : r, r.ok ? 200 : 400);
}

// --------------------------------------------------------------------------------------------- administration
// Seulement sur l'adresse workers.dev, avec la clé privée (cookie du Lab ou en-tête X-Cle) : voir worker.js.
export async function listeComptes(env) {
  const out = [];
  let curseur;
  do {
    const l = await env.COFFRE.list({ prefix: 'comptes/u/', cursor: curseur, limit: 1000 });
    for (const o of l.objects || []) {
      const u = await lire(env, o.key.slice('comptes/u/'.length, -5));
      // 382 : un compte jamais confirmé est effacé après 30 jours (politique de confidentialité)
      if (u && !u.verifie && Date.now() - Date.parse(u.cree || 0) > PURGE_J * 86400e3) { await env.COFFRE.delete(o.key); continue; }
      if (u) out.push(vueCompte(u));
    }
    curseur = l.truncated ? l.cursor : undefined;
  } while (curseur);
  return out.sort((a, b) => String(b.cree).localeCompare(String(a.cree)));
}
export async function donnerAcces(env, email, formule, jours, origine = 'admin') {
  const e = normaliser(email);
  if (!e || !(formule in FORMULES || formule === 'retirer')) return { ok: false, erreur: 'requete' };
  const u = await lire(env, await idCompte(e));
  if (!u) return { ok: false, erreur: 'inconnu' };
  if (formule === 'retirer') u.acces = { formule: null, jusqu_au: null };
  else {
    const j = Number(jours) > 0 ? Number(jours) : FORMULES[formule];
    const depart = Math.max(Date.now(), Date.parse((u.acces || {}).jusqu_au || 0) || 0);   // prolonge un accès en cours
    u.acces = { formule, jusqu_au: (formule === 'illimite' || formule === 'admin') ? null : (j ? new Date(depart + j * 86400e3).toISOString() : null),
      donne_le: new Date().toISOString() };
  }
  u.historique = [...(u.historique || []).slice(-19), { le: new Date().toISOString(), formule, jours: jours || null, origine }];
  await ecrire(env, u);
  return { ok: true, compte: vueCompte(u) };
}
export function pageAdmin() {
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Comptes · Game Set Algo</title><style>body{font:15px system-ui,sans-serif;background:#0e0a24;color:#f4f1ff;margin:0;padding:16px}
.c{background:#1b1342;border-radius:12px;padding:12px;margin:10px 0}input,select,button{font:inherit;padding:10px;border-radius:9px;border:1px solid #443a7a;background:#0e0a24;color:#f4f1ff;margin:4px 0;width:100%;box-sizing:border-box}
button{background:#2ee6ff;color:#0e0a24;font-weight:700;border:0}.ok{color:#7dff9a}.non{color:#ff4fae}small{color:#a99fd6}</style></head><body>
<h2>Comptes abonnés</h2><div class="c"><b>Donner un accès</b><input id="e" type="email" placeholder="e-mail du compte">
<select id="f"><option value="semaine">Semaine</option><option value="mois">Mois</option><option value="trimestre">Trimestre</option><option value="annee">Année</option><option value="offert">Offert (jours ci-dessous)</option><option value="illimite">Illimité</option><option value="admin">Admin (toi : sections internes)</option><option value="retirer">Retirer l'accès</option></select>
<input id="j" type="number" min="1" placeholder="jours (facultatif)"><button id="b">Valider</button><p id="r"></p></div>
<div class="c"><b>Créer des codes à usage unique</b><select id="cf"><option value="semaine">Semaine</option><option value="mois" selected>Mois</option><option value="trimestre">Trimestre</option><option value="annee">Année</option><option value="offert">Nombre de jours ci-dessous</option></select>
<input id="cj" type="number" min="1" placeholder="jours d'accès (facultatif)"><input id="cv" type="number" min="1" max="365" value="30" placeholder="code valable (jours)">
<input id="cn" type="number" min="1" max="50" value="1" placeholder="nombre de codes"><input id="cno" type="text" maxlength="80" placeholder="note (pour qui ?)">
<button id="cb">Créer</button><pre id="cr" style="white-space:pre-wrap;font-size:16px;user-select:all"></pre></div><div id="lc"></div><div id="l"></div>
<script>
const $=id=>document.getElementById(id);
function charger(){fetch('/compte/admin/api/liste',{cache:'no-store'}).then(r=>r.json()).then(o=>{$('l').innerHTML='<p><small>'+o.comptes.length+' compte(s)</small></p>'+o.comptes.map(c=>'<div class="c"><b>'+c.email.replace(/</g,'&lt;')+'</b><br><small>créé le '+String(c.cree).slice(0,10)+(c.verifie?'':' · e-mail non confirmé')+'</small><br>'+(c.abonne?'<span class="ok">Plus · '+(c.formule||'')+(c.jusqu_au?' jusqu’au '+c.jusqu_au.slice(0,10):'')+'</span>':'<span class="non">gratuit</span>')+'</div>').join('')});}
$('b').onclick=()=>fetch('/compte/admin/api/acces',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('e').value,formule:$('f').value,jours:$('j').value||null})}).then(r=>r.json()).then(o=>{$('r').textContent=o.ok?'Fait.':'Refusé : '+o.erreur;charger();});
function codes(){fetch('/compte/admin/api/codes',{cache:'no-store'}).then(r=>r.json()).then(o=>{const e=s=>String(s||'').replace(/</g,'&lt;');$('lc').innerHTML='<p><small>Codes ('+o.codes.length+')</small></p>'+o.codes.map(c=>'<div class="c">…'+e(c.indice)+' · '+e(c.formule)+' '+c.jours+' j'+(c.note?' · '+e(c.note):'')+'<br><small>'+(c.utilise_par?'<span class="ok">utilisé par '+e(c.utilise_par)+' le '+String(c.utilise_le).slice(0,10)+'</span>':(Date.parse(c.expire)<Date.now()?'<span class="non">expiré</span>':'libre jusqu’au '+String(c.expire).slice(0,10)))+'</small></div>').join('')});}
$('cb').onclick=()=>fetch('/compte/admin/api/codes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({formule:$('cf').value,jours:$('cj').value||null,validite:$('cv').value||30,nombre:$('cn').value||1,note:$('cno').value})}).then(r=>r.json()).then(o=>{$('cr').textContent=o.ok?o.codes.join('\n')+'\n('+o.jours+' jours d’accès, code valable '+o.valide_jours+' jours, une seule utilisation)':'Refusé : '+o.erreur;codes();});
charger();codes();
</script></body></html>`;
}
export async function adminComptes(req, env, url) {
  const p = url.pathname;
  if (p === '/compte/admin') return new Response(pageAdmin(), { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'private, no-store',
    'X-Robots-Tag': 'noindex', 'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'" } });
  if (p === '/compte/admin/api/liste' && req.method === 'GET') return rep({ ok: true, comptes: await listeComptes(env) });
  if (p === '/compte/admin/api/codes' && req.method === 'GET') return rep({ ok: true, codes: await listeCodes(env) });
  if (p === '/compte/admin/api/codes' && req.method === 'POST') {
    if (!memeOrigine(req)) return rep({ ok: false, erreur: 'origine' }, 403);
    const b = await corps(req);
    if (!b) return rep({ ok: false, erreur: 'requete' }, 400);
    const r = await creerCodes(env, b.formule, b.jours, b.validite, b.nombre, b.note);
    return rep(r, r.ok ? 200 : 400);
  }
  if (p === '/compte/admin/api/acces' && req.method === 'POST') {
    if (!memeOrigine(req)) return rep({ ok: false, erreur: 'origine' }, 403);
    const b = await corps(req);
    if (!b) return rep({ ok: false, erreur: 'requete' }, 400);
    const r = await donnerAcces(env, b.email, b.formule, b.jours);
    return rep(r, r.ok ? 200 : 400);
  }
  return rep({ ok: false, erreur: 'inconnu' }, 404);
}
