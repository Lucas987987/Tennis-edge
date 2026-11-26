// Ventes Game Set Algo : entonnoir, virements reçus et factures, rappels de fin d'accès (23/11/2026, paquet 386,
// Lucas : « 4-1-2 »).
//
// 1. ENTONNOIR (privé, /compte/admin) : visiteurs → comptes → confirmés → fondateurs → Plus payé. Un visiteur = un
//    chargement de /site.json sur gamesetalgo.com (le navigateur l'appelle à chaque ouverture de la page ; les robots
//    qui ne lancent pas le JavaScript ne comptent pas). Sans cookie : une empreinte du jour (HMAC de l'adresse IP et du
//    navigateur avec une clé qui change chaque jour) sert à compter les visiteurs uniques de la journée ; le lendemain,
//    la liste d'empreintes est effacée et seuls les totaux restent. Compte approché (deux visites à la même milliseconde
//    peuvent n'en faire qu'une).
// 2. VIREMENT REÇU (/compte/admin) : l'accès est donné (marqué « payé »), une facture numérotée sans trou
//    (F2026-0001, F2026-0002…) est créée et envoyée par e-mail. Identité du vendeur : secret FACTURE_VENDEUR du worker
//    (JSON : nom, adresse, siret, mention_tva) ; absent → aucune facture possible (refus). Les factures restent 10 ans
//    (obligation comptable), même si le compte est supprimé.
// 3. RAPPEL (tous les jours à 7 h 17 UTC) : un accès PAYÉ qui finit dans 3 jours ou moins reçoit un e-mail, une seule
//    fois par échéance, avec la référence de virement (et les coordonnées bancaires du secret VIREMENT s'il existe).
import { lire, ecrire, rep, memeOrigine, corps, utilisateur, envoyerMail, alerte, masquer, donnerAcces, listeComptes,
  referenceVirement, idCompte, normaliser, ESC, abonne, base, estAdmin, cadreMail, MAIL_P, MAIL_FORT, MAIL_BOITE, MAIL_LISTE, MAIL_VEDETTE } from './comptes.js';
// coordonnees(), PLACES_FONDATEUR et PRIX_FONDATEUR sont définis plus bas (fonctions et constantes du module)

const PAYANTES = { semaine: '1 semaine', mois: '1 mois', trimestre: '3 mois', annee: '1 an' };
// 24/11/2026 (paquet 407, Lucas : 14,99 €/mois ; semaine, mois, trimestre, année) — prix TTC, un seul endroit : le site
// les reçoit de /compte/api/moi, la demande d'abonnement et l'e-mail les reprennent. Semaine, trimestre et année : choisis
// par Claude (≈ −11 % au trimestre, ≈ −28 % à l'année), à confirmer par Lucas.
// 26/11/2026 (paquet 475, Lucas) : grille avant l'ouverture — mois 19,99 € ; fondateurs (100 premiers comptes) 9,99 € à vie
export const TARIFS = Object.freeze({ semaine: 5.99, mois: 19.99, trimestre: 49.99, annee: 169.99 });
const RAPPEL_J = 3;
const jourUtc = (t = Date.now()) => new Date(t).toISOString().slice(0, 10);
const eur = (x) => Number(x).toFixed(2).replace('.', ',') + ' €';
const hex = (u8) => [...u8].map((x) => x.toString(16).padStart(2, '0')).join('');

