# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 510) — favoris du tennis de table (page) et leurs notifications (worker, Plus seulement)."""
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def test_page_favoris():
    h = lire('algo', 'tennis-de-table.html')
    assert "fetch('/compte/api/favoris'" in h and "const kj=n=>'tt:'+n,km=id=>'tt:'+id;" in h
    assert 'id="b-fav"' in h and 'data-fav="joueur"' in h and 'data-fav="match"' in h
    assert 'href="/?compte=inscription"' in h


def test_worker_notifications_tt():
    n = lire('workers', 'algo', 'notifs.js')
    assert 'export async function notifsTT(' in n and "ETAT_TT_R2 = 'notifs/etat_tt.json'" in n
    assert "TT_R2 = 'site/algo/tt.json'" in n
    w = lire('workers', 'algo', 'worker.js')
    assert 'notifsTT(env)' in w and "import { notifsDirect, notifsMatin, notifsTT } from './notifs.js'" in w
    assert 'workers/algo/test_notifs_tt.mjs' in lire('.github', 'workflows', 'deploy_algo.yml')
