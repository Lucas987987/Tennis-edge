#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_du_jour.py — pronostic de chaque match à venir, deux versions côte à côte (21/10/2026).

  « stats seules »   : force Elo (elo_etat.json, refait chaque run depuis tous
                        les résultats) + style service/retour de chaque joueur
                        (notes_joueurs.json) + forme du jour, dans le moteur ;
  « stats + marché » : même moteur, niveau pris à la cote Pinnacle (marge
                        retirée) quand Pinnacle cote le match.
Pour chaque match : probabilité de victoire, 2-0 / 2-1 / 1-2 / 0-2 (ou en 5
sets), les 3 scores complets les plus probables set par set dans l'ordre réel
(ex. « 4-6 6-3 6-4 »), victoire après la perte du 1er set, set 1, total de jeux
moyen, au moins un tie-break.

JOURNAL : le PREMIER pronostic de chaque match est écrit une fois dans
simulateur/pronostics_log.jsonl et jamais modifié ; le bilan (taux de
vainqueurs devinés des deux versions, sur les matchs joués) se calcule sur ce
journal — un vrai suivi en direct, sans retouche.

MATCH SIMULÉ (22/10/2026) : chaque version est aussi jouée 5 000 fois point
par point (match_simule.py) avec le profil de service des deux joueurs
(profils_service.json : % de 1re balle, aces, doubles fautes, points gagnés
derrière la 1re et la 2e balle, qualité de retour), au niveau de la version.
On en tire la feuille de stats prévue (moyenne et fourchette à 80 %) et un
match type, set par set avec les breaks.

Entrées : matches_oddspapi.json (matchs à venir), simulateur/elo_etat.json,
simulateur/notes_joueurs.json, simulateur/profils_service.json, set_results.json (résultats).
Sorties : Tennis_Edge_Lab/live/pronostics.json, Tennis_Edge_Lab/live/pronostics_bilan.json,
simulateur/pronostics_log.jsonl. 0 requête API.
"""
import datetime as dt
import importlib.util
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as MS  # noqa: E402
import modele as M  # noqa: E402
import nos_resultats as NR  # noqa: E402
import profils_service as PS  # noqa: E402

SIGMA = 0.15
SIMULATIONS = int(os.environ.get('SIMULATIONS', '5000'))
BALLES_CONNU = 500          # profil « connu » : au moins 500 balles de service (pondérées) dans l'archive
HORIZON_H = 36
LOG = 'simulateur/pronostics_log.jsonl'
# 22/10/2026 — TOUT est enregistré pour l'analyse a posteriori :
#   INSTANTANES : chaque passage (toutes les 6 h), chaque match, chaque version (%, sets, scores,
#                 jeux, tie-break, facteurs, cote Pinnacle) — on voit le pronostic évoluer jusqu'au match ;
#   RESULTATS   : chaque match joué, prédiction (1re et dernière avant le match) contre résultat réel
#                 (vainqueur, score en sets et en jeux, feuille de stats), et ce qui était juste ou faux.
INSTANTANES = 'simulateur/journal_pronostics'
RESULTATS = 'Tennis_Edge_Lab/live/pronostics_resultats.json'
VERSIONS = ('combinaison', 'simulation', 'stats', 'marche')
SORTIE = 'Tennis_Edge_Lab/live/pronostics.json'
BILAN = 'Tennis_Edge_Lab/live/pronostics_bilan.json'


def _books(racine):
    sp = importlib.util.spec_from_file_location('tennis_edge_pj_books', os.path.join(racine, 'Tennis_Edge_Lab', 'books.py'))
    b = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(b)
    return b


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


def sig(z):
    return 1 / (1 + math.exp(-z))


class Styles:
    """Service / retour de chaque joueur (notes Sackmann ajustées aux adversaires)."""

    def __init__(self, chemin):
        try:
            doc = json.load(open(chemin, encoding='utf-8'))
        except (OSError, ValueError):
            doc = {}
        self.mu = {}
        for k, v in (doc.get('mu') or {}).items():
            c, _, s = k.partition(' ')
            self.mu[(c, s)] = v
        self.j = {}
        for v in (doc.get('joueurs') or {}).values():
            k = E.cle(v.get('nom'))
            if k and (k not in self.j or v.get('points', 0) > self.j[k][2]):
                self.j[k] = (v.get('service', 0.0), v.get('retour', 0.0), v.get('points', 0))

    def mu_de(self, c, s):
        if (c, s) in self.mu:
            return self.mu[(c, s)]
        v = [x for (cc, _), x in self.mu.items() if cc == c]
        return sum(v) / len(v) if v else 0.5

    def service(self, a, b, c, s):
        """P(A gagne un point sur son service contre B), avant ancrage au niveau."""
        sa, ra = (self.j.get(a) or (0.0, 0.0, 0))[:2]
        sb, rb = (self.j.get(b) or (0.0, 0.0, 0))[:2]
        mu = self.mu_de(c, s)
        return sig(mu + sa - rb), sig(mu + sb - ra)

    def connu(self, a):
        return a in self.j


def pronostic(p_home, c, sg, pa0, pb0):
    """Distribution complète, niveau ancré sur p_home, style (pa0, pb0).

    Scores : les 3 scores COMPLETS les plus probables, set par set et dans l'ordre
    réel (modele.scores_complets : rien n'est supposé — le vainqueur peut perdre le
    1er set). Il y a ~1 500 scores possibles : même le premier dépasse rarement 4 %."""
    a, b = M.ancrer_forme(pa0, pb0, min(max(p_home, 0.01), 0.99), sg, SIGMA, iterations=20)
    r = M.match_forme(a, b, sg, SIGMA)
    sc = M.scores_complets(a, b, sg, SIGMA, top=3)
    return {'p_home': round(r['victoire'], 4),
            'sets': {k: round(v, 4) for k, v in r['sets'].items()},
            'scores_probables': [[s_, round(p_, 4)] for s_, p_ in sc['scores']],
            'remontee': {'home': round(sc['remontee_A'], 4), 'away': round(sc['remontee_B'], 4)},
            'set1_home': round(r['set1'], 4),
            'jeux_moyen': round(M.moyenne(r['total_jeux']), 1),
            'tiebreak': round(r['tiebreak'], 3)}


def charger_profils(racine):
    try:
        with open(os.path.join(racine, 'simulateur', 'profils_service.json'), encoding='utf-8') as f:
            return PS.Profils.importer(json.load(f))
    except (OSError, ValueError, KeyError):
        return None


def charger_reglages(racine):
    """Réglages du match simulé, seulement s'ils ont été ADOPTÉS (reglage_match_simule.py)."""
    try:
        with open(os.path.join(racine, 'simulateur', 'reglages_match_simule.json'), encoding='utf-8') as f:
            d = json.load(f)
        return d['reglages'] if d.get('adopte') else None
    except (OSError, ValueError, KeyError):
        return None


