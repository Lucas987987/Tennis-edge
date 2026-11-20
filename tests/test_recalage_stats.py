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
    # 05/11/2026 : non adopté → seulement les cases adoptées directement (repli figé faute de données)
    assert RS.lire_coefs_ancien(str(tmp_path)) == RS.REPLI_DIRECT
    p.write_text(json.dumps({'decision': {'adopte': False}, 'direct': {'ATP|aces': {'retire': True}}}), encoding='utf-8')
    assert 'aces' not in RS.lire_coefs_ancien(str(tmp_path))['ATP']
    p.write_text(json.dumps({'decision': {'adopte': True, 'coefs': {'ATP': {'breaks': {'delta': 0, 'largeur': .75}}}}}),
                 encoding='utf-8')
    assert RS.lire_coefs_ancien(str(tmp_path)) == {'ATP': {'breaks': {'delta': 0, 'largeur': .75}}}


def test_lire_coefs_case_par_case(tmp_path):
    # 11/11/2026 (paquet 225) : variante en place de chaque case ; sans données, repli figé (largeur 1)
    (tmp_path / 'simulateur').mkdir()
    co = RS.lire_coefs(str(tmp_path))
    assert co['ATP']['premiere_pct'] == RS.REPLI_DIRECT['ATP']['premiere_pct']
    assert 'aces' not in co['ATP']                               # « sans » au départ
    p = tmp_path / 'simulateur' / 'recalage_stats.json'
    p.write_text(json.dumps({'cases': {'ATP|aces': {'variante': 'delta'}}}), encoding='utf-8')
    assert RS.lire_coefs(str(tmp_path)) == {'ATP': {'aces': {'delta': RS.REPLI_DIRECT['ATP']['aces']['delta'], 'largeur': 1.0}}}


def _lignes(n, reel, p10=0.0, p90=8.0, moy=4.0, jour='2026-11-02'):
    return [{'c': 'ATP', 'k': 'breaks', 'moy': moy, 'p10': p10, 'p90': p90, 'reel': reel(i), 'jour': jour} for i in range(n)]


def test_decider_cases_passe_a_la_meilleure_et_retire():
    # fourchette [0 ; 8] beaucoup trop large : le réel vaut 4 huit fois sur dix, 0 ou 8 sinon (décalage nul)
    sym = lambda i: 0.0 if i % 10 == 0 else 8.0 if i % 10 == 5 else 4.0  # noqa: E731
    appr, juge = _lignes(200, sym, jour='2026-10-26'), _lignes(60, sym)
    d = RS.decider_cases({'ATP|breaks': {'variante': 'sans', 'semaines_pires': 0}}, appr, juge, '2026-11-09')
    assert d['ATP|breaks']['variante'] == 'complet' and d['ATP|breaks']['depuis'] == '2026-11-09'
    # « delta » en place (décalage appris non nul) mais réel toujours au centre : même couverture, écart pire que
    # « sans » → une semaine pire, puis retrait à la deuxième
    appr2 = _lignes(200, lambda i: 8.0 if i % 5 == 0 else 4.0, jour='2026-10-26')
    juge2 = _lignes(60, lambda i: 4.0)
    d1 = RS.decider_cases({'ATP|breaks': {'variante': 'delta', 'semaines_pires': 0}}, appr2, juge2, '2026-11-16')
    assert d1['ATP|breaks']['variante'] == 'delta' and d1['ATP|breaks']['semaines_pires'] == 1
    d2 = RS.decider_cases(d1, appr2, juge2, '2026-11-23')
    assert d2['ATP|breaks']['variante'] == 'sans' and d2['ATP|breaks']['retiree'] == 'delta'


def test_vitrine_recaler_feuille():
    import vitrine as V
    fp = [{'breaks': 3.0, 'aces': 5.0}, {'breaks': 2.0}]
    fq = [{'breaks': [1.0, 5.0], 'aces': [2.0, 9.0]}, {'breaks': [0.0, 4.0]}]
    assert V.recaler_feuille('ATP', fp, fq, coefs={}) == (fp, fq)
    fp2, fq2 = V.recaler_feuille('ATP', fp, fq, coefs={'ATP': {'breaks': {'delta': 0.0, 'largeur': 0.5}}})
    assert fq2[0]['breaks'] == [2.0, 4.0] and fq2[0]['aces'] == [2.0, 9.0] and fq[0]['breaks'] == [1.0, 5.0]
    assert V.recaler_feuille('WTA', fp, fq, coefs={'ATP': {'breaks': {'delta': 0.0, 'largeur': 0.5}}}) == (fp, fq)


def test_retrait_direct_deux_semaines_pires():
    R = [{'c': 'ATP', 'k': 'aces', 'moy': 5.0, 'p10': 2.0, 'p90': 8.0, 'reel': 5.0, 'jour': '2026-11-02'} for _ in range(40)]
    a = RS.suivre_directes({}, [], R)
    assert a['ATP|aces']['semaines_pires'] == 1 and not a['ATP|aces']['retire']
    b = RS.suivre_directes(a, [], R)
    assert b['ATP|aces']['retire']
