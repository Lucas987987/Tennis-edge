#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_bilans_contexte.py — les « bilans par contexte » des autres sites prédisent-ils quelque chose ? (06/11/2026,
demande de Lucas après les fiches MatchUp : « bilan vitesse de court (rapide) », « % de victoires au tournoi »,
« bilan en WTA 250/500 »).

Archive Sackmann 2015 → juin 2026, ATP, WTA, Challenger, matchs complets sans abandon. Pour chaque match et chaque
joueur, son bilan PASSÉ dans le même contexte que le match :
  — VITESSE : courts de la même classe que celui du match (lent < 35, moyen 35–40, rapide ≥ 40 sur l'échelle CPI) ;
    classe tirée de l'ÉDITION PRÉCÉDENTE du tournoi (vitesse_courts.json), jamais de l'édition en cours ;
  — TOURNOI : ses matchs passés dans ce même tournoi (6 ans) ;
  — NIVEAU : ses matchs dans la même catégorie de tournoi (Grand Chelem, Masters, 250/500, Challenger…).
Deux mesures (fenêtre 3 ans, sauf tournoi 6 ans, jamais le jour même) :
  — « brut » (ce qu'affichent les sites) : (victoires − défaites) / 2 / (n + 10) ;
  — « ajusté » : Σ (résultat − probabilité Elo d'avant-match) / (n + 10) — ce qu'il a fait au-delà de son niveau.
Variable : mesure de A − mesure de B ; attendu = probabilité Elo (surface comprise) d'avant-match.

RÈGLE FIXÉE LE 06/11/2026, AVANT DE REGARDER LE RÉSULTAT (la même que set décisif et tie-breaks), par circuit, par
contexte et par mesure : β appris sur 2018–2022 ; RETENU si sur 2023 → juin 2026 la log loss baisse d'au moins 0,001
sur au moins 1 000 matchs ET β a le même signe sur les deux périodes. Le sous-cas « courts rapides » (demande de Lucas)
est jugé à part avec la même règle, sur les seuls matchs joués sur court rapide.
Usage : python simulateur/etude_bilans_contexte.py /tmp/sackmann [racine]
"""
import bisect
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_set_decisif as SD  # noqa: E402

DEBUT, COUPURE, FIN = SD.DEBUT, SD.COUPURE, SD.FIN
K_RAPPEL = 10.0
FENETRES = {'vitesse': 3 * 365, 'tournoi': 6 * 365, 'niveau': 3 * 365}
CONTEXTES = tuple(FENETRES)
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS, MESURES = SD.CIRCUITS, SD.MESURES
SORTIE = os.path.join(ICI, 'rapport_bilans_contexte.json')
_lg, _sg = SD._lg, SD._sg


def classe_vitesse(cpi):
    return None if cpi is None else 'lent' if cpi < 35 else 'moyen' if cpi < 40 else 'rapide'


def vitesse_avant(doc, circuit, tournoi, annee):
    """Classe du court d'après l'édition PRÉCÉDENTE du tournoi (sinon None)."""
    import vitesse_courts as VC
    ed = ((doc or {}).get('tournois') or {}).get(f'{circuit}|{VC.norme(tournoi)}') or {}
    v = ed.get(str(annee - 1))
    if not v:
        return None
    off = v.get('cpi_officiel')
    return classe_vitesse(off if off is not None else v.get('cpi_estime'))


class Historique:
    """joueur → contexte → liste triée (date, gagné, attendu)."""

    def __init__(self):
        self.h = collections.defaultdict(list)

    def ajouter(self, j, ctx, d, y, e):
        self.h[(j, ctx)].append((d, y, e))

    def mesures(self, j, ctx, d, fenetre):
        L = self.h.get((j, ctx), [])
        i0 = bisect.bisect_left(L, (d - dt.timedelta(days=fenetre),))
        i1 = bisect.bisect_left(L, (d,))
        X = L[i0:i1]
        n, v = len(X), sum(x[1] for x in X)
        return n, (v - (n - v)) / 2 / (n + K_RAPPEL), sum(x[1] - x[2] for x in X) / (n + K_RAPPEL)


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import vitesse_courts as VC
    try:
        with open(os.path.join(racine, 'simulateur', 'vitesse_courts.json'), encoding='utf-8') as f:
            vdoc = json.load(f)
    except (OSError, ValueError):
        vdoc = {}
    Mt = DN.charger(archive, 2015)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    k = E.cle
    el, H = E.Elo(), Historique()
    jour, attente, rows = None, [], []
    for m in Mt:
        d = m['date']
        if d != jour:
            for g, p, s, gc, ctxs, eg in attente:
                el.maj(g, p, s, gc, None)
                for c in ctxs:
                    H.ajouter(g, c, d_prec, 1, eg)
                    H.ajouter(p, c, d_prec, 0, 1 - eg)
            attente, jour = [], d
            d_prec = d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        eg = min(max(el.proba(g, p, s), 0.01), 0.99)
        ctxs = []
        if c in CIRCUITS and m.get('complet') and not m.get('abandon'):
            vit = vitesse_avant(vdoc, c, m.get('tournoi') or '', d.year)
            ctxs = [x for x in (('vitesse', vit) if vit else None,
                                ('tournoi', f"{c}|{VC.norme(m.get('tournoi') or '')}"),
                                ('niveau', f"{c}|{m.get('niveau') or '?'}")) if x]
            if DEBUT <= d < FIN and el.matchs(g) >= 10 and el.matchs(p) >= 10:
                a, b, ea, y = (g, p, eg, 1) if g < p else (p, g, 1 - eg, 0)
                r = {'d': d, 'c': c, 'q': ea, 'y': y, 'vitesse': vit}
                for ctx in ctxs:
                    na, ba, ja = H.mesures(a, ctx, d, FENETRES[ctx[0]])
                    nb, bb, jb = H.mesures(b, ctx, d, FENETRES[ctx[0]])
                    r[f'{ctx[0]}_brut'], r[f'{ctx[0]}_ajuste'] = ba - bb, ja - jb
                    r[f'{ctx[0]}_n'] = min(na, nb)
                rows.append(r)
        attente.append((g, p, s, m.get('niveau') == 'G', ctxs, eg))
    return rows


def juger_sous(R, x):
    av, ju = [r for r in R if r['d'] < COUPURE and x in r], [r for r in R if r['d'] >= COUPURE and x in r]
    if len(av) < 200 or not ju:
        return {'matchs': {'2018–2022': len(av), '2023 → juin 2026': len(ju)}, 'note': 'trop peu de matchs'}
    b1, b2 = SD.apprendre(av, x), SD.apprendre(ju, x)
    gain = SD.ll(ju) - SD.ll(ju, x, b1)
    forts = [r for r in ju if r.get(x.split('_')[0] + '_n', 0) >= 8 and abs(r[x]) >= 0.15]
    return {'matchs': {'2018–2022': len(av), '2023 → juin 2026': len(ju)},
            'beta_2018_2022': round(b1, 3), 'beta_2023_2026': round(b2, 3), 'gain_log_loss_juge': round(gain, 5),
            'retenue': bool(len(ju) >= MIN_JUGES and gain >= MARGE and b1 * b2 > 0),
            'gros_ecarts_juges': {
                'matchs': len(forts),
                'meilleur_bilan_gagne_pct': round(100 * sum((r['y'] if r[x] > 0 else 1 - r['y']) for r in forts)
                                                  / len(forts), 1) if forts else None,
                'attendu_pct': round(100 * sum((r['q'] if r[x] > 0 else 1 - r['q']) for r in forts)
                                     / len(forts), 1) if forts else None}}


def juger(rows):
    out = {}
    for c in CIRCUITS:
        R = [r for r in rows if r['c'] == c]
        bloc = {}
        for ctx in CONTEXTES:
            bloc[ctx] = {m: juger_sous(R, f'{ctx}_{m}') for m in MESURES}
        bloc['courts_rapides'] = {m: juger_sous([r for r in R if r['vitesse'] == 'rapide'], f'vitesse_{m}')
                                  for m in MESURES}
        out[c] = bloc
    return out


def main(argv):
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit, contexte et mesure : β appris 2018–2022 ; retenu si −0,001 de log loss sur ≥ 1 000 "
                     "matchs 2023 → juin 2026 et β de même signe sur les deux périodes ; courts rapides jugés à part"),
           'matchs': len(rows), 'circuits': juger(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, b in doc['circuits'].items():
        for ctx, v in b.items():
            for m, r in v.items():
                print(c, ctx, m, r.get('matchs'), r.get('gain_log_loss_juge'), r.get('beta_2018_2022'),
                      r.get('beta_2023_2026'), 'RETENU' if r.get('retenue') else '—', r.get('gros_ecarts_juges'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