REGLAGES = None


def charger_choix(racine):
    """Composantes retenues par le test (backtest_match_simule.py) : 'ajustees' ou 'profils'."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            return json.load(f).get('composantes', 'profils')
    except (OSError, ValueError):
        return 'profils'


CHOIX = 'profils'


def charger_combinaison(racine):
    """Poids de la combinaison simulation + Elo si le test l'a adoptée (backtest_match_simule.py), sinon None."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            cb = json.load(f).get('combinaison') or {}
        return cb['poids'] if cb.get('adopte') and cb.get('poids') else None
    except (OSError, ValueError, KeyError):
        return None


COMBINAISON = None


def charger_facteurs(racine):
    """Facteurs du match ADOPTÉS par l'étude (facteurs.py, règle fixée d'avance) et contexte du jour
    (forme, fatigue, vitesse des tournois, gaucher/taille, points importants). (None, None) sinon."""
    try:
        with open(os.path.join(racine, 'simulateur', 'facteurs.json'), encoding='utf-8') as f:
            doc = json.load(f)
        if not doc.get('adoptes') or not doc.get('coefs'):
            return None, None
        import facteurs as FA
        with open(os.path.join(racine, 'simulateur', 'facteurs_contexte.json'), encoding='utf-8') as f:
            return doc, FA.Contexte(json.load(f))
    except (OSError, ValueError, ImportError):
        return None, None


FACTEURS, CONTEXTE = None, None


def composantes_du_match(P, h, a, c, s):
    ph, nh = P.profil(h, c, s, P.jour_export)
    pa, na = P.profil(a, c, s, P.jour_export)
    mu = P.moyenne(c, s)
    if CHOIX == 'ajustees' and getattr(P, 'ajuste', None) is not None:
        cH, cA = MS.composantes_ajustees(P.ajuste, h, a, c, s), MS.composantes_ajustees(P.ajuste, a, h, c, s)
    else:
        cH, cA = MS.composantes(ph, pa, mu), MS.composantes(pa, ph, mu)
    return cH, cA, nh, na


