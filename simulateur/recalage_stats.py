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
#   aces ATP +0,6 / +1,1 / +0,8 (342, z 4,0).
# Cause probable : les profils viennent de l'archive Sackmann, les feuilles réelles de TennisApi (comptage différent).
# Les coefficients sont réappris à chaque mise à jour (apprendre, tous les matchs joués) ; repli figé si les données
# manquent. RETRAIT d'une case : deux semaines de suite (≥ 30 cas) où, sur la semaine jugée, l'écart moyen
# |annoncé − réel| avec recalage est PIRE que sans. Les autres cases restent soumises à la règle ci-dessus.
CASES_DIRECTES = (('ATP', 'premiere_pct'), ('WTA', 'premiere_pct'), ('ATP', 'aces'))
REPLI_DIRECT = {'ATP': {'premiere_pct': {'delta': 2.98, 'largeur': 1.0}, 'aces': {'delta': 0.72, 'largeur': 1.0}},
                'WTA': {'premiere_pct': {'delta': 2.92, 'largeur': 1.0}}}


def lignes(fiches, reels):
    """[{jour, c, k, moy, p10, p90, reel}] : une ligne par joueur, match et statistique."""
    out = []
    for uid, f in fiches.items():
        r, d = reels.get(uid) or {}, (f.get('dernier') or {})
        # valeurs AVANT recalage quand il est en place (sinon on recalerait par-dessus le recalage)
        fp, fq, fr = d.get('feuille_brute') or d.get('feuille'), d.get('fourchette_brute') or d.get('fourchette'), r.get('feuille')
        c = f.get('circuit')
        if c not in CIRCUITS or not (fp and fq and fr) or len(fp) != 2 or len(fq) != 2 or len(fr) != 2:
            continue
        for i in (0, 1):
            for k in STATS:
                m, q, x = fp[i].get(k), (fq[i] or {}).get(k), fr[i].get(k)
                if isinstance(m, (int, float)) and isinstance(x, (int, float)) and q and len(q) == 2:
                    out.append({'jour': str(f.get('debut'))[:10], 'c': c, 'k': k, 'moy': float(m),
                                'p10': float(q[0]), 'p90': float(q[1]), 'reel': float(x)})
    return out


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
    return lignes(AM.toutes_les_fiches(racine), reels)


def lire_coefs(racine):
    """Coefficients à appliquer sur le site : tous s'ils sont adoptés par la règle hebdomadaire ; sinon les cases
    adoptées directement (CASES_DIRECTES), sauf celles retirées."""
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
