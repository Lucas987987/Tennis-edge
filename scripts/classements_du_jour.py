#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classements_du_jour.py — deux cartes PNG 1080×1350 pour X (06/11/2026, demande de Lucas) :

  1. « Les classements du jour » : parmi les matchs ATP, WTA et Challenger du jour (heure de Paris), le plus d'aces
     attendus (5), la plus forte probabilité de 3 sets (3), d'au moins un tie-break (3), les plus nets favoris (3).
  2. « Les classements d'hier, vérifiés » : les mêmes classements pour la veille, à partir des prévisions FIGÉES au
     début de chaque match (apres_match), avec le résultat en face — juste ou faux, même mise en forme.
     Aces : « juste » si le match a dépassé la moyenne d'aces de la journée (le classement est jugé, pas le total,
     et la carte dit quand les totaux ont manqué).

Tout vient de algo/donnees.json (rien n'est recalculé) ; aucune cote, aucune adresse de site, aucun vocabulaire de
pari (« 3 sets », pas « +2,5 sets »). Usage : python scripts/classements_du_jour.py --sortie classements [--jour AAAA-MM-JJ]
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CIRC = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
PARTICULES = {'van', 'de', 'der', 'den', 'da', 'di', 'del', 'della', 'von', 'du', 'le', 'la', 'dos', 'das', 'mc', 'st'}
JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre',
        'décembre']


def paris():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Europe/Paris')
    except Exception:  # noqa: BLE001
        return dt.timezone(dt.timedelta(hours=1))


def jour_paris(s):
    t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(paris()).date()


def nom(n):
    """Nom de famille court : « Zizou Bergs » → Bergs ; « Raphael Van Assche » → Van Assche."""
    t = str(n or '').split()
    if len(t) < 2:
        return str(n or '')
    i = len(t) - 1
    while i > 1 and t[i - 1].lower() in PARTICULES:
        i -= 1
    return ' '.join(t[i:])


def court(h, a):
    return f"{nom(h)} – {nom(a)}"


def virgule(x, d=1):
    return f"{x:.{d}f}".replace('.', ',')


def date_fr(j):
    return f"{JOURS[j.weekday()].capitalize()} {j.day} {MOIS[j.month - 1]}"


def p3(sets):
    sets = sets or {}
    return (sets.get('2-1') or 0) + (sets.get('1-2') or 0)


def fav(p):
    return max(p, 1 - p)


# ---------------------------------------------------------------- données
def classements_jour(doc, jour):
    M = [m for m in doc.get('matchs') or [] if m.get('circuit') in CIRC and m.get('feuille_prevue')
         and m.get('p_home') is not None and jour_paris(m.get('debut_utc') or m['debut']) == jour
         and not m.get('forfait')]
    if len(M) < 3:
        return None
    aces = lambda m: sum((f or {}).get('aces') or 0 for f in m['feuille_prevue'])
    return {
        'n': len(M),
        'aces': [(court(m['home'], m['away']), CIRC[m['circuit']], virgule(aces(m)))
                 for m in sorted(M, key=aces, reverse=True)[:5]],
        'trois': [(court(m['home'], m['away']), CIRC[m['circuit']], f"{round(100 * p3(m.get('sets')))} %")
                  for m in sorted(M, key=lambda m: p3(m.get('sets')), reverse=True)[:3] if m.get('sets')],
        'tb': [(court(m['home'], m['away']), CIRC[m['circuit']], f"{round(100 * m['tiebreak'])} %")
               for m in sorted([m for m in M if m.get('tiebreak') is not None], key=lambda m: m['tiebreak'],
                               reverse=True)[:3]],
        'fav': [(nom(m['home'] if m['p_home'] >= .5 else m['away']), court(m['home'], m['away']),
                 f"{round(100 * fav(m['p_home']))} %")
                for m in sorted(M, key=lambda m: fav(m['p_home']), reverse=True)[:3]],
    }


