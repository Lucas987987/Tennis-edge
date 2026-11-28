"""528 : le badminton relié depuis le tennis et le tennis de table ; l'accès Plus dit qu'il comprend les trois."""
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def test_liens_et_textes():
    h = lire('algo', 'index.html')
    assert 'href="/badminton" data-t="bad_btn">🏸 Badminton</a>' in h and 'data-t="lg_bad"' in h
    assert h.count("bad_btn:'🏸 Badminton', lg_bad:'Badminton'") == 2
    assert 'le tennis, le tennis de table et le badminton' in h and 'tennis, table tennis and badminton' in h
    t = lire('algo', 'tennis-de-table.html')
    assert '<a class="btn" href="/badminton" id="l-bad">Badminton</a>' in t
    assert 'le tennis, le tennis de table et le badminton' in t
    for p in ('tennis-de-table.html', 'badminton.html'):
        assert 'flex-wrap:wrap;justify-content:flex-end}' in lire('algo', p)
