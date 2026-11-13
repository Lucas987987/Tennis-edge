#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
styles_jeu.py — le STYLE DE JEU de chaque joueur, d'après le détail de ses coups, et ses bilans contre chaque style
(13/11/2026, paquet 252, demande de Lucas : « créer des styles de joueurs », sur le modèle du duel des styles).

Les styles du site (styles_descriptifs.py) viennent du service et du retour. Celui-ci dit comment le joueur gagne ses
points dans l'échange ; il vient du Match Charting Project (matchs relevés coup par coup par des bénévoles, Jeff Sackmann,
CC BY-NC-SA 4.0) et n'existe que pour les joueurs relevés au moins MIN_MATCHS fois dans les 3 ans d'avant.

RÈGLE DE CLASSEMENT, ÉCRITE LE 13/11/2026 AVANT DE REGARDER UN SEUL JOUEUR (m = moyenne du circuit, hommes ou femmes, sur
les matchs relevés des 3 ans d'avant la même date) :
  joueur de filet          montées au filet par point joué ≥ 1,4 m ET part des points gagnés au filet ≥ m
  attaquant de coup droit  coups gagnants du coup droit par point joué ≥ 1,3 m
  attaquant de revers      coups gagnants du revers par point joué ≥ 1,3 m
  joueur de toucher        amortis joués par point joué ≥ 1,5 m
  régulier                 fautes directes par point joué ≤ 0,85 m
  au plus deux étiquettes, les plus marquées (rapport au seuil) ; aucune → complet.
Le style d'un ADVERSAIRE dans un bilan est figé à la date du match (ses seuls matchs relevés d'avant).

