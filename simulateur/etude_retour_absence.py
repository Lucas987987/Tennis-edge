#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_retour_absence.py — un joueur qui revient d'une longue absence est-il moins fort que son Elo ?
(04/11/2026, demande de Lucas, après la loupe etude_ecart_pinnacle.py : ATP, joueur qui revient après 45 jours ou plus
annoncé 56,0 % par l'Elo, 45,5 % par la clôture, 40,7 % en réel.) Jugé SÉPARÉMENT sur l'ATP, la WTA et le Challenger.

Définition, calculée AVANT le match avec les seuls matchs déjà joués (ITF compris, comme donnée) :
  absence = jours entre le match précédent du joueur et le premier match de son retour (≥ 45 jours) ;
  poids du retour r = 1 au 1er match du retour, 1/2 au 2e, 1/4 au 3e, 0 ensuite ;
  classe : court (45 à 119 jours) ou long (120 jours et plus).
Variables : x_court = r_A·court_A − r_B·court_B, x_long = r_A·long_A − r_B·long_B.
Correction : z = logit p_elo + β_court·x_court + β_long·x_long. Base : l'Elo du pronostic (~78 % du mélange). Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque circuit :
  β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu) ;
  positif si, sur les matchs CONCERNÉS jugés (au moins 300), la log loss du vainqueur baisse d'au moins 0,001 ET le
  gain reste positif sur tous les matchs jugés du circuit.
  Positif → modèle fantôme « retour d'absence » sur les nouveaux matchs de ce circuit, adopté seulement après deux
  semaines gagnantes (fantomes_circuits.py). Sinon : rien ne change.
