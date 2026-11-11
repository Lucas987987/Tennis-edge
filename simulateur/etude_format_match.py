#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_format_match.py — en ATP, l'Elo tient-il compte du FORMAT du match (2 ou 3 sets gagnants) ? (11/11/2026, audit)

Constat de l'audit, fait sur 2018–2022 SEULEMENT (simulateur/rapport_audit.json, paquet 227) : l'Elo donne le même %
quel que soit le format. En ATP il est trop sûr de lui en 2 sets gagnants (favori 64,5 % réels pour 67,3 % annoncés,
pente 0,81) et pas assez en 3 sets gagnants (74,0 % pour 71,0 %, pente 1,21). Les deux biais se compensent quand on
mélange les formats — d'où le rejet de « échelle de l'Elo par circuit » le 29/10/2026, qui n'est pas la même piste.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production : options de elo_etat.json,
départ bas des petits niveaux) et mis à jour APRÈS CHAQUE MATCH. Matchs jugés : ATP, sans abandon.

RÈGLE ÉCRITE LE 11/11/2026 (rapport_audit.json, paquet 227), AVANT DE REGARDER 2023 → :
  une pente par format, p' = σ(pente · logit p), apprise sur 2018–2022, jugée sur 2023 → juin 2026. Elle est retenue si,
  DANS CHAQUE FORMAT (2 sets gagnants ET 3 sets gagnants) :
    a) la log loss gagne au moins 0,001 sur au moins 1 000 matchs jugés ;
    b) le gain vaut au moins 2 erreurs types (condition ajoutée le 11/11/2026 avec l'accord de Lucas, avant le rejeu) ;
    c) le biais a le même sens sur les deux périodes (pente réapprise sur 2023 → du même côté de 1).
  Si un seul format passe, RIEN n'est adopté par ce script : le verdict de chaque format est publié et Lucas décide.
  Rien en WTA ni en Challenger (pentes 1,06 et 0,96 sur 2018–2022) : mesurés pour mémoire, jamais adoptés ici.

Usage : python simulateur/etude_format_match.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
SORTIE = os.path.join(ICI, 'rapport_format_match.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def ll(z):
    """Log loss d'un match vu du vainqueur (z = logit de la probabilité donnée au vainqueur)."""
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def pente(Z):
    """Pente k qui minimise la log loss de σ(k·z) (vainqueur = 1) ; Newton, sans constante (symétrique)."""
    k = 1.0
    for _ in range(60):
        g = h = 0.0
        for z in Z:
            q = _sg(k * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h < 1e-9:
            break
        k -= g / h
    return k


def lignes(archive, racine):
    """[(circuit, date, format, z du vainqueur)] — Elo de production, lu AVANT le match, mis à jour juste après."""
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    el, bas = E.de_production(racine)
    rows = []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in ('ATP', 'WTA', 'CH') and DEBUT <= m['date'] < FIN and not m.get('abandon'):
            rows.append((c, m['date'], m['bo'], _lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    return rows


def mesure(Z, k=None):
    """Favori annoncé / réel, pente propre à l'échantillon, et gain d'une pente k donnée (avec son erreur type)."""
    n = len(Z)
    if not n:
        return {'matchs': 0}
    out = {'matchs': n,
           'favori_annonce_pct': round(100 * sum(max(_sg(z), 1 - _sg(z)) for z in Z) / n, 1),
           'favori_reel_pct': round(100 * sum(1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z in Z) / n, 1),
           'log_loss': round(sum(ll(z) for z in Z) / n, 5), 'pente_propre': round(pente(Z), 3)}
    if k is not None:
        d = [ll(z) - ll(k * z) for z in Z]
        moy = sum(d) / n
        et = math.sqrt(sum((x - moy) ** 2 for x in d) / n) / math.sqrt(n)
        out.update(gain=round(moy, 5), erreur_type=round(et, 5), erreurs_types=round(moy / et, 2) if et else None)
    return out


def verdict(appr, juge, k):
    """La règle, pour UN format : (passe ?, raisons)."""
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f"gain sous {MIN_ERREURS_TYPES:g} erreurs types")
    if juge.get('pente_propre') is None or (juge['pente_propre'] - 1) * (k - 1) <= 0:
        raisons.append("biais de sens contraire sur 2023 →")
    return not raisons, raisons


def etudier(rows):
    out = {'circuits': {}}
    for c in ('ATP', 'WTA', 'CH'):
        bloc = {}
        for bo in (3, 5):
            A = [z for cc, d, b, z in rows if cc == c and b == bo and d < COUPURE]
            J = [z for cc, d, b, z in rows if cc == c and b == bo and d >= COUPURE]
            if len(A) < 200:
                continue
            k = pente(A)
            appr, juge = mesure(A, k), mesure(J, k)
            ok, raisons = verdict(appr, juge, k)
            bloc[f"{2 if bo == 3 else 3}_sets_gagnants"] = {'pente_apprise': round(k, 3), '2018–2022': appr,
                                                           '2023 → juin 2026': juge, 'passe_la_regle': ok,
                                                           'raisons': raisons}
        out['circuits'][c] = bloc
    atp = out['circuits'].get('ATP') or {}
    formats = ('2_sets_gagnants', '3_sets_gagnants')
    out['adopte'] = bool(all((atp.get(f) or {}).get('passe_la_regle') for f in formats))
    out['pentes_atp'] = {f: (atp.get(f) or {}).get('pente_apprise') for f in formats}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(archive, racine)
    doc = etudier(rows)
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               regle=("par format en ATP : pente apprise sur 2018–2022, jugée sur 2023 → juin 2026 ; retenue si, dans "
                      "CHAQUE format, le gain atteint 0,001 sur au moins 1 000 matchs, vaut au moins 2 erreurs types, "
                      "et si le biais a le même sens sur les deux périodes ; WTA et Challenger pour mémoire"),
               elo="réglé comme la production (elo.de_production), mis à jour après chaque match",
               options_elo=E.options_production(racine)[0])
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, bloc in doc['circuits'].items():
        for f_, v in bloc.items():
            j = v['2023 → juin 2026']
            print(f"{c} {f_} : pente {v['pente_apprise']} ; jugé sur {j['matchs']} matchs, favori {j['favori_reel_pct']} % "
                  f"pour {j['favori_annonce_pct']} % ; gain {j.get('gain')} ± {j.get('erreur_type')} "
                  f"({j.get('erreurs_types')} erreurs types) ; passe : {v['passe_la_regle']} {v['raisons']}")
    print('ADOPTÉ' if doc['adopte'] else 'NON ADOPTÉ', doc['pentes_atp'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