def verification(doc, jour):
    A = [x for x in (doc.get('apres_match') or {}).values() if x.get('circuit') in CIRC
         and jour_paris(x['debut']) == jour and (x.get('reel') or {}).get('gagnant') in ('home', 'away')]
    if len(A) < 3:
        return None
    prevu_aces = lambda x: sum((f or {}).get('aces') or 0 for f in (x['prevu'].get('feuille') or []))
    reel_aces = lambda x: sum((f or {}).get('aces') or 0 for f in (x['reel'].get('feuille') or []))
    AA = [x for x in A if x['prevu'].get('feuille') and x['reel'].get('feuille')]
    moy = sum(reel_aces(x) for x in AA) / len(AA) if AA else None
    tb = lambda x: ((x.get('ecarts') or {}).get('lignes') or {}).get('tie_break')
    S = [x for x in A if x['prevu'].get('sets') and (x['reel'].get('sets') in ('2-0', '2-1', '1-2', '0-2'))]
    T = [x for x in A if tb(x)]
    out = {'n': len(A), 'moy_aces': virgule(moy) if moy is not None else None,
           'aces': [(court(x['home'], x['away']), virgule(prevu_aces(x)), str(reel_aces(x)), reel_aces(x) > moy)
                    for x in sorted(AA, key=prevu_aces, reverse=True)[:5]] if AA else [],
           'trois': [(court(x['home'], x['away']), f"{round(100 * p3(x['prevu']['sets']))} %",
                      'Oui' if x['reel']['sets'] in ('2-1', '1-2') else 'Non', x['reel']['sets'] in ('2-1', '1-2'))
                     for x in sorted(S, key=lambda x: p3(x['prevu']['sets']), reverse=True)[:3]],
           'tb': [(court(x['home'], x['away']), f"{round(100 * tb(x)[0])} %", 'Oui' if tb(x)[1] else 'Non', bool(tb(x)[1]))
                  for x in sorted(T, key=lambda x: tb(x)[0], reverse=True)[:3]],
           'fav': [(court(x['home'], x['away']), f"{round(100 * fav(x['prevu']['p_home']))} %",
                    x['reel'].get('score') or 'gagné' if (x['reel']['gagnant'] == 'home') == (x['prevu']['p_home'] >= .5)
                    else x['reel'].get('score') or 'perdu',
                    (x['reel']['gagnant'] == 'home') == (x['prevu']['p_home'] >= .5))
                   for x in sorted(A, key=lambda x: fav(x['prevu']['p_home']), reverse=True)[:3]]}
    out['justes'] = sum(r[3] for k in ('aces', 'trois', 'tb', 'fav') for r in out[k])
    out['lignes'] = sum(len(out[k]) for k in ('aces', 'trois', 'tb', 'fav'))
    return out


