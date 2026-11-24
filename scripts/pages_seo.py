#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages_seo.py — une page web par MATCH TERMINÉ et par JOUEUR, pour être trouvé sur Google (24/11/2026, paquet 418,
Lucas : « on part sur 1-2 »).

Pourquoi : le site n'avait que trois adresses ; tout le reste (matchs, joueurs, bilan) est dessiné par le JavaScript
d'une seule page. Les gens cherchent des NOMS (« Kelm Taberner », « Carlos Taberner forme »). Chaque match terminé et
chaque joueur ont désormais leur page, lisible sans JavaScript, reliée aux autres et listée dans le plan du site.

Ce qui y figure — uniquement du PASSÉ, déjà public dans le bilan :
  • match : % annoncé AVANT le match (première prédiction, jamais retouchée), vainqueur, score, statistiques réelles
    face à ce que l'algorithme avait prévu ;
  • joueur : matchs analysés, victoires et défaites (total, par surface), forme récente, liste des matchs avec leur page.
Jamais : un match à venir ou pas encore commencé, une cote, une source de cotes, un classement interne de l'algorithme
(il permettrait de recalculer les % réservés à l'accès Plus), un match ITF (jamais pronostiqué), un conseil de pari.

Source : Tennis_Edge_Lab/live/pronostics_resultats.json (matchs jugés, rapatrié à jour de R2 par pages.yml).
Sortie (dans le dossier du site public, envoyé ensuite à R2 sous site/algo/) :
  match/<uid>.html, joueur/<slug>.html, matchs.html, joueurs.html, sitemap.xml (les trois pages du site + celles-ci).
Le worker les sert à /match/<uid>, /joueur/<slug>, /matchs, /joueurs et /sitemap.xml.

Usage : python scripts/pages_seo.py [racine] [dossier_site]     (défaut : . _site/algo)
"""
import collections
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata

SITE = 'https://gamesetalgo.com'
CIRCUITS = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
SURFACES = {'Hard': 'dur', 'Clay': 'terre battue', 'Grass': 'gazon', 'Carpet': 'moquette'}
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre')
MIN_MATCHS_JOUEUR = 2
STATS = (('premiere_pct', '% de 1res balles', True), ('gagnes_1re_pct', 'Points gagnés derrière la 1re', True),
         ('gagnes_2e_pct', 'Points gagnés derrière la 2e', True), ('aces', 'Aces', False),
         ('doubles_fautes', 'Doubles fautes', False), ('breaks', 'Breaks', False),
         ('jeux_service_gagnes_pct', 'Jeux de service gagnés', True), ('points_gagnes', 'Points gagnés', False))
UID = re.compile(r'^[a-z0-9_-]{5,140}$')
e = html.escape


def slug(nom):
    s = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:80]


def date_fr(iso):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)[:10]
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def pc(x):
    return f"{100 * x:.0f} %"


def p_annonce(m):
    pr = m.get('premier') or {}
    for k in ('combinaison', 'simulation', 'stats'):
        if isinstance(pr.get(k), dict) and pr[k].get('p_home') is not None:
            return float(pr[k]['p_home'])
    return float(m['p_affiche']) if m.get('p_affiche') is not None else None


def matchs_publiables(doc, maintenant=None):
    """Matchs terminés (vainqueur connu), commencés, hors ITF, avec un % annoncé et un identifiant propre."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M')
    out = []
    for m in (doc or {}).get('matchs') or []:
        r = m.get('reel') or {}
        if m.get('circuit') not in CIRCUITS or r.get('gagnant') not in ('home', 'away') or not UID.match(str(m.get('uid') or '')):
            continue
        if str(m.get('debut') or '')[:16] > maintenant or p_annonce(m) is None:
            continue
        out.append(m)
    out.sort(key=lambda m: (str(m.get('debut')), m['uid']), reverse=True)
    return out


# ------------------------------------------------------------------------------------------------ gabarit commun
CSS = """:root{--bg:#0E0A24;--panel:#191338;--ink:#F4F1FF;--dim:#A9A2CC;--p1:#2EE6FF;--p2:#FF4FAE;--ok:#3ee08a;--ko:#ff6b7d;--ball:#D4FF3A;--line:rgba(255,255,255,.12)}
@font-face{font-family:"Bungee";font-display:swap;src:url(/polices/bungee-400.woff2) format("woff2")}
@font-face{font-family:"Barlow";font-weight:400;font-display:swap;src:url(/polices/barlow-400.woff2) format("woff2")}
@font-face{font-family:"Barlow";font-weight:600;font-display:swap;src:url(/polices/barlow-600.woff2) format("woff2")}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Barlow,system-ui,sans-serif}
.w{max-width:760px;margin:0 auto;padding:18px 16px 40px}a{color:var(--p1)}
header{display:flex;align-items:center;gap:10px;margin-bottom:18px}header a{color:var(--ink);text-decoration:none;font-family:Bungee,system-ui;font-size:1.15rem}
header .b{width:14px;height:14px;border-radius:50%;background:var(--ball);box-shadow:0 0 12px var(--ball)}
h1{font-family:Bungee,system-ui;font-weight:400;font-size:1.7rem;line-height:1.15;margin:0 0 6px}h2{font-size:1.15rem;margin:26px 0 8px}
.sub{color:var(--dim);margin:0 0 14px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0}
.a{color:var(--p1)}.b2{color:var(--p2)}.ok{color:var(--ok)}.ko{color:var(--ko)}
table{width:100%;border-collapse:collapse;font-size:.95rem}th,td{padding:7px 6px;border-bottom:1px solid var(--line);text-align:center}
th:first-child,td:first-child{text-align:left}small{color:var(--dim)}ul.l{list-style:none;padding:0;margin:0}ul.l li{padding:7px 0;border-bottom:1px solid var(--line)}
.cta{display:inline-block;margin-top:10px;background:var(--ball);color:#141225;font-weight:600;padding:10px 16px;border-radius:999px;text-decoration:none}
footer{margin-top:34px;color:var(--dim);font-size:.85rem}footer a{color:var(--dim)}"""


def page(titre, description, chemin, corps, ld=None):
    url = SITE + chemin
    lds = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ''
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)}</title><meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(url)}"><meta name="theme-color" content="#0E0A24">
<meta property="og:title" content="{e(titre)}"><meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(url)}"><meta property="og:type" content="article"><meta property="og:site_name" content="Game Set Algo">
<meta property="og:image" content="{SITE}/partage.png"><link rel="icon" href="/icone-192.png">{lds}
<style>{CSS}</style></head><body><div class="w">
<header><span class="b" aria-hidden="true"></span><a href="/">Game Set Algo</a></header>
{corps}
<footer><p><a href="/">Accueil</a> · <a href="/matchs">Matchs analysés</a> · <a href="/joueurs">Joueurs</a> · <a href="/methode.html">Comment ça marche</a> · <a href="/#mentions">Mentions légales</a> · <a href="/#cgv">Conditions de vente</a></p>
<p>Des probabilités calculées par un algorithme indépendant, pas des certitudes. Ce site ne donne aucun conseil de pari. Les paris sportifs sont interdits aux mineurs ; jouer comporte des risques : 09 74 75 13 13 (appel non surtaxé).</p></footer>
</div></body></html>
"""


def _noms(m):
    return m['home'], m['away']


def page_match(m, slugs):
    h, a = _noms(m)
    r = m['reel']
    p = p_annonce(m)
    fav, pf = (h, p) if p >= 0.5 else (a, 1 - p)
    vainqueur = h if r['gagnant'] == 'home' else a
    juste = vainqueur == fav
    circ = CIRCUITS.get(m['circuit'], m['circuit'])
    surf = SURFACES.get(m.get('surface'), m.get('surface') or '')
    date = date_fr(m.get('debut'))
    lien = lambda n: f'<a href="/joueur/{slugs[n]}">{e(n)}</a>' if n in slugs else e(n)  # noqa: E731
    issue = (f'<p class="ok">✓ Le favori de l\'algorithme a gagné.</p>' if juste else
             f'<p class="ko">✗ Surprise : l\'algorithme donnait {e(fav)} favori à {pc(pf)}.</p>')
    if r.get('interrompu'):
        issue = f'<p><small>Match interrompu ({e(str(r["interrompu"]))}) : il ne compte pas dans le bilan.</small></p>'
    diag = ((m.get('diagnostic') or {}).get('stats') or {})
    feuille = r.get('feuille') if isinstance(r.get('feuille'), list) and len(r['feuille']) == 2 else None
    lignes = []
    for cle, lib, pct in STATS:
        d = diag.get(cle) or {}
        vals = []
        for i, camp in enumerate(('home', 'away')):
            reel = (d.get(camp) or {}).get('reel')
            if reel is None and feuille:
                reel = (feuille[i] or {}).get(cle)
            prevu = (d.get(camp) or {}).get('prevu')
            if reel is None:
                vals = None
                break
            fmt = (lambda x: f"{float(x):.0f} %") if pct else (lambda x: f"{float(x):.0f}")
            vals.append(f"{fmt(reel)}" + (f"<br><small>prévu {fmt(prevu)}</small>" if prevu is not None else ''))
        if vals:
            lignes.append(f"<tr><td>{e(lib)}</td><td>{vals[0]}</td><td>{vals[1]}</td></tr>")
    stats = (f"""<h2>Statistiques du match : réel contre prévu</h2><div class="panel"><table><thead><tr><th></th><th class="a">{e(h)}</th><th class="b2">{e(a)}</th></tr></thead>
