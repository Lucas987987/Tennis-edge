#!/usr/bin/env python3
"""
fetch_results_settlement.py — Flux RAPIDE de resultats via OddsPapi /settlement (v5).

Role (architecture "vitesse maintenant, verite ensuite") :
- Pour chaque match deja suivi en CLV (clv_history.jsonl porte fixture_id + noms),
  on demande la notation officielle du bookmaker (/fixtures/settlement) des qu'il est
  fini, et on en deduit le vainqueur de facon EXACTE (par fixtureId, zero ambiguite de
  noms) + le score en sets.
- Sorties :
    1) resultats_oddspapi.json  -> store EXACT keye par fixtureId (provisoire).
    2) gap-fill du backtest (colonne `resultat`/`src_resultat`) par NOMS, en reutilisant
       le matching eprouve de fetch_results_fast (same_player) -> nourrit les analyses
       existantes sans rien changer en aval.

REGLE : provisoire. Sackmann (fetch_results.py) reste PRIORITAIRE et ECRASE ensuite.
Ce module ne remplit QUE des resultats MANQUANTS (gap-fill) ; il ne verrouille aucun CLV.

Quota : 1 appel /settlement par match fini non encore resolu (dedup via le store).
Cle via env RAPIDAPI_KEY. Ne modifie jamais les fichiers en lecture seule.
"""
import json, os, datetime

import oddspapi_v5 as ov
# Reutilise le matching de fetch_results_fast (helpers au niveau module ;
# run() seulement sous __main__ -> import sans effet de bord)
from fetch_results_fast import same_player

CLV_LOG          = os.environ.get('CLV_LOG_FILE', 'clv_history.jsonl')
STORE            = os.environ.get('RESULTATS_OP_FILE', 'resultats_oddspapi.json')
BACKTEST         = os.environ.get('BACKTEST_FILE', 'backtest_tennis.csv')
# Marge avant de considerer un match "probablement fini" (h apres le coup d'envoi).
FINISHED_AFTER_H = float(os.environ.get('FINISHED_AFTER_H', '4'))
MAX_CALLS        = int(os.environ.get('MAX_SETTLEMENT_CALLS', '60'))
# Au-dela de cet age, on abandonne (Sackmann couvrira) -> evite de re-interroger
# eternellement des matchs jamais resolus.
MAX_AGE_DAYS     = float(os.environ.get('MAX_AGE_DAYS', '35'))
# Statuts terminaux SANS vainqueur exploitable : on les note "void" pour ne plus
# les re-interroger (sinon 1 appel gaspille a chaque run, indefiniment).
VOID_STATUSES    = {'Cancelled', 'Canceled', 'Abandoned', 'Walkover', 'Retired'}


