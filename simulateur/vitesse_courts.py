#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vitesse_courts.py — la vitesse de chaque tournoi, sur l'échelle du Court Pace Index (CPI) (04/11/2026, demande de Lucas).

1. CPI OFFICIEL (simulateur/cpi_officiel.json) : les valeurs publiées (graphiques TennisTV, compilées par Court Speed,
   courtspeed.com) — 14 tournois seulement (Grands Chelems, Masters 1000, ATP Finals), 2012 → 2026. Rien pour les
   ATP 250/500, la WTA ni les Challengers.
2. NOTRE INDICE, pour CHAQUE édition de CHAQUE tournoi (ATP, Challenger, WTA, ITF femmes en donnée) : ce que les
   serveurs y gagnent AU-DELÀ de ce qu'attendait l'Elo service / retour d'avant-match face à ces adversaires
   (elo_service_retour.py : le niveau des joueurs est retiré), et leurs aces au-delà de leur taux habituel :
       service = Σ (points gagnés − points joués × attendu) / Σ points joués
       aces    = Σ (aces − points joués × taux d'aces habituel du serveur) / Σ points joués
3. ÉTALONNAGE sur les éditions où le CPI officiel existe (ATP) : CPI ≈ a + b·service + c·aces (moindres carrés),
   jugé en « un tournoi laissé de côté » (l'étalonnage ne voit jamais l'édition qu'il prédit). Puis un CPI ESTIMÉ
   pour toutes les éditions, tous circuits — affiché sur la fiche du match (information : n'entre pas dans le
   pronostic ; la vitesse du court est déjà un facteur du modèle, facteurs.py).
Aucune cote. Usage : python simulateur/vitesse_courts.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import re
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402

FICHIER_CPI = os.path.join('simulateur', 'cpi_officiel.json')
SORTIE = os.path.join('simulateur', 'vitesse_courts.json')
PRIOR_ACES = 200.0          # points : taux d'aces habituel rapproché de la moyenne du circuit
MIN_PTS_EDITION = 600       # points de service au minimum pour qu'une édition ait un indice
RETRAIT_PTS = 2000.0        # CPI estimé : rapproché de la moyenne quand l'édition a peu de points
MOTS = r"\b(atp|wta|ch|challenger|masters?|open|1000|500|250|125|championships?|international|tennis|cup|classic|trophy|presented by .*)\b"
# noms de l'archive Sackmann / TennisApi → clé des tournois du CPI officiel
ALIAS = {'indian wells': 'indian wells', 'miami': 'miami', 'monte carlo': 'monte carlo', 'madrid': 'madrid',
         'rome': 'rome', 'roma': 'rome', 'canada': 'canada', 'montreal': 'canada', 'toronto': 'canada',
         'cincinnati': 'cincinnati', 'shanghai': 'shanghai', 'paris': 'paris', 'australian': 'australian open',
         'melbourne': 'australian open', 'roland garros': 'roland garros', 'wimbledon': 'wimbledon',
         'us': 'us open', 'tour finals': 'atp finals', 'finals': 'atp finals', 'turin': 'atp finals',
         'atp finals': 'atp finals', 'rolex paris': 'paris', 'rolex monte carlo': 'monte carlo',
         'mutua madrid': 'madrid', 'internazionali bnl d\'italia': 'rome', 'italian': 'rome', 'national bank': 'canada'}


def norme(nom):
    """Clé de tournoi commune à l'archive et à TennisApi : sans accents, sans pays, sans « Masters / CH / Open »."""
    s = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    s = s.split(',')[0]
    s = re.sub(r'[-_/.]', ' ', s)
    garde = s
    s = re.sub(MOTS, ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if 'tour finals' in garde or 'nitto' in garde:
        return 'atp finals'
    if garde.strip().startswith('us open'):
        return 'us open'
    if 'australian open' in garde:
        return 'australian open'
    return s or garde.strip()


def cle_officielle(nom):
    n = norme(nom)
    if re.search(r'olympi|next ?gen|davis|united cup|laver', n):          # autres épreuves dans la même ville
        return None
    for k, v in ALIAS.items():
        if n == k or n.startswith(k + ' '):
            return v
    return None


def lire_cpi(racine):
    with open(os.path.join(racine, FICHIER_CPI), encoding='utf-8') as f:
        doc = json.load(f)
    return {(t, int(a)): float(c) for t, ans in doc['cpi'].items() for a, c in ans.items()}


def matchs(archive, racine, depuis=2015):
    """[(jour, circuit, surface, tournoi normalisé, nom, gagnant, perdant, stats, détail)] archive + feuilles."""
    import donnees
    import elo as E
    import feuilles as FE
    M = donnees.charger(archive, depuis)
    fin = max(m['date'] for m in M) if M else dt.date(2000, 1, 1)
    F = [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    out = []
    for m in M + F:
        if not m.get('stats') or not m.get('complet') or m.get('abandon') or not m.get('detail'):
            continue
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if g and p and g != p:
            out.append((m['date'], m.get('tour', 0), m.get('num', 0), m['circuit'], m['surface'], norme(m.get('tournoi')),
                        m.get('tournoi') or '', g, p, m['stats'], m['detail']))
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    return out


def indices(M, eta=0.0015):
    """{(circuit, tournoi, année): {'pts', 'service', 'aces', 'nom', 'surface', 'debut', 'fin'}} — notes d'avant le jour."""
    el, jour, attente = SR.EloSR(eta), None, []
    ace_j, ace_c = {}, {}                       # joueur → [aces, points] ; circuit → [aces, points]
    E = {}
    for d, _, _, c, s, t, nom, g, p, st, det in M:
        if d != jour:
            for y in attente:
                el.maj(*y[:5])
                for srv, (n_, a_) in y[5]:
                    A = ace_j.setdefault(srv, [0.0, 0.0])
                    A[0] += a_
                    A[1] += n_
                    C = ace_c.setdefault(y[2], [0.0, 0.0])
                    C[0] += a_
                    C[1] += n_
            attente, jour = [], d
        e = E.setdefault((c, t, d.year if not (d.month == 12 and d.day > 25) else d.year + 1),
                         {'pts': 0.0, 'res': 0.0, 'res_ace': 0.0, 'nom': nom, 'surface': s, 'debut': d, 'fin': d})
        e['fin'] = max(e['fin'], d)
        aces = []
        for srv, rel, cle in ((g, p, 'w'), (p, g, 'l')):
            n, w = st[cle]
            dd = det.get(cle)
            if not n:
                continue
            e['pts'] += n
            e['res'] += w - n * el.p_service(srv, rel, c, s)
            if dd:
                a_ = dd[4]
                C = ace_c.get(c, [0.0, 0.0])
                moy = C[0] / C[1] if C[1] else 0.07
                A = ace_j.get(srv, [0.0, 0.0])
                r = (A[0] + PRIOR_ACES * moy) / (A[1] + PRIOR_ACES)
                e['res_ace'] += a_ - n * r
                aces.append((srv, (n, a_)))
        attente.append((g, p, c, s, st, aces))
    out = {}
    for (c, t, an), e in E.items():
        if e['pts'] >= MIN_PTS_EDITION:
            out[(c, t, an)] = {'pts': round(e['pts']), 'service': e['res'] / e['pts'], 'aces': e['res_ace'] / e['pts'],
                               'nom': e['nom'], 'surface': e['surface'], 'debut': e['debut'].isoformat(),
                               'fin': e['fin'].isoformat()}
    return out


def _resoudre(X, y, ridge=1e-6):
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (ridge if i == j and i > 0 else 0.0) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * yy for x, yy in zip(X, y)) for i in range(k)]
    for i in range(k):                                   # Gauss
        piv = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[piv], b[i], b[piv] = A[piv], A[i], b[piv], b[i]
        for r in range(k):
            if r != i and A[i][i]:
                f = A[r][i] / A[i][i]
                A[r] = [A[r][j] - f * A[i][j] for j in range(k)]
                b[r] -= f * b[i]
    return [b[i] / A[i][i] for i in range(k)]


def etalonner(I, cpi):
    """Moindres carrés CPI ~ a + b·service + c·aces sur les éditions ATP au CPI connu ; erreur « un tournoi de côté »."""
    rows = []
    for (c, t, an), v in I.items():
        if c != 'ATP':
            continue
        k = cle_officielle(v['nom']) or cle_officielle(t)
        if k and (k, an) in cpi:
            rows.append((k, an, v, cpi[(k, an)]))
    if len(rows) < 15:
        return None, rows
    X = [[1.0, r[2]['service'], r[2]['aces']] for r in rows]
    y = [r[3] for r in rows]
    coef = _resoudre(X, y)
    pred_loo, err = [], []
    for t in sorted({r[0] for r in rows}):
        tr = [i for i, r in enumerate(rows) if r[0] != t]
        cf = _resoudre([X[i] for i in tr], [y[i] for i in tr])
        for i, r in enumerate(rows):
            if r[0] == t:
                p = sum(a * b for a, b in zip(cf, X[i]))
                pred_loo.append((p, y[i]))
                err.append(abs(p - y[i]))
    my, mp = sum(y) / len(y), sum(p for p, _ in pred_loo) / len(pred_loo)
    cov = sum((p - mp) * (yy - my) for p, yy in pred_loo)
    sp = math.sqrt(sum((p - mp) ** 2 for p, _ in pred_loo))
    sy = math.sqrt(sum((yy - my) ** 2 for _, yy in pred_loo))
    naif = sum(abs(yy - my) for yy in y) / len(y)
    return {'coefs': [round(x, 4) for x in coef], 'editions': len(rows),
            'erreur_moyenne_tournoi_de_cote': round(sum(err) / len(err), 2),
            'erreur_moyenne_sans_indice': round(naif, 2),
            'correlation_tournoi_de_cote': round(cov / (sp * sy), 3) if sp and sy else None,
            'cpi_moyen': round(my, 1)}, rows


def cpi_estime(v, coef, moyen):
    brut = coef[0] + coef[1] * v['service'] + coef[2] * v['aces']
    w = v['pts'] / (v['pts'] + RETRAIT_PTS)
    return w * brut + (1 - w) * moyen


def classe(cpi):
    return 'lente' if cpi < 30 else 'moyennement lente' if cpi < 35 else 'moyenne' if cpi < 40 else \
        'moyennement rapide' if cpi < 45 else 'rapide'


def construire(archive, racine):
    cpi = lire_cpi(racine)
    I = indices(matchs(archive, racine))
    et, rows = etalonner(I, cpi)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'source_cpi_officiel': 'graphiques TennisTV compilés par Court Speed (courtspeed.com) — 14 tournois',
           'etalonnage': et, 'tournois': {}}
    if not et:
        return out
    for (c, t, an), v in I.items():
        if c == 'ITF':
            continue
        e = cpi_estime(v, et['coefs'], et['cpi_moyen'])
        k = cle_officielle(v['nom']) or cle_officielle(t) if c == 'ATP' else None
        off = cpi.get((k, an)) if k else None
        out['tournois'].setdefault(f'{c}|{t}', {})[str(an)] = {
            'cpi_estime': round(e, 1), 'classe': classe(off if off is not None else e), 'cpi_officiel': off,
            'points': v['pts'], 'nom': v['nom'], 'surface': v['surface'], 'debut': v['debut'], 'fin': v['fin']}
    out['comparaison'] = [{'tournoi': r[0], 'annee': r[1], 'cpi_officiel': r[3],
                           'cpi_estime': round(cpi_estime(r[2], et['coefs'], et['cpi_moyen']), 1)} for r in rows]
    return out


def vitesse_du_match(doc, circuit, tournoi, jour):
    """Pour la fiche : édition en cours (ou la dernière connue) du tournoi de ce match ; None si inconnu."""
    T = (doc or {}).get('tournois') or {}
    ed = T.get(f'{circuit}|{norme(tournoi)}')
    if not ed:
        return None
    an = str(jour.year)
    v = ed.get(an) or ed.get(str(jour.year - 1))
    if not v:
        return None
    return dict(v, annee=int(an) if an in ed else jour.year - 1)


def historique(doc, circuit, tournoi, jusqu_a=None, n=16):
    """05/11/2026 — pour le visuel de la fiche : [{an, cpi, officiel}] des éditions du tournoi (CPI officiel s'il existe,
    sinon notre CPI estimé), les n dernières jusqu'à l'année jusqu_a comprise."""
    ed = ((doc or {}).get('tournois') or {}).get(f'{circuit}|{norme(tournoi)}') or {}
    out = []
    for an, v in sorted(ed.items()):
        if jusqu_a and int(an) > jusqu_a:
            continue
        off = v.get('cpi_officiel')
        cpi = off if off is not None else v.get('cpi_estime')
        if cpi is not None:
            out.append({'an': int(an), 'cpi': round(float(cpi), 1), 'officiel': off is not None})
    return out[-n:]


def main(argv):
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    doc = construire(archive, racine)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    et = doc.get('etalonnage') or {}
    print(f"Vitesse des courts : {len(doc['tournois'])} tournois · étalonnage {et}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