<tbody>{''.join(lignes)}</tbody></table><p><small>« Prévu » : la moyenne des 20 000 simulations faites avant le match.</small></p></div>""" if lignes else '')
    lieu = m.get('tournoi') or ''
    lieu = lieu if circ.lower() in lieu.lower() else ' · '.join(x for x in (lieu, circ) if x)
    corps = f"""<h1>{e(h)} – {e(a)}</h1><p class="sub">{e(lieu)} · {e(surf)} · {e(date)}</p>
<div class="panel"><h2 style="margin-top:0">Avant le match</h2><p>L'algorithme, qui simule chaque match 20 000 fois point par point, donnait
<b class="a">{lien(h)} {pc(p)}</b> – <b class="b2">{pc(1 - p)} {lien(a)}</b>.</p>
<h2>Résultat</h2><p><b>{lien(vainqueur)}</b> gagne{(' ' + e(r['score'])) if r.get('score') else ''}{(' (sets ' + e(r['sets']) + ')') if r.get('sets') else ''}.</p>{issue}</div>
{stats}
<div class="panel"><p>Le % de chaque match est publié avant qu'il commence, pour les abonnés Plus ; le match du jour est offert à tous.</p>
<a class="cta" href="/">Voir les matchs du jour</a></div>
<p><a href="/matchs">← Tous les matchs analysés</a></p>"""
    titre = f"{h} – {a} : analyse, % de victoire et statistiques | {m.get('tournoi') or circ} {str(m.get('debut'))[:4]}"
    desc = (f"{h} – {a} ({m.get('tournoi') or circ}, {date}) : Game Set Algo donnait {fav} gagnant à {pc(pf)} avant le match. "
            f"Résultat : {vainqueur} gagne{(' ' + r['score']) if r.get('score') else ''}. Statistiques réelles contre prévues.")
    ld = {'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': f"{h} – {a}", 'sport': 'Tennis',
          'startDate': str(m.get('debut')), 'eventStatus': 'https://schema.org/EventScheduled',
          'location': {'@type': 'Place', 'name': m.get('tournoi') or circ},
          'competitor': [{'@type': 'Person', 'name': h}, {'@type': 'Person', 'name': a}],
          'url': f"{SITE}/match/{m['uid']}"}
    return page(titre, desc, f"/match/{m['uid']}", corps, ld)


def fiches_joueurs(matchs):
    """{nom: [matchs du plus récent au plus ancien]}."""
    par = collections.defaultdict(list)
    for m in matchs:
        for n in _noms(m):
            par[n].append(m)
    return par


def score_vu_par(score, a_domicile):
    """« 6-4 3-6 » vu du joueur : jeux inversés s'il était le second nommé."""
    if a_domicile or not score:
        return score
    return ' '.join('-'.join(reversed(s.split('-'))) if s.count('-') == 1 else s for s in str(score).split())


