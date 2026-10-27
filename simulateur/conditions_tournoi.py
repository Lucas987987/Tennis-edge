#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conditions résiduelles des tournois, estimées sur les éditions antérieures.

Pour chaque match passé, le résidu est la statistique observée moins la moyenne
attendue des deux joueurs avant ce match (leur propre historique, contracté vers
le circuit et la surface). L'édition en cours n'entre jamais dans son propre
effet. Un effet de tournoi est contracté vers le résidu moyen de la surface avec
20 matchs de prior. Les interactions rendent une condition commune aux deux
joueurs susceptible d'avantager l'un d'eux ; un effet principal commun serait
nul par construction dans une orientation alphabétique.
"""
import math

PRIOR_JOUEUR = 20.0
PRIOR_TOURNOI = 20.0
REPLI = {'aces': .06, 'service_gagne': .78, 'tiebreak': .20, 'jeux': 22.0, 'minutes': 110.0}


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _add(table, cle, valeur, n=1.0):
    ancien_n, somme = table.get(cle, (0.0, 0.0))
    table[cle] = (ancien_n + n, somme + valeur)


def _moyenne(table, cle, repli):
    n, somme = table.get(cle, (0.0, 0.0))
    return somme / n if n > 0 else repli


def _tb(m):
    return float(any((a, b) in ((7, 6), (6, 7)) for a, b in (m.get('sets') or [])))


def _jeux(m):
    return float(sum(a + b for a, b in (m.get('sets') or [])))


def _service(p):
    return .60 * p['w1'] + .40 * p['w2j']


def _retour(p):
    return 1.0 - (.60 * p['r1'] + .40 * p['r2j'])


class ConditionsTournoi:
    def __init__(self):
        self.joueurs = {}
        self.surface = {}
        self.residus_surface = {}
        self.editions = {}
        # Index court : évite de balayer toutes les éditions de l'archive à chaque match.
        self.par_tournoi = {}

    def _attendu_joueur(self, j, circuit, surface, metric):
        mu = _moyenne(self.surface, (circuit, surface, metric), REPLI[metric])
        n, somme = self.joueurs.get((j, metric), (0.0, 0.0))
        return (somme + PRIOR_JOUEUR * mu) / (n + PRIOR_JOUEUR)

    def attendu(self, m):
        """Photographie avant match, également enregistrée pour les matchs non retenus."""
        g, p = m['gagnant'], m['perdant']
        return {metric: .5 * (self._attendu_joueur(g, m['circuit'], m['surface'], metric)
                              + self._attendu_joueur(p, m['circuit'], m['surface'], metric))
                for metric in REPLI}

    def _environnement(self, m, metric):
        cle_surface = (m['circuit'], m['surface'], metric)
        mu_surface = _moyenne(self.residus_surface, cle_surface, 0.0)
        n = somme = 0.0
        # L'année de l'édition courante est explicitement exclue, même pour un
        # match dont les résultats antérieurs seraient déjà disponibles.
        circuit, base = m['circuit'], m.get('tournoi_base') or ''
        cle = (circuit, base, metric)
        for edition in self.par_tournoi.get(cle, ()):
            if edition < m['edition']:
                ni, si = self.editions[(circuit, base, edition, metric)]
                n += ni
                somme += si
        if n <= 0:
            return 0.0, 0.0
        return (somme + PRIOR_TOURNOI * mu_surface) / (n + PRIOR_TOURNOI), n

    def features(self, m, h, a, profil_h, profil_a, historique):
        env = {metric: self._environnement(m, metric) for metric in REPLI}
        ace_h, ace_a = profil_h['f'] * profil_h['a'], profil_a['f'] * profil_a['a']
        service = (_service(profil_h) - _service(profil_a)) / .05
        retour = (_retour(profil_h) - _retour(profil_a)) / .05
        pd_h, _ = historique.taux_pression(h, 'decisif')
        pd_a, _ = historique.taux_pression(a, 'decisif')
        endurance = _lg(pd_h) - _lg(pd_a)
        return {
            'conditions_aces_x_profil': env['aces'][0] * (ace_h - ace_a) / .02,
            # Jeux de service gagnés et breaks sont les deux faces du même résidu :
            # une seule interaction évite une colinéarité exacte dans la régression.
            'conditions_service_retour': env['service_gagne'][0] * (service - retour),
            'conditions_tiebreak_x_service': env['tiebreak'][0] * service,
            'conditions_longueur_x_endurance': env['jeux'][0] * endurance,
            'conditions_minutes_x_endurance': env['minutes'][0] * endurance,
            'conditions_matchs_editions': min(x[1] for x in env.values()),
            'conditions_env_aces': env['aces'][0],
            'conditions_env_service_gagne': env['service_gagne'][0],
            'conditions_env_breaks': -env['service_gagne'][0],
            'conditions_env_tiebreak': env['tiebreak'][0],
            'conditions_env_jeux': env['jeux'][0],
            'conditions_env_minutes': env['minutes'][0],
        }

    @staticmethod
    def _mesures(m):
        """(valeur du match, valeur individuelle gagnant, valeur individuelle perdant)."""
        out = {}
        d = m.get('detail')
        if d:
            dw, dl = d['w'], d['l']
            sv = dw[0] + dl[0]
            if sv > 0:
                out['aces'] = ((dw[4] + dl[4]) / sv, dw[4] / dw[0], dl[4] / dl[0])
            sg = dw[8] + dl[8]
            if sg > 0:
                holds_w = dw[8] - (dw[6] - dw[7])
                holds_l = dl[8] - (dl[6] - dl[7])
                out['service_gagne'] = ((holds_w + holds_l) / sg,
                                        holds_w / dw[8] if dw[8] else None,
                                        holds_l / dl[8] if dl[8] else None)
        if m.get('sets'):
            out['tiebreak'] = (_tb(m), _tb(m), _tb(m))
            out['jeux'] = (_jeux(m), _jeux(m), _jeux(m))
        if m.get('minutes') is not None:
            out['minutes'] = (float(m['minutes']), float(m['minutes']), float(m['minutes']))
        return out

    def ajouter(self, m, attendu):
        if not m.get('complet') or m.get('abandon'):
            return
        g, p = m['gagnant'], m['perdant']
        base = m.get('tournoi_base') or ''
        for metric, (obs_match, obs_g, obs_p) in self._mesures(m).items():
            if obs_match is None:
                continue
            residu = obs_match - attendu[metric]
            _add(self.residus_surface, (m['circuit'], m['surface'], metric), residu)
            if base:
                cle = (m['circuit'], base, m['edition'], metric)
                _add(self.editions, cle, residu)
                self.par_tournoi.setdefault((m['circuit'], base, metric), set()).add(m['edition'])
            _add(self.surface, (m['circuit'], m['surface'], metric), obs_match)
            for j, obs in ((g, obs_g), (p, obs_p)):
                if obs is not None:
                    _add(self.joueurs, (j, metric), obs)