Usage : python simulateur/etude_retour_absence.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
SEUIL_J, LONG_J = 45, 120
POIDS = (1.0, 0.5, 0.25)
MIN_CONCERNES, MARGE = 300, 0.001
SORTIE = os.path.join(ICI, 'rapport_retour_absence.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


class Retours:
    """joueur → (jour du dernier match, absence du retour en cours, matchs joués depuis le retour)."""
    def __init__(self):
        self.e = {}

    def etat(self, j, jour):
        """(r, long) pour le match de ce jour : r poids du retour, long = 1 si l'absence fait 120 jours ou plus."""
        e = self.e.get(j)
        if not e:
            return 0.0, 0
        dern, absence, apres = e
        gap = (jour - dern).days
        if gap >= SEUIL_J:
            return POIDS[0], int(gap >= LONG_J)
        if absence and apres < len(POIDS):
            return POIDS[apres], int(absence >= LONG_J)
        return 0.0, 0

    def jouer(self, j, jour):
        e = self.e.get(j)
        if not e:
            self.e[j] = (jour, None, 99)
            return
        dern, absence, apres = e
        gap = (jour - dern).days
        if gap >= SEUIL_J:
            self.e[j] = (jour, gap, 1)
        else:
            self.e[j] = (jour, absence, apres + 1)


def dates_matchs(archive, racine, depuis=2024):
    """Pour le pronostic du jour : {joueur: [jours de ses matchs, triés]} — archive, feuilles TennisApi, résultats ITF
    (hommes et femmes, donnée seule). Un match vu dans deux sources ne compte qu'une fois (jour + adversaire)."""
    import donnees as DN
    import elo as E
    import feuilles as FE
    sys.path.insert(0, os.path.join(racine, 'scripts'))
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    ev = {}

    def ajouter(jour, a, b):
        a, b = k(a), k(b)
        if a and b and a != b:
            ev.setdefault(a, set()).add((jour, b))
            ev.setdefault(b, set()).add((jour, a))
    try:
        M = DN.charger(archive, depuis)
    except Exception:  # noqa: BLE001 — sans archive : feuilles et ITF seulement
        M = []
    for m in M:
        ajouter(m['date'], m.get('nom_g'), m.get('nom_p'))
    fiches = list(FE.lire(racine))
    try:
        import resultats_itf as RI
        fiches += RI.lire_tout(racine) + RI.lire_tout(racine, RI.DOSSIER_FEMMES)
    except Exception:  # noqa: BLE001
        pass
    for r in fiches:
        if r.get('vainqueur') in (1, 2) and r.get('jour'):
            try:
                jour = dt.date.fromisoformat(r['jour'])
            except ValueError:
                continue
            ajouter(jour, (r.get('home') or {}).get('nom'), (r.get('away') or {}).get('nom'))
    return {j: sorted(d for d, _ in v) for j, v in ev.items()}


def etat_au(dates, jour):
    """(r, long) d'un joueur pour un match du jour `jour`, à partir de ses jours de matchs (seuls ceux d'avant comptent)."""
    rt = Retours()
    for d in dates or ():
        if d >= jour:
            break
        rt.jouer('j', d)
    return rt.etat('j', jour)


def variables(ra, rb):
    (r_a, l_a), (r_b, l_b) = ra, rb
    return (r_a * (1 - l_a) - r_b * (1 - l_b), r_a * l_a - r_b * l_b)


def apprendre(R, ridge=1.0):
    """R : [(z, (x1, x2))] (vainqueur = A) → (β1, β2), Newton à deux dimensions avec ridge."""
    b = [0.0, 0.0]
    for _ in range(50):
        g, H = [ridge * b[0], ridge * b[1]], [[ridge, 0.0], [0.0, ridge]]
        for z, x in R:
            q = _sg(z + b[0] * x[0] + b[1] * x[1])
            for i in range(2):
                g[i] += (q - 1) * x[i]
                for k in range(2):
                    H[i][k] += q * (1 - q) * x[i] * x[k]
        det = H[0][0] * H[1][1] - H[0][1] * H[1][0]
        if abs(det) < 1e-12:
            break
        d0 = (H[1][1] * g[0] - H[0][1] * g[1]) / det
        d1 = (H[0][0] * g[1] - H[1][0] * g[0]) / det
        b = [b[0] - d0, b[1] - d1]
        if max(abs(d0), abs(d1)) < 1e-9:
            break
    return b


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import feuilles as FE
    M = DN.charger(archive, 2012)
    fin = max(m['date'] for m in M)
    M = M + [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, rt, jour, attente, rows = E.Elo(), Retours(), None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        x = variables(rt.etat(g, d), rt.etat(p, d))
        if (c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon')
                and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            rows.append({'d': d, 'c': c, 'z': _lg(el.proba(g, p, s)), 'x': x})
        rt.jouer(g, d)
        rt.jouer(p, d)
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [(r['z'], r['x']) for r in R if r['d'] < COUPURE and (r['x'][0] or r['x'][1])]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = apprendre(av)
        cor = lambda r: r['z'] + b[0] * r['x'][0] + b[1] * r['x'][1]
        cc = [r for r in ju if r['x'][0] or r['x'][1]]
        l0c = sum(ll(r['z']) for r in cc) / max(1, len(cc))
        l1c = sum(ll(cor(r)) for r in cc) / max(1, len(cc))
        g_tout = sum(ll(r['z']) - ll(cor(r)) for r in ju) / max(1, len(ju))
        # descriptif : celui qui revient au 1er match (seul concerné), annoncé contre réel (A = vainqueur)
        prem = [r for r in cc if abs(r['x'][0] + r['x'][1]) == 1.0]
        ann = [(_sg(r['z']) if (r['x'][0] + r['x'][1]) > 0 else 1 - _sg(r['z']), int((r['x'][0] + r['x'][1]) > 0)) for r in prem]
        positif = len(cc) >= MIN_CONCERNES and (l0c - l1c) >= MARGE and g_tout > 0
        out[c] = {'appris_concernes': len(av), 'juges': len(ju), 'juges_concernes': len(cc),
                  'beta_court': round(b[0], 4), 'beta_long': round(b[1], 4),
                  'log_loss_concernes_sans': round(l0c, 5), 'log_loss_concernes_avec': round(l1c, 5),
                  'gain_concernes': round(l0c - l1c, 5), 'gain_tous': round(g_tout, 6), 'positif': bool(positif),
                  'premier_match_retour': {'matchs': len(ann),
                                           'elo_pct': round(100 * sum(a for a, _ in ann) / max(1, len(ann)), 1),
                                           'reel_pct': round(100 * sum(v for _, v in ann) / max(1, len(ann)), 1)}}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'definition': (f"retour = match précédent à {SEUIL_J} jours ou plus ; poids 1, 1/2, 1/4 sur les 3 premiers "
                          f"matchs ; court < {LONG_J} jours ≤ long"),
           'regle': ("β appris 2016–2022, jugé 2023 → ; positif si −0,001 de log loss sur ≥ 300 matchs concernés et gain "
                     "positif sur tous les matchs, par circuit"),
           'circuits': juger(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
