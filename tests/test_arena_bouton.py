# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 408, Lucas) — le bouton Arena dit « service en développement » et ne mène plus vers une page en
construction."""
import pathlib

PAGE = (pathlib.Path(__file__).resolve().parent.parent / 'algo/index.html').read_text(encoding='utf-8')


def test_arena_ne_mene_plus_nulle_part():
    assert 'Tennis-edge/arena' not in PAGE and 'href="https://lucas987987.github.io' not in PAGE
    assert '<button type="button" class="arena-nav" id="b-arena"' in PAGE and 'id="arena-bulle"' in PAGE
    assert PAGE.count('arena_btn:') == 2 and PAGE.count('arena_msg:') == 2
    assert 'service en développement' in PAGE and 'service in development' in PAGE
