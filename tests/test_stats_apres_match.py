# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 411, Lucas) — la vraie feuille d'un match terminé s'affiche dès la fin, sans attendre le bilan
après match : la page la demande au worker (/live/stats), qui la garde 24 h une fois le match dans les terminés."""
import pathlib

R = pathlib.Path(__file__).resolve().parent.parent
PAGE = (R / 'algo/index.html').read_text(encoding='utf-8')
WORKER = (R / 'workers/algo/worker.js').read_text(encoding='utf-8')


def test_page_demande_la_feuille_d_un_match_termine():
    i = PAGE.index('function statsFiche')
    seg = PAGE[i:PAGE.index('function rendStatsLive', i)]
    assert 'LIVE.vus[uf]' in seg and '!LIVE.par_uid[uf]' in seg and 'st.o.final' in seg
    assert "statsFiche();   // 411" in PAGE                         # dès l'ouverture de la fiche
    assert PAGE.count('ls_note_fin:') == 2


def test_worker_garde_la_feuille_definitive():
    assert 'STATS_FINAL_TTL_MS = 24 * 3600 * 1000' in WORKER
    assert 'await estTermine(env, id)) o.final = true' in WORKER
