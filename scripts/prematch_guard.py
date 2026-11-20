#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barriere PREMATCH unique des courbes d'alertes Tennis Edge.

AUCUN appel reseau. Source des horaires: dernier matches_oddspapi.json,
fraicheur: matches_oddspapi_meta.json, et garde optionnelle set_results.json.
Une inconnue doit conduire a BLOQUER l'alerte, jamais a deviner qu'un match
est a venir. Le statut reel n'est PAS garanti par ces fichiers.

On filtre UNIQUEMENT les courbes plates temporaires apres avoir archive leurs
points dans parts/live_* via curves_parts.append(). Le bilan historique reste
reconstructible. Le filtre est reapplique a chaque run (apres rebuild).
"""
import datetime as dt
import json
import os
import re
import unicodedata
from pathlib import Path

UTC = dt.timezone.utc
# Aucune marge avant le debut programme : toute seconde avant le depart reste eligible.
# Les canaux conservent leurs propres criteres statistiques (ex. MIN_LEAD=5).
MAX_SNAPSHOT_AGE_MINUTES = int(os.environ.get('PREMATCH_GUARD_MAX_AGE_MIN', '25'))
MAX_CURVE_AGE_MINUTES = int(os.environ.get('PREMATCH_GUARD_CURVE_AGE_MIN', '25'))
BLOCKED_STATUSES = {
    'inplay', 'in_play', 'live', 'started', 'playing', 'finished', 'ended',
    'complete', 'completed', 'settled', 'cancelled', 'canceled',
    'abandoned', 'retired', 'walkover', 'walk_over', 'withdrawn', 'postponed',
    'suspended', 'interrupted', 'void', 'forfeit',
}


def parse_utc(value):
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(value, UTC)
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        when = dt.datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def norm(value):
    s = unicodedata.normalize('NFKD', str(value or '').lower())
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def key(home, away):
    return norm(home), norm(away)


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def source_fresh(meta, now):
    if not isinstance(meta, dict):
        return False
    when = parse_utc(meta.get('last_write'))
    if when is None:
        return False
    age = (now - when).total_seconds() / 60
    return -2 <= age <= MAX_SNAPSHOT_AGE_MINUTES


def make_index(matches):
    """Ambiguites (meme paire dans deux fixtures) volontairement bloquees."""
    out = {}
    for match in matches if isinstance(matches, list) else []:
        if not isinstance(match, dict):
            continue
        k = key(match.get('home_team'), match.get('away_team'))
        if not all(k):
            continue
        if k in out:
            out[k] = None  # Ne pas choisir arbitrairement une date.
        else:
            out[k] = match
    return out


def finished_ids(resultats):
    return {uid for uid, data in (resultats or {}).items()
            if isinstance(data, dict) and data.get('match') in ('home', 'away')}


def has_blocked_status(match):
    for field in ('status', 'fixture_status', 'fixtureStatus', 'state', 'match_status'):
        status = match.get(field)
        if isinstance(status, dict):
            status = status.get('short') or status.get('name') or status.get('status')
        if status and str(status).strip().lower().replace(' ', '_') in BLOCKED_STATUSES:
            return True
    if match.get('inplay') is True or match.get('is_live') is True or match.get('live') is True:
        return True
    return False


def safe_curve(row, indexed, resolved, now):
    """Valide une courbe complete (UID/date/horaire/point et correspondance fixture)."""
    if not isinstance(row, dict):
        return False, 'format invalide', None
    fixture = indexed.get(key(row.get('home'), row.get('away')))
    if fixture is None:
        return False, 'fixture absente ou ambigue', None
    official = parse_utc(fixture.get('commence_time'))
    curve_time = parse_utc(row.get('commence_time'))
    if official is None or curve_time is None:
        return False, 'heure manquante', None
    if has_blocked_status(fixture):
        return False, 'statut non prematch', None
    # Si une date precedente est deja passee, une nouvelle date peut representer
    # un report ou une duplication d'UID: eviter toute reprise de cours in-play.
    if curve_time <= now and official > now:
        return False, 'ancien debut depasse, possible report', None
    # Un changement d'horaire > 2 jours merite une nouvelle fixture propre.
    if abs((official - curve_time).total_seconds()) > 2 * 86400:
        return False, 'report incertain', None
    lead = (official - now).total_seconds() / 60
    if lead <= 0:
        return False, 'heure de debut atteinte ou depassee', None
    if row.get('uid') in resolved:
        return False, 'resultat deja connu', None
    # Ne pas requalifier comme prematch des points historiques au-dela de
    # l'heure officielle. Filtrer egalement les anomalies de temps futur.
    all_pts = (row.get('home_curve') or []) + (row.get('away_curve') or [])
    last = None
    for pt in all_pts:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        stamp = parse_utc(pt[0])
        if stamp is None:
            continue
        if stamp >= official:
            return False, 'point apres heure du match', None
        if stamp <= now and (last is None or stamp > last):
            last = stamp
    if last is None or (now - last).total_seconds() / 60 > MAX_CURVE_AGE_MINUTES:
        return False, 'courbe perimee', None
    if (last - now).total_seconds() > 120:
        return False, 'horodatage futur', None
    return True, 'ok', official


def filter_file(path, indexed, resolved, now):
    p = Path(path)
    if not p.is_file():
        return {'file': str(p), 'total': 0, 'kept': 0, 'missing': True}
    kept, reasons, n = [], {}, 0
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        n += 1
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        ok, why, official = safe_curve(row, indexed, resolved, now)
        if ok:
            # L'horaire officiel recent prime celui stocke dans la courbe.
            row['commence_time'] = official.isoformat().replace('+00:00', 'Z')
            kept.append(json.dumps(row, ensure_ascii=False))
        else:
            reasons[why] = reasons.get(why, 0) + 1
    # Ecriture atomique pour ne pas livrer un fichier tronque aux detecteurs.
    tmp = p.with_name(p.name + '.prematch.tmp')
    tmp.write_text(('\n'.join(kept) + '\n') if kept else '', encoding='utf-8')
    tmp.replace(p)
    return {'file': str(p), 'total': n, 'kept': len(kept), 'excluded': reasons}


def filter_all(root='.', now=None, curve_paths=None):
    """Appele EN FIN de build_live_curves, avant tous les scripts Telegram.

    Le fichier cote brut est deja persiste dans parts/live_* a ce stade.
    S'il n'existe pas de snapshot recent, les sorties sont VIDES (fail-closed).
    """
    root = Path(root)
    now = now or dt.datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    defaults = ('book_curves_live.jsonl', 'set1_curves_live.jsonl', 'set2_curves_live.jsonl')
    paths = [root / x for x in (curve_paths or defaults)]
    meta = read_json(root / 'matches_oddspapi_meta.json')
    fresh = source_fresh(meta, now)
    indexed = make_index(read_json(root / 'matches_oddspapi.json', []) if fresh else [])
    resolved = finished_ids(read_json(root / 'set_results.json', {}) or {})
    report = {'snapshot_recent': fresh, 'sources_matchs': len(indexed), 'courbes': []}
    for path in paths:
        result = filter_file(path, indexed, resolved, now)
        report['courbes'].append(result)
    counts = ', '.join('%s: %s/%s' % (Path(x['file']).name, x.get('kept', 0), x['total'])
                       for x in report['courbes'])
    print(f"🛡️ PREMATCH_GUARD : source fraîche={fresh} | {counts} | aucune marge avant depart officiel")
    if not fresh:
        print('⚠️ Snapshot OddsPapi trop ancien/absent : alertes bloquées, 0 appel API')
    return report


if __name__ == '__main__':
    filter_all()
