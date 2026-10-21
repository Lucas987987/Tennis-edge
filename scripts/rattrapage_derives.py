#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rattrapage_derives.py — marchés dérivés Pinnacle des 60 derniers jours (21/10/2026).

La collecte garde désormais total de sets, handicap de sets, total et handicap
de jeux (marches_derives.py), mais seulement pour les matchs récupérés après
son installation. Ce rattrapage redemande UNE fois l'historique Pinnacle de
chaque match déjà collecté (courbe Pinnacle connue) qui n'a pas encore ses
marchés dérivés, du plus RÉCENT au plus ancien (les plus vieux risquent de ne
plus être servis : on prend d'abord ce qui est sûr).

Garde-fous, identiques à fetch_book_curves : réserve pour le reste du projet
jusqu'au renouvellement (consommation mesurée × 1,3, plancher CAPTURE_PAR_JOUR),
plancher de fin de cycle (QUOTA_PLANCHER), arrêt au premier 429, plafond par
run (RATTRAPAGE_MAX). Un match sans réponse est noté (derives_absences.json)
et n'est jamais redemandé. Rien n'est réécrit dans hist_book / set1 / set2.

Env : RAPIDAPI_KEY, RATTRAPAGE_MAX (def 2600), RATTRAPAGE_JOURS (def 60),
      DERIVES_BOOK (def pinnacle), CLV_COOLDOWN.
"""
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402
import closing_store  # noqa: E402
import marches_derives as md  # noqa: E402
import fetch_book_curves as F  # noqa: E402  (mêmes uid, mêmes garde-fous de quota)

MAX = int(os.environ.get('RATTRAPAGE_MAX', '2600'))
JOURS = int(os.environ.get('RATTRAPAGE_JOURS', '60'))
BOOK = os.environ.get('DERIVES_BOOK', 'pinnacle')
ABSENCES = os.environ.get('DERIVES_ABSENCES', 'derives_absences.json')
RAPPORT = os.environ.get('DERIVES_RAPPORT', 'derives_rattrapage.json')


def candidats(closing, deja_book, deja_derives, absences, now):
    """[(uid, m, fid, start)] du plus récent au plus ancien : courbe BOOK connue, dérivés absents."""
    out = []
    limite = now - datetime.timedelta(days=JOURS)
    for raw, m in closing.items():
        fid = m.get('fixture_id') or m.get('id')
        ct = m.get('commence_time', '')
        if not fid or not ct:
            continue
        home, away = m.get('home', ''), m.get('away', '')
        uid = f"{ct[:10]}_{F._slug(home)}_{F._slug(away)}" if home and away else raw
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            continue
        if not (limite <= start <= now - datetime.timedelta(hours=3)):
            continue
        if uid not in deja_book or uid in deja_derives or uid in absences:
            continue
        out.append((uid, m, fid, start))
    out.sort(key=lambda x: x[3], reverse=True)
    vus, uniq = set(), []
    for x in out:                       # un même match peut figurer deux fois dans closing_lines
        if x[0] not in vus:
            vus.add(x[0])
            uniq.append(x)
    return uniq


def connus(marche, book=None):
    s = set()
    for line in ov.iter_hist_lines(marche):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if book is None or d.get('book') == book:
            s.add(d.get('uid'))
    return s


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente")
        return 1
    if not closing_store.exists(F.CLOSING_FILE):
        print("Pas de closing_lines.json")
        return 1
    now = datetime.datetime.utcnow()
    closing = closing_store.load_all(F.CLOSING_FILE, max_age_days=None)
    deja_book, deja_derives = connus('book', BOOK), connus('derives', BOOK)
    try:
        absences = json.load(open(ABSENCES, encoding='utf-8'))
    except (OSError, ValueError):
        absences = {}
    todo = candidats(closing, deja_book, deja_derives, absences, now)
    print(f"{BOOK} : {len(deja_book)} matchs avec courbe, {len(deja_derives)} déjà avec dérivés ; "
          f"{len(todo)} à rattraper sur {JOURS} jours (plafond du run : {MAX})")
    if not todo:
        return 0
    if len(deja_book) < 100:
        print("❌ historique des courbes presque vide (R2 non rapatrié ?) : rien n'est demandé.")
        return 1
    table = md.charger_table(demander=lambda: ov.api_get('/markets', {'sportId': ov.TENNIS_SPORT_ID})[0])
    if not table:
        print("❌ table des marchés indisponible : rien n'est demandé.")
        return 1
    try:
        precedent = json.load(open(F.COUVERTURE, encoding='utf-8'))
    except (OSError, ValueError):
        precedent = {}
    reserve, mesure = F.CAPTURE_PAR_JOUR, None
    demandes, gardes, vides, arret = 0, 0, 0, None
    path = ov.current_hist_partition_path('derives')
    with open(path, 'a', encoding='utf-8') as fd:
        for uid, m, fid, start in todo:
            if demandes >= MAX:
                arret = f"plafond du run ({MAX})"
                break
            if ov.QUOTA.get('remaining') is not None and demandes <= 1:
                reserve, mesure = F.reserve_mesuree(precedent, ov.QUOTA['remaining'], now)
            marge = F.marge_quota(reserve)
            if marge is not None and marge <= 0:
                arret = (f"quota : {ov.QUOTA.get('remaining')} restants, réservés au reste du projet "
                         f"({reserve}/jour jusqu'au renouvellement)")
                break
            if ov.QUOTA_HIT:
                arret = "quota épuisé (429)"
                break
            time.sleep(F.COOLDOWN)
            demandes += 1
            try:
                data = ov.historical(fid, BOOK)
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠️ {uid}: {e}")
                continue
            res = md.resumer(data, BOOK, table, start)
            if res:
                fd.write(json.dumps(md.ligne(uid, fid, BOOK, m, start, res), ensure_ascii=False) + '\n')
                gardes += 1
            else:
                absences[uid] = now.isoformat(timespec='seconds')
                vides += 1
            if demandes % 200 == 0:
                print(f"  … {demandes} demandes · {gardes} gardés · {vides} sans marché · quota {ov.QUOTA.get('remaining')}",
                      flush=True)
    try:
        if os.path.getsize(path) == 0:
            os.remove(path)
    except OSError:
        pass
    limite = (now - datetime.timedelta(days=JOURS + 1)).date().isoformat()
    absences = {k: v for k, v in absences.items() if k[:10] >= limite}
    with open(ABSENCES, 'w', encoding='utf-8') as f:
        json.dump(absences, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    rap = {'ecrit_le': now.isoformat(timespec='seconds'), 'book': BOOK, 'demandes': demandes, 'gardes': gardes,
           'sans_marche': vides, 'restants': max(0, len(todo) - demandes), 'arret': arret,
           'reserve_par_jour': reserve, 'conso_mesuree_par_jour': mesure,
           'quota': {k: ov.QUOTA.get(k) for k in ('limit', 'remaining', 'reset_s')}}
    with open(RAPPORT, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(f"Rattrapage : {demandes} demandes, {gardes} matchs gardés, {vides} sans marché dérivé, "
          f"{rap['restants']} restants{' — arrêt : ' + arret if arret else ''} · quota restant {ov.QUOTA.get('remaining')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
