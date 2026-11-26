"""Paquet 458 : plus de % sur de tout petits échantillons (Lucas, à propos de MatchUp : « comparer des joueurs avec
2 matchs »). Styles : pas de % sous 10 matchs sur le site, 30 dans les posts X, sans ✅/⚠️, sans « 5 derniers matchs »,
rien dans « Ce qu'il faut retenir » ; note de fiabilité d'un joueur à partir de 20 matchs."""
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'scripts'))
sys.path.insert(0, str(R / 'simulateur'))
H = (R / 'algo' / 'index.html').read_text(encoding='utf-8')


def test_styles_site():
    assert 'const STYLE_MIN = 10, STYLE_MIN_X = 30;' in H
    assert H.index('const STYLE_MIN = 10') < H.index('function verdictStyle(b){')       # déclarée avant usage
    assert 'b.n < STYLE_MIN || typeof b.attendu_pct' in H
    assert 'if (b.n < STYLE_MIN) return' in H


def test_styles_posts_x():
    assert 'g.n < STYLE_MIN_X || !j.style_adverse' in H
    assert 'contre ce style : ${v} victoire' not in H                                   # plus de « 5 derniers matchs »
    assert 'que prévu face aux ${styleLibPluriel(j.style_adverse)}' not in H             # plus rien dans « à retenir »
    assert "sens: 'info', txt: `${i18nNom(x.i===0?m.home:m.away)} : ${x.v.texte}.`" in H


def test_note_joueur_20_matchs():
    import performance_joueurs as PJ
    import note_par_match as NP
    assert PJ.MIN_NOTE == 20 and PJ.MIN_GROUPE == 10
    assert NP.MIN_MATCHS_JOUEUR == 5                                                     # le critère de la note du match garde 5


def test_forme_sans_signal_459():
    # 26/11/2026 (paquet 459) : forme récente — le fait, sans ✅/⚠️, et rien dans « Ce qu'il faut retenir »
    assert 'présente la meilleure dynamique récente' not in H
    assert "r.ecart >= 1 ? '✅'" not in H
    assert "l.push(`▪️ ${N[i]} : ${r.victoires} victoires sur ses ${r.matchs} derniers matchs" in H


def test_peu_documentes_460():
    # 26/11/2026 (paquet 460) : seulement sous 500 points, en info neutre, sans badge dans la liste
    assert 'const DOC_PEU = 500, DOC_TRES_PEU = 500;' in H
    assert "peuDocumentes(m).forEach(x=>L_.push({ sens:'info', txt: t('es_tres_peu'" in H
    assert 'class="badge peu"' not in H