BILANS : comme le duel des styles (styles_descriptifs.py), victoires contre les adversaires de ce style, ATTENDU (moyenne
des probabilités Elo d'avant-match, Elo réglé comme la production et mis à jour après chaque match) et écart à
l'attendu ; résultats du même jour indisponibles. DESCRIPTIF : rien de ceci n'entre dans le % de victoire.

Usage : python simulateur/styles_jeu.py <archive Sackmann> [racine] [dossier du Match Charting Project]
Sortie : simulateur/styles_jeu.json (artefact régénéré, non commité).
"""
import bisect
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join('simulateur', 'styles_jeu.json')
MIN_MATCHS, FENETRE_J = 10, 3 * 365
STYLES = ('joueur_de_filet', 'attaquant_coup_droit', 'attaquant_revers', 'joueur_de_toucher', 'regulier', 'complet')
CHAMPS = ('points_joues', 'montees', 'montees_gagnees', 'coup_droit', 'revers', 'amortis_joues', 'fautes_directes')


class Profils:
    """Matchs relevés de chaque joueur (sommes cumulées par date) et du circuit."""

    def __init__(self, par_nom, cle):
        par = collections.defaultdict(list)
        cir = collections.defaultdict(list)
        for nom, L in par_nom.items():
            k = cle(nom)
            if not k:
                continue
            for d, c in L:
                x = {f: c.get(f, 0) for f in CHAMPS}
                par[k].append((d, x))
                cir[c.get('_g')].append((d, x))
        self.j = {k: self._cumul(L) for k, L in par.items()}
        self.c = {g: self._cumul(L) for g, L in cir.items()}
        self.genre = {}
        for nom, L in par_nom.items():
            k = cle(nom)
            if k and L:
                self.genre[k] = collections.Counter(c.get('_g') for _, c in L).most_common(1)[0][0]

    @staticmethod
    def _cumul(L):
        L.sort(key=lambda x: x[0])
        cum, s = [], collections.Counter()
        for _, c in L:
            s.update(c)
            cum.append(dict(s))
        return [d for d, _ in L], cum

    @staticmethod
    def _fenetre(e, jour):
        D, C = e
        i1 = bisect.bisect_left(D, jour)
        i0 = bisect.bisect_left(D, jour - dt.timedelta(days=FENETRE_J))
        if i1 <= i0:
            return 0, None
        haut, bas = C[i1 - 1], (C[i0 - 1] if i0 > 0 else {})
        return i1 - i0, {f: haut.get(f, 0) - bas.get(f, 0) for f in CHAMPS}

    def style(self, k, jour):
        """(étiquettes, matchs relevés) à la date (matchs d'avant seulement) ; (None, n) sous MIN_MATCHS."""
        e, g = self.j.get(k), self.genre.get(k)
        if not e or g not in self.c:
            return None, 0
        n, s = self._fenetre(e, jour)
        if n < MIN_MATCHS:
            return None, n
        _, m = self._fenetre(self.c[g], jour)
        return classer(s, m), n


def _r(a, b):
    return a / b if b else None


def classer(s, m):
    """Étiquettes (au plus deux, les plus marquées) d'après les sommes du joueur s et du circuit m."""
    if not s or not m:
        return None
    t = lambda x, f: _r(x[f], x['points_joues'])  # noqa: E731
    cand = []
    fj, fm = t(s, 'montees'), t(m, 'montees')
    wj, wm = _r(s['montees_gagnees'], s['montees']), _r(m['montees_gagnees'], m['montees'])
    if fj is not None and fm and wj is not None and wm is not None and fj >= 1.4 * fm and wj >= wm:
        cand.append(('joueur_de_filet', fj / (1.4 * fm)))
    for f, nom, seuil in (('coup_droit', 'attaquant_coup_droit', 1.3), ('revers', 'attaquant_revers', 1.3),
                          ('amortis_joues', 'joueur_de_toucher', 1.5)):
        a, b = t(s, f), t(m, f)
        if a is not None and b and a >= seuil * b:
            cand.append((nom, a / (seuil * b)))
    a, b = t(s, 'fautes_directes'), t(m, 'fautes_directes')
    if a and b and a <= 0.85 * b:
        cand.append(('regulier', (0.85 * b) / a))
    cand.sort(key=lambda x: -x[1])
    return [c for c, _ in cand[:2]] or ['complet']


def historique(M, P, cibles, jour, racine):
    """Bilans {(joueur, style adverse, global | surface): ligne} des joueurs cibles, avant `jour`."""
    import elo as E
    import styles_descriptifs as SD
    el, bas = E.de_production(racine)
    acc, veille, jour_courant = {}, [], None
    for m in sorted(M, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        if m['date'] > jour:
            break
        if jour_courant != m['date']:
            for args in veille:
                SD._ajouter(acc, *args)
            veille, jour_courant = [], m['date']
        g, p = m['_g'], m['_p']
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        pg = el.proba(g, p, s)
        if m.get('complet') and not m.get('abandon') and (g in cibles or p in cibles):
            for j, adv, nom_adv, v, att in ((g, p, m.get('nom_p') or p, True, pg), (p, g, m.get('nom_g') or g, False, 1 - pg)):
                if j not in cibles:
                    continue
                st, _ = P.style(adv, m['date'])
                if not st:
                    continue
                for lab in st:
                    ev = SD._evenement(m, j, adv, nom_adv, v, lab, att)
                    veille.append((j, lab, s, ev, v, None, att, None))
                ev = SD._evenement(m, j, adv, nom_adv, v, SD.TOUS_STYLES, att)
                veille.append((j, SD.TOUS_STYLES, s, ev, v, None, att, None))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    if jour_courant is not None and jour_courant < jour:
        for args in veille:
            SD._ajouter(acc, *args)
    return acc


def construire(racine, archive, mcp, maintenant=None):
    import coups_joueurs as CJ
    import donnees
    import elo as E
    import feuilles as FE
    import styles_descriptifs as SD
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    jour = maintenant.date()
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    cle = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    P = Profils(CJ.charger(mcp), cle)
    matchs, cibles = SD._cibles(racine, maintenant)
    courants = {k: P.style(k, jour) for k in cibles}
    garder = {k for k, (st, _) in courants.items() if st}
    M = donnees.charger(archive, 2018)
    fin = max(m['date'] for m in M) if M else None
    M = M + [m for m in FE.charger(racine) if fin is None or m['date'] > fin]
    for m in M:
        m['_g'], m['_p'] = cle(m.get('nom_g')), cle(m.get('nom_p'))
    acc = historique(M, P, garder, jour, racine)
    out = {}
    for x in matchs:
        h, a, s = x['h'], x['a'], x['surface']
        (sh, nh), (sa, na) = courants.get(h, (None, 0)), courants.get(a, (None, 0))
        if not sh and not sa:
            continue
        bloc = lambda j, st, n, adv: {  # noqa: E731
            'style': st, 'matchs_releves': n, 'style_adverse': adv,
            'global': SD.resume(acc.get((j, adv[0], 'global')), acc.get((j, SD.TOUS_STYLES, 'global'))) if st and adv else None,
            'surface': SD.resume(acc.get((j, adv[0], s)), acc.get((j, SD.TOUS_STYLES, s))) if st and adv else None}
        out[x['uid']] = {'descriptif_seulement': True, 'joueurs': [bloc(h, sh, nh, sa), bloc(a, sa, na, sh)]}
    return {'schema': 'styles_jeu_v1', 'genere_le': maintenant.isoformat(timespec='seconds'), 'descriptif_seulement': True,
            'source': 'Match Charting Project (Jeff Sackmann et bénévoles, CC BY-NC-SA 4.0)', 'min_matchs': MIN_MATCHS,
            'regle': ("style de jeu d'après les coups (filet, coup droit, revers, toucher, régularité) contre la moyenne du "
                      "circuit, seuils écrits le 13/11/2026 ; style adverse figé à la date du match ; ne change pas le %"),
            'matchs': out}


def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print('Usage : python simulateur/styles_jeu.py <archive Sackmann> [racine] [dossier MCP]')
        return 2
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    mcp = argv[3] if len(argv) > 3 else '/tmp/mcp'
    doc = construire(racine, archive, mcp)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Styles de jeu : {len(doc['matchs'])} matchs")
    return 0


if __name__ == '__main__':
    sys.exit(main())