// --------------------------------------------------------------------------------------------- 1. entonnoir
async function empreinteJour(env, req, jour) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(String(env.CLE_PRIVEE) + '|visites|' + jour),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const ip = req.headers.get('CF-Connecting-IP') || '', ua = req.headers.get('User-Agent') || '';
  return hex(new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(ip + '|' + ua)))).slice(0, 12);
}
export const ROBOT = /bot|crawl|spider|slurp|preview|facebookexternalhit|headless|lighthouse|curl|wget|python/i;
export async function compterVisite(req, env) {
  if (!env.COFFRE || !env.CLE_PRIVEE || ROBOT.test(req.headers.get('User-Agent') || '')) return;
  const jour = jourUtc(), cle = `stats/visites/${jour}.json`, h = await empreinteJour(env, req, jour);
  for (let essai = 0; essai < 3; essai++) {
    const o = await env.COFFRE.get(cle);
    let x = { jour, vues: 0, u: [] };
    try { if (o) x = JSON.parse(await o.text()); } catch (e) { /* repart de zéro */ }
    x.vues = (x.vues || 0) + 1;
    if (Array.isArray(x.u) && !x.u.includes(h) && x.u.length < 50000) x.u.push(h);
    x.uniques = Array.isArray(x.u) ? x.u.length : x.uniques;
    const r = await env.COFFRE.put(cle, JSON.stringify(x), o ? { onlyIf: { etagMatches: o.etag } } : {});
    if (r) return;
  }
}
// Le lendemain : on ne garde que les totaux (les empreintes du jour sont effacées).
export async function compacterVisites(env) {
  const l = await env.COFFRE.list({ prefix: 'stats/visites/' });
  for (const o of l.objects || []) {
    const jour = o.key.slice('stats/visites/'.length, -5);
    if (jour >= jourUtc()) continue;
    const b = await env.COFFRE.get(o.key);
    try {
      const x = JSON.parse(await b.text());
      if (Array.isArray(x.u)) await env.COFFRE.put(o.key, JSON.stringify({ jour, vues: x.vues || 0, uniques: x.u.length }));
    } catch (e) { /* objet illisible : laissé */ }
  }
}
// 25/11/2026 (paquet 434) : ce que le worker reçoit de TennisApi, par jour — direct (live/en_cours.json pour le jour
// en cours, prive/tennisapi_conso.json pour les jours passés) et fiches (live/compteur/<jour>.json : requêtes, octets).
export async function consoTennisApi(env) {
  const lire = async (k) => { try { const o = await env.COFFRE.get(k); return o ? JSON.parse(await o.text()) : null; } catch (e) { return null; } };
  const jours = {};
  const ajout = (jour, cle, req, oct) => { if (!jour) return; const j = jours[jour] || (jours[jour] = { jour, direct_req: 0, direct_octets: 0, fiches_req: 0, fiches_octets: 0 });
    j[cle + '_req'] += req || 0; j[cle + '_octets'] += oct || 0; };
  const h = await lire('prive/tennisapi_conso.json');
  for (const d of (h && h.direct) || []) ajout(d.jour, 'direct', d.requetes, d.octets);
  const enCours = await lire('live/en_cours.json');
  if (enCours && enCours.conso && !(h && (h.direct || []).some(d => d.jour === enCours.conso.jour)))
    ajout(enCours.conso.jour, 'direct', enCours.conso.requetes, enCours.conso.octets);
  try {
    const l = await env.COFFRE.list({ prefix: 'live/compteur/' });
    for (const o of (l.objects || []).slice(-60)) {
      const x = await lire(o.key); const jour = o.key.slice('live/compteur/'.length, -5);
      if (x) ajout(jour, 'fiches', x.n, x.o);
    }
  } catch (e) { /* rien */ }
  return Object.values(jours).sort((a, b) => (a.jour < b.jour ? -1 : 1)).slice(-30);
}
export async function entonnoir(env, maintenant = Date.now()) {
  const comptes = await listeComptes(env);
  const fenetre = (j) => {
    const depuis = jourUtc(maintenant - (j - 1) * 86400e3);
    const dans = (d) => !!d && String(d).slice(0, 10) >= depuis;
    return { depuis, comptes: comptes.filter((c) => dans(c.cree)).length,
      confirmes: comptes.filter((c) => dans(c.cree) && c.verifie).length,
      fondateurs: comptes.filter((c) => dans(c.fondateur)).length };
  };
  const visites = {};
  const l = await env.COFFRE.list({ prefix: 'stats/visites/' });
  for (const o of l.objects || []) {
    const b = await env.COFFRE.get(o.key);
    try { const x = JSON.parse(await b.text()); visites[x.jour] = { vues: x.vues || 0, uniques: x.uniques ?? (x.u || []).length }; } catch (e) { /* ignoré */ }
  }
  const out = {};
  for (const j of [1, 7, 30]) {
    const f = fenetre(j);
    const v = Object.entries(visites).filter(([d]) => d >= f.depuis);
    out[j] = { ...f, visiteurs: v.reduce((a, [, x]) => a + x.uniques, 0), vues: v.reduce((a, [, x]) => a + x.vues, 0) };
  }
  return { fenetres: out, tennisapi: await consoTennisApi(env), total: { comptes: comptes.length, confirmes: comptes.filter((c) => c.verifie).length,
    fondateurs: comptes.filter((c) => c.fondateur).length, plus_payes: comptes.filter((c) => c.abonne && c.paye).length,
    plus_tous: comptes.filter((c) => c.abonne && !c.admin).length },
  jours: Object.entries(visites).sort().slice(-30).map(([jour, x]) => ({ jour, ...x })) };
}

