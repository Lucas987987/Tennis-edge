#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pistes_common.py — socle partagé des études de pistes (gel 2026-08-25).

Conventions non négociables, héritées des leçons du projet :
- AUCUN point in-play : toute valeur est coupée à commence_time (le look-ahead
  a déjà coûté 6 corrections) ;
- Wilson pour tout intervalle, refus de conclure sous n=30 ;
- le témoin est le taux de base de la POPULATION concernée, jamais 50 % ;
- une lecture vide s'annonce à voix haute, jamais en silence.
"""
import glob
import gzip
import json
import math
import os


def wilson(k, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - m) / d, (c + m) / d


def _ouvrir(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def iter_hist(market='book'):
    """Itère les lignes (match×book) des partitions hist, gz inclus."""
    fichiers = sorted(glob.glob(f'parts/hist_{market}_*.jsonl')
                      + glob.glob(f'parts/hist_{market}_*.jsonl.gz'))
    if not fichiers:
        print(f"⚠️ iter_hist('{market}') : aucune partition — étude vide.")
    for f in fichiers:
        with _ouvrir(f) as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    yield json.loads(ligne)
                except json.JSONDecodeError:
                    continue


def courbes_par_uid(book, market='book'):
    """{uid: enregistrement} pour UN book ; en cas de doublon, garde la
    dernière version lue (la plus proche du closing réel)."""
    out = {}
    for r in iter_hist(market):
        if r.get('book') == book and r.get('uid'):
            out[r['uid']] = r
    return out


def ts_norm(t):
    return str(t or '').replace('Z', '')[:19]


def val_at(curve, ts, commence=None, champ=1):
    """Dernière valeur du champ (1=cote, 2=limite) AVANT ts, et jamais après
    commence_time. Renvoie None si rien d'antérieur — le silence interdit,
    c'est l'appelant qui décide quoi en dire."""
    coupure = ts_norm(ts)
    fin = ts_norm(commence) if commence else '9999'
    coupure = min(coupure, fin)
    out = None
    for pt in curve or []:
        t = ts_norm(pt[0])
        if t > coupure:
            break
        try:
            v = float(pt[champ])
            if champ != 1 or v > 1:
                out = v
        except (TypeError, ValueError, IndexError):
            continue
    return out


def closing_prematch(curve, commence):
    return val_at(curve, '9999', commence, champ=1)


def charge_moves():
    """moves_detail_hist.csv -> liste de dicts typés (CLV, lead, mag...)."""
    import csv
    out = []
    if not os.path.exists('moves_detail_hist.csv'):
        print('⚠️ moves_detail_hist.csv absent — études sur moves vides.')
        return out
    lecteur = csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8'))
    # GARDE DE VERSION (12/09/2026). Avant ce jour, `mag_cote_pct` était
    # calculée sur pin_close : elle contenait la clôture. Les pistes qui
    # segmentent par ampleur (P5 retournements, P1 limites) tournaient donc
    # sur un critère indisponible à l'instant du pari, ce qui produisait des
    # écarts spectaculaires (45 % vs 82 % de CLV>0) qui s'effondrent une fois
    # l'ampleur mesurée à la détection. Un CSV sans la colonne _POSTHOC est
    # antérieur au correctif : on REFUSE de le lire plutôt que d'en tirer les
    # anciens chiffres sans que personne ne le voie.
    if 'mag_cote_pct_POSTHOC' not in (lecteur.fieldnames or []):
        print('❌ moves_detail_hist.csv antérieur au correctif du 12/09/2026 '
              '(colonne mag_cote_pct_POSTHOC absente) : `mag_cote_pct` y '
              'contient la clôture. Relancer move_audit.py avant toute étude.')
        return out
    for r in lecteur:
        try:
            out.append({
                'uid': r['uid'], 'tour': r.get('tour', ''),
                'date': r.get('date', ''),
                # ampleur À LA DÉTECTION depuis le 12/09/2026 (la garde
                # ci-dessus certifie qu'on lit bien la version causale)
                'mag': float(r['mag_cote_pct']),
                'lead_min': float(r['lead_min']),
                'clv': float(r['clv_book_pct']),
                'entry_book': r.get('entry_book', ''),
            })
        except (TypeError, ValueError, KeyError):
            continue
    return out


# CORRIGÉ LE 12/09/2026. Les Grands Chelems ne portent aucun préfixe
# ATP/WTA dans les libellés du fournisseur ('US Open Men Singles',
# 'Wimbledon Men Singles', 'French Open Men Singles') : ils tombaient tous
# dans 'autre'. Le trou existe depuis l'origine ; il est devenu visible
# quand l'US Open a dominé la population -- 167 moves sur 180 en 'autre'
# après le 26/08, soit une piste entière illisible.
#
# Ils prennent leur PROPRE segment plutôt que d'être versés dans ATP/WTA :
# un Grand Chelem est structurellement différent d'un ATP 250 (profondeur
# de marché, format), et les mélanger recréerait l'hétérogénéité silencieuse
# que cette piste cherche justement à mesurer. Hommes et femmes sont ici
# regroupés pour tenir le n>=30 ; à séparer si le volume le permet.
#
# CE CORRECTIF NE TOUCHE PAS LE PROTOCOLE GELÉ le 25/08 : la règle
# 'Challenger' est inchangée, et le témoin global porte sur TOUS les moves.
# L'hypothèse pré-spécifiée (Challengers moins efficients vs témoin global)
# se teste exactement comme avant. Seule la ventilation descriptive gagne
# un segment. Pas de nouveau gel nécessaire.
GRANDS_CHELEMS = ('US Open', 'Wimbledon', 'French Open', 'Australian Open')


def segment_circuit(tour):
    t = tour or ''
    if 'Challenger' in t or t.startswith('CH'):
        return 'Challenger'
    if any(gc in t for gc in GRANDS_CHELEMS):
        return 'Grand Chelem'
    if 'WTA' in t:
        return 'WTA'
    if 'ATP' in t:
        return 'ATP'
    return 'autre'


def libelles_non_classes(moves):
    """Libellés tombant dans 'autre', avec leur effectif.

    'autre' est un fourre-tout muet : tant que personne ne regarde ce qu'il
    contient, un libellé non reconnu y dort sans que rien ne le signale --
    c'est exactement ce qui est arrivé aux Grands Chelems. Les études qui
    segmentent affichent désormais ce contenu, pour que le prochain libellé
    inconnu se voie au premier rapport hebdo et pas trois semaines plus tard.
    """
    compte = {}
    for m in moves:
        if segment_circuit(m.get('tour')) == 'autre':
            lab = m.get('tour') or '(vide)'
            compte[lab] = compte.get(lab, 0) + 1
    return sorted(compte.items(), key=lambda kv: -kv[1])


def temoin(moves):
    """(p0, n) : taux de base CLV>0 de la population passée en argument —
    l'étalon se calcule sur LA population étudiée (leçon du seuil adaptatif)."""
    n = len(moves)
    if not n:
        return 0.5, 0
    return sum(1 for m in moves if m['clv'] > 0) / n, n


def entete(titre, gel='2026-08-25'):
    print('=' * 62)
    print(f'{titre}')
    print(f'(exploratoire, protocole gelé le {gel} — voir frozen_pistes.json ;')
    print(' n<30 = suivi sans conclusion ; témoin = population concernée)')
    print('=' * 62)
