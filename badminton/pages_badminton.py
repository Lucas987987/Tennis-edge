#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages_badminton.py — PAGES DE RÉFÉRENCEMENT DU BADMINTON (27/11/2026, paquet 521, Lucas : « les pages pour Google par
match et par joueur »). Même principe que le tennis de table (tennis_de_table/pages_tt.py, paquet 514).

Seulement des matchs TERMINÉS et jugés (le pronostic figé à l'heure prévue, le résultat, juste ou faux) : rien d'un
match à venir. Pages en français, statiques, envoyées directement à R2 (site/algo/badminton/…) par
pronostics_badminton.py à chaque passage, au fil des matchs jugés (aucun commit) :
  /badminton/match/<numéro>     un match terminé : % de l'algo avant le match, résultat (points de chaque manche), verdict ;
  /badminton/joueur/<nom>       un joueur (à partir de MIN_JOUEUR matchs jugés) : bilan de l'algo sur ses matchs, ses
                                derniers matchs ; en double, chacun des deux joueurs de la paire (comme l'Elo) ;
  /badminton/matchs, /badminton/joueurs  les index ;
  /sitemap-bad.xml              le plan de ces pages (annoncé dans robots.txt par le worker).
Le suivi des joueurs vit au coffre privé (prive/badminton/pages.json). Au premier passage, les matchs déjà archivés
depuis novembre 2026 sont rattrapés par lots de RATTRAPAGE. Un joueur est reconnu par son nom. Aucun conseil.
"""
import datetime as dt
import html
import json
import re
import unicodedata

SITE = 'https://gamesetalgo.com'
BASE = '/badminton'
CLE_ETAT = 'prive/badminton/pages.json'
PREFIXE = 'site/algo/badminton/'
CLE_SITEMAP = 'site/algo/sitemap-bad.xml'
MIN_JOUEUR = 3                    # matchs jugés pour avoir une page joueur
DERNIERS = 20                     # matchs gardés par joueur
RATTRAPAGE = 800                  # matchs archivés rattrapés par passage
DEBUT = (2026, 11)                # premier mois de l'archive
INDEX_MATCHS = 300                # matchs sur la page « matchs »
SITEMAP_JOURS = 90                # pages de match dans le plan : les 90 derniers jours (les joueurs : toutes)
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre')
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo('Europe/Paris')
except Exception:  # noqa: BLE001
    PARIS = dt.timezone(dt.timedelta(hours=1))

e = html.escape


LETTRES = str.maketrans({'ł': 'l', 'Ł': 'L', 'ø': 'o', 'Ø': 'O', 'đ': 'd', 'Đ': 'D', 'ß': 'ss', 'æ': 'ae', 'œ': 'oe', 'ı': 'i'})


def slug(nom):
    s = unicodedata.normalize('NFD', str(nom or '').translate(LETTRES)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:80] or 'joueur'


def cle_joueur(nom):
    return slug(nom)


def tournoi_fr(t, epreuve=None):
    court = re.sub(r',\s*(MS|WS|MD|WD|XD|Men|Women|Mixed)\b.*$', '', str(t or ''), flags=re.I).strip()
    return f"{court} · {epreuve}" if epreuve else court


def joueurs(nom):
    """Les joueurs d'un camp : le nom seul en simple, les deux noms de la paire en double (« A / B »)."""
    L = [x.strip() for x in str(nom or '').split('/') if x.strip()]
    return L if len(L) == 2 else [str(nom or '').strip()]


def date_fr(t):
    d = dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(PARIS)
    return f"{d.day} {MOIS[d.month - 1]} {d.year} à {d.hour} h {d.minute:02d}"


def score(x):
    h = sum(1 for a, b in x.get('manches') or [] if a > b)
    a = sum(1 for p, q in x.get('manches') or [] if q > p)
    return h, a


CSS = """:root{--bg:#0E0A24;--panel:#191338;--ink:#F4F1FF;--dim:#A9A2CC;--ok:#3ee08a;--ko:#ff6b7d;--ball:#D4FF3A;--line:rgba(255,255,255,.12)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.w{max-width:760px;margin:0 auto;padding:14px}header{display:flex;gap:10px;align-items:center;margin-bottom:10px}
header a{color:var(--ink);text-decoration:none;font-weight:700}.b{width:18px;height:18px;border-radius:50%;background:var(--ball);display:inline-block}
a{color:#2EE6FF}h1{font-size:1.5rem;line-height:1.2;margin:14px 0 6px}.sub{color:var(--dim);margin:0 0 12px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:12px 14px;margin:12px 0}
.ok{color:var(--ok)}.ko{color:var(--ko)}ul.l{padding-left:18px}ul.l li{margin:6px 0}small{color:var(--dim)}
.cta{display:inline-block;margin-top:8px;background:var(--ball);color:#141225;font-weight:600;padding:9px 15px;border-radius:999px;text-decoration:none}
footer{color:var(--dim);font-size:.8rem;margin-top:24px}"""
PIED = ("Ce site ne donne pas de conseil de pari. Les paris sportifs sont interdits aux mineurs. Jouer comporte des risques : "
        "endettement, isolement, dépendance. Pour être aidé, appelez le 09 74 75 13 13 (appel non surtaxé).")


def page(titre, desc, chemin, corps, ld=None, indexer=True):
    lds = ''.join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (ld or []))
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{SITE}{e(chemin)}">
{'' if indexer else '<meta name="robots" content="noindex, follow">'}<meta name="theme-color" content="#0E0A24">
<meta property="og:title" content="{e(titre)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{SITE}{e(chemin)}">
<meta property="og:site_name" content="Game Set Algo"><meta property="og:image" content="{SITE}/partage.png"><link rel="icon" href="/icone-192.png">{lds}
<style>{CSS}</style></head><body><div class="w">
<header><span class="b" aria-hidden="true"></span><a href="{BASE}">Game Set Algo · badminton</a></header>
{corps}
<footer><p><a href="{BASE}">Les pronostics du jour</a> · <a href="{BASE}/matchs">Matchs terminés</a> · <a href="{BASE}/joueurs">Joueurs</a> · <a href="/">Tennis</a></p><p>{e(PIED)}</p></footer>
</div></body></html>
"""


def _lien_joueur(nom, J):
    out = []
    for n in joueurs(nom):
        k = cle_joueur(n)
        out.append(f'<a href="{BASE}/joueur/{k}">{e(n)}</a>' if (J.get(k) or {}).get('n', 0) >= MIN_JOUEUR else e(n))
    return ' / '.join(out)


def page_match(x, J):
    sh, sa = score(x)
    gagnant, perdant = (x['h'], x['a']) if x['g'] == 1 else (x['a'], x['h'])
    sc = f"{sh}-{sa}" if x['g'] == 1 else f"{sa}-{sh}"
    manches = ', '.join(f"{a}-{b}" if x['g'] == 1 else f"{b}-{a}" for a, b in x.get('manches') or [])
    fav, pf = (x['h'], x['p_h']) if x['p_h'] >= 0.5 else (x['a'], 1 - x['p_h'])
    ep = str(x.get('epreuve') or '')
    quand = date_fr(x['t'])
    verdict = '<span class="ok">✅ vainqueur trouvé</span>' if x.get('bon') else '<span class="ko">❌ vainqueur manqué</span>'
    jh, ja = _lien_joueur(x['h'], J), _lien_joueur(x['a'], J)
    corps = f"""<h1>{e(x['h'])} – {e(x['a'])} : pronostic et résultat</h1>
<p class="sub">Badminton · {e(tournoi_fr(x.get('tournoi'), ep))}{(' · ' + e(x['tour'])) if x.get('tour') else ''} · {e(quand)}</p>
<div class="panel"><p><b>Résultat :</b> {e(gagnant)} bat {e(perdant)} {e(sc)}{(' (' + e(manches) + ')') if manches else ''}.</p>
<p><b>L'algo avant le match :</b> {e(fav)} gagnant à {round(100 * pf)} % — {verdict}.</p>
<p><small>Le pronostic est figé à l'heure prévue du match, puis comparé au résultat : tous les matchs, erreurs comprises.</small></p></div>
<p>Les joueurs : {jh} · {ja}</p>
<div class="panel"><p>Le % de victoire de chaque match du jour des circuits BWF, simples et doubles.</p><a class="cta" href="{BASE}">Voir les pronostics du jour</a></div>"""
    titre = f"{x['h']} – {x['a']} : pronostic de l'algo et résultat (badminton, {ep})"
    desc = (f"{x['h']} contre {x['a']}, {tournoi_fr(x.get('tournoi'), ep)}, {quand} : l'algo donnait {fav} à {round(100 * pf)} %. "
            f"Résultat : {gagnant} {sc}.")
    ld = [{'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': f"{x['h']} – {x['a']}", 'sport': 'Badminton',
           'startDate': dt.datetime.fromtimestamp(int(x['t']), dt.timezone.utc).isoformat(),
           'competitor': [{'@type': 'Person', 'name': n} for n in joueurs(x['h']) + joueurs(x['a'])],
           'url': f"{SITE}{BASE}/match/{x['id']}"}]
    return page(titre, desc, f"{BASE}/match/{x['id']}", corps, ld)


def page_joueur(k, j):
    n, v = j['n'], j['v']
    bons = j['bons']
    li = []
    for m in j['derniers']:
        res = '<span class="ok">V</span>' if m['v'] else '<span class="ko">D</span>'
        avec = f" (avec {e(m['avec'])})" if m.get('avec') else ''
        li.append(f'<li>{res} <a href="{BASE}/match/{m["id"]}">contre {e(m["adv"])}</a>{avec} — {e(m["sc"])} · {e(date_fr(m["t"]).split(" à ")[0])}'
                  f'<br><small>L\'algo lui donnait {m["p"]} % · {"✅" if m["bon"] else "❌"}</small></li>')
    eps = ' · '.join(sorted(j.get('epreuves') or []))
    corps = f"""<h1>{e(j['nom'])}</h1><p class="sub">Badminton · {e(eps)} · {n} matchs suivis par l'algo</p>
<div class="panel"><p><b>{v} victoire{'s' if v > 1 else ''} – {n - v} défaite{'s' if n - v > 1 else ''}</b> sur ces matchs.</p>
<p>L'algo a trouvé le vainqueur de <b>{bons} de ses {n} matchs</b> ({round(100 * bons / n)} %), erreurs comprises.</p></div>
<h2>Ses derniers matchs</h2><ul class="l">{''.join(li)}</ul>
<div class="panel"><p>Son prochain match, avec le % de l'algo, est sur la page du jour.</p><a class="cta" href="{BASE}">Voir les pronostics du jour</a></div>
<p><a href="{BASE}/joueurs">Tous les joueurs</a></p>"""
    titre = f"{j['nom']} : pronostics et résultats de l'algo (badminton)"
    desc = f"{j['nom']} (badminton, {eps}) : {v} victoires et {n - v} défaites sur {n} matchs suivis ; l'algo a trouvé {bons} vainqueurs sur {n}."
    ld = [{'@context': 'https://schema.org', '@type': 'Person', 'name': j['nom'], 'url': f"{SITE}{BASE}/joueur/{k}"}]
    return page(titre, desc, f"{BASE}/joueur/{k}", corps, ld)


def index_matchs(recents):
    li = ''.join(f'<li><a href="{BASE}/match/{m["id"]}">{e(m["titre"])}</a> <small>{e(m["date"])}</small></li>' for m in recents)
    corps = f'<h1>Matchs de badminton terminés</h1><p class="sub">Les {len(recents)} derniers matchs jugés : le % de l\'algo, le résultat, le verdict.</p><ul class="l">{li}</ul>'
    return page('Badminton : matchs terminés et pronostics de l\'algo', 'Les derniers matchs de badminton jugés '
                '(circuits BWF) : le % de l\'algo avant le match et le résultat.', f'{BASE}/matchs', corps)


def index_joueurs(J):
    L = sorted(((k, j) for k, j in J.items() if j['n'] >= MIN_JOUEUR), key=lambda kv: (-kv[1]['n'], kv[1]['nom']))
    li = ''.join(f'<li><a href="{BASE}/joueur/{k}">{e(j["nom"])}</a> <small>{j["n"]} matchs</small></li>' for k, j in L[:2000])
    corps = f'<h1>Joueurs de badminton</h1><p class="sub">{len(L)} joueurs avec au moins {MIN_JOUEUR} matchs jugés.</p><ul class="l">{li}</ul>'
    return page('Badminton : les joueurs suivis par l\'algo', 'Les joueurs de badminton suivis par l\'algo '
                '(circuits BWF, simples et doubles) : bilan et derniers matchs.', f'{BASE}/joueurs', corps)


def sitemap(chemins):
    l = ''.join(f"  <url><loc>{e(SITE + c)}</loc><lastmod>{d}</lastmod></url>\n" for c, d in chemins)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{l}</urlset>\n'


def _html(cf, cle, texte):
    cf.put(cle, texte.encode('utf-8'), content_type='text/html; charset=utf-8')


def _mois(maintenant):
    a, m = DEBUT
    fin = (maintenant.year, maintenant.month)
    while (a, m) <= fin:
        yield f'{a:04d}-{m:02d}'
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)


def _rattrapage(cf, E, maintenant, cle_archive):
    """Les matchs archivés pas encore passés en pages (au plus RATTRAPAGE) ; marque la fin quand tout est rattrapé."""
    fait = E.setdefault('rattrapage', {})
    out = []
    for mois in _mois(maintenant):
        brut = cf.get(cle_archive.format(mois=mois)) or b''
        L = [l for l in brut.decode('utf-8').splitlines() if l.strip()]
        d = fait.get(mois, 0)
        pris = L[d:d + RATTRAPAGE - len(out)]
        out += [json.loads(l) for l in pris]
        fait[mois] = d + len(pris)
        if len(out) >= RATTRAPAGE:
            return out
    E['rattrapage_fini'] = True
    return out


def publier(cf, juges, maintenant, cle_archive=None, journal=print, signaler=None):
    """juges : matchs jugés à ce passage (déjà archivés). Tant que le rattrapage n'est pas fini, on lit l'archive
    (qui contient déjà ces matchs) au lieu de juges. Met à jour les pages."""
    brut = cf.get(CLE_ETAT)
    E = json.loads(brut) if brut else {}
    if cle_archive and not E.get('rattrapage_fini'):
        juges = _rattrapage(cf, E, maintenant, cle_archive)
    J = E.setdefault('joueurs', {})
    R = E.setdefault('matchs', [])
    changes = set()
    juges = [x for x in juges if 'p_h' in x and x.get('g') in (1, 2)]
    for x in juges:
        sh, sa = score(x)
        for camp, nom, adv in (('h', x['h'], x['a']), ('a', x['a'], x['h'])):
            noms = joueurs(nom)
            for qui in noms:                                    # en double : chacun des deux joueurs (comme l'Elo)
                k = cle_joueur(qui)
                j = J.setdefault(k, {'nom': qui, 'n': 0, 'v': 0, 'bons': 0, 'epreuves': [], 'derniers': []})
                if any(m['id'] == x['id'] for m in j['derniers']):
                    continue
                gagne = (x['g'] == 1) == (camp == 'h')
                j['n'] += 1
                j['v'] += int(gagne)
                j['bons'] += int(bool(x.get('bon')))
                if x.get('epreuve') and x['epreuve'] not in j['epreuves']:
                    j['epreuves'].append(x['epreuve'])
                p = x['p_h'] if camp == 'h' else 1 - x['p_h']
                sc = f"{sh}-{sa}" if camp == 'h' else f"{sa}-{sh}"
                d = {'id': x['id'], 't': x['t'], 'adv': adv, 'v': gagne, 'p': round(100 * p), 'bon': bool(x.get('bon')), 'sc': sc}
                if len(noms) == 2:
                    d['avec'] = noms[1] if qui == noms[0] else noms[0]
                j['derniers'] = ([d] + j['derniers'])[:DERNIERS]
                changes.add(k)
        if not any(m['id'] == x['id'] for m in R[:500]):
            R.insert(0, {'id': x['id'], 't': x['t'], 'titre': f"{x['h']} – {x['a']}", 'date': date_fr(x['t'])})
    R.sort(key=lambda m: -m['t'])
    del R[20000:]
    jour = maintenant.astimezone(dt.timezone.utc).date().isoformat()
    nouvelles = []                                             # 529 : les adresses à signaler (IndexNow)
    for x in juges:                                            # après les joueurs : les liens vers leurs pages existent
        _html(cf, f"{PREFIXE}match/{x['id']}.html", page_match(x, J))
        nouvelles.append(f"{SITE}{BASE}/match/{x['id']}")
    n_j = 0
    for k in changes:
        if J[k]['n'] >= MIN_JOUEUR:
            _html(cf, f"{PREFIXE}joueur/{k}.html", page_joueur(k, J[k]))
            J[k]['maj'] = jour                                 # 529 : la vraie date de mise à jour (plan du site)
            nouvelles.append(f"{SITE}{BASE}/joueur/{k}")
            n_j += 1
    if juges or E.get('index_le') != jour:
        nouvelles += [f"{SITE}{BASE}/matchs", f"{SITE}{BASE}/joueurs"]
        _html(cf, f"{PREFIXE}matchs.html", index_matchs(R[:INDEX_MATCHS]))
        _html(cf, f"{PREFIXE}joueurs.html", index_joueurs(J))
        limite = maintenant.timestamp() - SITEMAP_JOURS * 86400
        ch = [(BASE, jour), (f'{BASE}/matchs', jour), (f'{BASE}/joueurs', jour)]
        ch += [(f"{BASE}/joueur/{k}", j.get('maj') or jour) for k, j in J.items() if j['n'] >= MIN_JOUEUR]
        ch += [(f"{BASE}/match/{m['id']}", dt.datetime.fromtimestamp(m['t'], dt.timezone.utc).date().isoformat())
               for m in R if m['t'] >= limite]
        cf.put(CLE_SITEMAP, sitemap(ch[:45000]).encode('utf-8'), content_type='application/xml; charset=utf-8')
        E['index_le'] = jour
    cf.put(CLE_ETAT, json.dumps(E, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), content_type='application/json')
    journal(f"  pages : {len(juges)} matchs, {n_j} joueurs mis à jour, "
            f"{sum(1 for j in J.values() if j['n'] >= MIN_JOUEUR)} pages joueur en tout"
            + ('' if E.get('rattrapage_fini') else ' (rattrapage en cours)'))
    if signaler and nouvelles:                                 # 529 : Bing et les autres moteurs (IndexNow) ; Google lit le plan
        try:
            signaler(nouvelles[:10000])
        except Exception:  # noqa: BLE001 — jamais bloquant
            journal('  pages : signalement IndexNow impossible ce passage')
    return {'matchs': len(juges), 'joueurs': n_j, 'signalees': len(nouvelles)}
