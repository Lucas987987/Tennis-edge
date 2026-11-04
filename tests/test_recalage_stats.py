import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import recalage_stats as RS  # noqa: E402


def _fiche(c, jour, moy, q, reel, brute=False):
    d = {'feuille': [{'premiere_pct': moy}, {'premiere_pct': moy}],
         'fourchette': [{'premiere_pct': q}, {'premiere_pct': q}]}
    if brute:
        d['feuille_brute'] = [{'premiere_pct': moy - 10}, {'premiere_pct': moy - 10}]
        d['fourchette_brute'] = [{'premiere_pct': [q[0] - 10, q[1] - 10]}, {'premiere_pct': [q[0] - 10, q[1] - 10]}]
    return {'circuit': c, 'debut': f'{jour}T12:00', 'dernier': d}, {'feuille': [{'premiere_pct': reel}, {'premiere_pct': reel}]}


def test_recaler_decalage_largeur_et_bornes():
    assert RS.recaler(None, 'breaks', 3.0, 1.0, 5.0) == (3.0, 1.0, 5.0)
    m, lo, hi = RS.recaler({'delta': 2.0, 'largeur': 0.5}, 'premiere_pct', 60.0, 50.0, 70.0)
    assert (m, lo, hi) == (62.0, 57.0, 67.0)
    m, lo, hi = RS.recaler({'delta': -1.0, 'largeur': 1.0}, 'breaks', 0.5, 0.0, 2.0)
    assert lo == 0.0 and m == 0.0                     # jamais négatif
    _, lo, hi = RS.recaler({'delta': 5.0, 'largeur': 1.0}, 'premiere_pct', 97.0, 94.0, 99.0)
    assert hi == 100.0                                # % borné à 100


def test_apprendre_corrige_un_biais_de_niveau():
    rows = [{'jour': '2026-11-01', 'c': 'ATP', 'k': 'premiere_pct', 'moy': 60.0, 'p10': 55.0, 'p90': 65.0,
             'reel': 64.0 + (i % 5)} for i in range(200)]
    co = RS.apprendre(rows)['ATP']['premiere_pct']
    assert abs(co['delta'] - 4.0) < 1e-9              # écart 6 × 200 / (200 + 100)
    avant, apres = RS.mesurer(rows), RS.mesurer(rows, RS.apprendre(rows))
    assert apres['erreur_couverture'] < avant['erreur_couverture']


def test_juger_regle_fixee():
    a = {'cases': {'ATP|aces': {'couverture': 90.0, 'ecart': 2.0}, 'CH|breaks': {'couverture': 93.0, 'ecart': 1.4}},
         'erreur_couverture': 11.5, 'ecart_moyen': 1.7}
    b = {'cases': {'ATP|aces': {'couverture': 82.0, 'ecart': 1.9}, 'CH|breaks': {'couverture': 81.0, 'ecart': 1.4}},
         'erreur_couverture': 1.5, 'ecart_moyen': 1.65}
    assert RS.juger(a, b)[0]
    b2 = dict(b, cases=dict(b['cases'], **{'ATP|aces': {'couverture': 96.0, 'ecart': 1.9}}))
    assert not RS.juger(a, b2)[0]                     # une case s'éloigne de 80 % de plus de 5 points
    b3 = dict(b, ecart_moyen=1.8)
    assert not RS.juger(a, b3)[0]                     # l'écart moyen monte


def test_lignes_prennent_les_valeurs_brutes():
    f, r = _fiche('WTA', '2026-11-02', 70.0, [60.0, 80.0], 66.0, brute=True)
    L = RS.lignes({'u': f}, {'u': r})
    assert len(L) == 2 and L[0]['moy'] == 60.0 and L[0]['p10'] == 50.0


def test_lire_coefs_seulement_si_adopte(tmp_path):
    (tmp_path / 'simulateur').mkdir()
    p = tmp_path / 'simulateur' / 'recalage_stats.json'
    p.write_text(json.dumps({'decision': {'adopte': False, 'coefs': {'ATP': {}}}}), encoding='utf-8')
    assert RS.lire_coefs(str(tmp_path)) is None
    p.write_text(json.dumps({'decision': {'adopte': True, 'coefs': {'ATP': {'breaks': {'delta': 0, 'largeur': .75}}}}}),
                 encoding='utf-8')
    assert RS.lire_coefs(str(tmp_path)) == {'ATP': {'breaks': {'delta': 0, 'largeur': .75}}}


def test_vitrine_recaler_feuille():
    import vitrine as V
    fp = [{'breaks': 3.0, 'aces': 5.0}, {'breaks': 2.0}]
    fq = [{'breaks': [1.0, 5.0], 'aces': [2.0, 9.0]}, {'breaks': [0.0, 4.0]}]
    assert V.recaler_feuille('ATP', fp, fq, coefs={}) == (fp, fq)
    fp2, fq2 = V.recaler_feuille('ATP', fp, fq, coefs={'ATP': {'breaks': {'delta': 0.0, 'largeur': 0.5}}})
    assert fq2[0]['breaks'] == [2.0, 4.0] and fq2[0]['aces'] == [2.0, 9.0] and fq[0]['breaks'] == [1.0, 5.0]
    assert V.recaler_feuille('WTA', fp, fq, coefs={'ATP': {'breaks': {'delta': 0.0, 'largeur': 0.5}}}) == (fp, fq)
