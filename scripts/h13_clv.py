#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h13_clv.py — enrichit les signaux H13 avec leur CLV, une fois les matchs joués.

    signaux (h13_signal_log.jsonl)  +  courbes  +  résultats
        -> h13_clv_detail.csv

POURQUOI CE SCRIPT EXISTE

h13_signal.py enregistre la cote d'ENTRÉE, mais pas la clôture : au moment
où il alerte, elle n'existe pas encore. Sans elle, le seul indicateur
disponible était le ROI — et à 5 signaux par jour, le ROI ne dira rien avant
trois mois (300 paris pour que l'intervalle exclue le seuil de rentabilité).

Le CLV, lui, se stabilise beaucoup plus vite : mesuré sur l'historique, il
tranche à quelques centaines d'observations là où le ROI en demande des
milliers. C'est l'indicateur avancé, et il manquait.

Mesuré le 09/09 sur les 15 premiers signaux dénoués : ROI -37,7 %, IC95
[-90,6 ; +15,3]. L'intervalle contient largement le seuil de rentabilité :
ce chiffre ne dit rien. Le CLV aurait déjà commencé à parler.

DEUX CLV SONT CALCULÉS, et ils ne disent pas la même chose :

  clv_book_pct  prix d'entrée vs clôture DU MÊME BOOK.
                Mesure le retard capté sur ce book. C'est la métrique
                historique du projet (moves_detail_hist.csv).

  clv_pin_pct   prix d'entrée vs clôture PINNACLE.
                Mesure la valeur contre la meilleure estimation disponible.
                C'est la plus proche d'une espérance, mais elle compare des
                prix de books différents — dont les marges diffèrent de 3,2 %
                (coolbet) à 11,6 % (unibet.fr).

Aucun des deux n'est une espérance de gain : le premier ignore la marge, le
second compare des marges différentes. Ils servent à voir si le signal capte
un vrai décalage, pas à prédire un rendement.

Env : CURVES (déf. book_curves.jsonl), LOG, OUT, SET_RESULTS.
"""
import os
import sys
import csv
import json
import re
import unicodedata
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov      # noqa: E402

CURVES = os.environ.get('CURVES', 'book_curves.jsonl')
LOG = os.environ.get('LOG', 'h13_signal_log.jsonl')
OUT = os.environ.get('OUT', 'h13_clv_detail.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
SHARP = os.environ.get('SHARP', 'pinnacle')



def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]', '', s.lower())


def _deduire_side(uid, joueur):
    """'home'/'away' à partir du uid 'AAAA-MM-JJ_home_away', ou None.

    Ne tranche QUE si le nom colle d'un seul côté. Un nom qui matche les
    deux extrémités (homonymes, noms courts contenus l'un dans l'autre)
    renvoie None : mieux vaut perdre l'observation que l'inverser.
    """
    if not uid or not joueur or len(uid) < 12:
        return None
    u, j = _norm(uid[11:]), _norm(joueur)
    if not j:
        return None
    d, f = u.startswith(j), u.endswith(j)
    if d and not f:
        return 'home'
    if f and not d:
        return 'away'
    return None


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
    except (ValueError, TypeError):
        return None


def _pts(seq):
    out = []
    for p in (seq or []):
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            t = _dt(p[0])
            try:
                v = float(p[1])
            except (TypeError, ValueError):
                continue
            if t and v > 1:
                out.append((t, v))
    out.sort()
    return out


def _avant(serie, t):
    """Dernière valeur À t ou avant. La clôture est le dernier point AVANT le
    coup d'envoi : 96 % des courbes se prolongent en live (mesuré le 09/09),
    et prendre le dernier point tout court donnerait un prix in-play — erreur
    qui produisait un CLV médian de -73 % avant correction."""
    v = None
    for tt, o in serie:
        if tt <= t:
            v = o
        else:
            break
    return v


def charger_signaux():
    S = []
    try:
        for ligne in open(LOG, encoding='utf-8'):
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                S.append(json.loads(ligne))
            except ValueError:
                continue
    except OSError:
        print(f"  {LOG} absent.")
    return S


def charger_courbes(uids):
    """{uid: {book: {'h': [...], 'a': [...]}}} — limité aux uid utiles."""
    G = {}
    try:
        lignes = ov.open_curves(CURVES)
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        return G
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        u, b = r.get('uid'), r.get('book')
        if u not in uids or not b:
            continue
        h, a = _pts(r.get('home_curve')), _pts(r.get('away_curve'))
        if h and a:
            G.setdefault(u, {})[b] = {'h': h, 'a': a,
                                      'ct': _dt(r.get('commence_time'))}
    return G


def main():
    S = charger_signaux()
    if not S:
        return 0
    uids = {x.get('uid') for x in S if x.get('uid')}
    G = charger_courbes(uids)
    try:
        RES = json.load(open(SET_RESULTS, encoding='utf-8'))
    except (OSError, ValueError):
        RES = {}

    lignes, n_sans_courbe = [], 0
    for x in S:
        u = x.get('uid')
        side, deduit = x.get('side'), ''
        if not side:
            # Signaux d'avant le 09/09 : `side` n'était pas enregistré.
            # On le déduit UNIQUEMENT si c'est sans ambiguïté, et on le
            # TRACE dans la colonne side_deduit : une déduction silencieuse
            # se tromperait un jour sur un homonyme sans qu'on le sache.
            side = _deduire_side(u, x.get('joueur'))
            if not side:
                continue
            deduit = 'oui'
        books = G.get(u)
        if not books:
            n_sans_courbe += 1
            continue
        ct = next((v['ct'] for v in books.values() if v.get('ct')), None)
        if not ct:
            continue
        cle = 'h' if side == 'home' else 'a'
        cote = x.get('cote')
        book = x.get('book')

        sb = books.get(book)
        clot_book = _avant(sb[cle], ct) if sb else None
        pin = books.get(SHARP)
        clot_pin = _avant(pin[cle], ct) if pin else None

        g = (RES.get(u) or {}).get('match')
        gagne = None if g not in ('home', 'away') else (g == side)
        lignes.append({
            'date': str(x.get('signale_le'))[:10], 'side_deduit': deduit,
            'uid': u, 'joueur': x.get('joueur'), 'side': side,
            'book': book, 'tournoi': x.get('tournoi'),
            'cote': cote, 'ampleur_pts': x.get('ampleur_pts'),
            'lead_min': x.get('lead_min'),
            'cloture_book': clot_book, 'cloture_pin': clot_pin,
            'clv_book_pct': (round(100 * (cote / clot_book - 1), 2)
                             if clot_book else None),
            'clv_pin_pct': (round(100 * (cote / clot_pin - 1), 2)
                            if clot_pin else None),
            'gagne': '' if gagne is None else ('oui' if gagne else 'non'),
            'pnl': ('' if gagne is None
                    else round((cote - 1) if gagne else -1, 2)),
        })

    cols = ['date', 'uid', 'joueur', 'side', 'side_deduit', 'book',
            'tournoi', 'cote',
            'ampleur_pts', 'lead_min', 'cloture_book', 'cloture_pin',
            'clv_book_pct', 'clv_pin_pct', 'gagne', 'pnl']
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(lignes)

    avec = [r for r in lignes if r['clv_book_pct'] is not None]
    print(f"H13 CLV — {len(S)} signaux · {len(lignes)} exploitables · "
          f"{len(avec)} avec clôture -> {OUT}")
    if n_sans_courbe:
        print(f"  {n_sans_courbe} sans courbe (match trop récent ou "
              f"partition archivée)")
    if avec:
        import statistics as st
        cb = [r['clv_book_pct'] for r in avec]
        k = sum(1 for v in cb if v > 0)
        print(f"  CLV vs clôture book : médian {st.median(cb):+.2f} % · "
              f"positif {k}/{len(cb)} = {100 * k / len(cb):.1f} %")
        cp = [r['clv_pin_pct'] for r in avec if r['clv_pin_pct'] is not None]
        if cp:
            print(f"  CLV vs clôture Pinnacle : médian {st.median(cp):+.2f} %")
    return 0


if __name__ == '__main__':
    sys.exit(main())
