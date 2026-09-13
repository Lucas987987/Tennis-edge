#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_suivi.py — Suivi quotidien des écarts publiés sur le canal.

Un seul message par jour qui montre ce que sont devenus les écarts signalés la
veille : combien se sont refermés, de combien, avec le meilleur ET le moins bon
cas. Publier les échecs autant que les réussites est le point central — c'est ce
qui rend le suivi crédible et impossible à sélectionner a posteriori.

Mesure : prix signalé dans le message vs DERNIER PRIX PRÉ-MATCH du MÊME
opérateur. Pas de résultat de match, pas de gain : uniquement du prix.

Env : LOG (canal_public_log.jsonl), CURVES, DAYS (1 = la veille),
      TELEGRAM_TOKEN, TELEGRAM_PUBLIC_CHAT_ID, DRY_RUN, MIN_ROWS (3),
      REPO_URL (lien vers le détail public).
"""
import os, json, glob, datetime, statistics as st, urllib.request, urllib.parse
try:
    import oddspapi_v5 as ov            # ouvre aussi les partitions parts/
except Exception:                       # pragma: no cover
    ov = None

LOG      = os.environ.get('LOG', 'canal_public_log.jsonl')
CURVES   = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
# NOTE 13/09/2026 : `book_curves.jsonl` a migré vers parts/hist_* ; ouvert
# avec un open() brut, ce second maillon de la cascade ne donnait plus rien
# depuis la migration, laissant une seule source glissante. On passe par
# oddspapi_v5.open_curves, qui sait résoudre les noms hérités vers les
# partitions — même mécanisme que canal_clv.py et move_audit.py.
DAYS     = int(os.environ.get('DAYS', '1'))
MIN_ROWS = int(os.environ.get('MIN_ROWS', '3'))
# MARGE DE COMPLÉTUDE (13/09/2026) — minutes à attendre APRÈS le coup d'envoi
# avant de mesurer un écart. Voir la note « complétude » dans main().
MARGE_MIN = int(os.environ.get('MARGE_MIN', '60'))


def _maintenant():
    """Heure courante, surchargeable par NOW_OVERRIDE.

    Ajouté le 13/09/2026 avec la condition de complétude : une règle qui
    dépend de l'heure ne se teste pas si l'heure n'est pas injectable. Même
    convention que paper_journal.py.
    """
    v = os.environ.get('NOW_OVERRIDE', '')
    if v:
        try:
            return datetime.datetime.fromisoformat(
                v.replace('Z', '').replace('+00:00', ''))
        except Exception:
            pass
    return datetime.datetime.utcnow()
# Exchanges : sans marge intégrée, leur prix est structurellement plus haut,
# donc ils ressortent en permanence comme « en retard » sans l'être
# (CLV médian -1,7 %, 14 % de refermeture sur les alertes publiées).
# canal_public.py ne les signale plus depuis le 06/08/2026 ; on filtre ici
# aussi, au cas où d'anciennes alertes remonteraient dans la fenêtre.
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())
REPO_URL = os.environ.get('REPO_URL', '')
TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
CHAT     = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY      = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Suivi de prix uniquement : prix signalé comparé au dernier prix "
          "pré-match du même opérateur. Aucun résultat de match, aucun gain. "
          "Ceci n'est pas un conseil.\n"
          "18+ | joueurs-info-service.fr · 09 74 75 13 13")


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    closes = {}
    for src in CURVES:
        chemins = glob.glob(src) or [src]
        for path in chemins:
            if ov is not None:
                try:
                    lignes = ov.open_curves(path, verbose=False)
                except Exception:
                    continue
            elif os.path.exists(path):
                lignes = open(path, encoding='utf-8')
            else:
                continue
            for line in lignes:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ct = _dt(r.get('commence_time'))
                if not ct:
                    continue
                home = r.get('home_team') or r.get('home') or ''
                away = r.get('away_team') or r.get('away') or ''
                for key, name in (('home_curve', home), ('away_curve', away)):
                    pts = [(_dt(p[0]), p[1]) for p in (r.get(key) or []) if _dt(p[0]) and p[1] and p[1] > 1]
                    pts = sorted(p for p in pts if p[0] < ct)   # PRÉ-MATCH uniquement
                    if pts and name:
                        # cf. canal_clv.py : on garde le point pré-match le
                        # plus tardif, pas celui de la première source.
                        k = (r.get('uid'), r.get('book'), name)
                        if k not in closes or pts[-1][0] > closes[k][1]:
                            closes[k] = (pts[-1][1], pts[-1][0])
    return closes


def tg(text):
    if DRY:
        print("--- DRY RUN ---\n" + text)
        return
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=urllib.parse.urlencode({'chat_id': CHAT, 'text': text,
                                     'disable_web_page_preview': 'true'}).encode())
    urllib.request.urlopen(req, timeout=15)


def main():
    if not os.path.exists(LOG):
        print(f"{LOG} introuvable"); return
    now = _maintenant()
    day = (now - datetime.timedelta(days=DAYS)).date()
    closes = load_closes()
    rows = []
    en_attente = 0
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        t = _dt(m.get('t'))
        if not t or t.date() != day:
            continue
        joueur = m.get('joueur')
        commence = _dt(m.get('commence'))
        for entry in (m.get('retards') or []):
            try:
                book, prix = entry[0], float(entry[1])
            except Exception:
                continue
            if book in EXCHANGES:
                continue      # cf. note EXCHANGES en tête
            # COMPLÉTUDE — AJOUTÉ LE 13/09/2026.
            #
            # Le bilan du jour D est publié le matin de D+1, mais un écart
            # signalé le jour D peut porter sur un match qui commence le
            # lendemain. Mesuré à ce moment-là, le « dernier prix pré-match »
            # n'est pas le dernier : c'est le dernier CONNU À L'HEURE DE
            # PUBLICATION.
            #
            # Cas réel du 11/09/2026 : alerte 22bet sur Arthur Weber à 11h52,
            # match le 12/09 à 03h00 UTC. Le canal a publié
            # « 2.694 → 2.694 (+0 %) » ; le prix a fini à 2.32, soit +16 %.
            # Deux lignes fausses sur trois dans ce message, et dans le
            # sens qui dessert le canal.
            #
            # On ne mesure donc qu'une fois le coup d'envoi passé, avec une
            # marge pour laisser les dernières captures être ingérées. Les
            # écarts en attente ne sont PAS comptés comme non refermés : ils
            # sortent simplement de la fenêtre du jour.
            if commence and (now - commence).total_seconds() < MARGE_MIN * 60:
                en_attente += 1
                continue
            got = closes.get((m.get('uid'), book, joueur))
            if not got:
                continue
            cl = got[0]
            rows.append(dict(joueur=joueur, book=book, prix=prix, close=cl,
                             clv=(prix/cl - 1) * 100))
    if en_attente:
        print(f"suivi : {en_attente} écart(s) en attente (match pas encore "
              f"joué + {MARGE_MIN} min) — ils seront mesurés plus tard")
    if len(rows) < MIN_ROWS:
        print(f"suivi : seulement {len(rows)} écart(s) mesurable(s) pour le {day} "
              f"({en_attente} en attente) — pas de publication")
        return

    # DÉDUPLICATION : un match ne compte qu'UNE fois (moyenne de ses lignes).
    # Un même match génère plusieurs alertes (paliers successifs) et chaque
    # alerte plusieurs opérateurs ; les compter séparément gonfle le "n"
    # affiché et présente un seul match comme plusieurs observations
    # indépendantes. Le détail par opérateur reste affiché en dessous
    # (plus net / moins bon), mais le comptage porte sur les MATCHS.
    par_match = {}
    for r in rows:
        par_match.setdefault(r['joueur'], []).append(r)
    clv = [st.mean([x['clv'] for x in v]) for v in par_match.values()]
    refermes = sum(1 for x in clv if x > 0)

    # PRIX INCHANGÉ — AJOUTÉ LE 13/09/2026.
    #
    # Constat sur le registre : 71 lignes sur 226 ont un CLV d'exactement
    # 0,0 %, parce que l'opérateur signalé n'a pas retouché son prix une
    # seule fois avant le coup d'envoi (bet365 27 fois, bet365.fr 8, 22bet 4).
    # Ce n'est pas un défaut de mesure -- les séries de ticks montrent ces
    # prix capturés une centaine de fois pour deux valeurs distinctes -- mais
    # le message les comptait avec les autres, sous « 0 se sont refermés ».
    #
    # « L'écart ne s'est pas refermé » et « l'opérateur n'a pas bougé son
    # prix » ne sont pas la même information, et c'est la seconde qui a de la
    # valeur : elle dit que ces books ne repricent pas, ce qui recoupe le
    # constat déjà établi sur les marges des opérateurs mous.
    #
    # Le TAUX AFFICHÉ NE CHANGE PAS : il reste calculé sur tous les matchs.
    # Sortir les prix figés du dénominateur remonterait mécaniquement le
    # pourcentage publié, et ce serait un choix éditorial à assumer
    # explicitement, pas un effet de bord d'un correctif technique.
    figees = [r for r in rows if abs(r['prix'] - r['close']) < 1e-9]
    matchs_figes = sum(1 for v in par_match.values()
                       if all(abs(x['prix'] - x['close']) < 1e-9 for x in v))

    L = [f"📋 SUIVI DES ÉCARTS SIGNALÉS — {day.strftime('%d/%m')}", "",
         f"{len(clv)} matchs signalés ({len(rows)} écarts) · {refermes} se sont "
         f"refermés ({100*refermes/len(clv):.0f}%)",
         f"Refermement médian par match : {st.median(clv):+.1f}%"]
    if figees:
        L.append(f"Dont {len(figees)} écart(s) sur {matchs_figes} match(s) où "
                 f"l'opérateur n'a pas modifié son prix une seule fois avant "
                 f"le match.")
    L.append("")

    # EXTRÊMES — n'afficher deux lignes que s'il y a vraiment deux cas.
    # Quand toutes les valeurs sont égales (typiquement : tous les prix
    # figés), « le plus net » et « le moins bon » pointaient la MÊME ligne,
    # ce qui donne au lecteur l'impression d'un message cassé alors que le
    # chiffre est juste.
    best = max(rows, key=lambda r: r['clv'])
    worst = min(rows, key=lambda r: r['clv'])
    if abs(best['clv'] - worst['clv']) < 1e-9:
        L.append(f"Tous à {best['clv']:+.0f}% — par exemple {best['book']} "
                 f"{best['prix']:.2f} → {best['close']:.2f} sur {best['joueur']}.")
    else:
        L += [f"Le plus net : {best['book']} {best['prix']:.2f} → {best['close']:.2f} "
              f"sur {best['joueur']} ({best['clv']:+.0f}%)",
              f"Le moins bon : {worst['book']} {worst['prix']:.2f} → {worst['close']:.2f} "
              f"sur {worst['joueur']} ({worst['clv']:+.0f}%)"]
    L += ["",
          "Méthode : prix signalé comparé au dernier prix pré-match du même "
          "opérateur. Un opérateur qui ne retouche jamais son prix compte comme "
          "un écart non refermé. On publie autant les écarts qui ne se referment "
          "pas que les autres."]
    if REPO_URL:
        L.append(f"Historique complet : {REPO_URL}")
    tg("\n".join(L) + FOOTER)
    print(f"suivi publié : {len(clv)} matchs / {len(rows)} écarts, "
          f"{refermes} refermés, {len(figees)} prix inchangé(s), "
          f"médian {st.median(clv):+.1f}%")


if __name__ == '__main__':
    main()
