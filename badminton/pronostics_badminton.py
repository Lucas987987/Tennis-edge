#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_badminton.py — PRONOSTICS DU BADMINTON (27/11/2026, paquet 520, Lucas : « oui » à la page du badminton
après l'étape 4 et la sonde des matchs à venir).

Ce que l'algo annonce, et d'où cela vient (rien d'autre n'entre) :
  • le % de victoire, seul : l'Elo retenu par les études (étapes 3 et 4, badminton/etude_etape*_badminton.py ;
    jugement 2023 → 26/11/2026 : 71,2 % de bons vainqueurs, log loss 0,548, pente 1,09) — a = 400, c = 0,3, la cible
    est la part des points gagnés (w = 1, s = 32), et en double chaque JOUEUR a sa note (la paire = la moyenne des deux) ;
    rejoué sur tout l'historique collecté (historique/badminton/), puis sur les matchs du jour déjà terminés ;
  • le score en manches (paquet 527, Lucas : « fais le » après l'étude du score, etude_score_badminton.py : S1 retenu,
    part des matchs en 3 manches annoncée 29,7 % pour 30,4 % réels sur 2023 → 2026) : manches indépendantes ancrées
    sur le %, la part des matchs en 3 manches recalée par épreuve et tranche de 5 points du favori sur tout
    l'historique (rétrécie vers le modèle sans recalage, poids 50 matchs). Le % ne dépend jamais du score.
Aucune cote n'est lue, nulle part.

