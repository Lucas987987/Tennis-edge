#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_dynamique.py — des statistiques qui ÉVOLUENT DANS LE TEMPS (22/10/2026, point 3).

Aujourd'hui, le service et le retour de chaque joueur (ajustés au niveau des adversaires)
pèsent chaque match selon son ancienneté, demi-vie 1 an : un joueur qui progresse depuis
trois mois est vu avec retard. Le meilleur modèle point par point publié (Ingram) laisse
au contraire les compétences dériver semaine après semaine.

Variantes (ajustement.py) :
  fond_240 / fond_365 (actuel) / fond_730 : demi-vie du niveau de fond ;
  fond_365+recent_45 / fond_365+recent_90 : niveau de fond + DÉRIVE RÉCENTE (dernière année,
      demi-vie 45 ou 90 jours, écarts au fond ramenés vers 0 par le même prior).

Règle fixée AVANT les résultats :
  1. CHOIX sur 2023 seulement : ajustements au 1er janvier, mai, septembre 2023, chacun jugé
     sur la vraisemblance des points des 4 mois suivants (comme le prior N0) ;
  2. JUGEMENT de la variante choisie contre l'actuelle sur les matchs ATP/WTA du 01/01/2024
     au 01/02/2026 qui ont une feuille complète (niveau de fond refait chaque mois, dérive
     récente toutes les 2 semaines — en direct, tout est refait toutes les 6 heures) :
     adoptée si la simulation pure trouve mieux le vainqueur (log loss plus basse) ET si
     les points sont mieux prédits (vraisemblance meilleure).
Sortie : simulateur/rapport_dynamique.json ; décision dans simulateur/choix_simulation.json
(clé « dynamique »), lue ensuite par profils_service, facteurs et backtest_match_simule.

Usage : python simulateur/etude_dynamique.py <archive Sackmann>
"""
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import match_simule as S  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_dynamique.json')
CHOIX = os.path.join(ICI, 'choix_simulation.json')
SIGMA = 0.15
VARIANTES = {'fond_240': {'demi_vie_fond': 240}, 'fond_365': {'demi_vie_fond': 365}, 'fond_730': {'demi_vie_fond': 730},
             'fond_365+recent_45': {'demi_vie_fond': 365, 'demi_vie_recent': 45},
             'fond_365+recent_90': {'demi_vie_fond': 365, 'demi_vie_recent': 90}}
ACTUELLE = 'fond_365'
DATES_CHOIX = [dt.date(2023, 1, 1), dt.date(2023, 5, 1), dt.date(2023, 9, 1)]
PAS_RECENT_J = 14


def _fin4(d):
    return (d.replace(day=1) + dt.timedelta(days=125)).replace(day=1)


def choisir(M, n0, journal=print, variantes=VARIANTES, dates=DATES_CHOIX):
    """{variante: −log-vraisemblance moyenne par essai, 2023} ; le niveau de fond 365 j est partagé."""
    scores, fonds = {}, {}
    for nom, v in variantes.items():
        L = []
        for d in dates:
            h = v['demi_vie_fond']
            if (h, d) not in fonds:
                fonds[(h, d)] = AJ.ajuster(M, d, E.cle, n0=n0, demi_vie=h)
            A = fonds[(h, d)]
            if v.get('demi_vie_recent'):
                A = AJ.ajuster_recent(M, d, E.cle, A, n0=n0, demi_vie=v['demi_vie_recent'])
            x = AJ.log_vraisemblance(A, M, d, _fin4(d), E.cle)
            if x is not None:
                L.append(x)
        scores[nom] = sum(L) / len(L) if L else float('inf')
        journal(f"  2023 · {nom:<20} {scores[nom]:.5f}")
    return min(scores, key=scores.get), scores


def points(A, m, cle=E.cle):
    """(−log-vraisemblance, essais) des composantes d'un match prédites par A."""
    d = m['detail']
    a, b = cle(m['nom_g']), cle(m['nom_p'])
    tot, n_tot = 0.0, 0
    for srv, ret, det, dadv in ((a, b, d['w'], d['l']), (b, a, d['l'], d['w'])):
        t = A.taux(srv, ret, m['circuit'], m['surface'])
        for c, (n, k) in AJ.essais(det, dadv).items():
            if n > 0:
                p = min(max(t[c], 1e-6), 1 - 1e-6)
                tot -= k * math.log(p) + (n - k) * math.log(1 - p)
                n_tot += n
    return tot, n_tot


