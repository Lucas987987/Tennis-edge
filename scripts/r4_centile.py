"""r4_centile.py — le centile de % de victoires sur 365 jours, POINT-IN-TIME,
tel que défini par la règle R4 (gelée le 10/10/2026).

Même calcul que l'étude (etude_meilleurs.py) :
  — % de victoires d'un joueur sur ses matchs des 365 jours AVANT le jour
    du match (le jour même exclu), s'il en a au moins 20 ;
  — rangé parmi tous les joueurs de son circuit qui ont, ce jour-là, au
    moins 20 matchs sur 365 jours : centile = part des joueurs qui ont un
    % strictement plus bas.
"""

import re
import unicodedata
from bisect import bisect_left
from collections import defaultdict, deque

FENETRE = 365
MIN_MATCHS = 20


def _jetons(nom):
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z. ]+', ' ', s.replace('-', ' ')).split()


def relier_td(fiches):
    """Nom tennis-data (« Bublik A. ») -> clé de fiche, par circuit.
    Copie GELÉE le 10/10/2026 de build_profiles.relier_tennis_data, pour
    que R4 ne change pas si la fiche change.
    fiches : {clé: (nom affiché, circuit 'atp'/'wta'/None, nb de cotes)}."""
    idx = defaultdict(list)
    for k, (nom, circ, n) in fiches.items():
        t = [x.replace('.', '') for x in _jetons(nom)]
        t = [x for x in t if x]
        for i in range(1, len(t)):
            idx[' '.join(t[i:])].append((k, t[0], circ, n))
    cache = {}

    def relier(nom_td, circuit):
        cle_c = (nom_td, circuit)
        if cle_c in cache:
            return cache[cle_c]
        t = _jetons(nom_td)
        res = None
        if len(t) >= 2:
            abr = t[-1]
            nom = ' '.join(x.replace('.', '') for x in t[:-1])
            pre = abr.split('.')[0] if abr.count('.') > 1 else abr.replace('.', '')
            c = [(k, n) for k, prenom, circ, n in idx.get(nom, [])
                 if pre and prenom.startswith(pre)
                 and (circ is None or circ == circuit)]
            c = sorted(set(c), key=lambda x: -x[1])
            if len(c) == 1 or (len(c) > 1 and c[0][1] >= 3 * max(1, c[1][1])):
                res = c[0][0]
        cache[cle_c] = res
        return res
    return relier


def circuit_principal(tournoi):
    """'ATP' / 'WTA' pour un tournoi du circuit principal, sinon None
    (Challenger, WTA 125, ITF, compétitions par équipes)."""
    t = (tournoi or '').strip().lower()
    if any(x in t for x in ('challenger', '125', 'itf', 'davis', 'billie',
                            'united cup', 'laver', 'hopman', 'doubles',
                            'mixed', 'qualif')):
        return None
    # Grands Chelems : « US Open Men Singles », « Wimbledon Women Singles »
    if 'women singles' in t:
        return 'WTA'
    if 'men singles' in t:
        return 'ATP'
    if t.startswith('atp'):
        return 'ATP'
    if t.startswith('wta'):
        return 'WTA'
    return None


def centiles(matchs, requetes):
    """matchs   : [(date, circuit, id_vainqueur, id_perdant)]
    requetes : [(date, circuit, id)]
    -> {(date, circuit, id): (centile, % de victoires) ou None}"""
    par_jour = defaultdict(list)
    for m in matchs:
        par_jour[m[0]].append(m)
    q_jour = defaultdict(list)
    for r in requetes:
        q_jour[r[0]].append(r)
    hist = defaultdict(deque)               # (circuit, id) -> (date, gagné)
    somme = defaultdict(int)
    out = {}

    def taux(k, d):
        q = hist[k]
        while q and (d - q[0][0]).days > FENETRE:
            somme[k] -= q.popleft()[1]
        if len(q) < MIN_MATCHS:
            return None
        return somme[k] / len(q)

    for d in sorted(set(par_jour) | set(q_jour)):
        if q_jour.get(d):
            actifs = defaultdict(list)
            for k in list(hist):
                t = taux(k, d)
                if t is not None:
                    actifs[k[0]].append(t)
            for c in actifs:
                actifs[c].sort()
            for r in q_jour[d]:
                t = taux((r[1], r[2]), d)
                L = actifs.get(r[1], [])
                out[r] = None if t is None else (bisect_left(L, t) / max(1, len(L)), t)
        for _, c, w, l in par_jour.get(d, []):
            hist[(c, w)].append((d, 1))
            somme[(c, w)] += 1
            hist[(c, l)].append((d, 0))
    return out