def facteurs_du_match(h, a, tournoi, debut, adj=None):
    """{groupe adopté: ((d_service, d_aces, d_bp) home, (…) away)} en logit, + variables lues."""
    if not FACTEURS or CONTEXTE is None:
        return None
    import facteurs as FA
    ts = debut.replace(tzinfo=dt.timezone.utc).timestamp() if debut.tzinfo is None else debut.timestamp()
    vH, vA = CONTEXTE.variables(h, a, tournoi, ts, adj), CONTEXTE.variables(a, h, tournoi, ts, adj)
    coefs = FACTEURS['coefs']
    par_groupe = {}
    for g in FACTEURS['adoptes']:
        cg = {m: {f: b for f, b in (coefs.get(m) or {}).items() if f in FA.GROUPES[g].get(m, [])} for m in coefs}
        par_groupe[g] = (FA.deltas(vH, cg), FA.deltas(vA, cg))
    return {'groupes': par_groupe, 'total': (FA.deltas(vH, coefs), FA.deltas(vA, coefs))}


def avec_facteurs(cH, cA, fct):
    if not fct:
        return cH, cA
    dH, dA = fct['total']
    return MS.appliquer_facteurs(cH, *dH), MS.appliquer_facteurs(cA, *dA)


def impact_facteurs(cH, cA, sg, fct):
    """Ce qui pèse : victoire home (simulation pure, limite exacte) sans facteurs, avec tous, et
    l'écart dû à chaque groupe seul (en points de %)."""
    if not fct:
        return None
    base = MS.victoire_pure(cH, cA, sg, SIGMA)
    tH, tA = avec_facteurs(cH, cA, fct)
    out = {'sans': round(base, 4), 'avec': round(MS.victoire_pure(tH, tA, sg, SIGMA), 4), 'groupes': {}}
    for g, (dH, dA) in fct['groupes'].items():
        p = MS.victoire_pure(MS.appliquer_facteurs(cH, *dH), MS.appliquer_facteurs(cA, *dA), sg, SIGMA)
        out['groupes'][g] = round(100 * (p - base), 1)
    return out


def match_simule(P, h, a, c, s, sg, p_home, cle, fct=None):
    """Le match joué SIMULATIONS fois au niveau p_home, avec les profils de service des deux joueurs
    (et les facteurs du match adoptés, s'il y en a)."""
    cH, cA, nh, na = composantes_du_match(P, h, a, c, s)
    cH, cA = avec_facteurs(cH, cA, fct)
    r = MS.simuler(cH, cA, p_home, sg, SIMULATIONS, SIGMA, cle=cle, reglages=REGLAGES)
    r['reglages'] = REGLAGES
    r['composantes'] = CHOIX if (CHOIX == 'ajustees' and getattr(P, 'ajuste', None) is not None) else 'profils'
    r['profil_connu'] = [nh >= BALLES_CONNU, na >= BALLES_CONNU]
    return r