class Suivi:
    """Ajustements refaits au fil du temps pour une variante (fond chaque mois, récent toutes les 2 semaines)."""

    def __init__(self, M, n0, v):
        self.M, self.n0, self.v = M, n0, v
        self.fond = self.rec = None
        self.mois = self.jour_rec = None

    def a_la_date(self, d):
        m0 = d.replace(day=1)
        if self.mois != m0:
            self.fond = AJ.ajuster(self.M, m0, E.cle, n0=self.n0, depart=self.fond, tours=6 if self.fond is None else 2,
                                   demi_vie=self.v['demi_vie_fond'])
            self.mois = m0
            self.jour_rec = None
        if not self.v.get('demi_vie_recent'):
            return self.fond
        if self.jour_rec is None or (d - self.jour_rec).days >= PAS_RECENT_J:
            prec = self.rec.recent if self.rec is not None and self.jour_rec is not None else None
            self.rec = AJ.ajuster_recent(self.M, d, E.cle, self.fond, n0=self.n0, demi_vie=self.v['demi_vie_recent'],
                                         depart=prec, tours=4 if prec is None else 2)
            self.jour_rec = d
        return self.rec


def juger(M, n0, candidate, journal=print):
    """Simulation pure (limite exacte) et vraisemblance des points, actuelle contre candidate."""
    elig = [m for m in M if BP.DEBUT_A <= m['date'] < BP.FIN_A and m['circuit'] in ('ATP', 'WTA')
            and m.get('detail') and m['complet']]
    suivis = {ACTUELLE: Suivi(M, n0, VARIANTES[ACTUELLE]), candidate: Suivi(M, n0, VARIANTES[candidate])}
    acc = {k: {'ll': 0.0, 'ok': 0.0, 'n': 0, 'pts': 0.0, 'essais': 0} for k in suivis}
    t0 = time.time()
    for k_m, m in enumerate(elig):
        sg = 3 if m['bo'] == 5 else 2
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        for nom, su in suivis.items():
            A = su.a_la_date(m['date'])
            cg = S.composantes_ajustees(A, g, p, m['circuit'], m['surface'])
            cp = S.composantes_ajustees(A, p, g, m['circuit'], m['surface'])
            pv = min(max(S.victoire_pure(cg, cp, sg, SIGMA), 1e-6), 1 - 1e-6)
            x, n = points(A, m)
            a = acc[nom]
            a['ll'] -= math.log(pv)
            a['ok'] += 1.0 if pv > 0.5 else (0.5 if pv == 0.5 else 0.0)
            a['n'] += 1
            a['pts'] += x
            a['essais'] += n
        if k_m % 1000 == 999:
            journal(f"  {k_m + 1} matchs jugés ({round(time.time() - t0)} s)")
    return {k: {'n': a['n'], 'log_loss_vainqueur': round(a['ll'] / a['n'], 5) if a['n'] else None,
                'reussite_pct': round(100 * a['ok'] / a['n'], 2) if a['n'] else None,
                'points_log_vraisemblance': round(a['pts'] / a['essais'], 6) if a['essais'] else None}
            for k, a in acc.items()}


def main(argv):
    t0 = time.time()
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    try:
        with open(CHOIX, encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    n0 = float(choix.get('n0') or AJ.N0)
    print(f"Sackmann : {len(M)} matchs · prior N0 = {n0:g}", flush=True)
    print("Choix sur 2023 (vraisemblance des points des 4 mois suivants) :", flush=True)
    best, scores = choisir(M, n0)
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("Variante choisie sur 2023 seulement ; adoptée si, sur les matchs ATP/WTA 2024 → 01/02/2026, la "
                     "simulation pure trouve mieux le vainqueur (log loss plus basse) ET les points sont mieux prédits."),
           'choix_2023': {k: round(v, 6) for k, v in scores.items()}, 'variante_choisie': best}
    if best == ACTUELLE:
        rap.update(adopte=False, raison="la variante actuelle (demi-vie 1 an, sans dérive récente) reste la meilleure sur 2023")
    else:
        print(f"Jugement 2024 → 2026 : {best} contre {ACTUELLE}", flush=True)
        J = juger(M, n0, best)
        a, c = J[ACTUELLE], J[best]
        ok = c['log_loss_vainqueur'] < a['log_loss_vainqueur'] and c['points_log_vraisemblance'] < a['points_log_vraisemblance']
        rap.update(jugement=J, adopte=bool(ok),
                   raison=(f"vainqueur : log loss {c['log_loss_vainqueur']} contre {a['log_loss_vainqueur']} (réussite "
                           f"{c['reussite_pct']} % contre {a['reussite_pct']} %) ; points : {c['points_log_vraisemblance']} "
                           f"contre {a['points_log_vraisemblance']}"))
    rap['duree_s'] = round(time.time() - t0)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    choix['dynamique'] = dict(VARIANTES[best] if rap['adopte'] else VARIANTES[ACTUELLE], adopte=rap['adopte'],
                              variante=best if rap['adopte'] else ACTUELLE, raison=rap['raison'], genere_le=rap['genere_le'])
    with open(CHOIX, 'w', encoding='utf-8') as f:
        json.dump(choix, f, ensure_ascii=False, indent=1)
    print(f"{'ADOPTÉE' if rap['adopte'] else 'non adoptée'} : {best} — {rap['raison']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
