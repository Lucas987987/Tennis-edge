#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_poids_cumules.py — les poids du mélange passent à la règle cumulée (12/11/2026, audit, paquet 242)

CE QUI CHANGE. Le paquet 241 a retenu la règle cumulée (etude_regles_fenetres.py : 9,4 % de semaines dans le mauvais
état contre 12,7 % pour la règle en place) pour toutes les règles du lundi jugées sur 42 jours glissants. Cette étude
portait déjà sur « un réglage qui touche tous les matchs, comme un poids du mélange ». Mais les poids du mélange ne
fournissaient pas le détail par match : ils gardaient la règle d'avant (0,001 deux semaines de suite). Ce paquet leur
fournit ce détail (entrainement_progressif.paires_match) : poids appris sur les feuilles contre poids de l'archive
(combinaison_feuilles), poids propres ATP, WTA et Challenger contre poids communs (poids_circuit), mélange propre aux
désaccords WTA contre le pronostic de production (desaccord_wta, sur les seuls désaccords : ailleurs rien ne change).

RÈGLE ÉCRITE LE 12/11/2026, AVANT DE LANCER CE REJEU :
  - aucune décision n'est prise sur ce rejeu : les pronostics hors échantillon exportés (pronostics_hors_echantillon
    .jsonl.gz) couvrent une quinzaine de semaines, trop peu pour juger une règle (« on ne juge rien sur 100 matchs ») ;
  - il sert à vérifier que le détail par match se calcule chaque lundi, que chaque match n'est compté qu'une fois, et
    à montrer, sans le juger, ce que chaque règle aurait décidé semaine par semaine ;
  - les désaccords WTA ne sont pas rejoués ici (ils demandent les arbres de production) ;
  - la combinaison de backtest_match_simule.py n'est pas concernée : elle est jugée sur une période fixe de
    l'archive (2025 → 01/02/2026), la même chaque semaine, sans fenêtre qui glisse.
Rien ne change le % de victoire dans ce paquet par lui-même : il change QUAND un poids entre ou sort.

