#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Variables pré-match de calendrier, confrontations et matchs serrés.

Tous les résultats sont versés par le chef d'orchestre au changement de date :
sans heure historique fiable, aucun résultat du même jour n'est supposé connu.
Les taux sont contractés et les variables sont des écarts home − away. Ce module
ne produit aucune probabilité et ne modifie aucun réglage actif.
"""
import datetime as dt
import math

PRIOR_MAIN = 20.0
PRIOR_H2H = 5.0
DEMI_VIE_H2H = 730.0
PRIORS_PRESSION = {
    'tiebreak': (10.0, .5),
    'decisif': (10.0, .5),
    'proche': (20.0, .5),
    'bp_service': (30.0, .62),
    'bp_retour': (30.0, .38),
}


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _taux(ligne, force, prior):
    n, v = (ligne or (0.0, 0.0))
    return (v + force * prior) / (n + force), n


def _ecart_taux(table, h, a, prefixe, force, prior):
    ph, nh = _taux(table.get((h, prefixe)), force, prior)
    pa, na = _taux(table.get((a, prefixe)), force, prior)
    return _lg(ph) - _lg(pa), min(nh, na)


def _jeux(m):
    return sum(x + y for x, y in (m.get('sets') or []))


class HistoriquePreMatch:
    """État disponible la veille ; ajouter() n'est appelé qu'au changement de jour."""

    def __init__(self):
        self.matchs = {}
        self.contre_main = {}
        self.h2h = {}
        self.pression = {}

    # -------------------------------------------------------------- lectures
    def _repos(self, j, jour):
        lignes = self.matchs.get(j) or []
        if not lignes:
            return 90.0, None
        return max(0, (jour - lignes[-1][0]).days), lignes[-1]

    def _periode(self, j, jour, jours):
        debut = jour - dt.timedelta(days=jours)
        return [x for x in (self.matchs.get(j) or []) if debut < x[0] < jour]

    def _resume_periode(self, j, jour, jours):
        lignes = self._periode(j, jour, jours)
        return {
            'n': len(lignes),
            'minutes': sum(x[1] or 0 for x in lignes),
            'minutes_n': sum(x[1] is not None for x in lignes),
            'tournois': len({x[3] for x in lignes if x[3]}),
            'bo5': sum(x[2] == 5 for x in lignes),
        }

    def calendrier(self, m, h, a):
        jour, surface = m['date'], m['surface']
        rh, lh = self._repos(h, jour)
        ra, la = self._repos(a, jour)
        h7, a7 = self._resume_periode(h, jour, 7), self._resume_periode(a, jour, 7)
        h14, a14 = self._resume_periode(h, jour, 14), self._resume_periode(a, jour, 14)
        h30, a30 = self._resume_periode(h, jour, 30), self._resume_periode(a, jour, 30)
        minutes_dernieres = 0.0
        if lh and la and lh[1] is not None and la[1] is not None:
            minutes_dernieres = math.log1p(lh[1]) - math.log1p(la[1])
        jeux_derniers = 0.0
        if lh and la:
            jeux_derniers = math.log1p(lh[6]) - math.log1p(la[6])
        tournoi = m.get('tournoi_base') or m.get('tournoi') or ''
        enchaine_h = bool(lh and 0 < rh <= 7 and lh[3] and lh[3] != tournoi)
        enchaine_a = bool(la and 0 < ra <= 7 and la[3] and la[3] != tournoi)
        return {
            'fatigue_repos_log': math.log1p(min(rh, 90)) - math.log1p(min(ra, 90)),
            'fatigue_matchs_7j': float(h7['n'] - a7['n']),
            'fatigue_matchs_14j': float(h14['n'] - a14['n']),
            'fatigue_minutes_7j': math.log1p(h7['minutes']) - math.log1p(a7['minutes']),
            'fatigue_minutes_14j': math.log1p(h14['minutes']) - math.log1p(a14['minutes']),
            'fatigue_tournois_14j': float(h14['tournois'] - a14['tournois']),
            'fatigue_enchainement_7j': float(enchaine_h) - float(enchaine_a),
            'fatigue_bo5_30j': float(h30['bo5'] - a30['bo5']),
            'fatigue_derniere_duree': minutes_dernieres,
            'fatigue_derniers_jeux': jeux_derniers,
            'fatigue_transition_surface': float(bool(lh and lh[4] != surface) - bool(la and la[4] != surface)),
            'fatigue_retour_absence_30j': float(rh >= 30) - float(ra >= 30),
            'fatigue_retour_absence_60j': float(rh >= 60) - float(ra >= 60),
            'fatigue_retour_absence_90j': float(rh >= 90) - float(ra >= 90),
            'fatigue_documentation_duree_7j': min(h7['minutes_n'], a7['minutes_n']),
            'fatigue_duree_derniers_matchs_connue': bool(lh and la and lh[1] is not None and la[1] is not None),
            'fatigue_historique_deux_joueurs': bool(lh and la),
        }

    def _contre_main(self, j, main_adverse):
        if main_adverse not in ('R', 'L'):
            return .5, 0.0
        return _taux(self.contre_main.get((j, main_adverse)), PRIOR_MAIN, .5)

    def gauchers_h2h(self, m, h, a, main_h, main_a):
        ph, nh = self._contre_main(h, main_a)
        pa, na = self._contre_main(a, main_h)
        direct = 0.0
        if {main_h, main_a} == {'R', 'L'}:
            direct = 1.0 if main_h == 'L' else -1.0
        lignes = [x for x in self.h2h.get(tuple(sorted((h, a))), []) if x[0] < m['date']]
        n = v = ns = vs = 0.0
        for date, gagnant, surface in lignes:
            w = 2.0 ** (-(m['date'] - date).days / DEMI_VIE_H2H)
            n += w
            v += w * (gagnant == h)
            if surface == m['surface']:
                ns += w
                vs += w * (gagnant == h)
        p_global = (v + PRIOR_H2H / 2) / (n + PRIOR_H2H)
        # Le bilan de surface est contracté vers le bilan global, pas vers un nouveau 50 %.
        p_surface = (vs + PRIOR_H2H * p_global) / (ns + PRIOR_H2H)
        return {
            'main_gaucher_contre_droitier': direct,
            'main_bilan_contre_main': (_lg(ph) - _lg(pa)) if main_h in ('R', 'L') and main_a in ('R', 'L') else 0.0,
            'h2h_global': _lg(p_global),
            'h2h_surface_increment': _lg(p_surface) - _lg(p_global),
            'h2h_poids_effectif': n,
            'h2h_poids_surface': ns,
            'main_documentation': min(nh, na),
            'main_donnee_manquante': float(main_h not in ('R', 'L') or main_a not in ('R', 'L')),
            'main_deux_joueurs_connue': main_h in ('R', 'L') and main_a in ('R', 'L'),
        }

    def taux_pression(self, j, nom):
        force, prior = PRIORS_PRESSION[nom]
        return _taux(self.pression.get((j, nom)), force, prior)

    def features_pression(self, h, a):
        out, documentation = {}, {}
        for nom in PRIORS_PRESSION:
            ph, nh = self.taux_pression(h, nom)
            pa, na = self.taux_pression(a, nom)
            out['pression_' + nom] = _lg(ph) - _lg(pa)
            documentation[nom] = min(nh, na)
        out['pression_documentation_tiebreak'] = documentation['tiebreak']
        out['pression_documentation_decisif'] = documentation['decisif']
        out['pression_documentation_proche'] = documentation['proche']
        out['pression_documentation_bp'] = min(documentation['bp_service'], documentation['bp_retour'])
        return out

    def features(self, m, h, a, main_h, main_a):
        out = self.calendrier(m, h, a)
        out.update(self.gauchers_h2h(m, h, a, main_h, main_a))
        out.update(self.features_pression(h, a))
        return out

    # -------------------------------------------------------------- écriture
    @staticmethod
    def _add(table, cle, victoire, poids=1.0):
        n, v = table.get(cle, (0.0, 0.0))
        table[cle] = (n + poids, v + poids * victoire)

    def _ajouter_pression(self, m, gagnant, perdant):
        sets = m.get('sets') or []
        bo = m.get('bo') or 3
        for sg, sp in sets:
            if (sg, sp) in ((7, 6), (6, 7)):
                self._add(self.pression, (gagnant, 'tiebreak'), sg > sp)
                self._add(self.pression, (perdant, 'tiebreak'), sp > sg)
        if len(sets) == bo:
            self._add(self.pression, (gagnant, 'decisif'), 1)
            self._add(self.pression, (perdant, 'decisif'), 0)
        d = m.get('detail')
        if d:
            for j, propre, adverse in ((gagnant, d['w'], d['l']), (perdant, d['l'], d['w'])):
                bpf, bps = propre[6], propre[7]
                if bpf > 0:
                    # À son service : balles de break sauvées ; au retour : celles converties
                    # sur le service adverse. Les deux taux restent distincts.
                    self._add(self.pression, (j, 'bp_service'), bps / bpf)
                obpf, obps = adverse[6], adverse[7]
                if obpf > 0:
                    self._add(self.pression, (j, 'bp_retour'), (obpf - obps) / obpf)

    def ajouter(self, m, p_gagnant=None):
        """Ajoute un match terminé ; p_gagnant est la probabilité Elo d'avant match."""
        g, p = m['gagnant'], m['perdant']
        jeux = _jeux(m)
        for j in (g, p):
            self.matchs.setdefault(j, []).append((m['date'], m.get('minutes'), m.get('bo') or 3,
                                                  m.get('tournoi_base') or m.get('tournoi') or '',
                                                  m['surface'], m['circuit'], jeux))
        if not m.get('complet') or m.get('abandon'):
            return
        cle = tuple(sorted((g, p)))
        self.h2h.setdefault(cle, []).append((m['date'], g, m['surface']))
        for j, adv, main_adv in ((g, p, m.get('main_p')), (p, g, m.get('main_g'))):
            if main_adv in ('R', 'L'):
                self._add(self.contre_main, (j, main_adv), j == g)
        self._ajouter_pression(m, g, p)
        if p_gagnant is not None and .4 <= p_gagnant <= .6:
            self._add(self.pression, (g, 'proche'), 1)
            self._add(self.pression, (p, 'proche'), 0)
