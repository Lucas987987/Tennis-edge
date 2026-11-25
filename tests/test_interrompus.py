# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 427) — un match commencé puis interrompu reste dans le direct jusqu'à la fin."""
import pathlib
import re

R = pathlib.Path(__file__).resolve().parent.parent
P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
W = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')


def test_page():
    assert "function estInterrompu(x)" in P and "(commence ? 40 : 8)*3600e3" in P            # relié malgré l'heure de reprise
    assert "if (!liveUtile()) { if (Date.now() - liveDernierLent < 60e3) return;" in P       # un coup d'œil par minute
    assert len(re.findall(r'\blive_interrompu:', P)) == 2 and '.lv-on.pause{' in P


def test_worker():
    assert "export const INTERROMPUS_H = 72, VERIF_INTERROMPU_MS = 10 * 60e3" in W
    assert "matchs: [...(o.matchs || []), ...(o.interrompus || [])]" in W
    assert "o.interrompus = avant.interrompus || []" in W                                   # panne : rien de perdu