def matchs_a_venir(racine, maintenant):
    try:
        L = json.load(open(os.path.join(racine, 'matches_oddspapi.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    L = L if isinstance(L, list) else list(L.values())
    out = []
    for m in L:
        try:
            debut = dt.datetime.fromisoformat(str(m['commence_time']).replace('Z', '+00:00')).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if not (maintenant < debut <= maintenant + dt.timedelta(hours=HORIZON_H)):
            continue
        h, a = m.get('home_team'), m.get('away_team')
        if not h or not a:
            continue
        pin = None
        for bk in m.get('bookmakers') or []:
            if bk.get('key') != 'pinnacle':
                continue
            for mk in bk.get('markets') or []:
                if mk.get('key') == 'h2h':
                    px = {o.get('name'): o.get('price') for o in mk.get('outcomes') or []}
                    if px.get(h) and px.get(a):
                        pin = (float(px[h]), float(px[a]))
        out.append({'debut': debut, 'home': h, 'away': a, 'tournoi': m.get('sport_title') or '', 'pin': pin})
    out.sort(key=lambda x: x['debut'])
    return out


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.utcnow()
    books = _books(racine)
    etat = json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8'))
    elo = E.Elo.importer(etat['joueurs'], etat.get('options'))
    surf = etat.get('surfaces_tournois') or {}
    S = Styles(os.path.join(racine, 'simulateur', 'notes_joueurs.json'))
    PR = charger_profils(racine)
    global REGLAGES, CHOIX, FACTEURS, CONTEXTE, COMBINAISON
    REGLAGES = charger_reglages(racine)
    CHOIX = charger_choix(racine)
    COMBINAISON = charger_combinaison(racine)
    FACTEURS, CONTEXTE = charger_facteurs(racine)
    venir = matchs_a_venir(racine, maintenant)
    # Un joueur = un classement : alias du dernier calcul, puis noms nouveaux reliés au joueur connu.
    alias = dict(etat.get('alias') or {})
    alias.update(E.unifier({k: v.get('nom', k) for k, v in etat['joueurs'].items()},
                           [n for x in venir for n in (x['home'], x['away'])]))
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    out = []
    for x in venir:
        h, a = cle_c(x['home']), cle_c(x['away'])
        c = circuit(x['tournoi'])
        if etat.get('depart_bas') and c in ('CH', 'ITF'):
            elo.presenter(h, etat['depart_bas'])
            elo.presenter(a, etat['depart_bas'])
        s = NR.surface_de(x['tournoi'], surf)
        sg = 3 if NR.cinq_sets(x['tournoi']) else 2
        pa0, pb0 = S.service(h, a, c, s)
        stats = pronostic(elo.proba(h, a, s), c, sg, pa0, pb0)
        marche = None
        if x['pin'] and min(x['pin']) > 1:
            k = books.power_exponent(*x['pin'])
            ph = (1 / x['pin'][0]) ** k if k else (1 / x['pin'][0]) / (1 / x['pin'][0] + 1 / x['pin'][1])
            marche = pronostic(ph, c, sg, pa0, pb0)
        uid = f"{x['debut'].date()}_{NR.slug(x['home'])}_{NR.slug(x['away'])}"
        simulation = combinaison = direct = None
        if PR is not None:
            # 22/10/2026 — SIMULATION PURE : le match joué SIMULATIONS fois avec les seuls taux des deux
            # joueurs (1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e, retour),
            # sans Elo ni cote : c'est la simulation qui dit qui gagne.
            fct = facteurs_du_match(h, a, x['tournoi'], x['debut'], getattr(PR, 'ajuste', None))
            r = match_simule(PR, h, a, c, s, sg, None, f"{uid}|simulation", fct)
            simulation = {'p_home': r['victoire_A'], 'sets': r['sets'], 'scores_probables': r['scores'][:3],
                          'remontee': {'home': r['remontee'][0], 'away': r['remontee'][1]}, 'set1_home': r['set1_A'],
                          'jeux_moyen': r['jeux']['moy'], 'tiebreak': r['tiebreak'], 'match_simule': r}
            if fct:
                cH, cA, _, _ = composantes_du_match(PR, h, a, c, s)
                simulation['facteurs'] = impact_facteurs(cH, cA, sg, fct)
            if COMBINAISON:
                # 22/10/2026 — SIMULATION + ELO : le % de la simulation (limite exacte) mélangé à celui de l'Elo,
                # poids appris sur 2024 et adoptés parce qu'ils trouvent mieux le vainqueur en 2025–2026 ; le
                # match est ensuite joué avec les statistiques des deux joueurs, à ce niveau.
                cH, cA = avec_facteurs(*composantes_du_match(PR, h, a, c, s)[:2], fct)
                p_sim = MS.victoire_pure(cH, cA, sg, SIGMA)
                p_c = MS.melange(COMBINAISON, stats['p_home'], p_sim)
                combinaison = dict(pronostic(p_c, c, sg, pa0, pb0), p_simulation=round(p_sim, 4), p_elo=stats['p_home'])
            # 22/10/2026 — EN DIRECT (direct.py, Lab) : points de service des deux joueurs pour la version
            # principale (simulation + Elo si adoptée, sinon simulation pure), avant toute forme du jour.
            cH0, cA0 = avec_facteurs(*composantes_du_match(PR, h, a, c, s)[:2], fct)
            pa_s, pb_s = MS.p_service(cH0), MS.p_service(cA0)
            if combinaison:
                pa_s, pb_s = MS.ancrer_rapide(pa_s, pb_s, combinaison['p_home'], sg, SIGMA)
            direct = {'a': round(pa_s, 5), 'b': round(pb_s, 5), 'sigma': SIGMA, 'sets_gagnants': sg,
                      'tb_final': 10 if sg == 3 else 7, 'version': 'combinaison' if combinaison else 'simulation'}
            for nom_v, v in (('stats', stats), ('marche', marche), ('combinaison', combinaison)):
                if v:
                    v['match_simule'] = match_simule(PR, h, a, c, s, sg, v['p_home'], f"{uid}|{nom_v}", fct)
        out.append({'uid': uid,
                    'debut': x['debut'].isoformat(timespec='minutes'), 'tournoi': x['tournoi'], 'circuit': c,
                    'surface': s, 'meilleur_des': 2 * sg - 1, 'home': x['home'], 'away': x['away'],
                    'cles': [h, a], 'matchs_joues': [elo.matchs(h), elo.matchs(a)], 'style_connu': [S.connu(h), S.connu(a)],
                    'pin_cotes': list(x['pin']) if x['pin'] else None,
                    'combinaison': combinaison, 'simulation': simulation, 'stats': stats, 'marche': marche, 'direct': direct})
    return {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'elo_au': etat.get('dernier_match'),
            'horizon_h': HORIZON_H, 'sigma': SIGMA, 'simulations': SIMULATIONS if PR is not None else 0,
            'profils_au': PR.jour_export.isoformat() if PR is not None else None,
            'facteurs_adoptes': (FACTEURS or {}).get('adoptes') or [], 'combinaison': COMBINAISON,
            'noeuds_forme': [[round(z, 6), round(w, 8)] for z, w in zip(M._Z, M._W)], 'matchs': out}


SUIVI_STATS = ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'breaks', 'jeux')


def feuille_prevue(m):
    """Feuille simulée gardée au journal (simulation pure ; à défaut marché, puis stats seules) :
    {stat: [[moy, p10, p90] home, [..] away]} + total de jeux."""
    v = next((m[k] for k in ('simulation', 'marche', 'stats') if m.get(k) and m[k].get('match_simule')), None)
    S = (v or {}).get('match_simule')
    if not S:
        return None
    out = {'version': next(k for k in ('simulation', 'marche', 'stats') if m.get(k) is v)}
    for k in SUIVI_STATS:
        a, b = S['feuille'][0].get(k), S['feuille'][1].get(k)
        if a and b:
            out[k] = [[a['moy'], a['p10'], a['p90']], [b['moy'], b['p10'], b['p90']]]
    if S.get('jeux'):
        out['total_jeux'] = [S['jeux']['moy'], S['jeux']['p10'], S['jeux']['p90']]
    return out


def suivi_feuilles(racine, lignes):
    """Match simulé contre la vraie feuille (feuilles/ collectées) : par statistique, prévu moyen,
    réel moyen, écart moyen absolu et part des réels dans la fourchette à 80 % (bornes incluses)."""
    avec = [r for r in lignes if r.get('feuille')]
    if not avec:
        return {'n': 0}
    jours = sorted(r['debut'][:10] for r in avec)
    debut = (dt.date.fromisoformat(jours[0]) - dt.timedelta(days=1)).isoformat()
    idx = FE.Index(FE.lire(racine, depuis=debut))
    acc = {k: [] for k in SUIVI_STATS + ('total_jeux',)}
    n = 0
    for r in avec:
        fi, inv = idx.trouver(r['debut'][:10], r['home'], r['away'])
        if not fi or str((fi.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        reel = FE.feuille_reelle(fi, inv)
        if not reel:
            continue
        (fh, fa), tot = reel
        n += 1
        for k in SUIVI_STATS:
            if k in r['feuille']:
                for i, f in ((0, fh), (1, fa)):
                    moy, lo, hi = r['feuille'][k][i]
                    acc[k].append((moy, lo, hi, f[k]))
        if 'total_jeux' in r['feuille']:
            moy, lo, hi = r['feuille']['total_jeux']
            acc['total_jeux'].append((moy, lo, hi, tot))
    out = {'n': n, 'stats': {}}
    for k, L in acc.items():
        if L:
            out['stats'][k] = {'n': len(L), 'prevu': round(sum(x[0] for x in L) / len(L), 2),
                               'reel': round(sum(x[3] for x in L) / len(L), 2),
                               'ecart_moyen': round(sum(abs(x[0] - x[3]) for x in L) / len(L), 2),
                               'dans_fourchette_pct': round(100 * sum(x[1] <= x[3] <= x[2] for x in L) / len(L), 1)}
    return out


def resume_version(v):
    """Ce qu'on garde d'une version pour l'analyse : %, sets, 3 scores, jeux, tie-break, 1er set."""
    if not v:
        return None
    out = {k: v.get(k) for k in ('p_home', 'sets', 'scores_probables', 'jeux_moyen', 'tiebreak', 'set1_home') if v.get(k) is not None}
    if v.get('facteurs'):
        out['facteurs'] = v['facteurs']
    return out


def instantane(doc, m):
    return {'passage': doc['genere_le'], 'uid': m['uid'], 'debut': m['debut'], 'home': m['home'], 'away': m['away'],
            'tournoi': m['tournoi'], 'circuit': m['circuit'], 'surface': m['surface'], 'meilleur_des': m['meilleur_des'],
            'pin_cotes': m.get('pin_cotes'), 'matchs_joues': m.get('matchs_joues'),
            'modele': {'facteurs': doc.get('facteurs_adoptes') or [], 'combinaison': doc.get('combinaison'),
                       'profils_au': doc.get('profils_au'), 'elo_au': doc.get('elo_au')},
            **{k: resume_version(m.get(k)) for k in VERSIONS}, 'direct': m.get('direct')}


def enregistrer_instantanes(racine, doc):
    """Une ligne par match et par passage, dans simulateur/journal_pronostics/AAAA-MM-JJ.jsonl.gz
    (jour UTC du passage ; fichier gzip complété à chaque passage)."""
    import gzip
    dossier = os.path.join(racine, INSTANTANES)
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, doc['genere_le'][:10] + '.jsonl.gz')
    with gzip.open(chemin, 'at', encoding='utf-8') as f:
        for m in doc['matchs']:
            f.write(json.dumps(instantane(doc, m), ensure_ascii=False, separators=(',', ':')) + '\n')
    return len(doc['matchs'])


def lire_instantanes(racine, depuis=None):
    """{uid: [instantanés dans l'ordre des passages]}."""
    import glob
    import gzip
    out = {}
    for p in sorted(glob.glob(os.path.join(racine, INSTANTANES, '*.jsonl.gz'))):
        if depuis and os.path.basename(p)[:10] < depuis:
            continue
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    try:
                        r = json.loads(l)
                    except ValueError:
                        continue
                    out.setdefault(r['uid'], []).append(r)
        except (OSError, EOFError):
            continue
    for L in out.values():
        L.sort(key=lambda r: r['passage'])
    return out


def journaliser(racine, doc):
    chemin = os.path.join(racine, LOG)
    deja = set()
    try:
        with open(chemin, encoding='utf-8') as f:
            for l in f:
                try:
                    deja.add(json.loads(l)['uid'])
                except (ValueError, KeyError):
                    continue
    except OSError:
        pass
    n = 0
    with open(chemin, 'a', encoding='utf-8') as f:
        for m in doc['matchs']:
            if m['uid'] in deja:
                continue
            f.write(json.dumps({'uid': m['uid'], 'pronostique_le': doc['genere_le'], 'debut': m['debut'],
                                'home': m['home'], 'away': m['away'], 'tournoi': m['tournoi'], 'circuit': m['circuit'],
                                'stats': {'p_home': m['stats']['p_home'], 'sets': m['stats']['sets']},
                                'marche': ({'p_home': m['marche']['p_home'], 'sets': m['marche']['sets']} if m['marche'] else None),
                                'simulation': ({'p_home': m['simulation']['p_home'], 'sets': m['simulation']['sets']}
                                               if m.get('simulation') else None),
                                'combinaison': ({'p_home': m['combinaison']['p_home'], 'sets': m['combinaison']['sets']}
                                                if m.get('combinaison') else None),
                                'detail': {k: resume_version(m.get(k)) for k in VERSIONS},
                                'pin_cotes': m.get('pin_cotes'), 'surface': m.get('surface'),
                                'meilleur_des': m.get('meilleur_des'),
                                'feuille': feuille_prevue(m)},
                               ensure_ascii=False) + '\n')
            n += 1
    return n


def bilan(racine, maintenant=None):
    """Taux de vainqueurs devinés sur le journal (matchs joués, résultat connu)."""
    maintenant = maintenant or dt.datetime.utcnow()
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    vus, L, journal = set(), [], []
    try:
        lignes = open(os.path.join(racine, LOG), encoding='utf-8').read().splitlines()
    except OSError:
        lignes = []
    for l in lignes:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r['uid'] in vus:
            continue
        vus.add(r['uid'])
        journal.append(r)
        d0 = dt.date.fromisoformat(r['debut'][:10])
        res, sens = NR.resultat(sr, d0, r['home'], r['away'])
        if not res:
            continue
        o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
        g, s1, s2 = o(res.get('match')), o(res.get('set1')), o(res.get('set2'))
        sets = None
        if s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and g != s1) and len(r['stats']['sets']) == 4:
            sets = ('2-0' if g == 'home' else '0-2') if s1 == s2 else ('2-1' if g == 'home' else '1-2')
        L.append(dict(r, gagnant=g, sets_reel=sets))

    def bloc(items, cle):
        it = [x for x in items if x.get(cle)]
        n = len(it)
        if not n:
            return {'n': 0}
        ok = sum(1.0 if (x[cle]['p_home'] > 0.5) == (x['gagnant'] == 'home') and x[cle]['p_home'] != 0.5 else
                 (0.5 if x[cle]['p_home'] == 0.5 else 0.0) for x in it)
        s = [x for x in it if x['sets_reel']]
        sj = sum(max(x[cle]['sets'], key=x[cle]['sets'].get) == x['sets_reel'] for x in s)
        ll = sum(-math.log(min(max(x[cle]['p_home'] if x['gagnant'] == 'home' else 1 - x[cle]['p_home'], 1e-6), 1))
                 for x in it) / n
        return {'n': n, 'reussite_pct': round(100 * ok / n, 1), 'log_loss': round(ll, 4),
                'score_sets_juste_pct': round(100 * sj / len(s), 1) if s else None, 'n_sets': len(s)}

    def calibration(items, cle):
        """Point 9 : quand le favori est annoncé à 60 %, gagne-t-il 6 fois sur 10 ? (tranches de 10 points)"""
        out = []
        for lo in range(50, 100, 10):
            g = []
            for x in items:
                v = x.get(cle)
                if not v or x['gagnant'] not in ('home', 'away'):
                    continue
                pf = max(v['p_home'], 1 - v['p_home'])
                if lo <= 100 * pf < lo + 10 or (lo == 90 and pf >= 1):
                    g.append((pf, (v['p_home'] >= 0.5) == (x['gagnant'] == 'home')))
            if g:
                out.append({'tranche': f"{lo}–{lo + 10} %", 'n': len(g), 'prevu': round(100 * sum(p for p, _ in g) / len(g), 1),
                            'reel': round(100 * sum(w for _, w in g) / len(g), 1)})
        return out
    VERS = (('combinaison', 'combinaison'), ('simulation', 'simulation'), ('stats_seules', 'stats'), ('stats_plus_marche', 'marche'))
    depuis7 = (maintenant - dt.timedelta(days=7)).date().isoformat()
    L7 = [x for x in L if x['debut'] >= depuis7]
    doc = {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'pronostiques': len(vus), 'joues_avec_resultat': len(L),
           'tous': {k: bloc(L, c) for k, c in VERS},
           '7_derniers_jours': {k: bloc(L7, c) for k, c in VERS},
           'calibration': {k: calibration(L, c) for k, c in VERS},
           'par_circuit': {ci: {k: bloc([x for x in L if x.get('circuit') == ci], c) for k, c in VERS}
                           for ci in ('ATP', 'WTA', 'CH', 'ITF') if any(x.get('circuit') == ci for x in L)},
           'derniers': [{'debut': x['debut'], 'home': x['home'], 'away': x['away'], 'gagnant': x['gagnant'],
                         'combinaison': (x.get('combinaison') or {}).get('p_home'),
                         'simulation': (x.get('simulation') or {}).get('p_home'),
                         'stats': x['stats']['p_home'], 'marche': (x['marche'] or {}).get('p_home')}
                        for x in sorted(L, key=lambda x: x['debut'])[-30:]],
           'match_simule_contre_feuille': suivi_feuilles(racine, journal)}
    return doc


def score_reel(fi, inverse):
    """« 6-4 3-6 7-6 » du point de vue home du pronostic, depuis une feuille TennisApi ; None sinon."""
    a, b = (fi.get('score_home') or {}).get('sets') or [], (fi.get('score_away') or {}).get('sets') or []
    if not a or len(a) != len(b):
        return None
    if inverse:
        a, b = b, a
    return ' '.join(f"{x}-{y}" for x, y in zip(a, b))


def juger(v, gagnant, sets, score, jeux):
    """Ce qui était juste dans une version du pronostic."""
    if not v or v.get('p_home') is None:
        return None
    p = v['p_home']
    out = {'p_home': p, 'proba_du_vainqueur': round(p if gagnant == 'home' else 1 - p, 4),
           'vainqueur_juste': None if p == 0.5 else ((p > 0.5) == (gagnant == 'home'))}
    if sets and v.get('sets'):
        out['sets_prevus'] = max(v['sets'], key=v['sets'].get)
        out['sets_justes'] = out['sets_prevus'] == sets
        out['proba_des_sets_reels'] = v['sets'].get(sets)
    sc = [x[0] for x in v.get('scores_probables') or []]
    if sc:
        out['score_prevu'] = sc[0]
        if score:
            out['score_juste'] = sc[0] == score
            out['rang_du_score_reel'] = sc.index(score) + 1 if score in sc else None
    if jeux is not None and v.get('jeux_moyen') is not None:
        out['jeux_prevus'], out['ecart_jeux'] = v['jeux_moyen'], round(jeux - v['jeux_moyen'], 1)
    return out


def resoudre(racine, maintenant=None):
    """Chaque match du journal dont le résultat est connu : 1re prédiction, dernière avant le match,
    résultat réel (vainqueur, sets, score en jeux, feuille de stats), et le jugement de chaque version."""
    maintenant = maintenant or dt.datetime.utcnow()
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    journal, vus = [], set()
    try:
        for l in open(os.path.join(racine, LOG), encoding='utf-8'):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r['uid'] not in vus:
                vus.add(r['uid'])
                journal.append(r)
    except OSError:
        pass
    passes = [r for r in journal if dt.datetime.fromisoformat(r['debut']) < maintenant]
    if not passes:
        return []
    debut_min = (dt.date.fromisoformat(min(r['debut'] for r in passes)[:10]) - dt.timedelta(days=1)).isoformat()
    idx = FE.Index(FE.lire(racine, depuis=debut_min))
    inst = lire_instantanes(racine, depuis=debut_min)
    out = []
    for r in passes:
        d0 = dt.date.fromisoformat(r['debut'][:10])
        res, sens = NR.resultat(sr, d0, r['home'], r['away'])
        fi, inv = idx.trouver(r['debut'][:10], r['home'], r['away'])
        if fi is not None and str((fi.get('statut') or {}).get('texte') or '').lower() != 'ended':
            fi = None
        gagnant = sets = None
        if res:
            o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
            gagnant = o(res.get('match'))
            s1, s2 = o(res.get('set1')), o(res.get('set2'))
            if r.get('meilleur_des', 3) == 3 and s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and gagnant != s1):
                sets = ('2-0' if gagnant == 'home' else '0-2') if s1 == s2 else ('2-1' if gagnant == 'home' else '1-2')
        score = score_reel(fi, inv) if fi else None
        if gagnant not in ('home', 'away') and fi and fi.get('vainqueur') in (1, 2):
            gagnant = 'home' if (fi['vainqueur'] == 1) != inv else 'away'
        if gagnant not in ('home', 'away'):
            continue
        if score:
            ns = [tuple(int(v) for v in x.split('-')) for x in score.split()]
            gh, ga = sum(1 for a, b in ns if a > b), sum(1 for a, b in ns if b > a)
            if (gh > ga) == (gagnant == 'home'):
                sets = f"{gh}-{ga}"
            else:
                score = None                     # feuille incohérente avec le résultat : on ne garde pas le score
        jeux = sum(a + b for a, b in (tuple(int(v) for v in x.split('-')) for x in score.split())) if score else None
        feuille = FE.feuille_reelle(fi, inv) if fi else None
        avant = [x for x in inst.get(r['uid'], []) if x['passage'][:16] < r['debut'][:16]]
        dernier = avant[-1] if avant else None
        premier = r.get('detail') or {k: r.get(k) for k in VERSIONS}
        out.append({'uid': r['uid'], 'debut': r['debut'], 'home': r['home'], 'away': r['away'], 'tournoi': r['tournoi'],
                    'circuit': r.get('circuit'), 'pronostique_le': r.get('pronostique_le'),
                    'dernier_passage': dernier['passage'] if dernier else None, 'n_passages': len(avant),
                    'reel': {'gagnant': gagnant, 'sets': sets, 'score': score, 'jeux': jeux,
                             'feuille': feuille[0] if feuille else None},
                    'premier': {k: juger(premier.get(k), gagnant, sets, score, jeux) for k in VERSIONS},
                    'dernier': ({k: juger(dernier.get(k), gagnant, sets, score, jeux) for k in VERSIONS} if dernier else None),
                    'pin_cotes': r.get('pin_cotes')})
    out.sort(key=lambda x: x['debut'], reverse=True)
    return out


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    os.makedirs(os.path.join(racine, 'Tennis_Edge_Lab', 'live'), exist_ok=True)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    n = journaliser(racine, doc)
    ni = enregistrer_instantanes(racine, doc)
    b = bilan(racine)
    with open(os.path.join(racine, BILAN), 'w', encoding='utf-8') as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    R = resoudre(racine)
    with open(os.path.join(racine, RESULTATS), 'w', encoding='utf-8') as f:
        json.dump({'genere_le': doc['genere_le'], 'n': len(R), 'matchs': R}, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Enregistré : {ni} instantanés ({INSTANTANES}) · {len(R)} matchs joués prédit/réel ({RESULTATS})")
    t = b['tous']
    print(f"Pronostics : {len(doc['matchs'])} matchs dans les {HORIZON_H} h ({n} nouveaux au journal) · "
          f"bilan sur {b['joues_avec_resultat']} matchs joués : stats {t['stats_seules'].get('reussite_pct')} % · "
          f"marché {t['stats_plus_marche'].get('reussite_pct')} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
