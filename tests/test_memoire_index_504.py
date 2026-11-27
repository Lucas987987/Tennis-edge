# -*- coding: utf-8 -*-
"""28/11/2026 (paquet 504) — Steam pipeline coupé : validation_report.py montait à 15 Go (blocs « confirmation
Betfair » et « âge du mouvement ») puis canal_clv.py achevait la machine. Cause : l'enregistrement COMPLET de chaque
courbe (prix compris) était gardé en mémoire juste pour construire l'index des matchs, comme move_audit.py avant le
30/08/2026. Désormais seuls les champs lus par match_key.build_index() sont gardés : même index."""
import os
import random
import re
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import match_key as mk  # noqa: E402


def test_meme_index_avec_les_champs_seuls():
    rng = random.Random(5)
    joueurs = [f'Joueur {i}' for i in range(30)]
    recs = []
    for i in range(400):
        h, a = rng.sample(joueurs, 2)
        jour = 1 + rng.randrange(20)
        r = {'uid': f'u{i % 250}', 'book': rng.choice(['pinnacle', 'bet365', 'betfair-ex']),
             'home': h if rng.random() < 0.5 else None, 'home_team': h, 'away': a, 'away_team': a if rng.random() < 0.5 else None,
             'commence_time': f'2026-09-{jour:02d}T{rng.randrange(8, 22):02d}:00:00Z',
             'tournament': rng.choice(['ATP X', 'WTA Y', '']),
             'home_curve': [[f'2026-09-01T10:{m:02d}:00Z', 1.5 + m / 100] for m in range(50)],
             'away_curve': [[f'2026-09-01T10:{m:02d}:00Z', 2.5 - m / 100] for m in range(50)]}
        if rng.random() < 0.3:
            r['fixture_id'] = f'fx{rng.randrange(60)}'
        recs.append(r)
    plein, leger = mk.build_index(recs), mk.build_index([mk.cle_index(r) for r in recs])
    for r in recs:
        assert plein.key_of(r['uid']) == leger.key_of(r['uid'])
    assert 'home_curve' not in mk.cle_index(recs[0])


def test_plus_aucun_enregistrement_complet_garde_pour_l_index():
    for f in ('validation_report.py', 'canal_clv.py', 'alert_control_test.py', 'move_audit.py'):
        t = '\n'.join(l for l in open(os.path.join(R, 'scripts', f), encoding='utf-8') if not l.lstrip().startswith('#'))
        assert not re.search(r'(_recs|records|recs|_records)\.append\(r\)', t), f
    y = open(os.path.join(R, '.github', 'workflows', 'steam_pipeline.yml'), encoding='utf-8').read()
    assert 'python scripts/discret.py --pouls 3 -- python scripts/canal_clv.py || true' in y
