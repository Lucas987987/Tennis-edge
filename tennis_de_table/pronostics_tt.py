#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_tt.py — PRONOSTICS DU TENNIS DE TABLE (27/11/2026, paquet 499, Lucas : « construis le produit tennis de
table », « une page du site, pour le moment une page indépendante », accès « comme le tennis »).

Ce que l'algo annonce, et d'où cela vient (rien d'autre n'entre) :
  • le % de victoire : Elo E2 (étude 487 : K = 400 / (n + 5)^0,6, cible mêlant le résultat et la part de points),
    rejoué sur tout l'historique collecté (historique/tennis_de_table/), puis sur les matchs du jour déjà terminés ;
    la pente propre à la ligue quand l'étape 2 (paquet 494) l'a retenue (International : 1,249) ;
  • le scénario (score en manches le plus probable, chance d'une manche décisive) : distribution ancrée sur le %
    (étape 3, paquet 496), remplacée par la table recalée quand l'étape 3 l'a retenue pour la ligue (International et
    Pologne). La table est réapprise à chaque passage, même recette (ligue × format × tranche de 5 points du % du
    favori, rétrécie vers la distribution ancrée avec un poids de 50 matchs), sur tout l'historique.
Le vainqueur annoncé et le % ne dépendent jamais du scénario. Aucune cote n'est lue, nulle part.

Format (3 ou 4 manches gagnantes, paquet 502) : annoncé par la source, sinon 3 en Pologne (toujours), sinon le format
habituel du tour quand l'étude du format (etude_format_tt.py) l'a retenu, sinon 3 « supposé ». Jamais dans le %.

Ligues : International et Pologne (choix de Lucas). Écartées : les compétitions par équipes (le score y compte des
rencontres, pas des manches).

Un pronostic n'est plus modifié une fois l'heure prévue du match passée : c'est celui-là qui est jugé dans le bilan.

Accès « comme le tennis » (site_leger.py, paquet 377) : tt.json, complet, pour les abonnés Plus ; tt_libre.json pour
les autres : un match offert par ligue et par jour (le plus fort du jour, somme des Elo : choix neutre, comme le match
du jour du tennis), les autres matchs à venir réduits à l'affiche, le % seul une fois le match commencé, les résultats
et le bilan publics. Le worker choisit le fichier selon le compte.

CONFIDENTIALITÉ : les pronostics à venir ne vont JAMAIS dans le dépôt public. L'état (pronostics, matchs offerts,
bilan) vit au coffre R2 privé (prive/tennis_de_table/), les deux fichiers du site sont envoyés directement à R2
(site/algo/). Le journal du run n'affiche que des comptes, jamais un nom.