def page_joueur(nom, ms, slugs):
    jug = [m for m in ms if not (m.get('reel') or {}).get('interrompu')]
    gagne = lambda m: (m['reel']['gagnant'] == 'home') == (m['home'] == nom)  # noqa: E731
    v = sum(1 for m in jug if gagne(m))
    par_surf = collections.defaultdict(lambda: [0, 0])
    for m in jug:
        par_surf[SURFACES.get(m.get('surface'), m.get('surface') or '?')][0 if gagne(m) else 1] += 1
    forme = ''.join('V' if gagne(m) else 'D' for m in jug[:10])
    surf = ' · '.join(f"{s} : {x[0]} V – {x[1]} D" for s, x in sorted(par_surf.items(), key=lambda kv: -sum(kv[1])))
    li = []
    for m in ms[:40]:
        adv = m['away'] if m['home'] == nom else m['home']
        p = p_annonce(m)
        pj = p if m['home'] == nom else 1 - p
        res = '·' if (m.get('reel') or {}).get('interrompu') else ('<span class="ok">V</span>' if gagne(m) else '<span class="ko">D</span>')
        li.append(f'<li>{res} <a href="/match/{m["uid"]}">contre {e(adv)}</a> — {e(m.get("tournoi") or "")}, {e(date_fr(m.get("debut")))}'
                  f'<br><small>Annoncé à {pc(pj)} par l\'algorithme{(" · " + e(score_vu_par(m["reel"]["score"], m["home"] == nom))) if m["reel"].get("score") else ""}</small></li>')
    circuits = sorted({CIRCUITS.get(m['circuit'], m['circuit']) for m in ms})
    corps = f"""<h1>{e(nom)}</h1><p class="sub">{e(' · '.join(circuits))} · {len(ms)} match{'s' if len(ms) > 1 else ''} analysé{'s' if len(ms) > 1 else ''} par Game Set Algo</p>
<div class="panel"><p><b>{v} victoire{'s' if v > 1 else ''} – {len(jug) - v} défaite{'s' if len(jug) - v > 1 else ''}</b> sur les matchs analysés.</p>
<p>Par surface : {e(surf) or '—'}</p><p>Forme récente (du plus récent au plus ancien) : <b>{e(' '.join(forme)) or '—'}</b></p></div>
<h2>Ses matchs analysés</h2><ul class="l">{''.join(li)}</ul>
<div class="panel"><p>Le % de victoire de chaque match à venir est publié avant le match pour les abonnés Plus.</p><a class="cta" href="/">Voir les matchs du jour</a></div>
<p><a href="/joueurs">← Tous les joueurs</a></p>"""
    titre = f"{nom} : forme, résultats et matchs analysés | Game Set Algo"
    desc = (f"{nom} : {v} victoires et {len(jug) - v} défaites sur {len(jug)} matchs analysés par Game Set Algo, forme récente "
            f"{' '.join(forme[:5])}, résultats par surface et % annoncé avant chaque match.")
    ld = {'@context': 'https://schema.org', '@type': 'Person', 'name': nom, 'url': f"{SITE}/joueur/{slugs[nom]}"}
    return page(titre, desc, f"/joueur/{slugs[nom]}", corps, ld)


