#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_documentation_itf.py — LE SIGNAL « DOCUMENTATION FAIBLE » A-T-IL ENCORE LIEU D'ÊTRE AVEC LES RÉSULTATS ITF ?
(25/11/2026, paquet 452, Lucas : « si on a plus d'informations, documentation faible n'a plus lieu d'être pour certains
matchs »).

LE SIGNAL. Adopté le 05/11/2026 en Challenger (etude_documentation.py) : quand le joueur le moins vu a moins de 500
points de service cumulés (archive + feuilles de match), le % est écarté de 50 % : p' = σ(1,844 · logit p). Appris sur
nos pronostics rejoués d'août–septembre 2026, AVANT que l'Elo ait les résultats ITF hommes (28/10) et le départ des
joueurs ITF à 1000 (11/11). Les points de service ne comptent pas les matchs ITF (pas de feuille) : un joueur qui a
joué cent matchs ITF peut rester « peu documenté » alors que l'Elo le connaît bien.
Constat qui a mené à la question (analyse 448, direct, joueurs à moins de 30 matchs, 93 matchs) : Elo seul 75,1 %
annoncé pour 75,3 % réel ; % publié 81,5 % pour 73,1 %. Ce constat oriente la question sans rien décider.

REJEU. Challenger comme en production (etude_depart_itf.matchs : archive + résultats ITF hommes, elo.de_production,
départs par niveau, mis à jour après chaque match ; sans abandon ni compétition par équipes). Points de service
cumulés au jour du match (etude_documentation.Compteur, comme la production). Base : l'Elo seul.

RÈGLE ÉCRITE LE 25/11/2026, AVANT TOUT ESSAI (matchs « peu documentés » = moins de 500 points pour le moins vu) :
  apprentissage 01/01/2025 → 30/09/2025 ; jugement UNE SEULE FOIS 01/10/2025 → 31/05/2026.
  V0 « comme aujourd'hui » : tous les matchs peu documentés, pente 1,844 (celle en place).
  V1 « ITF compris » : seulement ceux où le moins connu a AUSSI moins de 30 matchs dans l'Elo (ITF compris), pente
     1,844 ; les autres matchs peu documentés ne sont plus touchés.
  Mesure : gain de log loss par match peu documenté, contre l'Elo sans le signal.
  Q1. Le signal en place aide-t-il encore ? Il est jugé NUISIBLE si V0 fait perdre (gain < 0) sur la période jugée
      ET sur la période d'apprentissage, avec au moins 1 000 matchs peu documentés jugés.
  Q2. V1 vaut-il mieux que V0 ? Retenu si, sur au moins 1 000 matchs peu documentés jugés, V1 bat V0 d'au moins 0,001
      par match, et le bat aussi (écart > 0) sur la période d'apprentissage.
  Publiés sans décider : la pente réapprise sur l'apprentissage pour V0 et V1 (et son effet jugé), le détail par
  classe d'expérience Elo, et nos matchs en direct où le signal a joué (log loss avec et sans lui, moins de 30 matchs
  Elo contre 30 et plus).
  Rien n'entre en production par ce paquet : les réponses sont proposées à Lucas.
Limite : l'Elo seul, sans la simulation ni les autres signaux ; le % publié en a.

Rapport public : simulateur/rapport_documentation_itf.json — comptes et pentes seulement, aucun nom de joueur.
Usage : python simulateur/etude_documentation_itf.py /tmp/sackmann .
        python simulateur/etude_documentation_itf.py --journal-depuis-rapport simulateur/rapport_documentation_itf.json
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_etalonnage_cases as EC  # noqa: E402

PAQUET = 452
DEBUT, COUPURE, FIN = dt.date(2025, 1, 1), dt.date(2025, 10, 1), dt.date(2026, 6, 1)
SEUIL_BALLES, SEUIL_ELO, PENTE_EN_PLACE = 500, 30, 1.844
MIN_JUGES, MARGE = 1000, 0.001
SORTIE = os.path.join(ICI, 'rapport_documentation_itf.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_452.json')


def rejeu(archive, racine):
    """[(date, z Elo du vainqueur, points de service du moins vu, matchs Elo du moins connu)] — Challenger."""
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    import etude_documentation as EDO
    M, n_itf = ED.matchs(archive, racine)
    cpt = EDO.Compteur(EDO.evenements(archive, racine))
    el, bas = E.de_production(racine)
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c == 'CH' and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            n = cpt.au(m['date'].isoformat())
            rows.append((m['date'], EC._lg(el.proba(g, p, s)), min(n.get(g, 0), n.get(p, 0)), min(el.matchs(g), el.matchs(p))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


def touche(r, variante):
    _, _, balles, n_elo = r
    return balles < SEUIL_BALLES and (variante == 'V0' or n_elo < SEUIL_ELO)


def gain(R, variante, a):
    """Gain moyen de log loss (sans − avec) sur les matchs peu documentés R, avec son erreur type."""
    d = [EC.ll(r[1]) - EC.ll(a * r[1] if touche(r, variante) else r[1]) for r in R]
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'touches': sum(touche(r, variante) for r in R), 'gain': round(g, 5), 'erreur_type': round(et, 5)}


def ecart(R, a0, a1):
    """V1 (pente a1) contre V0 (pente a0), par match peu documenté."""
    d = [EC.ll(a0 * r[1] if touche(r, 'V0') else r[1]) - EC.ll(a1 * r[1] if touche(r, 'V1') else r[1]) for r in R]
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'v1_moins_v0': round(g, 5), 'erreur_type': round(et, 5)}


