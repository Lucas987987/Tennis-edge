#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verif_comme_en_production.py — CONTRÔLE DES CORRECTIONS CHALLENGER SUR LE REJEU « COMME EN PRODUCTION » (21/11/2026,
paquet 319).

Les études des paquets 313 et 317 rejouent l'archive, où l'Elo des Challengers n'a PAS les résultats ITF hommes que la
production utilise (piège déjà rencontré aux paquets 229 et 230). Ce contrôle rejoue les Challengers comme en production
(résultats ITF hommes dans l'Elo, départs en place ; etude_depart_itf.matchs) du 01/01/2025 au 31/05/2026, et y applique
les corrections apprises sur l'archive, sans rien réapprendre :
  — pente des cases (paquet 318) : la pente de la classe d'expérience du moins connu (note de fiabilité v3) ;
  — zone d'hésitation (paquets 314–315) : classement, invitation, expérience, coefficients appris ensemble.
Base : l'Elo seul (sans les signaux), le même pour les deux. Rapport : simulateur/rapport_verif_production.json.
Usage : python simulateur/verif_comme_en_production.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import etude_depart_itf as ED  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import etude_outsiders_gagnants as EOG  # noqa: E402
import etude_hesitation as H  # noqa: E402
import etude_fiabilite_v3 as V3  # noqa: E402

DEBUT, FIN = dt.date(2025, 1, 1), dt.date(2026, 6, 1)
BETAS_HESITATION = (0.0447, -0.202, 0.0526)
SORTIE = os.path.join(ICI, 'rapport_verif_production.json')


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    M, n_itf = ED.matchs(archive, racine)
    X = EOG.extras(archive)
    el, bas = E.de_production(racine)
    mod = json.load(open(os.path.join(racine, 'simulateur', 'rapport_fiabilite_v3.json'), encoding='utf-8'))['modele']

    def a_classe(i):
        ks = [k for k in mod if k.startswith(f'CH|{i}|')]
        w = sum(mod[k]['matchs'] for k in ks)
        return sum(mod[k]['pente'] * mod[k]['matchs'] for k in ks) / w if w else mod['_circuits']['CH']
    nb, P0, P1, Z0, Z1 = {}, {}, {}, [], []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c == 'CH' and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            z = EO._lg(el.proba(g, p, s))
            n = min(el.matchs(g), el.matchs(p))
            if n >= 10:
                i = V3.classe_experience(n)
                P0.setdefault(i, []).append(z)
                P1.setdefault(i, []).append(a_classe(i) * z)
            pw = EOG._sg(z)
            if 0.5 < max(pw, 1 - pw) < 0.6:
                ex = X.get((str(m.get('tournoi_id') or ''), m.get('num') or 0, m.get('nom_g') or ''))
                vu = lambda j, r, e: {'rang': r, 'invite': (e or '') == 'WC', 'experience': nb.get(j, 0)}  # noqa: E731
                vg, vp = vu(g, ex[2] if ex else None, m.get('entree_g')), vu(p, ex[3] if ex else None, m.get('entree_p'))
                f, a, y = (vg, vp, 1) if pw > 0.5 else (vp, vg, 0)
                d = sum(b * H.indice(nm, f, a) for b, nm in zip(BETAS_HESITATION, ('classement', 'invitation', 'experience')))
                Z0.append(abs(z) if y else -abs(z))
                Z1.append(abs(z) + d if y else -abs(z) - d)
        if c in ('ATP', 'WTA', 'CH'):
            for j in (g, p):
                nb[j] = nb.get(j, 0) + 1
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    classes = {str(i): {'pente_reelle': round(V3.pente(P0[i]), 3), 'pente_appliquee': round(a_classe(i), 3),
                        **EO.bilan(P0[i], P1[i])} for i in sorted(P0)}
    tous0 = [z for i in sorted(P0) for z in P0[i]]
    tous1 = [z for i in sorted(P1) for z in P1[i]]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 319,
           'periode': '01/01/2025 → 31/05/2026', 'itf_hommes_dans_le_rejeu': n_itf,
           'pente_des_cases': {'tous': EO.bilan(tous0, tous1), 'par_classe_d_experience': classes},
           'zone_d_hesitation': EO.bilan(Z0, Z1),
           'conclusion': 'pente des cases : pire comme en production (retirée) ; zone d\'hésitation : même sens, gain plus faible (gardée, retrait automatique en place)',
           'descriptif': 'contrôle seulement'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: doc[k] for k in ('pente_des_cases', 'zone_d_hesitation')}, ensure_ascii=False)[:1500])


if __name__ == '__main__':
    main(sys.argv)
