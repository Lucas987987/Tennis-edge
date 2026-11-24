# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 426) — grand écran du direct, analyse détaillée refaite, filtre de fiabilité aligné."""
import pathlib
import re

P = (pathlib.Path(__file__).resolve().parent.parent / 'algo' / 'index.html').read_text(encoding='utf-8')


def test_grand_ecran():
    assert 'function entrerPlein(el, uid)' in P and 'function quitterPlein()' in P and 'function statsPlein(m, r)' in P
    assert "class=\"btn lv-plein-b\"" in P and "class=\"btn lv-pe-x\"" in P and '.live-match.plein{position:fixed;inset:0' in P
    assert 'requestFullscreen' in P and "addEventListener(ev, () =>" in P                  # sortie du plein écran système
    assert "deja.dataset.vue === String(vue3dLive())" in P                                  # mise à jour sur place
    for cle in ('pe_bouton', 'pe_quitter', 'pe_attente'):
        assert len(re.findall(r'\b' + cle + ':', P)) == 2, cle


def test_analyse_detaillee():
    i = P.index('function ouvrirAnalyseDetaillee(m){')
    f = P[i:P.index('\n}\n', i)]
    for mot in ('Le duel', 'Où se joue le match', 'La carte de l’outsider', 'En direct'):
        assert mot in f
    for ancien in ('Conclusion', 'Scénarios de score les plus fréquents', 'Fiabilité de la prévision'):
        assert ancien not in f
    assert 'cote' not in f.lower() and 'marché' not in f


def test_filtre_fiabilite():
    assert '<span class="fiab-lab" data-t="fiab" aria-hidden="true"></span>' in P
    assert '.circuits button,.fiab-filtre button{min-height:44px;min-width:44px}' in P