def page_index_matchs(matchs, n=400):
    par_jour = collections.OrderedDict()
    for m in matchs[:n]:
        par_jour.setdefault(str(m.get('debut'))[:10], []).append(m)
    blocs = []
    for j, ms in par_jour.items():
        li = ''.join(f'<li><a href="/match/{m["uid"]}">{e(m["home"])} – {e(m["away"])}</a> <small>{e(m.get("tournoi") or "")}'
                     f'{(" · " + e(m["reel"]["score"])) if m["reel"].get("score") else ""}</small></li>' for m in ms)
        blocs.append(f"<h2>{e(date_fr(j))}</h2><ul class=\"l\">{li}</ul>")
    corps = f"""<h1>Matchs analysés</h1><p class="sub">Chaque match terminé, avec le % que l'algorithme annonçait avant le match et les statistiques réelles. Erreurs comprises.</p>
{''.join(blocs)}"""
    return page('Matchs de tennis analysés par l\'algorithme : % annoncé et résultats | Game Set Algo',
                'Tous les matchs de tennis ATP, WTA et Challenger analysés par Game Set Algo : le % de victoire annoncé avant '
                'le match, le résultat et les statistiques réelles contre prévues.', '/matchs', corps)


def page_index_joueurs(par, slugs):
    noms = sorted(slugs, key=lambda n: slug(n))
    li = ''.join(f'<li><a href="/joueur/{slugs[n]}">{e(n)}</a> <small>{len(par[n])} matchs</small></li>' for n in noms)
    corps = f"""<h1>Joueurs</h1><p class="sub">Les joueuses et joueurs dont Game Set Algo a analysé au moins {MIN_MATCHS_JOUEUR} matchs.</p><ul class="l">{li}</ul>"""
    return page('Joueurs de tennis : forme et matchs analysés | Game Set Algo',
                'Forme récente, résultats par surface et matchs analysés par Game Set Algo pour chaque joueur et joueuse '
                'des circuits ATP, WTA et Challenger.', '/joueurs', corps)