# ---------------------------------------------------------------- mise en forme
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Source+Sans+3:wght@400;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:#F4F6F8;color:#0E1A2B;font-family:'Source Sans 3',Inter,'DejaVu Sans',sans-serif;position:relative;overflow:hidden}
.tete{background:#0E1A2B;color:#F4F6F8;padding:40px 56px 34px}
.tete h1{font-family:'Barlow Condensed',Inter,sans-serif;font-size:66px;font-weight:700;line-height:1}
.tete p{font-size:25px;color:#C9D2DD;margin-top:12px}
.grille{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:26px 40px}
.bloc{background:#fff;border:2px solid #DCE1E7;border-radius:20px;padding:20px 24px 12px}
.bloc.large{grid-column:1/-1}
.bloc h2{font-family:'Barlow Condensed',Inter,sans-serif;font-size:34px;font-weight:700;line-height:1.05}
.bloc .sous{font-size:20px;color:#4E5B6B;margin:2px 0 8px}
.l{display:flex;align-items:baseline;gap:12px;padding:9px 0;border-top:1.5px solid #E4E9EF}
.l .m{font-size:25px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l .c{font-size:18px;color:#4E5B6B;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l .v{font-family:'Barlow Condensed',Inter,sans-serif;font-size:32px;font-weight:700;color:#1D4F91;white-space:nowrap}
.l3{display:grid;grid-template-columns:1fr 92px 130px 40px;gap:10px;align-items:center;padding:8px 0;border-top:1.5px solid #E4E9EF;font-size:24px}
.l3 .m{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l3 .n{font-family:'Barlow Condensed',Inter,sans-serif;font-size:29px;font-weight:700;text-align:right;white-space:nowrap}
.l3 .n.r{color:#1D4F91}
.l3.t{border-top:none;font-size:17px;color:#4E5B6B;padding:0}
.l3.t span{text-align:right}
.demi .l3{grid-template-columns:1fr 74px 64px 34px;gap:8px;font-size:21px}
.demi .l3 .n{font-size:26px}
.demi .l3.t{font-size:15px}
.ok,.ko{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.ok{background:#1D4F91}.ko{border:3px solid #B4501A}
.pied{position:absolute;bottom:30px;left:56px;right:56px;font-size:20px;color:#4E5B6B;line-height:1.35}
"""
OK = ('<span class="ok"><svg width="20" height="20" viewBox="0 0 20 20"><path d="M4 10.5l4 4 8-9" fill="none" '
      'stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>')
KO = ('<span class="ko"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 3l10 10M13 3L3 13" '
      'stroke="#B4501A" stroke-width="3" stroke-linecap="round"/></svg></span>')
e = html.escape


def _page(corps):
    return f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{corps}</body></html>'


def _liste(rows):
    return ''.join(f'<div class="l"><span class="m">{e(a)}</span><span class="c">{e(b)}</span>'
                   f'<span class="v">{e(v)}</span></div>' for a, b, v in rows)


def _bloc(titre, sous, contenu, classe='large'):
    if not contenu:
        return ''
    s = f'<p class="sous">{e(sous)}</p>' if sous else ''
    return f'<div class="bloc {classe}"><h2>{e(titre)}</h2>{s}{contenu}</div>'


def html_jour(c, jour):
    return _page(
        f'<div class="tete"><h1>Les classements du jour</h1><p>{date_fr(jour)} · {c["n"]} matchs ATP, WTA, Challenger'
        ' · 20 000 simulations par match, sans aucune cote</p></div><div class="grille">'
        + _bloc("Le plus d'aces attendus", 'Total des deux joueurs', _liste(c['aces']))
        + _bloc('Vers un 3e set', "Probabilité d'un match en 3 sets", _liste(c['trois']), 'demi')
        + _bloc('Tie-break en vue', 'Au moins un tie-break', _liste(c['tb']), 'demi')
        + _bloc('Les plus nets favoris', "Chance de victoire selon l'algo", _liste(c['fav']))
        + '</div><p class="pied">Prévisions figées avant les matchs. Demain, on compare chaque ligne au résultat réel,'
          ' juste ou faux.</p>')


def _l3(rows, t1, t2):
    if not rows:
        return ''
    t = f'<div class="l3 t"><span></span><span>{t1}</span><span>{t2}</span><span></span></div>'
    return t + ''.join(f'<div class="l3"><span class="m">{e(m)}</span><span class="n">{e(a)}</span>'
                       f'<span class="n r">{e(b)}</span>{OK if ok else KO}</div>' for m, a, b, ok in rows)


def html_verif(v, jour):
    n_ok = sum(1 for r in v['aces'] if r[3])
    sous_aces = (f"Classement : {n_ok} sur {len(v['aces'])} au-dessus de la moyenne du jour ({v['moy_aces']})."
                 + (' Les totaux, eux, ont manqué.' if any(abs(float(r[1].replace(',', '.')) - float(r[2])) > 5
                                                         for r in v['aces']) else ''))
    return _page(
        f'<div class="tete"><h1>Les classements d\'hier, vérifiés</h1><p>{date_fr(jour)} · prévisions figées au début'
        ' de chaque match, comparées au résultat</p></div><div class="grille">'
        + _bloc("Le plus d'aces attendus", sous_aces, _l3(v['aces'], 'Prévu', 'Réel'))
        + _bloc('Vers un 3e set', '', _l3(v['trois'], 'Prévu', '3 sets'), 'demi')
        + _bloc('Tie-break en vue', '', _l3(v['tb'], 'Prévu', 'TB'), 'demi')
        + _bloc('Les plus nets favoris', '', _l3(v['fav'], 'Annoncé', 'Score'))
        + f'</div><p class="pied">Bilan : {v["justes"]} lignes justes sur {v["lignes"]}. Tout est affiché, juste ou'
          ' faux.</p>')


def rendre(pages, sortie):
    from playwright.sync_api import sync_playwright
    os.makedirs(sortie, exist_ok=True)
    faits = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
        for nom_f, h in pages:
            chemin = os.path.abspath(os.path.join(sortie, nom_f + '.html'))
            with open(chemin, 'w', encoding='utf-8') as f:
                f.write(h)
            pg.goto('file://' + chemin)
            try:
                pg.wait_for_function('document.fonts.status === "loaded"', timeout=8000)
            except Exception:  # noqa: BLE001
                pass
            pg.wait_for_timeout(300)
            haut = pg.evaluate("Math.max(...[...document.querySelectorAll('.bloc')].map(x => x.getBoundingClientRect().bottom))")
            if haut > 1290:
                print(f'::warning::{nom_f} : contenu trop haut ({haut:.0f} px), carte tronquée')
            pg.screenshot(path=os.path.join(sortie, nom_f + '.png'))
            os.remove(chemin)
            faits.append(nom_f + '.png')
        b.close()
    return faits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sortie', default='classements')
    ap.add_argument('--jour', default='', help='jour de la carte du matin (défaut : aujourd\'hui, heure de Paris)')
    ap.add_argument('--donnees', default=os.path.join(RACINE, 'algo', 'donnees.json'))
    a = ap.parse_args(argv)
    with open(a.donnees, encoding='utf-8') as f:
        doc = json.load(f)
    jour = dt.date.fromisoformat(a.jour) if a.jour else dt.datetime.now(paris()).date()
    pages = []
    v = verification(doc, jour - dt.timedelta(days=1))
    if v:
        pages.append(('verification', html_verif(v, jour - dt.timedelta(days=1))))
    c = classements_jour(doc, jour)
    if c:
        pages.append(('classements', html_jour(c, jour)))
    if not pages:
        print('Pas assez de matchs pour une carte.')
        return 0
    print('Cartes :', rendre(pages, a.sortie))
    return 0


if __name__ == '__main__':
    sys.exit(main())