// --------------------------------------------------------------------------------------------- 2. virements et factures
function vendeur(env) {
  try {
    const v = JSON.parse(env.FACTURE_VENDEUR || 'null');
    return v && v.nom && v.adresse && v.siret ? { nom: String(v.nom), adresse: String(v.adresse), siret: String(v.siret),
      mention_tva: String(v.mention_tva || 'TVA non applicable, art. 293 B du CGI') } : null;
  } catch (e) { return null; }
}
async function numeroSuivant(env, annee) {
  const cle = `factures/compteur-${annee}.json`;
  for (let essai = 0; essai < 5; essai++) {
    const o = await env.COFFRE.get(cle);
    let n = 0;
    try { if (o) n = Number(JSON.parse(await o.text()).n) || 0; } catch (e) { n = 0; }
    const r = await env.COFFRE.put(cle, JSON.stringify({ n: n + 1 }), o ? { onlyIf: { etagMatches: o.etag } } : {});
    if (r) return `F${annee}-${String(n + 1).padStart(4, '0')}`;
  }
  return null;
}
export async function trouverCompte(env, q) {
  const e = normaliser(q);
  if (e) return lire(env, await idCompte(e));
  const ref = String(q || '').trim().toUpperCase();
  if (!/^GSA-[0-9A-F]{6}$/.test(ref)) return null;
  const l = await env.COFFRE.list({ prefix: 'comptes/u/' + ref.slice(4).toLowerCase() });
  const o = (l.objects || [])[0];
  return o ? lire(env, o.key.slice('comptes/u/'.length, -5)) : null;
}
export async function virementRecu(env, b, req) {
  const v = vendeur(env);
  // 26/11/2026 (paquet 471, Lucas : « désactive le blocage facture vendeur temporairement pour que je teste ») : TANT QUE
  // le secret FACTURE_VENDEUR est absent, la case « test sans facture » de l'administration ouvre l'accès sans créer de
  // facture ni consommer de numéro. Dès que FACTURE_VENDEUR existe, la case est ignorée : facture obligatoire.
  const sansFacture = !v && b.test_sans_facture === true;
  if (!v && !sansFacture) return { ok: false, erreur: 'vendeur_absent' };
  if (!(b.formule in PAYANTES)) return { ok: false, erreur: 'formule' };
  const montant = Math.round(Number(String(b.montant || '').replace(',', '.')) * 100) / 100;
  if (!(montant > 0 && montant < 10000)) return { ok: false, erreur: 'montant' };
  const u = await trouverCompte(env, b.compte);
  if (!u) return { ok: false, erreur: 'inconnu' };
  if (b.fondateur && fondateurPerdu(u)) return { ok: false, erreur: 'fondateur_perdu' };     // 412
  // 474 : deux validations en moins de 10 minutes pour le même compte = sans doute un double appui : refus, sauf confirmation
  if (u.dernier_virement && Date.now() - Date.parse(u.dernier_virement) < 10 * 60e3 && b.confirmer_doublon !== true)
    return { ok: false, erreur: 'doublon', le: u.dernier_virement };
  // 403 : sans demande d'accès immédiat, refus sauf case « sans renonciation » (le client garde alors ses 14 jours)
  const ri = u.acces_immediat && u.acces_immediat.le ? u.acces_immediat : null;
  if (!ri && b.sans_renonciation !== true) return { ok: false, erreur: 'sans_renonciation' };
  const paye_le = /^\d{4}-\d{2}-\d{2}$/.test(b.date || '') ? b.date : jourUtc();
  if (sansFacture) return virementSansFacture(env, u, b, montant, !!ri, req);
  const num = await numeroSuivant(env, new Date().getUTCFullYear());
  if (!num) return { ok: false, erreur: 'numero' };
  const r = await donnerAcces(env, u.email, b.formule, null, 'virement ' + num);
  if (!r.ok) return r;
  const u2 = await lire(env, u.id);
  const fondateur = !!b.fondateur;
  const f = { numero: num, emise_le: new Date().toISOString(), vendeur: v, client: { email: u2.email, reference: referenceVirement(u2) },
    designation: `Accès Plus Game Set Algo, ${PAYANTES[b.formule]}${fondateur ? ' (tarif fondateur)' : ''}`,
    periode: { du: jourUtc(), au: String(u2.acces.jusqu_au || '').slice(0, 10) }, quantite: 1, prix_unitaire: montant, total: montant,
    paiement: { moyen: 'virement bancaire', le: paye_le },
    retractation: ri ? { renonciation_le: ri.le, version: ri.version } : { delai_jours: 14 } };
  await env.COFFRE.put(`factures/${num}.json`, JSON.stringify(f), { httpMetadata: { contentType: 'application/json' } });
  u2.acces = { ...u2.acces, paye: true, montant, formule_payee: b.formule, fondateur_tarif: fondateur };
  if (u2.demande) {                                                  // 407 : la demande d'abonnement est honorée
    u2.historique = [...(u2.historique || []).slice(-19), { le: new Date().toISOString(), demande: 'payee ' + num }];
    u2.demande = null;
  }
  u2.factures = [...(u2.factures || []), num];
  u2.dernier_virement = new Date().toISOString();
  u2.rappel_fin = null;
  await ecrire(env, u2);
  const lienF = `${base(req, env)}/compte/api/facture?n=${num}`;
  const corps_ = mailAccesOuvert({ jusquau: f.periode.au, formule: b.formule, montant, fondateur, url: env.SITE_URL || base(req, env),
    facture: htmlFacture(f, true) + `<p style="color:#666;font-size:13px;margin:8px 0">Elle reste disponible dans « Mon compte » : ${ESC(lienF)}</p>` });
  const m = await envoyerMail(env, u2.email, { sujet: `Ton accès Plus est ouvert · facture ${num} · Game Set Algo`, html: corps_.html,
    texte: `${corps_.texte}\nFacture ${num} : ${eur(montant)}.\n${lienF}` });
  await alerte(env, `virement reçu ${eur(montant)} (${PAYANTES[b.formule]}) : ${masquer(u2.email)} · facture ${num}`);
  return { ok: true, numero: num, mail: m.ok, jusqu_au: u2.acces.jusqu_au, renonciation: !!ri };
}
// 26/11/2026 (paquet 473, Lucas : « un mail plus joli qui reprend le thème du site ») — e-mail « accès Plus ouvert »
// aux couleurs du site (nuit #0E0A24, panneau #1B1342, balle #D4FF3A, cyan #2EE6FF, rose #FF4FAE). Tableaux et styles en
// ligne : seule mise en page fiable dans les messageries (Gmail, Outlook, Hotmail). Aucune cote, aucune promesse de gain.
export function mailAccesOuvert({ jusquau, formule, montant, fondateur, url, facture }) {
  const site = String(url || 'https://gamesetalgo.com').replace(/\/$/, '');
  const inclus = ['Le % de victoire de tous les matchs, avant le match', 'La note de fiabilité de chaque pronostic',
    'Les sets et les scores probables', 'Les statistiques prévues (aces, 1re balle, breaks…)',
    'Le direct, la simulation rejouable et « Demande à l’algo » en direct'];
  const detail = [formule ? PAYANTES[formule] : null, montant ? eur(montant) : null, fondateur ? 'tarif fondateur' : null].filter(Boolean).join(' · ');
  const html = cadreMail({ surtitre: 'Virement bien reçu', titre: 'Ton accès Plus est ouvert 🎾', site,
    corps: `<p style="margin:0 0 18px;color:#ABA3D6;font-size:15px;line-height:1.5">Merci&nbsp;! Tout l’algo est à toi, sur tous les matchs ATP, WTA et Challenger.</p>`
      + MAIL_VEDETTE('Accès ouvert jusqu’au', ESC(dateFr(jusquau)), detail ? ESC(detail) : '')
      + `<p style="margin:6px 0 8px;color:#F4F1FF;font-size:15px;font-weight:bold">Ce qui est maintenant débloqué</p>` + MAIL_LISTE(inclus.map(ESC)),
    bouton: { lib: 'Voir les matchs du jour', url: site + '/' },
    apres: facture ? `<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#FFFFFF" style="background:#FFFFFF;border-radius:14px;padding:6px 12px">${facture}</td></tr></table>` : '',
    pied: ['Rien ne se renouvelle tout seul : un e-mail te prévient avant la fin de ton accès.'] });
  const texte = [`Ton accès Plus est ouvert jusqu'au ${dateFr(jusquau)}${detail ? ' (' + detail + ')' : ''}.`, 'Merci ! Tout l’algo est à toi, sur tous les matchs ATP, WTA et Challenger.',
    ...inclus.map((t) => '- ' + t), `Voir les matchs du jour : ${site}/`, 'Rien ne se renouvelle tout seul.'].join('\n');
  return { html, texte };
}
// 471 : test sans facture (FACTURE_VENDEUR absent) — accès ouvert, aucune facture, aucun numéro, marqué sur le compte
async function virementSansFacture(env, u, b, montant, renonciation, req) {
  const r = await donnerAcces(env, u.email, b.formule, null, 'virement (test sans facture)');
  if (!r.ok) return r;
  const u2 = await lire(env, u.id);
  const fondateur = !!b.fondateur;
  u2.acces = { ...u2.acces, paye: true, montant, formule_payee: b.formule, fondateur_tarif: fondateur, sans_facture: true };
  u2.dernier_virement = new Date().toISOString();
  if (u2.demande) {
    u2.historique = [...(u2.historique || []).slice(-19), { le: new Date().toISOString(), demande: 'payee (test sans facture)' }];
    u2.demande = null;
  }
  u2.rappel_fin = null;
  await ecrire(env, u2);
  const au = String(u2.acces.jusqu_au || '').slice(0, 10);
  const corps_ = mailAccesOuvert({ jusquau: au, formule: b.formule, montant, fondateur, url: env.SITE_URL || base(req, env) });
  const m = await envoyerMail(env, u2.email, { sujet: 'Ton accès Plus est ouvert · Game Set Algo', html: corps_.html, texte: corps_.texte });
  await alerte(env, `virement reçu ${eur(montant)} (${PAYANTES[b.formule]}) : ${masquer(u2.email)} · SANS FACTURE (test, FACTURE_VENDEUR absent)`);
  return { ok: true, numero: null, sans_facture: true, mail: m.ok, jusqu_au: u2.acces.jusqu_au, renonciation };
}
const dateFr = (d) => String(d || '').slice(0, 10).split('-').reverse().join('/');
// 403 : la facture dit ce qu'il en est du droit de rétractation (anciennes factures : rien)
export function ligneRetractation(f) {
  const r = f.retractation;
  if (!r) return '';
  const t = r.renonciation_le
    ? `Accès immédiat demandé par le client le ${dateFr(r.renonciation_le)}, avec renonciation au droit de rétractation (Code de la consommation, art. L221-28).`
    : `Droit de rétractation : ${r.delai_jours || 14} jours à compter du paiement.`;
  return `<p style="margin:6px 0 0;color:#555;font-size:13px">${ESC(t)}</p>`;
}
export function htmlFacture(f, mail = false) {
  const v = f.vendeur, l = (t) => ESC(t).replace(/\n/g, '<br>');
  const td = 'style="padding:8px;border-bottom:1px solid #ddd"';
  return `<div style="font-family:Arial,sans-serif;color:#14102e;${mail ? '' : 'max-width:720px;margin:24px auto;padding:24px'}">
<h2 style="margin:0 0 4px">Facture ${ESC(f.numero)}</h2><p style="margin:0;color:#555">Émise le ${ESC(dateFr(f.emise_le))}</p>
<table style="width:100%;margin:18px 0;border-collapse:collapse"><tr><td style="vertical-align:top;width:50%"><b>Vendeur</b><br>${l(v.nom)}<br>${l(v.adresse)}<br>SIRET ${ESC(v.siret)}</td>
<td style="vertical-align:top"><b>Client</b><br>${ESC(f.client.email)}<br><span style="color:#555">Réf. ${ESC(f.client.reference)}</span></td></tr></table>
<table style="width:100%;border-collapse:collapse"><tr style="background:#f1eefc"><th ${td} align="left">Désignation</th><th ${td}>Qté</th><th ${td} align="right">Prix unitaire</th><th ${td} align="right">Total</th></tr>
<tr><td ${td}>${ESC(f.designation)}<br><small style="color:#555">du ${ESC(dateFr(f.periode.du))} au ${ESC(dateFr(f.periode.au))}</small></td><td ${td} align="center">${f.quantite}</td><td ${td} align="right">${eur(f.prix_unitaire)}</td><td ${td} align="right">${eur(f.total)}</td></tr>
<tr><td colspan="3" ${td} align="right"><b>Total à payer</b></td><td ${td} align="right"><b>${eur(f.total)}</b></td></tr></table>
<p style="margin:14px 0 0">${ESC(v.mention_tva)}</p><p style="margin:6px 0 0">Payée par ${ESC(f.paiement.moyen)} le ${ESC(dateFr(f.paiement.le))}.</p>${ligneRetractation(f)}</div>`;
}
async function lireFacture(env, n) {
  if (!/^F\d{4}-\d{4,6}$/.test(String(n || ''))) return null;
  const o = await env.COFFRE.get(`factures/${n}.json`);
  try { return o ? JSON.parse(await o.text()) : null; } catch (e) { return null; }
}
export function pageFacture(f) {
  return new Response(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Facture ${ESC(f.numero)}</title><style>@media print{button{display:none}}body{background:#fff;margin:0}</style></head><body>
${htmlFacture(f)}<p style="text-align:center"><button onclick="print()" style="font:16px Arial;padding:10px 16px">Imprimer / enregistrer en PDF</button></p></body></html>`,
  { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex',
    'X-Frame-Options': 'DENY', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'" } });
}
// Le client voit ses factures (cookie) ; l'administration voit toutes.
export async function factureClient(req, env, url) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  const n = url.searchParams.get('n');
  if (!(u.factures || []).includes(n)) return rep({ ok: false, erreur: 'inconnu' }, 404);
  const f = await lireFacture(env, n);
  return f ? pageFacture(f) : rep({ ok: false, erreur: 'inconnu' }, 404);
}
export async function listeFactures(env) {
  const out = [];
  const l = await env.COFFRE.list({ prefix: 'factures/F' });
  for (const o of l.objects || []) {
    const f = await lireFacture(env, o.key.slice('factures/'.length, -5));
    if (f) out.push({ numero: f.numero, emise_le: f.emise_le, email: f.client.email, total: f.total, designation: f.designation });
  }
  return out.sort((a, b) => b.numero.localeCompare(a.numero));
}
export async function adminVentes(req, env, url) {
  const p = url.pathname;
  if (p === '/compte/admin/api/entonnoir' && req.method === 'GET') return rep({ ok: true, ...(await entonnoir(env)) });
  if (p === '/compte/admin/api/factures' && req.method === 'GET') return rep({ ok: true, vendeur: !!vendeur(env), factures: await listeFactures(env) });
  if (p === '/compte/admin/facture' && req.method === 'GET') {
    const f = await lireFacture(env, url.searchParams.get('n'));
    return f ? pageFacture(f) : rep({ ok: false, erreur: 'inconnu' }, 404);
  }
  if (p === '/compte/admin/api/ouverture' && req.method === 'POST') {
    if (!memeOrigine(req)) return rep({ ok: false, erreur: 'origine' }, 403);
    const b = await corps(req);
    if (!b) return rep({ ok: false, erreur: 'requete' }, 400);
    const r = await ouverture(env, b, req);
    return rep(r, r.ok ? 200 : 400);
  }
  if (p === '/compte/admin/api/virement' && req.method === 'POST') {
    if (!memeOrigine(req)) return rep({ ok: false, erreur: 'origine' }, 403);
    const b = await corps(req);
    if (!b) return rep({ ok: false, erreur: 'requete' }, 400);
    const r = await virementRecu(env, b, req);
    return rep(r, r.ok ? 200 : 400);
  }
  return null;
}

// --------------------------------------------------------------------------------------------- 3. rappels de fin d'accès
function coordonnees(env) {
  try { const v = JSON.parse(env.VIREMENT || 'null'); return v && v.iban ? v : null; } catch (e) { return null; }
}
export function messageRappel(u, env, url) {
  const fin = dateFr(u.acces.jusqu_au), ref = referenceVirement(u), c = coordonnees(env);
  const banque = c ? `Pour le prolonger, fais un virement${u.acces.montant ? ' de ' + eur(u.acces.montant) : ''} à :\nTitulaire : ${c.titulaire || ''}\nIBAN : ${c.iban}${c.bic ? '\nBIC : ' + c.bic : ''}\nLibellé (important) : ${ref}`
    : `Pour le prolonger, réponds à ce message ou écris-nous : ta référence de virement est ${ref}.`;
  // 412 : un fondateur sait jusqu'à quand il garde son tarif
  const ft = finTarifFondateur(u);
  const garde = ft ? `\nPour garder ton tarif fondateur, paie au plus tard le ${dateFr(ft)}.` : '';
  const lignes = banque.split('\n');
  return { sujet: `Ton accès Plus se termine le ${fin}`,
    html: cadreMail({ surtitre: 'Bientôt la fin', titre: `Ton accès Plus se termine le ${fin}`, site: url,
      corps: MAIL_P("Merci d'avoir soutenu Game Set Algo. Le virement ne se renouvelle pas tout seul.")
        + (c ? MAIL_P(ESC(lignes[0])) + MAIL_BOITE(lignes.slice(1).map(ESC)) : MAIL_P(ESC(lignes.join(' '))))
        + (garde ? MAIL_FORT(ESC(garde.trim())) : '') + MAIL_P("L'accès est prolongé dès réception (un virement instantané arrive en quelques secondes)."),
      bouton: { lib: 'Ouvrir mon compte', url: url.replace(/\/$/, '') + '/#plus' } }),
    texte: `Ton accès Plus se termine le ${fin}.\n${banque}${garde}\n\n${url}` };
}
export async function rappels(env, maintenant = Date.now()) {
  let n = 0, curseur;
  do {
    const l = await env.COFFRE.list({ prefix: 'comptes/u/', cursor: curseur, limit: 1000 });
    for (const o of l.objects || []) {
      const u = await lire(env, o.key.slice('comptes/u/'.length, -5));
      const a = (u && u.acces) || {};
      if (!a.paye || !a.jusqu_au || u.rappel_fin === a.jusqu_au || !abonne(u, maintenant)) continue;
      if (Date.parse(a.jusqu_au) - maintenant > RAPPEL_J * 86400e3) continue;
      const m = await envoyerMail(env, u.email, messageRappel(u, env, String(env.SITE_URL || 'https://gamesetalgo.com')));
      if (m.ok) { u.rappel_fin = a.jusqu_au; await ecrire(env, u); n++; }
    }
    curseur = l.truncated ? l.cursor : undefined;
  } while (curseur);
  if (n) await alerte(env, `${n} rappel(s) de fin d'accès envoyé(s)`);
  return n;
}
// --------------------------------------------------------------------------------------------- 4. ouverture fondateurs
// 24/11/2026 (paquet 405, Lucas : « fais 1-2-3 ») : depuis /compte/admin, l'e-mail d'ouverture part aux 100 premières
// places de la liste d'attente (comptes confirmés, ordre de réservation), par lots (limites du worker et quota Brevo).
// Chaque e-mail est personnel : n° de place, prix fondateur, référence de virement, coordonnées bancaires (secret
// VIREMENT), lien vers la section Plus pour demander l'accès immédiat, lien vers les conditions de vente. Un compte
// déjà prévenu ne l'est pas deux fois. Refus sans vendeur (FACTURE_VENDEUR) ou sans coordonnées (VIREMENT).
export const PLACES_FONDATEUR = 100, PRIX_FONDATEUR = 9.99, LOT_OUVERTURE = 25, DELAI_FONDATEUR_J = 7;
export async function fondateursOrdonnes(env) {
  const L = [];
  let curseur;
  do {
    const l = await env.COFFRE.list({ prefix: 'comptes/u/', cursor: curseur, limit: 1000 });
    for (const o of l.objects || []) {
      const u = await lire(env, o.key.slice('comptes/u/'.length, -5));
      // 474 (Lucas : « les 100 premiers sont automatiquement fondateurs ») : tous les comptes confirmés, sauf admin,
      // dans l'ordre de création ; plus de réservation à faire
      if (u && u.verifie && !estAdmin(u)) L.push(u);
    }
    curseur = l.truncated ? l.cursor : undefined;
  } while (curseur);
  const cle = (u) => (u.fondateur_place ? '0' + String(u.fondateur_place).padStart(4, '0') : '1') + String(u.cree || '');
  return L.sort((a, b) => cle(a).localeCompare(cle(b)) || String(a.id).localeCompare(String(b.id)));
}
// 474 : place fondateur attribuée une fois pour toutes (confirmation de l'adresse, ou première visite d'un compte
// confirmé avant) ; une place déjà donnée ne change jamais. Retourne vrai si le compte a changé (à écrire).
export async function attribuerFondateur(env, u) {
  if (!u || !u.verifie || estAdmin(u) || u.fondateur_place || u.fondateur_calcule) return false;
  const L = await fondateursOrdonnes(env);
  const pris = new Set(L.filter((x) => x.fondateur_place).map((x) => x.fondateur_place));
  const sansPlace = L.filter((x) => !x.fondateur_place);
  const i = sansPlace.findIndex((x) => x.id === u.id);
  const maintenant = new Date().toISOString();
  u.fondateur_calcule = maintenant;
  if (i >= 0 && pris.size + i < PLACES_FONDATEUR) {
    let n = 0, k = -1;
    while (k < i) { n++; if (!pris.has(n)) k++; }         // i-ème numéro libre
    u.fondateur_place = n;
    u.fondateur = u.fondateur || { le: maintenant, auto: true };
    u.historique = [...(u.historique || []).slice(-19), { le: maintenant, fondateur: 'place ' + n + ' (automatique)' }];
  }
  return true;
}
export function mailOuverture(u, place, c, url) {
  const fr = u.lang !== 'en', ref = referenceVirement(u), prix = eur(PRIX_FONDATEUR);
  const prixEn = '€' + PRIX_FONDATEUR.toFixed(2);
  const banque = fr ? [`Titulaire : ${c.titulaire || ''}`, `IBAN : ${c.iban}`, ...(c.bic ? [`BIC : ${c.bic}`] : []), `Montant : ${prix}`, `Libellé (important) : ${ref}`]
    : [`Account holder: ${c.titulaire || ''}`, `IBAN: ${c.iban}`, ...(c.bic ? [`BIC: ${c.bic}`] : []), `Amount: ${prixEn}`, `Reference (important): ${ref}`];
  const T = fr ? {
    sujet: `L'accès Plus est ouvert : ta place fondateur n° ${place}`,
    intro: `L'accès Plus de Game Set Algo est ouvert, et ton compte fait partie des ${PLACES_FONDATEUR} premiers : tu es fondateur (place n° ${place}).`,
    prix: `Ton tarif : ${prix} par mois, à vie, tant que tu renouvelles chaque mois au plus tard ${DELAI_FONDATEUR_J} jours après la fin du précédent. Rien ne se renouvelle tout seul.`,
    e1: "1. Dans la section Plus du site (connecté à ton compte), coche les deux cases « accès immédiat » : ton accès s'ouvrira dès réception du virement.",
    e2: '2. Fais un virement :', e3: "Ton accès s'ouvre dès réception (un virement instantané arrive en quelques secondes) et la facture part par e-mail.",
    bouton: 'Ouvrir la section Plus', cgv: 'Conditions de vente', fin: "Les pronostics restent des probabilités, sans conseil de pari." }
    : {
      sujet: `Plus access is open: your founder spot no. ${place}`,
      intro: `Game Set Algo Plus access is open, and your account is one of the first ${PLACES_FONDATEUR}: you are a founder (spot no. ${place}).`,
      prix: `Your price: ${prixEn} a month, for life, as long as you renew each month no later than ${DELAI_FONDATEUR_J} days after the previous one ends. Nothing renews by itself.`,
      e1: '1. In the Plus section of the site (logged in), tick the two "immediate access" boxes: your access will open as soon as the transfer arrives.',
      e2: '2. Make a bank transfer:', e3: 'Access opens on receipt (an instant transfer arrives within seconds) and the invoice is emailed to you.',
      bouton: 'Open the Plus section', cgv: 'Terms of sale', fin: 'Forecasts remain probabilities, never betting advice.' };
  const lienPlus = url.replace(/\/$/, '') + '/#plus', lienCgv = url.replace(/\/$/, '') + '/#cgv';
  const html = cadreMail({ lang: fr ? 'fr' : 'en', surtitre: fr ? `Fondateur n° ${place}` : `Founder no. ${place}`, titre: T.sujet, site: url,
    corps: MAIL_P(ESC(T.intro)) + MAIL_VEDETTE(fr ? 'Ton tarif fondateur' : 'Your founder price', ESC(fr ? `${prix} / mois` : `${prixEn} / month`), ESC(T.prix))
      + MAIL_P(ESC(T.e1)) + MAIL_P(ESC(T.e2)) + MAIL_BOITE(banque.map(ESC)) + MAIL_P(ESC(T.e3)),
    bouton: { lib: T.bouton, url: lienPlus }, pied: [ESC(T.fin)] });
  void lienCgv;
  return { sujet: T.sujet, html, texte: [T.intro, T.prix, T.e1, lienPlus, T.e2, ...banque, T.e3, `${T.cgv} : ${lienCgv}`].join('\n') };
}
export async function ouverture(env, b, req) {
  if (!vendeur(env)) return { ok: false, erreur: 'vendeur_absent' };
  const c = coordonnees(env);
  if (!c) return { ok: false, erreur: 'coordonnees_absentes' };
  const L = (await fondateursOrdonnes(env)).slice(0, PLACES_FONDATEUR);
  const url = String(env.SITE_URL || 'https://gamesetalgo.com');      // les liens de l'e-mail vont toujours au site
  if (b.mode === 'apercu') {
    if (!L.length) return { ok: false, erreur: 'aucun_fondateur' };
    const m = mailOuverture(L[0], 1, c, url);
    return { ok: true, sujet: m.sujet, html: m.html, places: L.length, deja: L.filter((u) => u.ouverture_envoyee).length };
  }
  if (b.mode !== 'envoyer') return { ok: false, erreur: 'requete' };
  let envoyes = 0, arret = null;
  for (let i = 0; i < L.length && envoyes < LOT_OUVERTURE; i++) {
    const u = L[i];
    if (u.ouverture_envoyee) continue;
    const m = await envoyerMail(env, u.email, mailOuverture(u, u.fondateur_place || i + 1, c, url));
    if (!m.ok) { arret = m.raison; break; }
    u.fondateur_place = u.fondateur_place || i + 1;      // 474 : une place déjà attribuée ne change jamais
    u.ouverture_envoyee = new Date().toISOString();
    u.historique = [...(u.historique || []).slice(-19), { le: u.ouverture_envoyee, fondateur: 'ouverture ' + (i + 1) }];
    await ecrire(env, u);
    envoyes++;
  }
  const restants = L.filter((u) => !u.ouverture_envoyee).length;
  if (envoyes) await alerte(env, `ouverture fondateurs : ${envoyes} e-mail(s) envoyé(s), ${restants} restant(s)`);
  return { ok: true, envoyes, restants, places: L.length, arret };
}

// --------------------------------------------------------------------------------------------- 5. demande d'abonnement
// 24/11/2026 (paquet 407, Lucas : « si on se connecte sur le site, que quelqu'un puisse faire une demande d'abonnement »).
// Un compte confirmé choisit sa formule dans la section Plus. Le montant est fixé ICI (jamais celui envoyé par le
// navigateur) : TARIFS, ou 9,99 € au mois pour une place fondateur parmi les 100 premières (rang calculé à la demande).
// La demande est gardée sur le compte, l'e-mail part au client (formule, montant, référence, coordonnées si le secret
// VIREMENT existe, sinon « coordonnées envoyées par e-mail »), une alerte Telegram part à Lucas ; l'administration la
// montre et préremplit « Virement reçu ». Le client peut l'annuler ou en changer tant qu'elle n'est pas payée.
export function montantDemande(formule, place) {
  if (!(formule in TARIFS)) return null;
  return formule === 'mois' && place && place <= PLACES_FONDATEUR ? PRIX_FONDATEUR : TARIFS[formule];
}
export function mailDemande(u, d, c, url) {
  const fr = u.lang !== 'en', ref = referenceVirement(u);
  const lib = fr ? { semaine: '1 semaine', mois: '1 mois', trimestre: '3 mois', annee: '1 an' } : { semaine: '1 week', mois: '1 month', trimestre: '3 months', annee: '1 year' };
  const m = fr ? eur(d.montant) : '€' + d.montant.toFixed(2);
  const banque = c ? (fr ? [`Titulaire : ${c.titulaire || ''}`, `IBAN : ${c.iban}`, ...(c.bic ? [`BIC : ${c.bic}`] : []), `Montant : ${m}`, `Libellé (important) : ${ref}`]
    : [`Account holder: ${c.titulaire || ''}`, `IBAN: ${c.iban}`, ...(c.bic ? [`BIC: ${c.bic}`] : []), `Amount: ${m}`, `Reference (important): ${ref}`]) : null;
  const T = fr ? { sujet: `Ta demande d'abonnement : ${lib[d.formule]}, ${m}`,
    intro: `Merci ! Ta demande d'accès Plus est bien enregistrée : ${lib[d.formule]}, ${m}${d.fondateur ? ' (tarif fondateur)' : ''}.`,
    pay: banque ? 'Pour la finaliser, fais un virement :' : `Les coordonnées du virement t'arrivent par e-mail très vite. Ta référence : ${ref}.`,
    ri: "Pour que l'accès s'ouvre dès réception du virement, coche les deux cases « accès immédiat » dans la section Plus.",
    fin: "Rien ne se renouvelle tout seul. Tu peux annuler ta demande dans la section Plus tant qu'elle n'est pas payée.", cgv: 'Conditions de vente' }
    : { sujet: `Your subscription request: ${lib[d.formule]}, ${m}`,
      intro: `Thank you! Your Plus access request is saved: ${lib[d.formule]}, ${m}${d.fondateur ? ' (founder price)' : ''}.`,
      pay: banque ? 'To complete it, make a bank transfer:' : `Transfer details will reach you by email very soon. Your reference: ${ref}.`,
      ri: 'For access to open as soon as the transfer arrives, tick the two "immediate access" boxes in the Plus section.',
      fin: 'Nothing renews by itself. You can cancel your request in the Plus section until it is paid.', cgv: 'Terms of sale' };
  const lienCgv = url.replace(/\/$/, '') + '/#cgv';
  const html = cadreMail({ lang: fr ? 'fr' : 'en', surtitre: fr ? "Demande d'abonnement" : 'Subscription request', titre: T.sujet, site: url,
    corps: MAIL_P(ESC(T.intro)) + MAIL_P(ESC(T.pay)) + (banque ? MAIL_BOITE(banque.map(ESC)) : '') + (d.acces_immediat ? '' : MAIL_FORT(ESC(T.ri))),
    bouton: { lib: fr ? 'Ouvrir la section Plus' : 'Open the Plus section', url: url.replace(/\/$/, '') + '/#plus' }, pied: [ESC(T.fin)] });
  void lienCgv;
  return { sujet: T.sujet, html, texte: [T.intro, T.pay, ...(banque || []), d.acces_immediat ? '' : T.ri, T.fin, `${T.cgv} : ${lienCgv}`].filter(Boolean).join('\n') };
}
// 24/11/2026 (paquet 412, Lucas) — conditions de vente, art. 3 : le tarif fondateur est garanti tant que chaque nouveau
// mois est payé au plus tard DELAI_FONDATEUR_J jours après la fin du précédent. Un accès payé au tarif fondateur, fini
// depuis plus longtemps, le fait perdre pour de bon (u.fondateur_perdu, gardé sur le compte). Le premier paiement d'une
// place fondateur n'a pas de délai (aucun accès payé avant).
export function fondateurPerdu(u, maintenant = Date.now()) {
  if (!u) return false;
  if (u.fondateur_perdu) return true;
  const a = u.acces || {};
  if (!a.paye || !a.fondateur_tarif || !a.jusqu_au) return false;
  return Date.parse(a.jusqu_au) + DELAI_FONDATEUR_J * 86400e3 < maintenant;
}
export const finTarifFondateur = (u) => {
  const a = (u && u.acces) || {};
  return a.paye && a.fondateur_tarif && a.jusqu_au ? new Date(Date.parse(a.jusqu_au) + DELAI_FONDATEUR_J * 86400e3).toISOString() : null;
};
async function rangFondateur(env, u) {
  if (u.fondateur_place) return u.fondateur_place;
  await attribuerFondateur(env, u);          // 474 : automatique ; le compte est écrit par l'appelant
  return u.fondateur_place || null;
}
export async function demandeAbonnement(req, env, b) {
  const u = await utilisateur(req, env);
  if (!u) return rep({ ok: false, erreur: 'connexion' }, 401);
  if (!u.verifie) return rep({ ok: false, erreur: 'non_verifie' }, 403);
  const maintenant = new Date().toISOString();
  if (b.annuler === true) {
    if (u.demande) {
      u.historique = [...(u.historique || []).slice(-19), { le: maintenant, demande: 'annulee' }];
      u.demande = null;
      await ecrire(env, u);
      await alerte(env, `demande d'abonnement annulée : ${masquer(u.email)}`);
    }
    return rep({ ok: true });
  }
  if (!(b.formule in TARIFS)) return rep({ ok: false, erreur: 'formule' }, 400);
  const perdu = fondateurPerdu(u);
  if (perdu && !u.fondateur_perdu) {
    u.fondateur_perdu = maintenant;
    u.historique = [...(u.historique || []).slice(-19), { le: maintenant, fondateur: 'tarif perdu (renouvellement en retard)' }];
  }
  const place = perdu ? null : await rangFondateur(env, u);
  const montant = montantDemande(b.formule, place);
  const fondateur = montant === PRIX_FONDATEUR && b.formule === 'mois';
  if (u.demande && u.demande.formule === b.formule && u.demande.montant === montant) return rep({ ok: true, deja: true });
  if (fondateur && !u.fondateur_place) u.fondateur_place = place;
  u.demande = { le: maintenant, formule: b.formule, montant, fondateur };
  u.historique = [...(u.historique || []).slice(-19), { le: maintenant, demande: `${b.formule} ${montant}` }];
  await ecrire(env, u);
  const url = String(env.SITE_URL || 'https://gamesetalgo.com');
  let mail = { ok: false };
  try { mail = await envoyerMail(env, u.email, mailDemande(u, { ...u.demande, acces_immediat: !!u.acces_immediat }, coordonnees(env), url)); } catch (e) { /* la demande reste notée */ }
  await alerte(env, `demande d'abonnement : ${PAYANTES[b.formule]}, ${eur(montant)}${fondateur ? ' (fondateur n° ' + place + ')' : ''} · réf. ${referenceVirement(u)} · ${masquer(u.email)}${u.acces_immediat ? '' : ' · accès immédiat pas encore coché'}`);
  return rep({ ok: true, mail: !!mail.ok });
}

export async function quotidien(env) {
  if (!env.COFFRE) return;
  try { await compacterVisites(env); } catch (e) { /* le lendemain */ }
  try { await rappels(env); } catch (e) { /* le lendemain */ }
  try { await sauvegarderComptes(env); } catch (e) { /* le lendemain */ }
}

// 25/11/2026 (paquet 435, avant l'ouverture du site) — SAUVEGARDE QUOTIDIENNE des comptes, des codes et des factures :
// chaque jour (7 h 17 UTC), copie de comptes/u/, comptes/codes/ et factures/ sous sauvegardes/comptes/<jour>/ ; les
// 14 derniers jours sont gardés. Protège d'un effacement ou d'une écriture ratée (bug, fausse manœuvre) ; le même
// coffre R2, donc pas d'une suppression du coffre entier. Restaurer : recopier les fichiers d'un jour à leur place.
export const PREFIXES_SAUVES = ['comptes/u/', 'comptes/codes/', 'factures/'];
export const JOURS_SAUVES = 14;
async function lister(env, prefix) {
  const cles = []; let cursor;
  do {
    const l = await env.COFFRE.list({ prefix, cursor });
    for (const o of l.objects || []) cles.push(o.key);
    cursor = l.truncated ? l.cursor : undefined;
  } while (cursor);
  return cles;
}
export async function sauvegarderComptes(env, jour = jourUtc()) {
  let n = 0;
  for (const p of PREFIXES_SAUVES) {
    for (const k of await lister(env, p)) {
      const o = await env.COFFRE.get(k);
      if (!o) continue;
      await env.COFFRE.put(`sauvegardes/comptes/${jour}/${k}`, await o.text());
      n++;
    }
  }
  const jours = [...new Set((await lister(env, 'sauvegardes/comptes/')).map(k => k.split('/')[2]))].sort();
  const vieux = new Set(jours.slice(0, Math.max(0, jours.length - JOURS_SAUVES)));
  if (vieux.size) for (const k of await lister(env, 'sauvegardes/comptes/')) if (vieux.has(k.split('/')[2])) await env.COFFRE.delete(k);
  return n;
}