def sitemap(entrees):
    l = ''.join(f"  <url><loc>{e(SITE + c)}</loc><lastmod>{d}</lastmod></url>\n" for c, d in entrees)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{l}</urlset>\n'


def construire(doc, dossier, maintenant=None):
    matchs = matchs_publiables(doc, maintenant)
    par = fiches_joueurs(matchs)
    slugs, pris = {}, set()
    for n in sorted(par, key=lambda n: (-len(par[n]), n)):
        if len(par[n]) < MIN_MATCHS_JOUEUR or not slug(n):
            continue
        s, i = slug(n), 2
        while s in pris:
            s, i = f"{slug(n)}-{i}", i + 1
        pris.add(s)
        slugs[n] = s
    os.makedirs(os.path.join(dossier, 'match'), exist_ok=True)
    os.makedirs(os.path.join(dossier, 'joueur'), exist_ok=True)
    for m in matchs:
        with open(os.path.join(dossier, 'match', m['uid'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(page_match(m, slugs))
    for n, s in slugs.items():
        with open(os.path.join(dossier, 'joueur', s + '.html'), 'w', encoding='utf-8') as f:
            f.write(page_joueur(n, par[n], slugs))
    with open(os.path.join(dossier, 'matchs.html'), 'w', encoding='utf-8') as f:
        f.write(page_index_matchs(matchs))
    with open(os.path.join(dossier, 'joueurs.html'), 'w', encoding='utf-8') as f:
        f.write(page_index_joueurs(par, slugs))
    jour = (maintenant or dt.datetime.now(dt.timezone.utc).isoformat())[:10]
    entrees = [('/', jour), ('/methode.html', jour), ('/apropos.html', jour), ('/matchs', jour), ('/joueurs', jour)]
    entrees += [(f"/match/{m['uid']}", str(m.get('debut'))[:10]) for m in matchs]
    entrees += [(f"/joueur/{s}", str(par[n][0].get('debut'))[:10]) for n, s in slugs.items()]
    with open(os.path.join(dossier, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(sitemap(entrees))
    return len(matchs), len(slugs)


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    dossier = argv[2] if len(argv) > 2 else os.path.join('_site', 'algo')
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        print('Pages des matchs et des joueurs : résultats absents, rien de construit.')
        return 0
    nm, nj = construire(doc, dossier)
    print(f"Pages des matchs et des joueurs : {nm} match(s), {nj} joueur(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
