#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fréquence et réussite par longueur d'échange — Match Charting Project.

Les relevés sont lus strictement avant chaque match. Les variables prédictives
utilisent une demi-vie de 365 jours, une contraction de surface et des priors en
points. Les bilans récents restent descriptifs et conservent leurs effectifs.
"""
import bisect
import collections
import csv
import datetime as dt
import math
import os

import elo as E

SCHEMA = 'echanges_atp_wta_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
TRANCHES = ('1-3', '4-6', '7-9', '10')
LIBELLES = {'1-3': '1–3 frappes', '4-6': '4–6 frappes', '7-9': '7–9 frappes', '10': '10 frappes ou plus'}
SCOPES = ('total', 'service', 'retour')
DEMI_VIE_J = 365.0
PRIOR_REUSSITE = 100.0
PRIOR_FREQUENCE = 300.0
VARIABLES = [f'echange_{type_}_{tranche.replace("-", "_")}_ecart'
             for type_ in ('reussite', 'frequence') for tranche in TRANCHES]


def _i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _lire(chemin):
    try:
        with open(chemin, encoding='utf-8', errors='replace', newline='') as f:
            yield from csv.DictReader(f)
    except OSError:
        return


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def charger(dossier):
    """{clé joueur: [(date, surface, circuit, scope, tranche, points, gagnés)]}."""
    out = collections.defaultdict(list)
    if not dossier or not os.path.isdir(dossier):
        return {}
    for sexe, circuit in (('m', 'ATP'), ('w', 'WTA')):
        base = lambda n: os.path.join(dossier, f'charting-{sexe}-{n}.csv')
        matches = {}
        for r in _lire(base('matches')):
            try:
                matches[r['match_id']] = {
                    'date': dt.datetime.strptime(r['Date'][:8], '%Y%m%d').date(),
                    'joueurs': (r['Player 1'], r['Player 2']),
                    'surface': r.get('Surface') or 'Hard',
                }
            except (KeyError, TypeError, ValueError):
                continue
        for r in _lire(base('stats-Rally')):
            m = matches.get(r.get('match_id'))
            row = r.get('row') or ''
            if not m:
                continue
            scope = None
            serveur = None
            if row in TRANCHES:
                tranche, scope = row, 'total'
            else:
                for tr in TRANCHES:
                    if row in (tr + '-1', tr + '-2'):
                        tranche, serveur = tr, int(row.rsplit('-', 1)[1])
                        break
                else:
                    continue
            for k, nom in enumerate(m['joueurs']):
                if scope is None:
                    scope_j = 'service' if k + 1 == serveur else 'retour'
                else:
                    scope_j = scope
                points = _i(r.get('pts'))
                gagnes = _i(r.get('pl1_won' if k == 0 else 'pl2_won'))
                if points > 0:
                    out[E.cle(nom)].append((m['date'], m['surface'], circuit, scope_j,
                                            tranche, points, gagnes))
    for lignes in out.values():
        lignes.sort(key=lambda x: x[0])
    return dict(out)


class Echanges:
    """Profils pré-match de fréquence et de réussite, sans match courant."""

    def __init__(self, donnees, demi_vie=DEMI_VIE_J):
        self.D = donnees or {}
        self.demi_vie = float(demi_vie)
        self.dates = {j: [x[0] for x in lignes] for j, lignes in self.D.items()}
        moy = collections.defaultdict(list)
        for lignes in self.D.values():
            for date, surface, circuit, scope, tranche, points, gagnes in lignes:
                if scope == 'total':
                    moy[(circuit, tranche)].append((date, points, gagnes))
        self.moy_dates, self.moy_cum = {}, {}
        for cle, lignes in moy.items():
            lignes.sort()
            self.moy_dates[cle] = [x[0] for x in lignes]
            cum, p, g = [], 0, 0
            for _, points, gagnes in lignes:
                p += points
                g += gagnes
                cum.append((p, g))
            self.moy_cum[cle] = cum

    def _avant(self, joueur, jour):
        lignes = self.D.get(joueur) or []
        return lignes[:bisect.bisect_left(self.dates.get(joueur) or [], jour)]

    def documentation(self, joueur, jour):
        return sum(x[5] for x in self._avant(joueur, jour) if x[3] == 'total')

    def _moyenne(self, circuit, tranche, jour):
        cle = (circuit, tranche)
        dates = self.moy_dates.get(cle) or []
        k = bisect.bisect_left(dates, jour)
        return self.moy_cum[cle][k - 1] if k else (0, 0)

    def _sommes(self, joueur, tranche, jour, surface=None):
        points = gagnes = total = 0.0
        for date, surf, _, scope, tr, p, g in self._avant(joueur, jour):
            if scope != 'total' or (surface is not None and surf != surface):
                continue
            w = .5 ** ((jour - date).days / self.demi_vie)
            total += w * p
            if tr == tranche:
                points += w * p
                gagnes += w * g
        return points, gagnes, total

    def mesure(self, joueur, circuit, surface, tranche, jour):
        circuit = {'CH': 'ATP', 'ITF': 'WTA', 'ITFH': 'ATP'}.get(circuit, circuit)
        mu = {}
        total_mu = 0
        for tr in TRANCHES:
            p, g = self._moyenne(circuit, tr, jour)
            mu[tr] = (p, g)
            total_mu += p
        p_mu, g_mu = mu[tranche]
        mu_freq = p_mu / total_mu if total_mu else .25
        mu_reussite = g_mu / p_mu if p_mu else .5
        p, g, total = self._sommes(joueur, tranche, jour)
        freq = (p + PRIOR_FREQUENCE * mu_freq) / (total + PRIOR_FREQUENCE)
        reussite = (g + PRIOR_REUSSITE * mu_reussite) / (p + PRIOR_REUSSITE)
        ps, gs, totals = self._sommes(joueur, tranche, jour, surface)
        freq_s = (ps + PRIOR_FREQUENCE * freq) / (totals + PRIOR_FREQUENCE)
        reussite_s = (gs + PRIOR_REUSSITE * reussite) / (ps + PRIOR_REUSSITE)
        return {'frequence': freq_s, 'reussite': reussite_s,
                'points': p, 'points_surface': ps, 'points_totaux': total}

    def variables_match(self, h, a, circuit, surface, jour):
        out = {}
        docs = []
        for tranche in TRANCHES:
            mh = self.mesure(h, circuit, surface, tranche, jour)
            ma = self.mesure(a, circuit, surface, tranche, jour)
            suffixe = tranche.replace('-', '_')
            out[f'echange_reussite_{suffixe}_ecart'] = _lg(mh['reussite']) - _lg(ma['reussite'])
            out[f'echange_frequence_{suffixe}_ecart'] = _lg(mh['frequence']) - _lg(ma['frequence'])
            docs.append(min(mh['points'], ma['points']))
        out['echanges_documentation_min_tranches'] = min(docs)
        out['echanges_deux_joueurs_couverts'] = bool(self.documentation(h, jour) and self.documentation(a, jour))
        return out


def _periode(lignes, debut, fin, surface=None):
    acc = {(scope, tr): [0, 0] for scope in SCOPES for tr in TRANCHES}
    dates = set()
    for date, surf, _, scope, tranche, points, gagnes in lignes:
        if debut <= date < fin and (surface is None or surf == surface):
            acc[(scope, tranche)][0] += points
            acc[(scope, tranche)][1] += gagnes
            dates.add(date)
    out = {'matchs_releves': len(dates), 'scopes': {}}
    for scope in SCOPES:
        total = sum(acc[(scope, tr)][0] for tr in TRANCHES)
        bloc = {}
        for tr in TRANCHES:
            points, gagnes = acc[(scope, tr)]
            bloc[tr] = {'points': points, 'points_gagnes': gagnes,
                        'frequence_pct': round(100 * points / total, 2) if total else None,
                        'reussite_pct': round(100 * gagnes / points, 2) if points else None}
        out['scopes'][scope] = {'points_totaux': total, 'tranches': bloc}
    return out


def comparaison(lignes, reference, fenetre=180, surface=None):
    debut_recent = reference - dt.timedelta(days=fenetre)
    debut_ancien = reference - dt.timedelta(days=2 * fenetre)
    ancien = _periode(lignes, debut_ancien, debut_recent, surface)
    recent = _periode(lignes, debut_recent, reference, surface)
    variations = {}
    for scope in SCOPES:
        variations[scope] = {}
        for tr in TRANCHES:
            a = ancien['scopes'][scope]['tranches'][tr]
            b = recent['scopes'][scope]['tranches'][tr]
            variations[scope][tr] = {
                'frequence_points': (round(b['frequence_pct'] - a['frequence_pct'], 2)
                                     if min(ancien['scopes'][scope]['points_totaux'], recent['scopes'][scope]['points_totaux']) >= 200
                                     and a['frequence_pct'] is not None and b['frequence_pct'] is not None else None),
                'reussite_points': (round(b['reussite_pct'] - a['reussite_pct'], 2)
                                    if min(a['points'], b['points']) >= 50
                                    and a['reussite_pct'] is not None and b['reussite_pct'] is not None else None),
                'statut': 'comparaison_documentee' if min(a['points'], b['points']) >= 50 else 'sous_documentee',
            }
    return {'periode_precedente': ancien, 'periode_recente': recent, 'variations': variations}
