"""Paquet 349 — candidates du chercheur contrôlées en direct (A) et Challenger favori 50–60 % (B)."""
import gzip
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import controle_candidates as CC  # noqa: E402
import etude_ch_50_60 as B  # noqa: E402


def _racine(tmp, matchs):
    """matchs : [(uid, jour, circuit, surface, p, gagnant, tour_feuille, interrompu)]"""
    os.makedirs(tmp / 'simulateur' / 'journal_pronostics')
    os.makedirs(tmp / 'Tennis_Edge_Lab' / 'live')
    os.makedirs(tmp / 'feuilles')
    with gzip.open(tmp / 'simulateur' / 'journal_pronostics' / '2026-11-01.jsonl.gz', 'wt', encoding='utf-8') as f:
        for uid, j, c, s, p, *_ in matchs:
            for passage, pp in ((f'{j}T08:00:00Z', 0.5), (f'{j}T11:00:00Z', p), (f'{j}T13:00:00Z', 0.99)):  # le 3e : après le début
                f.write(json.dumps({'uid': uid, 'passage': passage, 'debut_utc': f'{j}T12:00:00+00:00', 'circuit': c,
                                    'surface': s, 'meilleur_des': 3, 'home': 'A ' + uid, 'away': 'B ' + uid,
                                    'combinaison': {'p_home': pp}}) + '\n')
    res = [{'uid': uid, 'reel': {'gagnant': g, 'interrompu': it}} for uid, j, c, s, p, g, t, it in matchs]
    json.dump({'matchs': res}, open(tmp / 'Tennis_Edge_Lab' / 'live' / 'pronostics_resultats.json', 'w'))
    with gzip.open(tmp / 'feuilles' / '2026-11-01.jsonl.gz', 'wt', encoding='utf-8') as f:
        for uid, j, c, s, p, g, t, it in matchs:
            if t:
                f.write(json.dumps({'jour': j, 'tour': t, 'home': {'nom': 'B ' + uid}, 'away': {'nom': 'A ' + uid}}) + '\n')
    return str(tmp)


def test_charger_dernier_avant_debut_et_tour(tmp_path):
    r = _racine(tmp_path, [('mun', '2026-11-01', 'CH', 'Hard', 0.7, 'home', 'Qualification Round 1', False),
                           ('mdeux', '2026-11-01', 'CH', 'Clay', 0.6, 'away', 'Round of 32', False),
                           ('mtrois', '2026-11-01', 'CH', 'Clay', 0.6, 'away', None, 'abandon')])
    X = {round(x['p'], 3): x for x in CC.charger(r)}
    assert len(X) == 2                                   # abandon écarté
    assert X[0.7]['y'] == 1 and X[0.7]['tour'] == 0      # pronostic d'avant le début ; noms inversés dans la feuille
    assert X[0.6]['y'] == 0 and CC.case_du_match('tour', X[0.6]) == '32es ou poule'
    assert CC.case_du_match('saison', X[0.7]) == 'septembre-décembre'


def test_verdicts():
    piste = {'parametre': 1.2}
    peu = [{'p': .7, 'y': 1}] * 50
    assert CC.controler(peu, piste)['verdict'] == 'en attente'
    trop_prudent = [{'p': .7, 'y': 1}] * 170 + [{'p': .7, 'y': 0}] * 30      # gagne 85 % pour 70 % annoncés
    v = CC.controler(trop_prudent, piste)
    assert v['verdict'] == 'confirmée' and v['pente_direct'] > 1 and v['gain'] > 0
    juste = [{'p': .7, 'y': 1}] * 140 + [{'p': .7, 'y': 0}] * 60
    assert CC.controler(juste, piste)['verdict'] == 'non confirmée'


def test_en_service_et_non_controlable(tmp_path):
    os.makedirs(tmp_path / 'simulateur')
    json.dump({'corrections': [{'id': 'CH_terre', 'circuit': 'CH', 'surface': 'Clay', 'pente': 1.065}]},
              open(tmp_path / 'simulateur' / 'corrections_chercheur.json', 'w'))
    assert CC.en_service(str(tmp_path), {'famille': 'surface', 'circuit': 'CH', 'case': 'Clay'})
    assert not CC.en_service(str(tmp_path), {'famille': 'surface', 'circuit': 'CH', 'case': 'Hard'})
    assert 'niveau du tournoi' not in CC.CONTROLABLES


def test_ch_50_60_regle():
    assert B.COUPURE == '2026-11-23' and B.N_MIN == 1000 and B.GAIN_MIN == 0.001 and 0.0 in B.GRILLE
    trop = ([{'circuit': 'CH', 'debut': '2026-11-01', 'p': .55, 'y': 1}] * 50
            + [{'circuit': 'CH', 'debut': '2026-11-01', 'p': .55, 'y': 0}] * 50)        # 50 % gagnés pour 55 %
    d = B.etudier(trop)
    assert d['apprentissage']['delta'] < 0 and d['verdict'].startswith('pas encore jugeable')
    assert B.favori({'p': .45, 'y': 0}) == (.55, 1)
    assert not B.dans_tranche({'circuit': 'ATP', 'p': .55, 'y': 1}) and not B.dans_tranche({'circuit': 'CH', 'p': .65, 'y': 1})
    J = [{'circuit': 'CH', 'debut': '2026-12-01', 'p': .55, 'y': i % 2} for i in range(1200)]
    d = B.etudier(trop + J)
    assert d['verdict'] == 'RETENU' and d['jugement']['matchs'] == 1200
    J = [{'circuit': 'CH', 'debut': '2026-12-01', 'p': .55, 'y': int(i % 20 < 11)} for i in range(1200)]  # 55 % : calibré
    assert B.etudier(trop + J)['verdict'] == 'NON RETENU'


def test_workflows_et_worker():
    w = open(os.path.join(RACINE, 'workers', 'tennis-edge-closing', 'worker.js'), encoding='utf-8').read()
    for wf, ev in (('etude_ancrage.yml', 'etude_ancrage'), ('chercheur.yml', 'chercheur')):
        assert f"workflowFile: '{wf}'" in w and f"evenement: '{ev}'" in w
        y = open(os.path.join(RACINE, '.github', 'workflows', wf), encoding='utf-8').read()
        assert f'types: [{ev}]' in y and 'push --force' not in y
    y = open(os.path.join(RACINE, '.github', 'workflows', 'chercheur.yml'), encoding='utf-8').read()
    assert 'python simulateur/controle_candidates.py .' in y and 'simulateur/rapport_controle_candidates.json' in y
    y = open(os.path.join(RACINE, '.github', 'workflows', 'etude_ancrage.yml'), encoding='utf-8').read()
    assert 'python simulateur/etude_ch_50_60.py .' in y and 'simulateur/rapport_ch_50_60.json' in y


def test_rapports_sans_noms():
    for f in ('rapport_controle_candidates.json', 'rapport_ch_50_60.json'):
        t = open(os.path.join(RACINE, 'simulateur', f), encoding='utf-8').read().lower()
        assert 'home' not in t and 'pinnacle' not in t and 'cote' not in t