def parse_iso(s):
    if not s:
        return None
    s = str(s).replace('Z', '+00:00')
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def load_clv_matches():
    """Matchs uniques suivis en CLV : {fixture_id: {home,away,commence_time,tournament}}."""
    out = {}
    if not os.path.exists(CLV_LOG):
        return out
    with open(CLV_LOG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            fid = d.get('fixture_id')
            if not fid:
                continue
            out[fid] = {
                'home': d.get('home', ''), 'away': d.get('away', ''),
                'commence_time': d.get('commence_time', ''),
                'tournament': d.get('tournament', ''),
            }
    return out


def load_store():
    if os.path.exists(STORE):
        try:
            return json.load(open(STORE, encoding='utf-8'))
        except Exception:
            pass
    return {}


def main():
    if not os.environ.get('RAPIDAPI_KEY'):
        print("X RAPIDAPI_KEY absente -- abandon")
        return

    matches = load_clv_matches()
    store = load_store()
    now = datetime.datetime.now(datetime.timezone.utc)

    # candidats = suivis en CLV, probablement finis, pas trop vieux, pas deja resolus
    todo = []
    backfill = []   # deja resolus MAIS sans set1 (donnee ajoutee apres coup) -> 1 requete pour completer
    for fid, m in matches.items():
        prev = store.get(fid)
        if prev and (prev.get('winner') or prev.get('void')):
            # Backfill set1 : entree resolue avant l'ajout du champ. On re-interroge
            # UNE fois (le settlement contient le marche 123 gratuitement) puis on
            # marque set1 (ou set1=False si indisponible) pour ne plus revenir.
            if prev.get('winner') and ('set1' not in prev or 'set2' not in prev):
                backfill.append((fid, m))
            continue   # deja resolu (resultat) ou terminal sans vainqueur (void)
        ct = parse_iso(m['commence_time'])
        if ct is not None:
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=datetime.timezone.utc)
            age_s = (now - ct).total_seconds()
            if age_s < FINISHED_AFTER_H * 3600:
                continue   # pas encore (probablement) fini
            if age_s > MAX_AGE_DAYS * 86400:
                continue   # trop vieux -> on abandonne (Sackmann couvrira)
        todo.append((fid, m))

    print(f"[i] {len(matches)} matchs suivis | {len(store)} deja resolus | "
          f"{len(todo)} a interroger | {len(backfill)} backfill set1")
    # Budget : les nouveaux matchs d'abord, le backfill avec le reliquat.
    todo = todo[:MAX_CALLS]
    backfill = backfill[:max(0, MAX_CALLS - len(todo))]

    resolved = 0
    voided = 0
    backfilled = 0
    parsed = []   # (home, away, winner_name) pour gap-fill backtest
    for fid, m in todo:
        r = ov.settlement_result(fid)
        if not r['winner']:
            # terminal sans vainqueur (annule, etc.) -> on note "void" et on ne
            # re-interroge plus ; sinon (NotStarted/InProgress) -> retry plus tard.
            if r['status_name'] in VOID_STATUSES:
                store[fid] = {
                    'home': m['home'], 'away': m['away'],
                    'tournament': m['tournament'],
                    'winner': None, 'void': True,
                    'status_name': r['status_name'],
                    'source': 'oddspapi_settlement', 'provisional': True,
                    'resolved_at': now.isoformat(),
                }
                voided += 1
                print(f"  -- {fid} {m['home']} v {m['away']} : VOID ({r['status_name']})")
            else:
                print(f"  .. {fid} {m['home']} v {m['away']} : pas encore note ({r['status_name']})")
            continue
        winner_name = m['home'] if r['winner'] == 'home' else m['away']
        sets = None
        if r['p1_sets'] is not None and r['p2_sets'] is not None:
            sets = f"{r['p1_sets']}-{r['p2_sets']}"
        store[fid] = {
            'home': m['home'], 'away': m['away'],
            'tournament': m['tournament'],
            'winner': r['winner'],           # 'home' / 'away'
            'winner_name': winner_name,
            'set1': r.get('set1'),           # 'home'/'away'/None (vainqueur du 1er set, marche 123)
            'set2': r.get('set2'),           # 'home'/'away'/None (vainqueur du 2e set, marche 125)
            'sets': sets,
            'p1_sets': r['p1_sets'], 'p2_sets': r['p2_sets'],
            'source': 'oddspapi_settlement', 'provisional': True,
            'resolved_at': now.isoformat(),
        }
        parsed.append((m['home'], m['away'], winner_name))
        resolved += 1
        s1 = {'home': m['home'], 'away': m['away']}.get(r.get('set1'), '?')
        print(f"  OK {fid} {m['home']} v {m['away']} -> {winner_name} ({sets}) | set1: {s1}")

    # Backfill set1 sur les entrees deja resolues (1 requete chacune, borné)
    for fid, m in backfill:
        r = ov.settlement_result(fid)
        # set1=False (et non None) si le settlement 123 n'existe pas pour ce match :
        # on distingue "indisponible, ne plus re-interroger" de "jamais demande".
        # Ne jamais DEGRADER une valeur deja connue (si l'API a un rate sur ce
        # re-passage, on garde l'existant ; False = definitivement indispo).
        if not store[fid].get('set1'):
            store[fid]['set1'] = r.get('set1') if r.get('set1') else False
        if not store[fid].get('set2'):
            store[fid]['set2'] = r.get('set2') if r.get('set2') else False
        backfilled += 1
        s1 = {'home': m['home'], 'away': m['away']}.get(r.get('set1'), 'indispo')
        s2 = {'home': m['home'], 'away': m['away']}.get(r.get('set2'), 'indispo')
        print(f"  S1/S2 {fid} {m['home']} v {m['away']} | set1: {s1} | set2: {s2}")

    # store exact (fixtureId)
    with open(STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nOK {STORE} : +{resolved} nouveaux"
          + (f" | {voided} void" if voided else "")
          + (f" | {backfilled} set1 backfill" if backfilled else "")
          + f" | {len(store)} au total")

    # gap-fill backtest par NOMS (src='oddspapi', ne remplit QUE le manquant)
    fill_backtest(parsed)


def fill_backtest(parsed):
    if not parsed or not os.path.exists(BACKTEST):
        return
    with open(BACKTEST, encoding='utf-8') as f:
        lines = [l for l in f.read().split('\n') if l.strip()]
    if len(lines) < 2:
        return
    headers = lines[0].split(';')
    def idx(n): return headers.index(n) if n in headers else -1
    iJA, iJB = idx('joueurA'), idx('joueurB')
    iRes = idx('resultat')
    iSrc = idx('src_resultat')
    if min(iJA, iJB, iRes) < 0:
        print("  !! Colonnes backtest manquantes : gap-fill CSV desactive")
        return
    rows = [l.split(';') for l in lines[1:]]
    for r in rows:
        while len(r) < len(headers):
            r.append('')
    created_src = False
    if iSrc < 0:
        headers.append('src_resultat'); iSrc = len(headers) - 1
        for r in rows:
            r.append('')
        created_src = True

    updated = 0; ambigus = 0
    for r in rows:
        if r[iRes].strip() not in ('', 'nan'):
            continue   # gap-fill only : ne jamais ecraser (Sackmann/Matchstat prioritaires)
        ja, jb = r[iJA], r[iJB]
        cands = [w for (a, b, w) in parsed
                 if (same_player(ja, a) and same_player(jb, b))
                 or (same_player(ja, b) and same_player(jb, a))]
        if not cands:
            continue
        if len({same_player(c, ja) for c in cands}) > 1:
            ambigus += 1; continue   # vainqueurs contradictoires -> on s'abstient
        win_name = cands[0]
        r[iRes] = '1' if same_player(win_name, ja) else '0'
        if iSrc >= 0:
            r[iSrc] = 'oddspapi'
        updated += 1

    if updated or created_src:
        out = [';'.join(headers)] + [';'.join(r) for r in rows]
        with open(BACKTEST, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')
    print(f"OK backtest (matching par noms) : {updated} resultats remplis" +
          (f" | !! {ambigus} ambigus" if ambigus else ""))


if __name__ == '__main__':
    main()
