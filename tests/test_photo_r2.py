# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 414, Lucas : « stocker sur Cloudflare comme le reste ») — les gros fichiers des pronostics vivent
au coffre R2 ; git n'en reçoit qu'une photo toutes les 2 h ; les journaux figés publics ne montrent que les matchs commencés."""
import gzip
import json
import os
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import pronostics_prives as PP  # noqa: E402


def test_coffre_couvre_les_gros_fichiers(tmp_path):
    j = tmp_path / 'simulateur' / 'journal_pronostics'
    (j / 'apres_match').mkdir(parents=True)
    (j / 'styles_global_v1.jsonl').write_text('', encoding='utf-8')
    with gzip.open(j / 'apres_match' / '2026-11-24.json.gz', 'wt') as f:
        f.write('{}')
    (tmp_path / 'Tennis_Edge_Lab' / 'live').mkdir(parents=True)
    (tmp_path / PP.RESULTATS).write_text('{}', encoding='utf-8')
    L = PP.fichiers_locaux(str(tmp_path))
    assert PP.RESULTATS in L and 'simulateur/journal_pronostics/styles_global_v1.jsonl' in L
    assert 'simulateur/journal_pronostics/apres_match/2026-11-24.json.gz' in L


def test_journaux_figes_publics_seulement_matchs_commences(tmp_path):
    j = tmp_path / 'simulateur' / 'journal_pronostics'
    j.mkdir(parents=True)
    lignes = [{'uid': 'a', 'debut_utc': '2026-11-24T10:00:00+00:00'}, {'uid': 'b', 'debut_utc': '2026-11-24T18:00:00+00:00'},
              {'uid': 'c', 'debut': '2026-11-24T09:00:00+00:00'}]
    (j / 'styles_global_v1.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lignes), encoding='utf-8')
    PP.rendre_public(str(tmp_path), '2026-11-24T12:00')
    gardes = [json.loads(l)['uid'] for l in (j / 'styles_global_v1.jsonl').read_text(encoding='utf-8').splitlines()]
    assert gardes == ['a', 'c']


def test_photo_git_toutes_les_2h():
    wf = (R / '.github' / 'workflows' / 'pronostics_quotidien.yml').read_text(encoding='utf-8')
    i = wf.index('- name: Publier')
    seg = wf[i:]
    toujours = seg[:seg.index('derniere=$(git log -1')]
    for gros in ('simulateur/pronostics_log.jsonl', 'simulateur/journal_pronostics', 'pronostics_resultats.json', 'algo/donnees.json'):
        assert gros not in toujours.split('# 24/11/2026 (paquet 414')[0], gros
    assert '${PHOTO_MIN:-110}' in seg and 'git add -- simulateur/pronostics_log.jsonl simulateur/journal_pronostics' in seg
    pages = (R / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
    assert '--seulement Tennis_Edge_Lab/live/pronostics_resultats.json' in pages
