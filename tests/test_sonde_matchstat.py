# -*- coding: utf-8 -*-
"""Paquet 331 — sonde Matchstat : budget respecté, réserve de quota protégée, clé jamais écrite, comparaison Sackmann."""
import io
import json
import os
import sys
import urllib.error

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import sonde_matchstat as S  # noqa: E402

CLE = 'cle-secrete-123456789'


class Rep(io.BytesIO):
    def __init__(self, doc, restant=500, code=200):
        super().__init__(json.dumps(doc).encode())
        self.status = code
        self.headers = {'x-ratelimit-requests-remaining': str(restant), 'x-ratelimit-requests-limit': '1000'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


FIX = {'data': [{'id': 900001, 'player1': {'id': 11, 'name': 'Jan Choinski'}, 'player2': {'id': 22, 'name': 'Max Purcell'},
                 'tournament': {'id': 7001, 'name': 'Heilbronn Challenger'}}] + [{'id': 900002 + i} for i in range(3)]}
RES = {'data': [{'id': 900001, 'player1': {'id': 11, 'name': 'Jan Choinski'}, 'player2': {'id': 22, 'name': 'Max Purcell'},
                 'match_winner': 11}, {'id': 2}]}
FEUILLE = {'data': {'stats': [{'name': 'Aces', 'p1': 5, 'p2': 3}, {'name': 'Double Faults', 'p1': 2, 'p2': 4},
                              {'name': 'Service Points', 'p1': 60, 'p2': 70}]}}


def faux(restant=500, appels=None):
    def ouvrir(req, timeout=0):
        u = req.full_url
        if appels is not None:
            appels.append(u)
        if '/fixtures/' in u:
            return Rep(FIX, restant)
        if '/tournament/results/' in u:
            return Rep(RES, restant)
        if '/match-stats/' in u:
            return Rep(FEUILLE, restant)
        raise urllib.error.HTTPError(u, 404, 'x', {}, io.BytesIO(b'{}'))
    return ouvrir


def sackmann(tmp):
    d = tmp / 'atp'
    d.mkdir()
    (d / 'atp_matches_qual_chall_2019.csv').write_text(
        'tourney_id,tourney_level,tourney_date,winner_name,loser_name,w_ace,l_ace,w_df,l_df,w_svpt,l_svpt\n'
        '2019-1,C,20190506,Jan Choinski,Max Purcell,5,3,2,4,60,70\n2019-1,C,20190506,A B,C D,,,,,,\n', encoding='utf-8')
    return str(tmp)


def test_feuille_trouvee_comparee_a_sackmann_et_volumes(tmp_path):
    appels = []
    r = S.sonder(CLE, budget=12, sackmann=sackmann(tmp_path), ouvrir=faux(appels=appels), echantillons=(('atp', '2019-05-08', 'challenger'),))
    assert len(appels) <= 12
    assert r['chemin_stats'] == '/tennis/v2/atp/h2h/match-stats/{id}/{id}/{id}'
    comp = r['echantillons'][0]['comparaison_sackmann']
    assert comp['ace'] == {'matchstat': [5, 3], 'sackmann': [5, 3], 'egal': True} and comp['svpt']['egal']
    assert r['volumes_2018_2025']['Challengers'] == {'matchs': 2, 'tournois': 1, 'avec_stats_sackmann': 1}
    assert r['requetes_pour_tout_recuperer'] == {'unite': 'matchs', 'total': 2}
    assert any('3/3' in x for x in r['conclusion'])


def test_budget_et_reserve_de_quota():
    appels = []
    S.sonder(CLE, budget=2, ouvrir=faux(appels=appels))
    assert len(appels) == 2
    appels = []
    S.sonder(CLE, budget=12, ouvrir=faux(restant=S.RESERVE, appels=appels))
    assert len(appels) == 1, 'sous la réserve, la sonde s’arrête après la première réponse'


def test_rapport_sans_cle(tmp_path):
    r = S.sonder(CLE, budget=12, ouvrir=faux())
    assert CLE not in json.dumps(r, ensure_ascii=False)


def test_workflow_manuel_lecture_seule():
    w = open(os.path.join(RACINE, '.github/workflows/sonde_matchstat.yml'), encoding='utf-8').read()
    assert 'workflow_dispatch' in w and 'contents: read' in w and 'git push' not in w
    assert 'secrets.RAPIDAPI_KEY' in w and 'sonde_matchstat.json' in w


def test_331b_part_des_tournois_connus_sans_la_liste_du_jour(tmp_path, monkeypatch):
    (tmp_path / 'tournois_ids.json').write_text(json.dumps({
        'ATP Heilbronn Challenger': {'tour': 'atp', 'id': 7001}, 'WTA W35 Monastir': {'tour': 'wta', 'id': 9},
        'WTA Midland': {'tour': 'wta', 'id': 7002}, '_discovered_at': 'x'}), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    ech = S.echantillons_connus(annee=2019)
    assert ech == (('atp', '2019', 'challenger', 7001, 'ATP Heilbronn Challenger'), ('wta', '2019', 'principal', 7002, 'WTA Midland'))
    appels = []
    r = S.sonder(CLE, budget=6, sackmann=sackmann(tmp_path), ouvrir=faux(appels=appels), echantillons=ech[:1])
    assert not any('/fixtures/' in u for u in appels) and len(appels) == 2
    assert r['echantillons'][0]['comparaison_sackmann']['ace']['egal']


def test_331b_resultats_ranges_par_tour():
    doc = {'data': {'rounds': [{'name': 'R1', 'matches': [RES['data'][0]]}, {'name': 'F', 'matches': [{'match_winner': 3}]}]}}
    assert len(S.tous_les_matchs(doc)) == 2
