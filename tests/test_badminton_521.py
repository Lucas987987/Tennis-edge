"""521 : badminton — favoris et notifications, post du jour, pages de référencement."""
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def test_page_favoris_post_et_liens():
    h = lire('algo', 'badminton.html')
    assert "const kj=n=>'bad:'+n,km=id=>'bad:'+id;" in h
    assert "fetch('/compte/api/favoris'" in h and 'data-fav="joueur"' in h and 'id="b-fav"' in h
    assert 'id="post-admin"' in h and 'MOI.admin||(MOI.compte&&MOI.compte.admin)' in h
    assert 'href="/badminton/matchs"' in h and 'href="/badminton/joueurs"' in h
    assert '.value' not in h


def test_workflow_telegram_et_pages():
    y = lire('.github', 'workflows', 'pronostics_badminton.yml')
    for s in ('TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        assert '${{ secrets.%s }}' % s in y
    p = lire('badminton', 'pronostics_badminton.py')
    assert 'pages_badminton.publier(cf, archives, maintenant, CLE_ARCHIVE, journal)' in p
    assert "etat.get('post_envoye') != jour" in p


def test_worker_notifs_et_routes():
    w = lire('workers', 'algo', 'worker.js')
    assert 'notifsBad(env)' in w and "'/sitemap-bad.xml'" in w and 'sitemap-bad.xml\\n' in w
    n = lire('workers', 'algo', 'notifs.js')
    assert "prefixe: 'bad:'" in n and "'notifs/etat_bad.json'" in n