La sonde du 27/11 (paquet 518) : les matchs apparaissent 3 à 24 h avant, avec les deux camps connus, quand le tour
précédent est fini. Chaque passage lit donc le jour de Paris et le lendemain (2 requêtes ; + 1 tant que la collecte de la
veille n'est pas faite). Les heures annoncées sont celles du programme : un match « à venir » après son heure prévue
est fréquent (les matchs s'enchaînent sur un court). Le pronostic n'est plus modifié une fois l'heure prévue passée :
c'est celui-là qui est jugé. Abandon, forfait, annulation : ni bilan ni verdict.

Accès « comme le tennis et le tennis de table » : bad.json, complet, pour les abonnés Plus ; bad_libre.json pour les
autres : un match offert par jour (le plus fort du jour de Paris, somme des Elo : choix neutre), les autres matchs à
venir réduits à l'affiche, le % seul une fois le match commencé, les résultats et le bilan publics. Le worker choisit
le fichier selon le compte.

CONFIDENTIALITÉ : les pronostics à venir ne vont JAMAIS dans le dépôt public. L'état vit au coffre R2 privé
(prive/badminton/), les deux fichiers du site sont envoyés directement à R2 (site/algo/). Le journal du run n'affiche
que des comptes, jamais un nom.
Usage : python badminton/pronostics_badminton.py [racine]
"""
import datetime as dt
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import elo_badminton as EB  # noqa: E402

PAQUET = 520
SPORT = 'badminton'
LIGUE = 'International'
CATEGORIE_DEFAUT = 259
REGLAGE = (400, 0.3, 1.0, 32)        # a, c, w, s — étapes 3 et 4 (jugé une seule fois)
DEPART = 1500.0
CLE_ETAT = 'prive/badminton/etat_pronostics.json'
CLE_ARCHIVE = 'prive/badminton/archive/{mois}.jsonl'
CLE_SITE = 'site/algo/bad.json'
CLE_LIBRE = 'site/algo/bad_libre.json'
GARDE_H = 36
PAGE_PASSES_H = 24
TRANCHES = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01))
A_VENIR, EN_COURS, TERMINE, ANNULE = 'a_venir', 'en_cours', 'termine', 'annule'
STATUTS = {'notstarted': A_VENIR, 'inprogress': EN_COURS, 'interrupted': EN_COURS, 'willcontinue': EN_COURS,
           'finished': TERMINE}
AFFICHE = ('id', 't', 'tournoi', 'tour', 'epreuve', 'h', 'a', 'statut', 'manches')
PRONOSTIC = ('p_h', 'n_h', 'n_a', 'maj', 'g', 'bon', 'scores', 'decisive', 'score_trouve', 'decisive_reelle')
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo('Europe/Paris')
except Exception:  # noqa: BLE001
    PARIS = dt.timezone(dt.timedelta(hours=1))


def jour_paris(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(PARIS).date().isoformat()


def _lire(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ l'Elo (doubles au joueur), avec son état final
def camps(m):
    """(entités du camp h, entités du camp a) : le joueur en simple, les deux joueurs en double."""
    noms = m[9] if len(m) > 9 else None
    if noms:
        return [('d', x) for x in noms[0]], [('d', x) for x in noms[1]]
    return [m[3]], [m[4]]


class Modele:
    def __init__(self, M, reglage=REGLAGE):
        self.a, self.c, self.w, self.s = reglage
        self.R, self.N = {}, {}
        self.matchs = 0
        self.P = []                                   # 527 : le % d'avant match de chaque match rejoué (table des scores)
        self.ajouter(M)

    def note(self, cs):
        return sum(self.R.get(x, DEPART) for x in cs) / len(cs)

    def experience(self, cs):
        return min(self.N.get(x, 0) for x in cs)

    def ajouter(self, M):
        import math
        for m in M:
            ch, cb = camps(m)
            rh, rb = self.note(ch), self.note(cb)
            p = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
            self.P.append(p)
            y, sp = m[5], m[6]
            cible = (1 - self.w) * y + self.w * (1.0 / (1.0 + math.exp(-(sp - 0.5) * self.s))) if self.w else y
            d = cible - p
            for x, sg in [(x, 1) for x in ch] + [(x, -1) for x in cb]:
                n = self.N.get(x, 0)
                self.R[x] = self.R.get(x, DEPART) + sg * self.a / (n + 5) ** self.c * d
                self.N[x] = n + 1
            self.matchs += 1

    def predire(self, ch, cb):
        rh, rb = self.note(ch), self.note(cb)
        return {'p_h': round(1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0)), 4), 'n_h': self.experience(ch),
                'n_a': self.experience(cb), 'elo_somme': round(rh + rb, 1)}


# ------------------------------------------------------------------ 527 : le score en manches (étude du score, S1)
def table_scores(H, P):
    """La table S1 apprise sur tout l'historique (sans la série hors circuits) : {(épreuve, tranche): [n, en 3, S0]}."""
    import etude_score_badminton as SC
    idx = [i for i, m in enumerate(H) if len(m) > 10 and not m[7]]
    return SC.apprendre(H, P, idx)


def scores_de(p, epreuve, T):
    """[[manches h, manches a, probabilité]] du plus probable au moins probable, et la chance d'une 3e manche."""
    import etude_score_badminton as SC
    d = SC.s1(p, epreuve, T) if T else SC.s0(p)
    L = sorted([[2, 0, d['h20']], [2, 1, d['h21']], [1, 2, d['a21']], [0, 2, d['a20']]], key=lambda x: -x[2])
    return [[a, b, round(q, 4)] for a, b, q in L], round(d['h21'] + d['a21'], 4)


# ------------------------------------------------------------------ lecture des matchs (même format que l'historique)
def epreuves_connues(M):
    """{entité: épreuve} lue dans l'historique (pour les matchs dont le nom du tournoi ne dit pas le sexe)."""
    E = {}
    for m in M:
        E[m[3]] = m[2]
        E[m[4]] = m[2]
    return E


def comme_termine(r):
    """La ligne lue comme un match régulier (pour les camps et l'épreuve seulement, jamais pour l'Elo)."""
    x = dict(r, statut='finished', g=1, manches=[[21, 10], [21, 10]])
    x.pop('detail', None)
    return x


def epreuve_de(r, connues):
    m, _ = EB.ligne_lue(comme_termine(r))
    if m is None:
        return None
    if m['sexe']:
        return EB._nom_epreuve(m['double'], m['sexe'])
    for k in (m['h'], m['a']):
        if k in connues and connues[k].startswith('double') == m['double']:
            return connues[k]
    return EB._nom_epreuve(m['double'], 'M')


def tuple_de(r, epreuve):
    """Une ligne terminée → le tuple de l'historique (pour l'Elo), ou None si elle n'est pas gardée."""
    m, _ = EB.ligne_lue(r, jour_paris(r['t']))
    if m is None:
        return None
    return (m['t'], m['jour'], epreuve, m['h'], m['a'], m['y'], m['part'], m['hors'], 'jour', m['noms'])


def ligne_api(e):
    import collecte_tennis_de_table as CT
    return CT.ligne(e, LIGUE)


def matchs_des_jours(c, jours, categorie):
    """[ligne] des jours demandés ; None si une réponse manque."""
    out, vus = [], set()
    for d in jours:
        code, doc = c.get(f'/api/{SPORT}/category/{categorie}/events/{d.day}/{d.month}/{d.year}')
        if code not in (200, 204):
            return None
        for e in (doc or {}).get('events') or []:
            if e.get('id') and e.get('startTimestamp') and e['id'] not in vus:
                vus.add(e['id'])
                out.append(ligne_api(e))
    return out


def veille_collectee(racine, jour):
    e = _lire(os.path.join(racine, EB.DOSSIER, 'etat.json'))
    return bool(((e.get('jours') or {}).get(jour.isoformat()) or {}).get('complet'))


def categorie(racine):
    e = _lire(os.path.join(racine, EB.DOSSIER, 'etat.json'))
    for nom, i in e.get('categories') or []:
        if nom == LIGUE:
            return i
    return CATEGORIE_DEFAUT


def statut(r):
    s = STATUTS.get(r.get('statut'))
    if s == TERMINE and (r.get('detail') or r.get('g') not in (1, 2)):
        return ANNULE
    return s or ANNULE


# ------------------------------------------------------------------ passage
def mettre_a_jour(etat, lignes, mod, connues, maintenant, table=None):
    ts = int(maintenant.timestamp())
    M = etat.setdefault('matchs', {})
    archives = []
    for r in lignes:
        k = str(r['id'])
        s = statut(r)
        x = M.get(k)
        ep = epreuve_de(r, connues)
        if ep is None:
            continue                                   # camps illisibles (un joueur contre une paire…)
        if x is None:
            if s != A_VENIR or int(r['t']) <= ts:
                continue                               # vu après son heure prévue : jamais de pronostic
            x = M[k] = {'id': r['id']}
        if 'p_h' in x and int(x['t']) <= ts:
            x['fige'] = True
        x.update({'t': int(r['t']), 'tournoi': r.get('tournoi'), 'h': r['h'][1], 'a': r['a'][1], 'statut': s,
                  'epreuve': ep})
        if r.get('tour'):
            x['tour'] = r['tour']
        if s == A_VENIR and int(r['t']) > ts and not x.get('fige'):
            ch, cb = camps(tuple_de(comme_termine(r), ep))
            x.update(mod.predire(ch, cb), maj=ts)
            x['scores'], x['decisive'] = scores_de(x['p_h'], ep, table)      # 527
        if s in (EN_COURS, TERMINE):
            x['manches'] = r.get('manches') or []
        if s == TERMINE and 'p_h' in x and not x.get('juge'):
            if tuple_de(r, ep) is None:
                x['statut'] = ANNULE                   # score irrégulier : ni bilan ni verdict
                continue
            x['g'] = r['g']
            x['bon'] = (r['g'] == 1) == (x['p_h'] >= 0.5)
            mh = sum(1 for a_, b_ in x.get('manches') or [] if a_ > b_)
            ma = sum(1 for a_, b_ in x.get('manches') or [] if b_ > a_)
            if x.get('scores'):                                          # 527
                x['score_trouve'] = [mh, ma] == x['scores'][0][:2]
                x['decisive_reelle'] = min(mh, ma) == 1
            x['juge'] = True
            compter(etat, x)
            archives.append(dict(x))
    for k in [k for k, x in M.items() if x['t'] < ts - GARDE_H * 3600]:
        del M[k]
    choisir_offert(etat, maintenant)
    return archives


def compter(etat, x):
    for cle in ('tout', x['epreuve']):
        B = etat.setdefault('bilan', {}).setdefault(cle, {'matchs': 0, 'bons': 0, 'somme_p_favori': 0.0, 'tranches': {}})
        if 'scores' in x and 'score_trouve' in x:                       # 527 : le score, depuis qu'il est annoncé
            B['avec_score'] = B.get('avec_score', 0) + 1
            B['scores_trouves'] = B.get('scores_trouves', 0) + int(x['score_trouve'])
            B['somme_decisive'] = round(B.get('somme_decisive', 0.0) + x['decisive'], 4)
            B['decisives_reelles'] = B.get('decisives_reelles', 0) + int(x['decisive_reelle'])
        pf = max(x['p_h'], 1 - x['p_h'])
        B['matchs'] += 1
        B['bons'] += int(x['bon'])
        B['somme_p_favori'] = round(B['somme_p_favori'] + pf, 4)
        for lo, hi in TRANCHES:
            if lo <= pf < hi:
                t = B['tranches'].setdefault(f'{round(lo * 100)}', [0, 0.0, 0])
                t[0] += 1
                t[1] = round(t[1] + pf, 4)
                t[2] += int(x['bon'])
    etat.setdefault('depuis', jour_paris(x['t']))
    # 521 : le bilan de chaque jour (Paris), pour le post du lendemain ; 10 jours gardés
    J = etat.setdefault('bilan_jours', {})
    d = J.setdefault(jour_paris(x['t']), [0, 0, 0.0])
    d[0] += 1
    d[1] += int(x['bon'])
    d[2] = round(d[2] + max(x['p_h'], 1 - x['p_h']), 4)
    for k in sorted(J)[:-10]:
        del J[k]


def choisir_offert(etat, maintenant):
    """Un match offert par jour de Paris : le plus fort (somme des Elo) parmi les matchs à venir du jour, choisi une fois ;
    rechoisi seulement si le match retenu disparaît ou est annulé."""
    jour = maintenant.astimezone(PARIS).date().isoformat()
    O = etat.setdefault('offerts', {})
    for j in [j for j in O if j < (maintenant - dt.timedelta(days=3)).date().isoformat()]:
        del O[j]
    M = etat.get('matchs') or {}
    k = O.get(jour)
    if k and k in M and M[k]['statut'] != ANNULE:
        return
    ts = int(maintenant.timestamp())
    cand = [x for x in M.values() if x['statut'] == A_VENIR and x['t'] > ts and 'p_h' in x and jour_paris(x['t']) == jour]
    if cand:
        O[jour] = str(max(cand, key=lambda x: (x.get('elo_somme', 0), -x['t'], x['id']))['id'])
    else:
        O.pop(jour, None)


def bilan_public(etat):
    out = {}
    for cle, B in (etat.get('bilan') or {}).items():
        n = B['matchs']
        if not n:
            continue
        out[cle] = {'matchs': n, 'bons_pct': round(100 * B['bons'] / n, 1),
                    'annonce_pct': round(100 * B['somme_p_favori'] / n, 1),
                    'tranches': [{'de': int(k), 'matchs': t[0], 'annonce_pct': round(100 * t[1] / t[0], 1),
                                  'reel_pct': round(100 * t[2] / t[0], 1)}
                                 for k, t in sorted(B['tranches'].items(), key=lambda kv: int(kv[0])) if t[0]]}
        ns = B.get('avec_score', 0)
        if ns:                                                          # 527
            out[cle].update(avec_score=ns, scores_trouves_pct=round(100 * B['scores_trouves'] / ns, 1),
                            decisive_annoncee_pct=round(100 * B['somme_decisive'] / ns, 1),
                            decisive_reelle_pct=round(100 * B['decisives_reelles'] / ns, 1))
    return out


# ------------------------------------------------------------------ 521 : le post du jour (X, Telegram)
HEURE_POST = 8                    # heure de Paris à partir de laquelle le post du jour part (une fois par jour)


def _tournoi_court(t):
    return re.sub(r',\s*(MS|WS|MD|WD|XD|Men|Women|Mixed)\b.*$', '', str(t or ''), flags=re.I).strip()


def _heure_fr(t):
    d = dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(PARIS)
    return f"{d.hour} h {d.minute:02d}"


def bilan_veille(etat, maintenant):
    """{'jour', 'matchs', 'bons_pct', 'annonce_pct'} des matchs jugés la veille (Paris) ; None sans match."""
    hier = (maintenant.astimezone(PARIS).date() - dt.timedelta(days=1)).isoformat()
    v = (etat.get('bilan_jours') or {}).get(hier)
    if not v or not v[0]:
        return None
    return {'jour': hier, 'matchs': v[0], 'bons_pct': round(100 * v[1] / v[0], 1), 'annonce_pct': round(100 * v[2] / v[0], 1)}


def _ligne_offert(m, pc_score=True):
    """530 : une ligne du match offert selon où il en est — à venir : le % (et le score le plus probable) ; en cours : le
    % d'avant match ; terminé : le résultat et le verdict de l'algo. Rien d'autre que ce que la page montre déjà."""
    fav, pf = (m['h'], m['p_h']) if m['p_h'] >= 0.5 else (m['a'], 1 - m['p_h'])
    if m.get('statut') == A_VENIR:
        s = m.get('scores')
        return f"L'algo : {fav} gagnant à {round(100 * pf)} %" + (
            f" · score le plus probable {s[0][0]}-{s[0][1]} ({round(100 * s[0][2])} %)" if s and pc_score else '')
    if m.get('statut') == 'termine' and m.get('g') in (1, 2):
        mh = sum(1 for a, b in m.get('manches') or [] if a > b)
        ma = sum(1 for a, b in m.get('manches') or [] if b > a)
        g, sc = (m['h'], f'{mh}-{ma}') if m['g'] == 1 else (m['a'], f'{ma}-{mh}')
        return f"Résultat : {g} gagne {sc} · l'algo donnait {fav} à {round(100 * pf)} % {'✅' if m.get('bon') else '❌'}"
    etat_ = 'Terminé' if m.get('statut') == 'termine' else 'En cours'
    return f"{etat_} · l'algo donnait {fav} gagnant à {round(100 * pf)} % avant le match"


def post_du_jour(complet, veille):
    """27/11/2026 (paquet 521, Lucas : « le post du jour ») — le match offert du jour, le bilan de la veille à partir de
    30 matchs jugés, l'adresse de la page. Aucune cote, aucun conseil.
    530 (Lucas : « pas de post du jour ») : le match offert était souvent déjà commencé à 8 h (tournois en Asie) et le
    post n'existait alors pas. Le match offert du jour est maintenant dans le post où qu'il en soit (à venir, en cours,
    terminé), et sans match offert le bilan de la veille suffit. None seulement s'il n'y a ni l'un ni l'autre."""
    offerts = [m for m in complet.get('matchs') or [] if m.get('offert') and 'p_h' in m and m.get('statut') != 'annule']
    bilan = veille and veille['matchs'] >= 30
    if not offerts and not bilan:
        return None
    L = ['🏸 Badminton · le match offert du jour' if offerts else "🏸 Badminton · le bilan d'hier"]
    for m in sorted(offerts, key=lambda m: m['t']):
        L += ['', f"{_tournoi_court(m.get('tournoi'))} · {str(m.get('epreuve') or '').capitalize()} · {_heure_fr(m['t'])} (heure du programme)",
              f"{m['h']} – {m['a']}", _ligne_offert(m)]
    if bilan:
        L += ['', f"Hier : {veille['matchs']} matchs jugés, {str(veille['bons_pct']).replace('.', ',')} % de vainqueurs trouvés "
                  f"(annoncé en moyenne {str(veille['annonce_pct']).replace('.', ',')} %)."]
    L += ['', 'Tous les pronostics et le bilan, erreurs comprises : gamesetalgo.com/badminton']
    return '\n'.join(L)


def envoyer_post(etat, complet, maintenant, jour, journal=print):
    """521 : une fois par jour, au Telegram privé, à partir de HEURE_POST. 530 : quand il ne part pas après l'heure, le
    journal dit pourquoi (sans rien afficher de secret)."""
    if maintenant.astimezone(PARIS).hour < HEURE_POST or etat.get('post_envoye') == jour:
        return
    if not complet.get('post_du_jour'):
        journal("  post du jour : rien à poster pour l'instant (ni match offert du jour, ni bilan d'hier sur 30 matchs)")
    elif envoyer_telegram(complet['post_du_jour'], journal):
        etat['post_envoye'] = jour
        journal('  post du jour envoyé au Telegram privé')
    elif not (os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID')):
        journal('::warning::post du jour : TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID absent du workflow')


def envoyer_telegram(texte, journal=print):
    """Le post du jour au Telegram PRIVÉ de Lucas (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID), à recopier sur X et sur le canal."""
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not (tok and chat):
        return False
    import urllib.parse
    import urllib.request
    try:
        corps = urllib.parse.urlencode({'chat_id': chat, 'text': texte, 'disable_web_page_preview': 'true'}).encode()
        with urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=corps, timeout=20) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 — jamais bloquant
        journal('::warning::post du jour : envoi Telegram impossible')
        return False


def site(etat, maintenant):
    ts = int(maintenant.timestamp())
    jour = maintenant.astimezone(PARIS).date().isoformat()
    offert = str(((etat.get('offerts') or {}).get(jour)) or '')
    complets, libres = [], []
    for x in sorted((etat.get('matchs') or {}).values(), key=lambda x: (x['t'], x['id'])):
        if 'p_h' not in x or x['statut'] == ANNULE or (x['statut'] == TERMINE and x['t'] < ts - PAGE_PASSES_H * 3600):
            continue
        m = {k: x[k] for k in AFFICHE + PRONOSTIC if k in x}
        m['offert'] = str(x['id']) == offert
        complets.append(m)
        if m['offert']:
            libres.append(dict(m))
        elif x['statut'] == A_VENIR and x['t'] > ts:
            libres.append(dict({k: x[k] for k in AFFICHE if k in x}, verrou=True))
        else:
            libres.append({k: x[k] for k in AFFICHE + ('p_h', 'g', 'bon') if k in x})
    haut = {'genere_le': maintenant.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
            'jour': jour, 'epreuves': EB.EPREUVES, 'bilan': bilan_public(etat), 'depuis': etat.get('depuis')}
    haut['bilan_veille'] = bilan_veille(etat, maintenant)
    complet = dict(haut, acces='plus', matchs=complets)
    complet['post_du_jour'] = post_du_jour(complet, haut['bilan_veille'])     # 521 : pour l'administrateur (page)
    return complet, dict(haut, acces='libre', matchs=libres)


# ------------------------------------------------------------------ coffre
class CoffreLocal:
    def __init__(self, dossier):
        self.dossier = dossier

    def get(self, cle):
        try:
            with open(os.path.join(self.dossier, cle), 'rb') as f:
                return f.read()
        except OSError:
            return None

    def put(self, cle, data, content_type=None):
        p = os.path.join(self.dossier, cle)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)


def coffre():
    if os.environ.get('BAD_COFFRE_LOCAL'):
        return CoffreLocal(os.environ['BAD_COFFRE_LOCAL'])
    import r2_io
    return r2_io.client(quiet=True)


def _json(d):
    return json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def archiver(cf, archives):
    par_mois = {}
    for x in archives:
        par_mois.setdefault(dt.datetime.fromtimestamp(x['t'], dt.timezone.utc).strftime('%Y-%m'), []).append(x)
    for mois, L in par_mois.items():
        cle = CLE_ARCHIVE.format(mois=mois)
        avant = cf.get(cle) or b''
        deja = {json.loads(l).get('id') for l in avant.decode('utf-8').splitlines() if l.strip()}
        L = [x for x in L if x['id'] not in deja]
        if L:
            cf.put(cle, avant + b''.join(_json(x) + b'\n' for x in L), content_type='application/x-ndjson')


def signaler_indexnow(journal=print):
    """529 (Lucas : « il faut que l'on référence les pages ») : les pages nouvelles ou modifiées sont signalées à
    IndexNow (Bing, Yandex, Seznam, Naver…) par scripts/indexnow.py, comme les pages du tennis ; Google lit le plan
    du site. Seulement dans le workflow (INDEXNOW_ACTIF=1) : jamais depuis les tests."""
    if os.environ.get('INDEXNOW_ACTIF') != '1':
        return None
    try:
        import indexnow
    except ImportError:
        return None

    def signaler(urls):
        codes = indexnow.envoyer(urls)
        journal(f"  IndexNow : {len(set(urls))} adresse(s) signalée(s) · réponses {codes}")
    return signaler


def passage(racine, client, cf, maintenant=None, journal=print):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    brut = cf.get(CLE_ETAT)
    etat = json.loads(brut) if brut else {}
    H, _ = EB.lire(racine)
    connues = epreuves_connues(H)
    d = maintenant.astimezone(PARIS).date()
    jours = [d, d + dt.timedelta(days=1)]
    veille = d - dt.timedelta(days=1)
    if not veille_collectee(racine, veille):
        jours.insert(0, veille)
    lignes = matchs_des_jours(client, jours, categorie(racine))
    if lignes is None:
        journal('badminton : une réponse manque, rien de publié ce passage')
        return {'publie': False}
    dernier = H[-1][0] if H else 0                    # l'historique s'arrête à la dernière journée collectée
    nouveaux = []
    for r in sorted(lignes, key=lambda r: (int(r['t']), r['id'])):
        if statut(r) == TERMINE and int(r['t']) > dernier:
            ep = epreuve_de(r, connues)
            m = tuple_de(r, ep) if ep else None
            if m:
                nouveaux.append(m)
    mod = Modele(H + nouveaux)
    try:
        table = table_scores(H, mod.P[:len(H)])                        # 527 : la table du score, sur tout l'historique
    except Exception as ex:  # noqa: BLE001 — sans table, le score suit le modèle sans recalage
        journal(f'  score : table indisponible ({type(ex).__name__}), modèle sans recalage')
        table = None
    archives = mettre_a_jour(etat, lignes, mod, connues, maintenant, table)
    complet, libre = site(etat, maintenant)
    jour = maintenant.astimezone(PARIS).date().isoformat()
    envoyer_post(etat, complet, maintenant, jour, journal)          # 521 ; 530 : la raison dans le journal
    archiver(cf, archives)
    try:                                              # 521 : pages de référencement (matchs terminés, joueurs)
        import pages_badminton
        pages_badminton.publier(cf, archives, maintenant, CLE_ARCHIVE, journal, signaler=signaler_indexnow(journal))
    except Exception as ex:  # noqa: BLE001 — les pages ne doivent jamais bloquer les pronostics
        journal(f'  pages : non publiées ce passage ({type(ex).__name__})')
    cf.put(CLE_ETAT, _json(etat), content_type='application/json')
    cf.put(CLE_SITE, _json(complet), content_type='application/json; charset=utf-8')
    cf.put(CLE_LIBRE, _json(libre), content_type='application/json; charset=utf-8')
    par = {}
    for m in complet['matchs']:
        par[m['statut']] = par.get(m['statut'], 0) + 1
    journal(f"badminton : historique {len(H)} matchs, {len(nouveaux)} matchs du jour ajoutés à l'Elo, {len(lignes)} matchs vus, "
            f"{len(archives)} jugés ce passage")
    journal(f"  page : {par} ; offert {sum(1 for m in complet['matchs'] if m['offert'])} ; "
            f"bilan {(complet['bilan'].get('tout') or {}).get('matchs', 0)} matchs")
    if hasattr(client, 'bilan'):
        journal(f'  {client.bilan()}')
    return {'publie': True, 'matchs': len(complet['matchs']), 'juges': len(archives)}


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('pronostics badminton : RAPIDAPI_KEY absente, rien à faire')
        return 0
    cf = coffre()
    if cf is None:
        print('::warning::pronostics badminton : coffre R2 indisponible, rien de publié')
        return 0
    import allsports as AS
    try:
        passage(racine, AS.Client(cle, minutes=float(os.environ.get('BAD_MINUTES', '10'))), cf)
    except AS.Arret as e:
        print(f'::warning::pronostics badminton : arrêt du client ({e})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
