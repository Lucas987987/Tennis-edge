#!/usr/bin/env python3
"""
clean_clv_metrics.py — Recalcule proprement les metriques CLV des matchs DEJA enregistres.

Pourquoi : les courbes stockees dans clv_history.jsonl contiennent des points IN-PLAY
(apres le coup d'envoi). Le CLV open->close etait deja correct (close = dernier prix
PRE-match), mais amplitude/min/max etaient calcules sur TOUTE la courbe -> pollues.
Ce script recalcule home_metrics/away_metrics en PRE-MATCH UNIQUEMENT, a partir des
courbes deja sur disque. AUCUN appel API. Ne touche ni aux courbes, ni aux resultats.

Garde-fou : open/close ne doivent PAS bouger (le CLV-forward etait deja propre) ; tout
ecart est signale. Idempotent. Sauvegarde clv_history.jsonl.bak avant ecriture.
"""
import json, os, datetime, shutil

from fetch_clv import analyze_side   # reutilise EXACTEMENT la logique de calcul (corrigee)

CLV_LOG = os.environ.get('CLV_LOG_FILE', 'clv_history.jsonl')


def pdt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def to_curve(raw):
    out = []
    for item in (raw or []):
        try:
            dt = pdt(item[0]); pr = item[1]
            if dt is None or pr is None:
                continue
            out.append((dt, float(pr)))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def main():
    if not os.path.exists(CLV_LOG):
        print(f"X {CLV_LOG} introuvable"); return
    lines = [l for l in open(CLV_LOG, encoding='utf-8').read().split('\n') if l.strip()]
    total = 0; changed = 0; flagged = []
    out_lines = []
    for l in lines:
        try:
            d = json.loads(l)
        except Exception:
            out_lines.append(l); continue
        total += 1
        start = pdt(d.get('commence_time'))
        for side in ('home', 'away'):
            cur = to_curve(d.get(side + '_curve'))
            if not cur:
                continue
            new = analyze_side(cur, start)
            old = d.get(side + '_metrics') or {}
            # garde-fou : le close (donc le CLV) ne doit pas changer
            if new and old.get('close') is not None and \
               abs((new.get('close') or 0) - (old.get('close') or 0)) > 1e-9:
                flagged.append((d.get('home'), d.get('away'), side, old.get('close'), new.get('close')))
            if new and new != old:
                d[side + '_metrics'] = new
                changed += 1
        out_lines.append(json.dumps(d, ensure_ascii=False))

    shutil.copyfile(CLV_LOG, CLV_LOG + '.bak')
    with open(CLV_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines) + '\n')
    print(f"OK {total} matchs | {changed} jeux de metriques recalcules | sauvegarde: {CLV_LOG}.bak")
    if flagged:
        print(f"!! {len(flagged)} close MODIFIES (anormal -- a verifier) :")
        for x in flagged[:10]:
            print('  ', x)
    else:
        print("OK close inchanges partout : CLV-forward intact")


if __name__ == '__main__':
    main()