def juger(rows):
    peu = [r for r in rows if r[2] < SEUIL_BALLES]
    A = [r for r in peu if r[0] < COUPURE]
    J = [r for r in peu if r[0] >= COUPURE]
    out = {'matchs_challenger': len(rows), 'peu_documentes': len(peu),
           'peu_documentes_dont_moins_de_30_matchs_elo': sum(r[3] < SEUIL_ELO for r in peu)}
    a_v0 = EC.pente([r[1] for r in A])[0] if A else None
    a_v1 = EC.pente([r[1] for r in A if r[3] < SEUIL_ELO])[0] if any(r[3] < SEUIL_ELO for r in A) else None
    out['V0'] = {'apprentissage': gain(A, 'V0', PENTE_EN_PLACE), 'jugement': gain(J, 'V0', PENTE_EN_PLACE),
                 'pente_reapprise': round(a_v0, 3) if a_v0 else None,
                 'jugement_avec_pente_reapprise': gain(J, 'V0', a_v0) if a_v0 else None}
    out['V1'] = {'apprentissage': gain(A, 'V1', PENTE_EN_PLACE), 'jugement': gain(J, 'V1', PENTE_EN_PLACE),
                 'pente_reapprise': round(a_v1, 3) if a_v1 else None,
                 'jugement_avec_pente_reapprise': gain(J, 'V1', a_v1) if a_v1 else None}
    out['V1_contre_V0'] = {'apprentissage': ecart(A, PENTE_EN_PLACE, PENTE_EN_PLACE),
                           'jugement': ecart(J, PENTE_EN_PLACE, PENTE_EN_PLACE)}
    out['pente_reelle_jugee'] = {
        'peu_documentes': EC.decrire([r[1] for r in J]).get('pente'),
        'dont_moins_de_30_matchs_elo': EC.decrire([r[1] for r in J if r[3] < SEUIL_ELO]).get('pente'),
        'dont_30_matchs_elo_et_plus': EC.decrire([r[1] for r in J if r[3] >= SEUIL_ELO]).get('pente')}
    j0, a0 = out['V0']['jugement'], out['V0']['apprentissage']
    out['Q1_signal_nuisible'] = bool(j0.get('matchs', 0) >= MIN_JUGES and j0.get('gain', 0) < 0 and a0.get('gain', 0) < 0)
    e_j, e_a = out['V1_contre_V0']['jugement'], out['V1_contre_V0']['apprentissage']
    out['Q2_V1_retenu'] = bool(e_j.get('matchs', 0) >= MIN_JUGES and e_j.get('v1_moins_v0', -1) >= MARGE
                               and e_a.get('v1_moins_v0', -1) > 0)
    return out


def direct(racine):
    """Nos matchs Challenger où le signal a joué : log loss avec et sans lui (son décalage retiré), par expérience Elo."""
    L = [r for r in EC.lignes_direct(racine) if r['c'] == 'CH' and 'documentation_faible' in (r.get('decalages') or {})]
    out = {}
    for nom, G in (('moins_de_30_matchs_elo', [r for r in L if r['n'] < SEUIL_ELO]),
                   ('30_matchs_elo_et_plus', [r for r in L if r['n'] >= SEUIL_ELO])):
        d = [EC.ll(r['z_fiche'] - r['decalages']['documentation_faible']) - EC.ll(r['z_fiche']) for r in G]
        n = len(d)
        if not n:
            out[nom] = {'matchs': 0}
            continue
        g = sum(d) / n
        et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
        out[nom] = {'matchs': n, 'gain_du_signal': round(g, 4), 'erreur_type': round(et, 4),
                    'favori_annonce_pct': EC.decrire([r['z_fiche'] for r in G]).get('favori_annonce_pct'),
                    'favori_reel_pct': EC.decrire([r['z_fiche'] for r in G]).get('favori_reel_pct')}
    return out


def fr(v):
    return str(v).replace('.', ',')


def entree_journal(doc, gabarit):
    j = doc['jugement']
    v0, v1, e = j['V0']['jugement'], j['V1']['jugement'], j['V1_contre_V0']['jugement']
    res = (f" RÉSULTAT (jugé du 01/10/2025 au 31/05/2026 sur {v0.get('matchs', 0)} matchs Challenger peu documentés) : "
           f"signal en place {fr(v0.get('gain'))} ± {fr(v0.get('erreur_type'))} par match (apprentissage "
           f"{fr(j['V0']['apprentissage'].get('gain'))}) ; limité aux joueurs à moins de 30 matchs Elo "
           f"{fr(v1.get('gain'))} ± {fr(v1.get('erreur_type'))} ; écart {fr(e.get('v1_moins_v0'))} ± {fr(e.get('erreur_type'))}. "
           f"Q1 (signal nuisible) : {'oui' if j['Q1_signal_nuisible'] else 'non'} ; Q2 (limiter aux joueurs peu connus "
           f"de l'Elo) : {'retenu' if j['Q2_V1_retenu'] else 'non retenu'}. Proposé à Lucas ; rien n'est changé par ce paquet.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + res + ' Le % de victoire ne change pas.', 'garde_fou': gabarit['garde_fou']}


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            EC.ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, n_itf = rejeu(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'itf_hommes_dans_le_rejeu': n_itf, 'jugement': juger(rows), 'direct': direct(racine), 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EC.ajouter_au_journal(JOURNAL, doc['entree_journal'])
    print(json.dumps({k: doc[k] for k in ('jugement', 'direct')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