Requêtes AllSportsApi : 2 par passage (les matchs du jour de Paris de chaque ligue) + 2 tant que la collecte de la veille
n'est pas faite (vers 6 h UTC, pour que l'Elo tienne compte des matchs de la veille) + 1 la première fois (numéros des
ligues). Soit une soixantaine par jour.
Usage : python tennis_de_table/pronostics_tt.py [racine]
"""
import datetime as dt
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import elo_tt as ET  # noqa: E402
import etude_etape3_tt as E3  # noqa: E402
import format_tt as FT  # noqa: E402

PAQUET = 499
SPORT = 'table-tennis'
LIGUES = ('International', 'Poland')
EQUIPES = re.compile(r'champions league|team|europe cup|europe trophy|bundesliga|superliga|liga|club|world cup teams',
                     re.I)
RAPPORT_487 = os.path.join(ICI, 'rapport_elo_tt.json')
RAPPORT_494 = os.path.join(ICI, 'rapport_etape2_tt.json')
RAPPORT_496 = os.path.join(ICI, 'rapport_etape3_tt.json')
CLE_ETAT = 'prive/tennis_de_table/etat_pronostics.json'
CLE_ARCHIVE = 'prive/tennis_de_table/archive/{mois}.jsonl'
CLE_SITE = 'site/algo/tt.json'
CLE_LIBRE = 'site/algo/tt_libre.json'
GARDE_H = 36                  # heures pendant lesquelles un match reste dans l'état (et sur la page s'il est terminé)
PAGE_PASSES_H = 24            # matchs terminés affichés : les 24 dernières heures
TRANCHES = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01))
A_VENIR, EN_COURS, TERMINE, ANNULE = 'a_venir', 'en_cours', 'termine', 'annule'
STATUTS = {'notstarted': A_VENIR, 'inprogress': EN_COURS, 'interrupted': EN_COURS, 'willcontinue': EN_COURS,
           'finished': TERMINE}
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo('Europe/Paris')
except Exception:  # noqa: BLE001 — sans base des fuseaux : heure d'hiver
    PARIS = dt.timezone(dt.timedelta(hours=1))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def jour_paris(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(PARIS).date().isoformat()


def _lire(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ réglages retenus par les études
def reglages(r487=RAPPORT_487, r494=RAPPORT_494, r496=RAPPORT_496):
    """E2, pentes et ligues recalées, lus dans les rapports des études (seulement ce qu'elles ont retenu)."""
    a = _lire(r487)
    e2 = ((a.get('reglages_appris') or {}).get('E2') or {}).get('reglage') or [400, 0.6, 0.5, 20]
    b = (_lire(r494).get('A_pente_par_ligue') or {})
    pentes = {lg: v['pente_apprise'] for lg, v in b.items() if v.get('retenue') and lg in LIGUES}
    c = (_lire(r496).get('par_ligue') or {})
    recal = sorted(lg for lg, v in c.items() if (v.get('Q2_recalage') or {}).get('retenu') and lg in LIGUES)
    return {'e2': list(e2), 'pentes': pentes, 'recalees': recal}


class Modele:
    """L'Elo de chaque joueur à la fin de l'historique (puis des matchs du jour) et la table recalée."""

    def __init__(self, M, reg):
        self.reg = reg
        a, c, w, s = reg['e2']
        self.etat = {}
        P = ET.rejouer(M, a=a, c=c, w=w, s=s, etat=self.etat)
        rec = set(reg['recalees'])
        L = E3.lignes(M, P, reg['pentes'], [i for i, m in enumerate(M) if m[2] in rec])
        self.table = E3.apprendre_table(L)
        self.matchs_historique = len(M)
        self.lignes_table = len(L)
        self.cles_recentes = {(m[0], m[3], m[4]) for m in M[-20000:]}
        self.dernier_t = M[-1][0] if M else 0

    def ajouter(self, nouveaux):
        """Matchs terminés du jour (tuples de ET.match_de) absents de l'historique : l'Elo continue."""
        neufs = sorted({(m[0], m[3], m[4]): m for m in nouveaux
                        if (m[0], m[3], m[4]) not in self.cles_recentes}.values(), key=lambda x: (x[0], x[3], x[4]))
        if neufs:
            a, c, w, s = self.reg['e2']
            ET.rejouer(neufs, a=a, c=c, w=w, s=s, etat=self.etat)
            self.cles_recentes.update((m[0], m[3], m[4]) for m in neufs)
        return len(neufs)

    def elo(self, j):
        return self.etat['R'].get(j, ET.DEPART), self.etat['N'].get(j, 0)

    def predire(self, ligue, h, a, n):
        """{'p_h', 'scores': [[manches h, manches a, proba]…] du plus probable au moins probable, 'decisive', 'n_h', 'n_a'}."""
        (rh, nh), (ra, na) = self.elo(h), self.elo(a)
        p = ET.proba(rh, ra)
        pente = self.reg['pentes'].get(ligue)
        if pente:
            p = _sg(pente * _lg(p))
        p = round(p, 4)                   # le même p partout : scénario, favori affiché, jugement
        fav_h = p >= 0.5
        pf = p if fav_h else 1 - p
        D = E3.distribution(pf, n)
        if ligue in self.reg['recalees']:
            D = {k: E3.proba_recalee(self.table, ligue, n, pf, k) for k in E3.categories(n)}
        sc = []
        for (cote, k), v in D.items():
            sf, so = (n, k) if cote == 'F' else (k, n)
            sc.append([sf, so, v] if fav_h else [so, sf, v])
        tot = sum(x[2] for x in sc) or 1.0
        sc = [[x[0], x[1], round(x[2] / tot, 4)] for x in sorted(sc, key=lambda x: -x[2])]
        dec = sum(x[2] for x in sc if min(x[0], x[1]) == n - 1)
        return {'p_h': p, 'scores': sc, 'decisive': round(dec, 4), 'n_h': nh, 'n_a': na,
                'elo_somme': round(rh + ra, 1)}


# ------------------------------------------------------------------ matchs du jour (AllSportsApi)
def ligne_api(e, ligue):
    """Événement AllSportsApi → ligne au format de l'historique (collecte_tennis_de_table.ligne) + format annoncé."""
    import collecte_tennis_de_table as CT
    r = CT.ligne(e, ligue)
    dpc = e.get('defaultPeriodCount') or e.get('bestOf')
    if dpc in (5, 7):
        r['format'] = (dpc + 1) // 2
    tour = (e.get('roundInfo') or {}).get('name')
    if tour:
        r['tour'] = tour
    return r


def categories(c, d, etat):
    """{ligue: numéro} (gardé dans l'état : une requête la première fois seulement)."""
    cats = dict(etat.get('categories') or {})
    if all(lg in cats for lg in LIGUES):
        return cats
    code, idx = c.get(f'/api/{SPORT}/calendar/{d.day}/{d.month}/{d.year}/categories')
    if code not in (200, 204):
        return cats
    for x in (idx or {}).get('categories') or []:
        cat = x.get('category') or {}
        if cat.get('name') in LIGUES and cat.get('id'):
            cats[cat['name']] = cat['id']
    etat['categories'] = cats
    return cats


def matchs_du_jour(c, d, cats):
    """[ligne] des deux ligues (la réponse d'une ligue couvre le jour ± 12 h) ; None si une ligue n'a pas répondu."""
    out = []
    for lg in LIGUES:
        if lg not in cats:
            continue
        code, doc = c.get(f'/api/{SPORT}/category/{cats[lg]}/events/{d.day}/{d.month}/{d.year}')
        if code not in (200, 204):
            return None
        for e in (doc or {}).get('events') or []:
            if e.get('id') and e.get('startTimestamp'):
                out.append(ligne_api(e, lg))
    return out


def veille_collectee(racine, jour):
    """Vrai si la collecte quotidienne a rangé ce jour (complet) dans l'historique."""
    e = _lire(os.path.join(racine, ET.DOSSIER, 'etat.json'))
    return bool(((e.get('jours') or {}).get(jour.isoformat()) or {}).get('complet'))


def format_du_match(r):
    """(manches gagnantes, source) — 502 : annoncé par la source ; sinon la Pologne (toujours 3 : 197 409 matchs sur
    197 409 en 2025–2026) ; sinon le format habituel du tour appris par l'étude du format (si retenue) ; sinon 3 supposé.
    Ne change jamais le %."""
    if r.get('format') in (3, 4):
        return r['format'], 'source'
    if r.get('ligue') == 'Poland':
        return 3, 'ligue'
    T = FT.table_retenue()
    if T and r.get('ligue') == 'International':
        return FT.predire(T, r.get('tournoi'), r.get('tour')), 'habituel'
    return 3, 'suppose'


def equipe(r):
    return bool(EQUIPES.search(str(r.get('tournoi') or '')))


def statut(r):
    s = STATUTS.get(r.get('statut'))
    if s == TERMINE and (r.get('detail') or r.get('g') not in (1, 2)):
        return ANNULE                     # abandon, forfait, vainqueur inconnu : ni bilan ni verdict
    return s or ANNULE


# ------------------------------------------------------------------ passage
def mettre_a_jour(etat, lignes, mod, maintenant):
    """Met l'état à jour avec les matchs vus ce passage. Renvoie les matchs à archiver (terminés et jugés)."""
    ts = int(maintenant.timestamp())
    M = etat.setdefault('matchs', {})
    archives = []
    for r in lignes:
        if r.get('ligue') not in LIGUES or equipe(r):
            continue
        k = str(r['id'])
        s = statut(r)
        x = M.get(k)
        if x is None:
            if s != A_VENIR or int(r['t']) <= ts:
                continue                  # vu après son début : jamais de pronostic (rien à juger)
            x = M[k] = {'id': r['id'], 'ligue': r['ligue']}
        if 'p_h' in x and int(x['t']) <= ts:
            x['fige'] = True              # l'heure prévue est passée : le pronostic ne bouge plus, même si le match est reporté
        x.update({'t': int(r['t']), 'tournoi': r.get('tournoi'), 'h': r['h'][1], 'a': r['a'][1], 'statut': s})
        if r.get('tour'):
            x['tour'] = r['tour']
        if s == A_VENIR and int(r['t']) > ts and not x.get('fige'):   # avant l'heure prévue, le pronostic suit l'Elo
            n, src = format_du_match(r)
            x['format'], x['format_suppose'], x['format_source'] = n, src == 'suppose', src
            x.update(mod.predire(r['ligue'], r['h'][0], r['a'][0], n), maj=ts)
        if s in (EN_COURS, TERMINE):
            x['manches'] = r.get('manches') or []
        if s == TERMINE and 'p_h' in x and not x.get('juge'):
            mh = sum(1 for a, b in x['manches'] if a > b)
            ma = sum(1 for a, b in x['manches'] if b > a)
            if mh == ma or max(mh, ma) < 3:
                continue                  # score incomplet : jugé à un prochain passage
            x['g'] = r['g']
            fav_h = x['p_h'] >= 0.5
            x['bon'] = (r['g'] == 1) == fav_h
            x['score_trouve'] = [mh, ma] == x['scores'][0][:2]
            x['decisive_reelle'] = min(mh, ma) == max(mh, ma) - 1
            x['juge'] = True
            compter(etat, x)
            archives.append(dict(x))
    for k in [k for k, x in M.items() if x['t'] < ts - GARDE_H * 3600]:
        del M[k]
    choisir_offerts(etat, maintenant)
    return archives


def compter(etat, x):
    B = etat.setdefault('bilan', {}).setdefault(x['ligue'], {
        'matchs': 0, 'bons': 0, 'somme_p_favori': 0.0, 'scores_trouves': 0, 'somme_decisive': 0.0,
        'decisives_reelles': 0, 'tranches': {}})
    pf = max(x['p_h'], 1 - x['p_h'])
    B['matchs'] += 1
    B['bons'] += int(x['bon'])
    B['somme_p_favori'] = round(B['somme_p_favori'] + pf, 4)
    B['scores_trouves'] += int(x['score_trouve'])
    B['somme_decisive'] = round(B['somme_decisive'] + x['decisive'], 4)
    B['decisives_reelles'] += int(x['decisive_reelle'])
    for lo, hi in TRANCHES:
        if lo <= pf < hi:
            t = B['tranches'].setdefault(f'{round(lo * 100)}', [0, 0.0, 0])
            t[0] += 1
            t[1] = round(t[1] + pf, 4)
            t[2] += int(x['bon'])
    etat.setdefault('depuis', jour_paris(x['t']))


def choisir_offerts(etat, maintenant):
    """Un match offert par ligue et par jour (heure de Paris) : le plus fort (somme des Elo) parmi les matchs à venir du
    jour, choisi une fois ; rechoisi seulement si le match retenu disparaît (annulé)."""
    jour = maintenant.astimezone(PARIS).date().isoformat()
    O = etat.setdefault('offerts', {})
    for j in [j for j in O if j < (maintenant - dt.timedelta(days=3)).date().isoformat()]:
        del O[j]
    du_jour = O.setdefault(jour, {})
    M = etat.get('matchs') or {}
    ts = int(maintenant.timestamp())
    for lg in LIGUES:
        k = du_jour.get(lg)
        if k and k in M and M[k]['statut'] != ANNULE:
            continue
        cand = [x for x in M.values() if x['ligue'] == lg and x['statut'] == A_VENIR and x['t'] > ts and 'p_h' in x
                and jour_paris(x['t']) == jour]
        if cand:
            du_jour[lg] = str(max(cand, key=lambda x: (x.get('elo_somme', 0), -x['t'], x['id']))['id'])
        else:
            du_jour.pop(lg, None)


# ------------------------------------------------------------------ fichiers du site
AFFICHE = ('id', 'ligue', 't', 'tournoi', 'tour', 'h', 'a', 'statut', 'format', 'format_suppose', 'format_source',
           'manches')
PRONOSTIC = ('p_h', 'scores', 'decisive', 'n_h', 'n_a', 'maj', 'g', 'bon', 'score_trouve', 'decisive_reelle')


def bilan_public(etat):
    out = {}
    for lg, B in (etat.get('bilan') or {}).items():
        n = B['matchs']
        if not n:
            continue
        out[lg] = {'matchs': n, 'bons_pct': round(100 * B['bons'] / n, 1),
                   'annonce_pct': round(100 * B['somme_p_favori'] / n, 1),
                   'scores_trouves_pct': round(100 * B['scores_trouves'] / n, 1),
                   'decisive_annoncee_pct': round(100 * B['somme_decisive'] / n, 1),
                   'decisive_reelle_pct': round(100 * B['decisives_reelles'] / n, 1),
                   'tranches': [{'de': int(k), 'matchs': t[0], 'annonce_pct': round(100 * t[1] / t[0], 1),
                                 'reel_pct': round(100 * t[2] / t[0], 1)}
                                for k, t in sorted(B['tranches'].items(), key=lambda kv: int(kv[0])) if t[0]]}
    return out


def site(etat, mod_info, maintenant):
    """(tt.json complet, tt_libre.json)."""
    ts = int(maintenant.timestamp())
    jour = maintenant.astimezone(PARIS).date().isoformat()
    offerts = {str(v) for v in ((etat.get('offerts') or {}).get(jour) or {}).values()}
    complets, libres = [], []
    for x in sorted((etat.get('matchs') or {}).values(), key=lambda x: (x['t'], x['id'])):
        if 'p_h' not in x or x['statut'] == ANNULE or (x['statut'] == TERMINE and x['t'] < ts - PAGE_PASSES_H * 3600):
            continue
        m = {k: x[k] for k in AFFICHE + PRONOSTIC if k in x}
        m['offert'] = str(x['id']) in offerts
        complets.append(m)
        if m['offert']:
            libres.append(dict(m))
        elif x['statut'] == A_VENIR and x['t'] > ts:
            libres.append(dict({k: x[k] for k in AFFICHE if k in x}, verrou=True))
        else:                                       # commencé : le % de l'algo seul (et le verdict une fois terminé)
            libres.append({k: x[k] for k in AFFICHE + ('p_h', 'g', 'bon') if k in x})
    haut = {'genere_le': maintenant.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
            'jour': jour, 'ligues': list(LIGUES), 'bilan': bilan_public(etat), 'depuis': etat.get('depuis'),
            'modele': mod_info}
    return dict(haut, acces='plus', matchs=complets), dict(haut, acces='libre', matchs=libres)


# ------------------------------------------------------------------ coffre (R2 privé, ou dossier local pour les essais)
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
    if os.environ.get('TT_COFFRE_LOCAL'):
        return CoffreLocal(os.environ['TT_COFFRE_LOCAL'])
    import r2_io
    return r2_io.client(quiet=True)


def _json(d):
    return json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def archiver(cf, archives, maintenant):
    if not archives:
        return
    par_mois = {}
    for x in archives:
        par_mois.setdefault(dt.datetime.fromtimestamp(x['t'], dt.timezone.utc).strftime('%Y-%m'), []).append(x)
    for mois, L in par_mois.items():
        cle = CLE_ARCHIVE.format(mois=mois)
        avant = cf.get(cle) or b''
        deja = {json.loads(l).get('id') for l in avant.decode('utf-8').splitlines() if l.strip()}
        L = [x for x in L if x['id'] not in deja]     # état non écrit au passage précédent : jamais deux fois
        if L:
            cf.put(cle, avant + b''.join(_json(x) + b'\n' for x in L), content_type='application/x-ndjson')


def passage(racine, client, cf, maintenant=None, journal=print):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    brut = cf.get(CLE_ETAT)
    etat = json.loads(brut) if brut else {}
    reg = reglages()
    M = ET.matchs(racine)
    mod = Modele(M, reg)
    d = maintenant.astimezone(PARIS).date()          # la réponse couvre le jour de Paris entier (± 12 h)
    cats = categories(client, d, etat)
    lignes = []
    veille = d - dt.timedelta(days=1)
    if not veille_collectee(racine, veille):          # avant la collecte de 6 h UTC : la veille aussi, pour l'Elo
        lv = matchs_du_jour(client, veille, cats)
        lignes += lv or []
    lj = matchs_du_jour(client, d, cats)
    lignes = None if lj is None else lignes + lj
    if lignes is None:
        journal('tennis de table : une ligue n\'a pas répondu, rien de publié ce passage')
        return {'publie': False}
    ajoutes = mod.ajouter([m for m in (ET.match_de(r, jour_paris(r['t'])) for r in lignes) if m])
    archives = mettre_a_jour(etat, lignes, mod, maintenant)
    info = {'matchs_historique': mod.matchs_historique, 'matchs_du_jour_ajoutes': ajoutes, 'pentes': reg['pentes'],
            'recalees': reg['recalees'], 'e2': reg['e2']}
    complet, libre = site(etat, info, maintenant)
    archiver(cf, archives, maintenant)
    cf.put(CLE_ETAT, _json(etat), content_type='application/json')
    cf.put(CLE_SITE, _json(complet), content_type='application/json; charset=utf-8')
    cf.put(CLE_LIBRE, _json(libre), content_type='application/json; charset=utf-8')
    par = {}
    for m in complet['matchs']:
        par.setdefault(m['ligue'], {}).setdefault(m['statut'], 0)
        par[m['ligue']][m['statut']] += 1
    journal(f"tennis de table : historique {mod.matchs_historique} matchs, {ajoutes} matchs du jour ajoutés à l'Elo, "
            f"{len(lignes)} matchs vus, {len(archives)} jugés ce passage")
    journal(f"  page : {par} ; offerts {sum(1 for m in complet['matchs'] if m['offert'])} ; "
            f"bilan {dict((lg, b['matchs']) for lg, b in complet['bilan'].items())}")
    if hasattr(client, 'bilan'):
        journal(f'  {client.bilan()}')
    return {'publie': True, 'matchs': len(complet['matchs']), 'juges': len(archives)}


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('pronostics tennis de table : RAPIDAPI_KEY absente, rien à faire')
        return 0
    cf = coffre()
    if cf is None:
        print('::warning::pronostics tennis de table : coffre R2 indisponible, rien de publié')
        return 0
    import allsports as AS
    try:
        passage(racine, AS.Client(cle, minutes=float(os.environ.get('TT_MINUTES', '10'))), cf)
    except AS.Arret as e:
        print(f'::warning::pronostics tennis de table : arrêt du client ({e})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
