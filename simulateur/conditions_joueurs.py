#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conditions_joueurs.py — bilans DESCRIPTIFS d'un joueur « dans ces conditions » (11/11/2026, paquet 223).

Pour chaque joueur, sur ses matchs connus (archive 2016 → et feuilles depuis juin 2026), rangés par condition :
pays, continent, altitude, mois de l'année, salle ou plein air, chaleur, vent, humidité. Pour chaque case :
matchs, victoires RÉELLES et victoires ATTENDUES (probabilité Elo d'avant chaque match, comme la « réussite »).
L'écart réel − attendu dit si le joueur a fait mieux ou moins bien que son niveau ne le laissait prévoir, sans être
trompé par le niveau des adversaires (un % de victoires brut l'est). Le site le compare à SON écart habituel (case
« tout ») : un joueur qui dépasse ses chances partout (fréquent chez ceux qui ont progressé) n'a rien de particulier
« aux États-Unis » s'il y fait comme d'habitude.

Lieux : feuilles/tournois.json (feuilles) et feuilles/lieux_archive.json (archive). Météo : feuilles/meteo.json,
donc seulement pour les matchs des feuilles (depuis juin 2026) : température maximale et vent maximal du jour,
humidité moyenne de 11 h à 20 h. Salle : feuilles seulement.
Seuils fixés avant de regarder : chaleur < 18 °C frais, 18–28 tempéré, > 28 chaud ; vent < 15 km/h calme, 15–30
modéré, > 30 fort ; humidité < 50 % sec, 50–75 humide, > 75 très humide ; altitude < 500 m plaine, 500–1000
moyenne, > 1000 haute. Affiché à partir de 15 matchs. Descriptif : rien n'entre dans le % (le facteur
« conditions » a été rejeté par le jugement du lundi). Aucune cote.
"""
import json
import os

MIN_MATCHS = 15
DIMS = ('pays', 'continent', 'altitude', 'mois', 'salle', 'chaleur', 'vent', 'humidite')

CONTINENT = {}
for _c, _codes in {
    'europe': 'AD AL AT BA BE BG BY CH CY CZ DE DK EE ES FI FR GB GE GR HR HU IE IS IT LI LT LU LV MC MD ME MK MT NL NO '
              'PL PT RO RS RU SE SI SK SM TR UA XK AM AZ',
    'amerique_nord': 'US CA MX GT SV HN NI CR PA CU DO PR JM BS BB TT BZ HT GP MQ',
    'amerique_sud': 'AR BO BR CL CO EC PE PY UY VE GY SR',
    'asie': 'CN JP KR KP TW HK MO IN PK BD LK NP TH VN MY SG ID PH KH LA MM MN KZ UZ KG TJ TM AE QA SA BH KW OM IL JO LB '
            'IR IQ SY YE AF',
    'oceanie': 'AU NZ NC PF FJ PG',
    'afrique': 'MA DZ TN EG LY ZA NG KE GH CI SN CM RW UG TZ ZW ZM MZ AO NA BW MU ET CG CD BJ TG BF ML NE GA MG RE'}.items():
    for _k in _codes.split():
        CONTINENT[_k] = _c


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _sans_qualif(nom):
    import re
    return re.sub(r',\s*(Qualifying|Qualification|Qualifiers?)\s*$', '', str(nom or '').strip(), flags=re.I)


def tranche(x, bornes, noms):
    if x is None:
        return None
    for b, n in zip(bornes, noms):
        if x < b:
            return n
    return noms[-1]


def cases(code=None, altitude=None, mois=None, salle=None, t_max=None, vent=None, humidite=None):
    """{dimension: valeur} d'un match (les inconnues sont absentes)."""
    out = {}
    if code:
        out['pays'] = str(code).upper()
        if CONTINENT.get(out['pays']):
            out['continent'] = CONTINENT[out['pays']]
    a = tranche(altitude, (500, 1000), ('plaine', 'moyenne', 'haute'))
    if a:
        out['altitude'] = a
    if mois:
        out['mois'] = str(int(mois))
    if salle is not None:
        out['salle'] = 'salle' if salle else 'plein_air'
    if not salle:                       # la météo ne compte pas en salle
        for dim, x, b, n in (('chaleur', t_max, (18, 28), ('frais', 'tempere', 'chaud')),
                             ('vent', vent, (15, 30), ('calme', 'modere', 'fort')),
                             ('humidite', humidite, (50, 75), ('sec', 'humide', 'tres_humide'))):
            v = tranche(x, b, n)
            if v:
                out[dim] = v
    return out


class Lieux:
    """Lieu et météo d'un match de l'historique (archive ou feuilles)."""

    def __init__(self, racine):
        F = os.path.join(racine, 'feuilles')
        self.T = _lire(os.path.join(F, 'tournois.json'), {}) or {}
        self.M = _lire(os.path.join(F, 'meteo.json'), {}) or {}
        self.A = _lire(os.path.join(F, 'lieux_archive.json'), {}) or {}
        self.par_nom, self.par_match = {}, {}
        for tid, v in self.T.items():
            if v.get('nom'):
                self.par_nom.setdefault(_sans_qualif(v['nom']), tid)
        try:                                 # identifiant du tournoi de chaque match des feuilles
            import feuilles as FE
            for r in FE.lire(racine):
                if r.get('id') is not None and r.get('tournoi_id') is not None:
                    self.par_match[r['id']] = str(r['tournoi_id'])
        except Exception:  # noqa: BLE001
            pass

    def cases_du_match(self, m):
        nom, d = m.get('tournoi'), m.get('date')
        mois = d.month if d else None
        if m.get('source') == 'tennisapi':
            tid = self.par_match.get(m.get('id')) or self.par_nom.get(_sans_qualif(nom))
            l = self.T.get(tid) or {}
            met = (self.M.get(tid) or {}).get(d.isoformat()) if d else None
            return cases(l.get('code'), l.get('altitude'), mois, bool(l.get('interieur')) if l else None,
                         met[0] if met else None, met[1] if met else None, met[5] if met and len(met) >= 6 else None)
        l = self.A.get(nom) or {}
        return cases(l.get('code'), l.get('altitude'), mois)


def bilans(L):
    """{dimension: {valeur: [matchs, victoires, attendues]}} sur l'historique L d'un joueur
    (entrées d'infos_avant_match : e[1] gagné, e[2] attendu, e[6] abandon, e[9] cases)."""
    out = {}
    for e in L:
        if e[2] is None or e[6] or len(e) < 10:
            continue
        # « tout » : référence du joueur (toutes conditions), pour juger une case PAR RAPPORT À SON HABITUDE —
        # un joueur qui dépasse ses chances partout ne doit pas paraître « fort aux États-Unis » pour autant
        c = out.setdefault('tout', {}).setdefault('tout', [0, 0, 0.0])
        c[0] += 1
        c[1] += e[1]
        c[2] += e[2]
        for dim, val in (e[9] or {}).items():
            c = out.setdefault(dim, {}).setdefault(val, [0, 0, 0.0])
            c[0] += 1
            c[1] += e[1]
            c[2] += e[2]
    return {d: {v: [c[0], c[1], round(c[2], 1)] for v, c in vs.items()} for d, vs in out.items()}