Usage : python simulateur/etude_poids_cumules.py [--export pronostics_hors_echantillon.jsonl.gz]
"""
import datetime as dt
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import backtest_match_simule as BMS  # noqa: E402
import entrainement_progressif as EP  # noqa: E402
import stabilite as ST  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_poids_cumules.json')
CLES = ('combinaison_feuilles', 'poids_CH', 'poids_ATP', 'poids_WTA')


def charger(chemin):
    """(ligne, p_sim, p_elo) vus du vrai vainqueur, comme les « hors » de rejouer_saison."""
    out = []
    with gzip.open(chemin, 'rt', encoding='utf-8') as f:
        for l in f:
            e = json.loads(l)
            if e.get('p_sim') is None or e.get('p_elo') is None or e.get('gagnant') not in ('home', 'away'):
                continue
            v = e['gagnant'] == 'home'
            ps, pe = (e['p_sim'], e['p_elo']) if v else (1 - e['p_sim'], 1 - e['p_elo'])
            out.append(({'jour': dt.date.fromisoformat(e['jour']), 'circuit': e.get('circuit')}, ps, pe))
    return out


def verdicts(hors, lundi, poids_archive):
    """Les verdicts de la semaine du lundi donné, comme entrainement_progressif.rejouer_saison les calcule."""
    vus = [h for h in hors if h[0]['jour'] < lundi]
    lim = lundi - dt.timedelta(days=EP.FENETRE_JUGE_J)
    avant, juge = [h for h in vus if h[0]['jour'] < lim], [h for h in vus if h[0]['jour'] >= lim]
    if len(avant) < 300 or len(juge) < 200:
        return None
    wa = BMS.ajuster_poids([[EP._lg(pe), EP._lg(ps)] for _, ps, pe in avant])
    P = {'elo': wa[0], 'simulation': wa[1]}
    p_new = [EP.S.melange(P, pe, ps) for _, ps, pe in juge]
    p_arc = [EP.S.melange(poids_archive, pe, ps) for _, ps, pe in juge]
    l_new, l_arc = EP._ll(p_new), EP._ll(p_arc)
    out = {'combinaison_feuilles': {'adopte': l_new < l_arc, 'll': {'avec': l_new, 'sans': l_arc}, 'n': len(juge),
                                    'paires': EP.paires_match([h[0]['jour'] for h in juge], p_arc, p_new)}}
    for c in ('CH', 'ATP', 'WTA'):
        r = EP.poids_circuit(vus, P, lim, BMS.ajuster_poids, c)
        out['poids_' + c] = dict(r, n=r.get('n_juge', 0))
    return out


def rejouer(hors, poids_archive):
    j0, j1 = min(h[0]['jour'] for h in hors), max(h[0]['jour'] for h in hors)
    lundi = j0 + dt.timedelta(days=(7 - j0.weekday()) % 7)
    etats = {'en_place': {}, 'cumulee': {}}
    semaines = []
    compte = {k: {} for k in CLES}                  # contrôle : chaque match compté une fois au plus
    installation = {}                               # ce que ferait un état neuf (la règle installée ce lundi-là)
    while lundi <= j1 + dt.timedelta(days=7):
        V = verdicts(hors, lundi, poids_archive)
        if V:
            sem = {'lundi': str(lundi)}
            installation[str(lundi)] = {}
            for k in CLES:
                v = V[k]
                ll = v.get('ll') or {}
                a, _ = ST.decider(etats['en_place'], k, False, bool(v.get('adopte')), ll.get('avec'), ll.get('sans'),
                                  semaine=str(lundi))
                vu = (etats['cumulee'].get(k) or {}).get('cumul', {}).get('vu')
                for j in {j for j, _, _ in v.get('paires') or () if vu is None or j > vu}:
                    compte[k][j] = compte[k].get(j, 0) + 1          # semaines où ce jour est compté
                ini = {}
                ST.decider_cumule(ini, k, False, v.get('paires') or [])
                installation[str(lundi)][k] = ini[k]['adopte']
                b, _ = ST.decider_cumule(etats['cumulee'], k, False, v.get('paires') or [])
                c = etats['cumulee'][k]['cumul']
                sem[k] = {'n_juge': v.get('n'), 'gain_fenetre': round(ll['sans'] - ll['avec'], 5) if ll.get('avec') else None,
                          'regle_en_place': 'adopté' if a else 'pas adopté', 'regle_cumulee': 'adopté' if b else 'pas adopté',
                          'cumul_matchs': c['n'], 'cumul_gain': etats['cumulee'][k].get('gain')}
            semaines.append(sem)
        lundi += dt.timedelta(days=7)
    return semaines, etats, compte, installation


def main(argv):
    opt = {a.split('=')[0]: a.split('=', 1)[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    chemin = opt.get('--export') or os.path.join(ICI, 'pronostics_hors_echantillon.jsonl.gz')
    hors = charger(chemin)
    choix = json.load(open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8'))
    pa = (choix.get('combinaison') or {}).get('poids') or {}
    poids_archive = {'elo': pa['elo'], 'simulation': pa['simulation']}
    semaines, etats, compte, installation = rejouer(hors, poids_archive)
    doubles = {k: sum(1 for n in d.values() if n > 1) for k, d in compte.items()}
    changements = {k: {r: sum(1 for a, b in zip(semaines, semaines[1:]) if a[k][r] != b[k][r])
                       for r in ('regle_en_place', 'regle_cumulee')} for k in CLES}
    fin = {k: {r: semaines[-1][k][r] for r in ('regle_en_place', 'regle_cumulee')} if semaines else None for k in CLES}
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 242,
           'statut': 'controle',
           'regle': ("aucune décision sur ce rejeu (trop peu de semaines) : il vérifie que le détail par match se calcule "
                     "chaque lundi et que chaque match n'est compté qu'une fois, et montre ce que chaque règle aurait décidé"),
           'matchs_exportes': len(hors), 'semaines_rejouees': len(semaines),
           'jours_comptes_deux_fois': doubles,
           'changements_d_etat': changements, 'etat_a_la_fin': fin,
           'cumul_a_la_fin': {k: {'matchs': etats['cumulee'][k]['cumul']['n'], 'gain': etats['cumulee'][k].get('gain')}
                              for k in CLES if k in etats['cumulee']},
           'installee_ce_lundi_la': {l: {k: ('adopté' if v else 'pas adopté') for k, v in d.items()}
                                     for l, d in installation.items()},
           'semaines': semaines,
           'a_surveiller': "rejugé chaque lundi en production ; à relire quand la règle cumulée aura vu 1 000 matchs par poids"}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: rap[k] for k in ('matchs_exportes', 'semaines_rejouees', 'jours_comptes_deux_fois', 'installee_ce_lundi_la',
                                           'changements_d_etat', 'etat_a_la_fin', 'cumul_a_la_fin')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
