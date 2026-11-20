#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recalage_stats.py — recalage des statistiques annoncées (aces, doubles fautes, % de 1res balles, breaks) par circuit
(04/11/2026, demande de Lucas, après le tableau « Statistiques annoncées : ce qui s'est passé »).

Constat (nos matchs du 28/10 au 04/11) : % de 1res balles annoncé trop bas sur les trois circuits (−4,7 pts ATP,
−3,5 WTA, −1,5 Challenger), fourchette des breaks trop large (90–93 % dedans au lieu de 80 %), doubles fautes ATP
trop larges (94 %). Ne change PAS la probabilité de victoire (ancrée sur la combinaison Elo + simulation) : seulement
les statistiques annoncées et leur fourchette 80 %.

Données : fiches figées (journal_pronostics/fiches : moyenne et fourchette p10–p90 annoncées au dernier pronostic)
reliées aux feuilles réelles (Tennis_Edge_Lab/live/pronostics_resultats.json). Une ligne = un joueur dans un match.

MÉTHODE, par circuit (ATP, WTA, CH) et par statistique :
  décalage δ = moyenne(réel − annoncé) × n / (n + 100)   (peu de cas : décalage réduit vers 0) ;
  largeur w : facteur appliqué aux deux demi-largeurs autour du centre de la fourchette, choisi sur la grille
  0,50 … 2,00 (pas 0,05) pour que la part du réel dans la fourchette recalée soit la plus proche de 80 % ;
  fourchette recalée = [centre + δ − w·(centre − p10) ; centre + δ + w·(p90 − centre)], bornée à 0 (et 100 pour
  le %) ; les comptes (aces, doubles fautes, breaks) sont arrondis à l'entier, le % au dixième.

RÈGLE FIXÉE LE 04/11/2026 AVANT TOUT CALCUL :
  chaque semaine, appris sur tous les matchs joués AVANT la dernière semaine complète (lundi → dimanche), jugé sur
  cette semaine-là : erreur de couverture = |part dans la fourchette − 80 %| moyennée sur les 12 cases
  (circuit × statistique) d'au moins 30 cas, et écart moyen |annoncé − réel| sur les mêmes cases.
  Gagnant si l'erreur de couverture baisse d'au moins 2 points ET l'écart moyen ne monte pas ET aucune case
  ne voit sa couverture s'éloigner de 80 % de plus de 5 points. Adopté après deux semaines gagnantes de suite
  (stabilite.py, série « recalage_stats »). Avant adoption : rien ne change sur le site.
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

STATS = ('aces', 'doubles_fautes', 'premiere_pct', 'breaks')
CIRCUITS = ('ATP', 'WTA', 'CH')
PRIOR = 100.0
GRILLE = [round(0.5 + 0.05 * i, 2) for i in range(31)]
CIBLE = 80.0
MIN_CAS = 30
SORTIE = os.path.join('simulateur', 'recalage_stats.json')
# 05/11/2026 (décision de Lucas) — ADOPTION DIRECTE des cases au biais net et stable chaque semaine (nos matchs suivis
# du 19/10 au 04/11, réel − annoncé, par joueur et par match) :
#   % de 1res balles ATP +3,8 / +3,8 / +4,0 pts (342 cas, z 11,4) ; WTA +6,8 / +3,3 / +2,2 (372, z 8,2) ;
#   aces ATP +0,6 / +1,1 / +0,8 (342, z 4,0) ; aces WTA −0,6 / −0,2 / −0,5 (372, z −3,2 : annoncés trop haut).
# Cause probable : les profils viennent de l'archive Sackmann, les feuilles réelles de TennisApi (comptage différent).
# 05/11/2026 — CONFIRMÉ sur les 211 matchs Challenger présents dans les DEUX sources (juin 2026) : mêmes points, mêmes
# aces, mais TennisApi compte +0,9 point de 1res balles de plus que Sackmann (dans 48 % des matchs) ; d'où l'ajout
# du Challenger (+1,1 pt sur nos matchs suivis, 952 cas, z 4,7 : le biais est un écart de mesure, pas du hasard).
# Les coefficients sont réappris à chaque mise à jour (apprendre, tous les matchs joués) ; repli figé si les données
# manquent. RETRAIT d'une case : deux semaines de suite (≥ 30 cas) où, sur la semaine jugée, l'écart moyen
# |annoncé − réel| avec recalage est PIRE que sans. Les autres cases restent soumises à la règle ci-dessus.
CASES_DIRECTES = (('ATP', 'premiere_pct'), ('WTA', 'premiere_pct'), ('CH', 'premiere_pct'), ('ATP', 'aces'), ('WTA', 'aces'))
# 11/11/2026 (paquet 225, décision de Lucas : « il faut améliorer ça ») — RECALAGE CASE PAR CASE, adoption directe avec
# règle de retrait. La règle d'ensemble ci-dessus échouait à cause d'UNE case (aces ATP : 82 % → 90 %), et bloquait
# les autres, nettement meilleures. Désormais chaque case (circuit × statistique) a sa VARIANTE en place :
#   « sans » (rien), « delta » (décalage seul) ou « complet » (décalage + largeur), apprise sur les matchs d'avant la
#   semaine jugée. RÈGLE (fixée le 11/11/2026), chaque lundi, sur la dernière semaine complète, case d'au moins 30 cas :
#   — on passe à la meilleure variante si elle rapproche la couverture de 80 % d'au moins 2 points par rapport à la
#     variante en place, sans augmenter l'écart moyen |annoncé − réel| ;
#   — une variante en place (autre que « sans ») qui fait PIRE que « sans » (couverture plus loin de 80 %, ou écart
#     moyen plus grand) deux semaines de suite est retirée (retour à « sans »).
# Point de départ (jugement de la semaine du 02/11, 2 920 cas — voir recalage_stats.json) : complet pour doubles fautes
# ATP (92 % → 80 %), breaks ATP (91 % → 76 %), % 1res balles ATP (74 % → 81 %), aces WTA (89 % → 85 %), % 1res balles
# WTA (67 % → 81 %), doubles fautes Challenger (90 % → 83 %), breaks Challenger (92 % → 80 %) ; delta pour % 1res balles
# Challenger (écart de mesure entre sources, confirmé le 05/11) ; sans pour aces ATP (le recalage l'élargissait trop),
# doubles fautes et breaks WTA, aces Challenger (aucun gain).
DEPART_CASES = {
    'ATP|doubles_fautes': 'complet', 'ATP|breaks': 'complet', 'ATP|premiere_pct': 'complet', 'ATP|aces': 'sans',
    'WTA|aces': 'complet', 'WTA|premiere_pct': 'complet', 'WTA|doubles_fautes': 'sans', 'WTA|breaks': 'sans',
    'CH|doubles_fautes': 'complet', 'CH|breaks': 'complet', 'CH|premiere_pct': 'delta', 'CH|aces': 'sans'}
DEPART_LE = '2026-11-11'
VARIANTES = ('sans', 'delta', 'complet')
REPLI_DIRECT = {'ATP': {'premiere_pct': {'delta': 2.98, 'largeur': 1.0}, 'aces': {'delta': 0.72, 'largeur': 1.0}},
                'WTA': {'premiere_pct': {'delta': 2.92, 'largeur': 1.0}, 'aces': {'delta': -0.30, 'largeur': 1.0}},
                'CH': {'premiere_pct': {'delta': 1.02, 'largeur': 1.0}}}


# 12/11/2026 (audit, paquet 237) — CASES RÉGLÉES SUR L'ARCHIVE (etude_statistiques_annoncees.py). Le recalage appris sur
# nos matchs repose sur quelques centaines de cas par case. L'étude a rejoué les statistiques annoncées sur l'archive
# (9 000 cas par case) : décalage et largeur appris sur 2019–2022, couverture entre 78 et 82 % sur 2023 → juin 2026.
# Ces coefficients ne remplacent ceux d'ici QUE pour les cases où, sur nos matchs suivis, ils ne font pas moins bien
# (recalage_stats_archive.json) : variante « archive », coefficients FIXES. RETRAIT (écrit avant) : sur nos cas joués
# depuis ARCHIVE_DEPUIS, dès 300 cas, si la couverture est plus loin de 80 % que sans recalage de plus de 5 points,
# la case revient à « sans » et à la règle hebdomadaire.
ARCHIVE = os.path.join('simulateur', 'recalage_stats_archive.json')
ARCHIVE_DEPUIS = '2026-11-12'
ARCHIVE_MIN_CAS, ARCHIVE_TOLERANCE = 300, 5.0


def coefs_archive(racine):
    """{'circuit|stat': {'delta', 'largeur'}} des cases réglées sur l'archive ; {} si le fichier manque."""
    try:
        with open(os.path.join(racine, ARCHIVE), encoding='utf-8') as f:
            doc = json.load(f)
        return {cle: {'delta': float(v['delta']), 'largeur': float(v['largeur'])} for cle, v in (doc.get('cases') or {}).items()}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def avec_archive(cases, arch):
    """Les cases réglées sur l'archive prennent la variante « archive », sauf celles que le suivi a retirées."""
    out = dict(cases or {})
    for cle in arch or {}:
        e = out.get(cle) or {}
        if e.get('archive_retiree') or e.get('variante') == 'archive':
            continue
        out[cle] = {'variante': 'archive', 'depuis': ARCHIVE_DEPUIS, 'semaines_pires': 0}
    return out


def suivi_archive(rows, c, k, coef):
    """Nos cas depuis ARCHIVE_DEPUIS pour cette case : nombre, couverture sans recalage et avec les coefficients de
    l'archive, et verdict de retrait."""
    R = [r for r in rows if r['c'] == c and r['k'] == k and r['jour'] >= ARCHIVE_DEPUIS]
    if not R:
        return {'cas': 0, 'retrait': False}
    sans = 100.0 * sum(r['p10'] <= r['reel'] <= r['p90'] for r in R) / len(R)
    avec = 100.0 * sum(lo <= r['reel'] <= hi for r in R for _, lo, hi in [recaler(coef, k, r['moy'], r['p10'], r['p90'])]) / len(R)
    return {'cas': len(R), 'couverture_sans': round(sans, 1), 'couverture_archive': round(avec, 1),
            'retrait': bool(len(R) >= ARCHIVE_MIN_CAS and abs(avec - CIBLE) > abs(sans - CIBLE) + ARCHIVE_TOLERANCE)}


# 12/11/2026 (audit, paquet 238) — EN SALLE OU EN PLEIN AIR (etude_premieres_balles_salle.py). En salle, le serveur passe
# plus de 1res balles et fait moins de doubles fautes que son profil d'ensemble ne l'annonce (ATP : +1,2 point et −0,5
# double faute, appris sur 2019–2022, jugés sur 2023 → juin 2026). Le décalage (salle_stats.json) s'applique AVANT le
# recalage appris ici, à l'affichage (vitrine.py) comme à l'apprentissage (lignes) : une fiche figée avant le 12/11 n'a
# pas le décalage dans ses valeurs, il lui est ajouté ici ; une fiche d'après le porte déjà (« salle_appliquee »).
# RETRAIT (écrit avant) : sur nos cas EN SALLE joués depuis SALLE_DEPUIS, dès 300 cas, si l'écart moyen |annoncé − réel|
# avec le décalage dépasse celui sans, le décalage de cette statistique est retiré (suivi_salle, clé « salle » du rapport).
SALLE = os.path.join('simulateur', 'salle_stats.json')
SALLE_DEPUIS = '2026-11-12'
SALLE_MIN_CAS = 300


def decalages_salle(racine, retires=None):
    """{circuit: {stat: {'salle': δ, 'plein_air': δ}}} ; {} si le fichier manque. retires : {'ATP|premiere_pct', …}."""
    try:
        with open(os.path.join(racine, SALLE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for c, d in (doc.get('decalages') or {}).items():
        for k, v in (d or {}).items():
            if f'{c}|{k}' not in (retires or ()):
                out.setdefault(c, {})[k] = {'salle': float(v.get('salle', 0.0)), 'plein_air': float(v.get('plein_air', 0.0))}
    return out


def salle_retiree(racine):
    """Statistiques dont le décalage « en salle » a été retiré par le suivi (rapport du lundi)."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            return {cle for cle, v in ((json.load(f).get('salle') or {}).get('cases') or {}).items() if (v or {}).get('retire')}
    except (OSError, ValueError):
        return set()


def decaler_salle(dec, c, k, salle, moy, p10, p90):
    """(moyenne, p10, p90) décalés selon salle (True) ou plein air (False) ; inchangés si salle est None ou sans décalage."""
    d = ((dec or {}).get(c) or {}).get(k)
    if not d or salle is None:
        return moy, p10, p90
    x = d['salle'] if salle else d['plein_air']
    if k == 'premiere_pct':
        f = lambda v: round(max(0.0, min(100.0, v + x)), 1)
        return f(moy), f(p10), f(p90)
    return round(max(0.0, moy + x), 2), float(round(max(0.0, p10 + x))), float(round(max(0.0, p90 + x)))


def decaler_feuille(dec, c, salle, fp, fq):
    """Feuille prévue et fourchette d'un match (deux joueurs), décalées. Renvoie (fp, fq, appliqué ?)."""
    if not (dec or {}).get(c) or salle is None or not fp or not fq:
        return fp, fq, False
    fp2, fq2 = [dict(j) for j in fp], [dict(j or {}) for j in fq]
    for i in range(min(len(fp2), len(fq2))):
        for k in dec[c]:
            m, q = fp2[i].get(k), fq2[i].get(k)
            if isinstance(m, (int, float)) and q and len(q) == 2:
                m2, lo, hi = decaler_salle(dec, c, k, salle, float(m), float(q[0]), float(q[1]))
                fp2[i][k], fq2[i][k] = m2, [lo, hi]
    return fp2, fq2, True


def salles_des_matchs(racine):
    """{(jour, joueur, joueur): en salle ?} d'après la surface des feuilles (« Hardcourt indoor »)."""
    import elo as E
    import feuilles as FE
    out = {}
    for r in FE.lire(racine):
        h, a, s = (r.get('home') or {}).get('nom'), (r.get('away') or {}).get('nom'), str(r.get('surface') or '')
        if h and a and s and s.lower() != 'none' and r.get('jour'):
            out[(str(r['jour']), *sorted((E.cle(h), E.cle(a))))] = 'indoor' in s.lower()
    return out


def salle_de_la_fiche(f, salles):
    """En salle ? — ce que la fiche a noté au pronostic, sinon la feuille du match (jour même, veille ou lendemain)."""
    d = f.get('dernier') or {}
    if d.get('en_salle') is not None:
        return bool(d['en_salle'])
    if not salles or not f.get('home') or not f.get('away') or not f.get('debut'):
        return None
    import elo as E
    cles = sorted((E.cle(f['home']), E.cle(f['away'])))
    try:
        j0 = dt.date.fromisoformat(str(f['debut'])[:10])
    except ValueError:
        return None
    for dj in (0, -1, 1):
        v = salles.get(((j0 + dt.timedelta(days=dj)).isoformat(), *cles))
        if v is not None:
            return v
    return None


def lignes(fiches, reels, salles=None, dec=None, sans_decalage=False):
    """[{jour, c, k, moy, p10, p90, reel, salle}] : une ligne par joueur, match et statistique. dec : décalages « en
    salle » ajoutés aux fiches qui ne les portent pas déjà ; sans_decalage=True : valeurs sans aucun décalage (suivi)."""
    out = []
    for uid, f in fiches.items():
        r, d = reels.get(uid) or {}, (f.get('dernier') or {})
        salle = salle_de_la_fiche(f, salles)
        # valeurs AVANT recalage quand il est en place (sinon on recalerait par-dessus le recalage)
        fp, fq, fr = d.get('feuille_brute') or d.get('feuille'), d.get('fourchette_brute') or d.get('fourchette'), r.get('feuille')
        c = f.get('circuit')
        if c not in CIRCUITS or not (fp and fq and fr) or len(fp) != 2 or len(fq) != 2 or len(fr) != 2:
            continue
        for i in (0, 1):
            for k in STATS:
                m, q, x = fp[i].get(k), (fq[i] or {}).get(k), fr[i].get(k)
                if isinstance(m, (int, float)) and isinstance(x, (int, float)) and q and len(q) == 2:
                    m, lo, hi = float(m), float(q[0]), float(q[1])
                    brut = (m, lo, hi)
                    deja = bool(d.get('salle_appliquee'))
                    if dec and not deja and not sans_decalage:
                        m, lo, hi = decaler_salle(dec, c, k, salle, m, lo, hi)
                    elif sans_decalage and deja and (d.get('salle_brut') or [{}, {}])[i].get(k):
                        m, lo, hi = (float(v) for v in d['salle_brut'][i][k])      # valeurs d'avant le décalage, gardées
                    out.append({'jour': str(f.get('debut'))[:10], 'c': c, 'k': k, 'moy': m, 'p10': lo, 'p90': hi,
                                'reel': float(x), 'salle': salle, 'avant_decalage': brut if not deja else None})
    return out


def suivi_salle(racine, ancien=None):
    """{'cases': {'ATP|premiere_pct': {cas en salle, écart avec, écart sans, retire}}} sur nos cas en salle joués
    depuis SALLE_DEPUIS. Un décalage retiré le reste (ancien)."""
    import apres_match as AM
    dec_tous = decalages_salle(racine)
    if not dec_tous:
        return {'cases': {}}
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            reels = {m['uid']: m.get('reel') for m in json.load(f).get('matchs') or [] if m.get('uid')}
    except (OSError, ValueError):
        reels = {}
    fiches, salles = AM.toutes_les_fiches(racine), salles_des_matchs(racine)
    avec, sans = lignes(fiches, reels, salles, dec_tous), lignes(fiches, reels, salles, None, sans_decalage=True)
    cases = {}
    for c, d in dec_tous.items():
        for k in d:
            cle = f'{c}|{k}'
            A = [r for r in avec if r['c'] == c and r['k'] == k and r['salle'] and r['jour'] >= SALLE_DEPUIS]
            S = [r for r in sans if r['c'] == c and r['k'] == k and r['salle'] and r['jour'] >= SALLE_DEPUIS]
            n = min(len(A), len(S))
            e1 = sum(abs(r['moy'] - r['reel']) for r in A) / len(A) if A else None
            e0 = sum(abs(r['moy'] - r['reel']) for r in S) / len(S) if S else None
            deja = bool((((ancien or {}).get('cases') or {}).get(cle) or {}).get('retire'))
            cases[cle] = {'cas_en_salle': n, 'ecart_avec': round(e1, 3) if e1 is not None else None,
                          'ecart_sans': round(e0, 3) if e0 is not None else None,
                          'retire': bool(deja or (n >= SALLE_MIN_CAS and e1 is not None and e0 is not None and e1 > e0))}
    return {'depuis': SALLE_DEPUIS, 'cases': cases}


def borner(k, lo, hi):
    haut = 100.0 if k == 'premiere_pct' else None
    lo, hi = max(0.0, lo), max(0.0, hi)
    if haut is not None:
        lo, hi = min(haut, lo), min(haut, hi)
    if k == 'premiere_pct':
        return round(lo, 1), round(hi, 1)
    return float(round(lo)), float(round(hi))


def recaler(coef, k, moy, p10, p90):
    """(moyenne, p10, p90) recalés ; coef = {'delta', 'largeur'} ou None (inchangé)."""
    if not coef:
        return moy, p10, p90
    d, w = coef.get('delta', 0.0), coef.get('largeur', 1.0)
    centre = (p10 + p90) / 2
    lo, hi = borner(k, centre + d - w * (centre - p10), centre + d + w * (p90 - centre))
    m = moy + d
    m = max(0.0, min(100.0, m)) if k == 'premiere_pct' else max(0.0, m)
    return round(m, 1), lo, hi


def apprendre(rows):
    """{circuit: {stat: {delta, largeur, n}}}."""
    out = {}
    for c in CIRCUITS:
        for k in STATS:
            R = [r for r in rows if r['c'] == c and r['k'] == k]
            if len(R) < MIN_CAS:
                continue
            n = len(R)
            delta = sum(r['reel'] - r['moy'] for r in R) / n * n / (n + PRIOR)
            meilleur = None
            for w in GRILLE:
                co = {'delta': delta, 'largeur': w}
                cov = 100.0 * sum(lo <= r['reel'] <= hi for r in R
                                  for _, lo, hi in [recaler(co, k, r['moy'], r['p10'], r['p90'])]) / n
                cle = (abs(cov - CIBLE), abs(w - 1.0))
                if meilleur is None or cle < meilleur[0]:
                    meilleur = (cle, w)
            out.setdefault(c, {})[k] = {'delta': round(delta, 3), 'largeur': meilleur[1], 'n': n}
    return out


def mesurer(rows, coefs=None):
    """{(c, k): {n, couverture, ecart}} et les moyennes sur les cases d'au moins 30 cas."""
    cases = {}
    for c in CIRCUITS:
        for k in STATS:
            R = [r for r in rows if r['c'] == c and r['k'] == k]
            if len(R) < MIN_CAS:
                continue
            co = ((coefs or {}).get(c) or {}).get(k)
            dans = ec = 0.0
            for r in R:
                m, lo, hi = recaler(co, k, r['moy'], r['p10'], r['p90'])
                dans += lo <= r['reel'] <= hi
                ec += abs(m - r['reel'])
            cases[f'{c}|{k}'] = {'n': len(R), 'couverture': round(100 * dans / len(R), 1), 'ecart': round(ec / len(R), 3)}
    if not cases:
        return {'cases': {}, 'erreur_couverture': None, 'ecart_moyen': None}
    return {'cases': cases,
            'erreur_couverture': round(sum(abs(v['couverture'] - CIBLE) for v in cases.values()) / len(cases), 2),
            'ecart_moyen': round(sum(v['ecart'] for v in cases.values()) / len(cases), 4)}


def juger(avant, apres):
    """Règle fixée le 04/11/2026 (voir en tête)."""
    if not avant['cases'] or not apres['cases']:
        return False, 'pas assez de cas'
    gain = avant['erreur_couverture'] - apres['erreur_couverture']
    pire = max(abs(apres['cases'][k]['couverture'] - CIBLE) - abs(avant['cases'][k]['couverture'] - CIBLE)
               for k in apres['cases'] if k in avant['cases'])
    ok = gain >= 2.0 and apres['ecart_moyen'] <= avant['ecart_moyen'] and pire <= 5.0
    return ok, (f"erreur de couverture {avant['erreur_couverture']} → {apres['erreur_couverture']} (gain {gain:+.2f}) ; "
                f"écart moyen {avant['ecart_moyen']} → {apres['ecart_moyen']} ; pire case {pire:+.1f} pts")


def derniere_semaine(aujourdhui):
    lundi = aujourdhui - dt.timedelta(days=aujourdhui.weekday())
    return lundi - dt.timedelta(days=7), lundi           # [lundi dernier ; ce lundi[


def charger(racine):
    import apres_match as AM
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            res = json.load(f)
    except (OSError, ValueError):
        res = {}
    reels = {m['uid']: m.get('reel') for m in res.get('matchs') or [] if m.get('uid')}
    dec = decalages_salle(racine, salle_retiree(racine))      # 12/11/2026 : appris sur les valeurs décalées « en salle »
    return lignes(AM.toutes_les_fiches(racine), reels, salles_des_matchs(racine) if dec else None, dec)


def coef_variante(co, variante):
    if not co or variante == 'sans':
        return None
    return {'delta': co['delta'], 'largeur': co['largeur'] if variante == 'complet' else 1.0}


def cases_en_place(doc):
    """{'c|k': {'variante', 'depuis', ...}} : l'état de la règle case par case (paquet 225), ou le point de départ."""
    cases = (doc or {}).get('cases')
    if cases:
        return cases
    return {k: {'variante': v, 'depuis': DEPART_LE, 'semaines_pires': 0} for k, v in DEPART_CASES.items()}


def decider_cases(ancien, appr, juge, fin, arch=None):
    """Règle case par case (fixée le 11/11/2026, voir DEPART_CASES). arch : cases réglées sur l'archive (12/11/2026)."""
    co = apprendre(appr)
    out = {}
    for c in CIRCUITS:
        for k in STATS:
            cle = f'{c}|{k}'
            prec = dict((ancien or {}).get(cle) or {'variante': 'sans', 'depuis': None, 'semaines_pires': 0})
            if cle in (arch or {}) and not prec.get('archive_retiree'):      # coefficients fixes, suivi cumulé
                s = suivi_archive(list(appr) + list(juge), c, k, arch[cle])
                if s['retrait']:
                    out[cle] = {'variante': 'sans', 'depuis': fin, 'semaines_pires': 0, 'archive_retiree': True,
                                'retiree': 'archive', 'cumul': s}
                else:
                    out[cle] = {'variante': 'archive', 'semaines_pires': 0, 'cumul': s,
                                'depuis': prec.get('depuis') if prec.get('variante') == 'archive' and prec.get('depuis') else ARCHIVE_DEPUIS}
                continue
            R = [r for r in juge if r['c'] == c and r['k'] == k]
            cc = (co.get(c) or {}).get(k)
            if len(R) < MIN_CAS or not cc:
                out[cle] = dict(prec, note=f'semaine : {len(R)} cas, inchangé')
                continue
            m = {}
            for v in VARIANTES:
                coef = coef_variante(cc, v)
                dans = sum(lo <= r['reel'] <= hi for r in R for _, lo, hi in [recaler(coef, k, r['moy'], r['p10'], r['p90'])])
                ec = sum(abs(recaler(coef, k, r['moy'], r['p10'], r['p90'])[0] - r['reel']) for r in R) / len(R)
                m[v] = (abs(100.0 * dans / len(R) - CIBLE), ec, round(100.0 * dans / len(R), 1))
            v0 = prec.get('variante') or 'sans'
            best = min(VARIANTES, key=lambda v: (m[v][0], m[v][1]))
            mesure = {v: {'couverture': m[v][2], 'ecart': round(m[v][1], 3)} for v in VARIANTES}
            if best != v0 and m[best][0] <= m[v0][0] - 2.0 and m[best][1] <= m[v0][1] + 1e-9:
                out[cle] = {'variante': best, 'depuis': fin, 'semaines_pires': 0, 'semaine': mesure}
                continue
            pire = v0 != 'sans' and (m[v0][0] > m['sans'][0] or m[v0][1] > m['sans'][1] + 1e-9)
            n_p = (prec.get('semaines_pires', 0) + 1) if pire else 0
            if n_p >= 2:
                out[cle] = {'variante': 'sans', 'depuis': fin, 'semaines_pires': 0, 'retiree': v0, 'semaine': mesure}
            else:
                out[cle] = dict(prec, semaines_pires=n_p, semaine=mesure)
    return out


def lire_coefs(racine):
    """Coefficients à appliquer sur le site. Depuis le 11/11/2026 (paquet 225) : la variante en place de CHAQUE case
    (cases_en_place), apprise sur tous les matchs joués."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    arch = coefs_archive(racine)
    cases = avec_archive(cases_en_place(doc), arch)
    try:
        appris = apprendre(charger(racine))
    except Exception:  # noqa: BLE001
        appris = {}
    out = {}
    for cle, e in cases.items():
        c, k = cle.split('|')
        co = (appris.get(c) or {}).get(k) or (REPLI_DIRECT.get(c) or {}).get(k)
        coef = coef_variante(co, e.get('variante')) if co else None
        if e.get('variante') == 'archive':                  # 12/11/2026 : coefficients fixes de l'archive
            coef = dict(arch[cle]) if cle in arch else None
        if coef:
            out.setdefault(c, {})[k] = coef
    return out or None


def etat_pour_le_site(racine):
    """{circuit: {stat: {variante, depuis, n, couverture}}} : la variante en place et la part du réel dans la fourchette
    AFFICHÉE depuis sa mise en place (fiches figées), pour le tableau « Statistiques annoncées » du site."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    cases = avec_archive(cases_en_place(doc), coefs_archive(racine))
    import apres_match as AM
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            reels = {m['uid']: m.get('reel') for m in json.load(f).get('matchs') or [] if m.get('uid')}
    except (OSError, ValueError):
        reels = {}
    F = AM.toutes_les_fiches(racine)
    out = {}
    for cle, e in cases.items():
        c, k = cle.split('|')
        depuis = e.get('depuis') or DEPART_LE
        n = dans = 0
        for uid, f in F.items():
            if f.get('circuit') != c or str(f.get('debut'))[:10] < depuis:
                continue
            q, r = (f.get('dernier') or {}).get('fourchette'), ((reels.get(uid) or {}).get('feuille'))
            if not q or not r or len(q) != 2 or len(r) != 2:
                continue
            for i in (0, 1):
                b, x = (q[i] or {}).get(k), (r[i] or {}).get(k)
                if b and len(b) == 2 and isinstance(x, (int, float)):
                    n += 1
                    dans += b[0] <= x <= b[1]
        sem = None
        v = e.get('variante')
        if e.get('semaine') and v in e['semaine']:
            sem = {'sans': e['semaine']['sans']['couverture'], 'avec': e['semaine'][v]['couverture']}
        elif v == 'complet':
            j = doc.get('jugement') or {}
            a, b = ((j.get('sans_recalage') or {}).get('cases') or {}).get(cle), ((j.get('avec_recalage') or {}).get('cases') or {}).get(cle)
            if a and b:
                sem = {'sans': a['couverture'], 'avec': b['couverture']}
        out.setdefault(c, {})[k] = {'variante': v, 'depuis': depuis, 'n': n, 'semaine_jugee': sem,
                                    'couverture': round(100.0 * dans / n, 1) if n else None}
    return out


def lire_coefs_ancien(racine):
    """Avant le 11/11/2026 : tous les coefficients s'ils sont adoptés par la règle hebdomadaire ; sinon les cases
    adoptées directement (CASES_DIRECTES), sauf celles retirées. Gardé pour mémoire."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    d = doc.get('decision') or {}
    if d.get('adopte') and d.get('coefs'):
        return d['coefs']
    retirees = {k for k, v in (doc.get('direct') or {}).items() if (v or {}).get('retire')}
    try:
        appris = apprendre(charger(racine))
    except Exception:  # noqa: BLE001 — repli figé
        appris = {}
    out = {}
    for c, k in CASES_DIRECTES:
        if f'{c}|{k}' in retirees:
            continue
        co = (appris.get(c) or {}).get(k) or (REPLI_DIRECT.get(c) or {}).get(k)
        if co:
            out.setdefault(c, {})[k] = co
    return out or None


def suivre_directes(ancien, appr, juge):
    """Retrait des cases directes : deux semaines pires de suite (≥ 30 cas) sur l'écart moyen."""
    co = apprendre(appr)
    out = {}
    for c, k in CASES_DIRECTES:
        cle, prec = f'{c}|{k}', (ancien or {}).get(f'{c}|{k}') or {}
        R = [r for r in juge if r['c'] == c and r['k'] == k]
        coef = (co.get(c) or {}).get(k) or (REPLI_DIRECT.get(c) or {}).get(k)
        if prec.get('retire'):
            out[cle] = prec
            continue
        if len(R) < MIN_CAS or not coef:
            out[cle] = dict(prec, cas_semaine=len(R), note='trop peu de cas : inchangé')
            continue
        sans = sum(abs(r['moy'] - r['reel']) for r in R) / len(R)
        avec = sum(abs(recaler(coef, k, r['moy'], r['p10'], r['p90'])[0] - r['reel']) for r in R) / len(R)
        pires = (prec.get('semaines_pires', 0) + 1) if avec > sans else 0
        out[cle] = {'cas_semaine': len(R), 'ecart_sans': round(sans, 3), 'ecart_avec': round(avec, 3),
                    'semaines_pires': pires, 'retire': pires >= 2}
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    aujourdhui = dt.date.fromisoformat(os.environ['RECALAGE_JOUR']) if os.environ.get('RECALAGE_JOUR') else dt.date.today()
    rows = charger(racine)
    debut, fin = derniere_semaine(aujourdhui)
    appr = [r for r in rows if r['jour'] < debut.isoformat()]
    juge = [r for r in rows if debut.isoformat() <= r['jour'] < fin.isoformat()]
    coefs_juges = apprendre(appr)
    avant, apres = mesurer(juge), mesurer(juge, coefs_juges)
    ok, raison = juger(avant, apres)
    verdict = {'adopte': ok, 'raison': f"semaine du {debut.isoformat()} ({len(juge)} cas) : {raison}",
               'coefs': apprendre([r for r in rows if r['jour'] < fin.isoformat()])}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("appris avant la dernière semaine complète, jugé sur elle ; gagnant si l'erreur de couverture "
                     "baisse d'au moins 2 points, l'écart moyen ne monte pas et aucune case ne s'éloigne de 80 % de "
                     "plus de 5 points ; adopté après deux semaines gagnantes de suite"),
           'cas': {'apprentissage': len(appr), 'jugement': len(juge), 'total': len(rows)},
           'jugement': {'sans_recalage': avant, 'avec_recalage': apres, 'coefs_juges': coefs_juges}}
    chemin = os.path.join(racine, SORTIE)
    try:
        ancien_doc = json.load(open(chemin, encoding='utf-8'))
    except (OSError, ValueError):
        ancien_doc = {}
    ancien = ancien_doc.get('decision') or {}
    doc['direct'] = suivre_directes(ancien_doc.get('direct'), appr, juge)
    # 11/11/2026 (paquet 225) : la règle case par case décide de ce qui s'applique sur le site
    try:                                                    # 12/11/2026 (paquet 240) : amplification des profils, suivi et retrait
        import profils_amplification as PA
        doc['amplification_profils'] = PA.suivi(appr + juge, PA.lire(racine).get('amplifications') or {},
                                                (ancien_doc.get('amplification_profils') or {}).get('retirees'))
    except Exception as e_:  # noqa: BLE001
        print(f'::warning::suivi de l\'amplification des profils non fait : {e_}')
    doc['salle'] = suivi_salle(racine, ancien_doc.get('salle'))      # 12/11/2026 : décalage « en salle », suivi et retrait
    arch = coefs_archive(racine)
    doc['cases'] = decider_cases(avec_archive(cases_en_place(ancien_doc), arch), appr, juge, fin.isoformat(), arch)
    if '--sans-decision' in argv:
        doc['decision'] = dict(ancien, verdict_semaine=verdict)
    else:
        import stabilite as ST
        etat_path = os.path.join(racine, 'simulateur', 'stabilite.json')
        etat = ST.lire(etat_path)
        doc['decision'] = ST.appliquer(etat, 'recalage_stats', ancien, verdict, params=('coefs',))
        ST.ecrire(etat, etat_path)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Recalage des statistiques annoncées : {verdict['raison']} → {doc['decision'].get('stabilite', '')}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
