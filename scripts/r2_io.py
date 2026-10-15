#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r2_io.py — LECTEUR / ÉCRIVAIN R2 UNIQUE du dépôt (créé le 15/10/2026).

POURQUOI
Le dépôt pèse 5,24 Go et grossit surtout à cause des partitions qui changent
à chaque run : ticks Polymarket/Kalshi (parts/pm_ticks_*, parts/kx_ticks_*)
et courbes live (parts/live_*). Ce module est le SEUL point d'accès à R2 pour
ces données : get / put / list / exists, un manifeste par famille, et
`materialize()` qui rapatrie dans parts/ une partition absente du checkout.

TROIS MODES — variable de dépôt R2_PRIMARY (env du même nom) :
  off     : R2 ignoré. Tout vient de git (comportement d'avant).
  double  : git reste la source de vérité ; chaque écrivain copie AUSSI ses
            partitions dans R2 (une écriture par partition et par run).
  on      : R2 est la source de vérité pour ces partitions ; git ne les
            reçoit plus (r2_parts.py gate), les lecteurs les rapatrient.
Sans variable (exécution locale, Codespace, tests) : off.

SANS SECRETS, RIEN NE CASSE
Si R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ENDPOINT manquent, client()
renvoie None avec UN message clair, et chaque fonction se replie sur les
copies git : aucun script ne doit échouer parce que R2 est absent.

CLIENT
boto3 s'il est installé (même configuration que r2_storage.create_client,
éprouvée sur R2), sinon un client S3 minimal en bibliothèque standard
(signature AWS SigV4, testée sur le vecteur officiel AWS) : les workflows
qui ne font que LIRE n'ont rien à installer.

COÛT (offre gratuite R2 : 1 M opérations classe A/mois, 10 M classe B/mois)
Chaque appel est compté : classe A = PUT/LIST, classe B = GET/HEAD.
`ops_summary()` est imprimé par les commandes de r2_parts.py.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import gzip
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from xml.etree import ElementTree

DEFAULT_BUCKET = "tennis-edge-courbes"
MODES = ("off", "double", "on")

# Familles de partitions servies par R2. Clés : <prefix><nom de fichier>.
# Un manifeste PAR ÉCRIVAIN (pm, kx, live) : les deux collecteurs tournent en
# parallèle, ils ne se disputent jamais le même objet.
FAMILIES = {
    "pm": {
        "regex": re.compile(r"^pm_ticks_(\d{4}-\d{2}-\d{2})(?:_\d+)?\.jsonl\.gz$"),
        "prefix": "parts/ticks/",
        "manifest": "parts/ticks/_manifest_pm.json",
        "glob": "parts/pm_ticks_*.jsonl.gz",
        "window_env": "R2_WINDOW_DAYS_TICKS", "window_default": 7,
    },
    "kx": {
        "regex": re.compile(r"^kx_ticks_(\d{4}-\d{2}-\d{2})(?:_\d+)?\.jsonl\.gz$"),
        "prefix": "parts/ticks/",
        "manifest": "parts/ticks/_manifest_kx.json",
        "glob": "parts/kx_ticks_*.jsonl.gz",
        "window_env": "R2_WINDOW_DAYS_TICKS", "window_default": 7,
    },
    "live": {
        "regex": re.compile(r"^live_(?:match|set1|set2)_(\d{4}-\d{2}-\d{2})\.jsonl\.gz$"),
        "prefix": "parts/live/",
        "manifest": "parts/live/_manifest.json",
        "glob": "parts/live_*.jsonl.gz",
        # 3 jours = rétention git de purge_data (LIVE_DAYS) : jamais plus.
        "window_env": "R2_WINDOW_DAYS_LIVE", "window_default": 3,
    },
}
ALIASES = {"ticks": ("pm", "kx"), "all": ("pm", "kx", "live")}
PARTS_DIR = "parts"

# Compteur d'opérations du PROCESSUS (imprimé en fin de commande).
OPS = {"A": 0, "B": 0, "bytes_in": 0, "bytes_out": 0}
_WARNED = set()


def log(msg: str) -> None:
    print(f"[r2] {msg}", flush=True)


def warn_once(key: str, msg: str) -> None:
    if key not in _WARNED:
        _WARNED.add(key)
        log(msg)


def ops_summary() -> str:
    return (f"opérations R2 : classe A={OPS['A']} classe B={OPS['B']} "
            f"(reçu {OPS['bytes_in']/1e6:.1f} Mo, envoyé {OPS['bytes_out']/1e6:.1f} Mo)")


def mode(environ=None) -> str:
    environ = os.environ if environ is None else environ
    value = (environ.get("R2_PRIMARY") or "off").strip().lower()
    if value not in MODES:
        warn_once("mode", f"R2_PRIMARY={value!r} inconnu — traité comme 'off'")
        return "off"
    return value


def families(spec: str | None) -> list[str]:
    out = []
    for part in (spec or "all").split(","):
        part = part.strip()
        if not part:
            continue
        for fam in ALIASES.get(part, (part,)):
            if fam not in FAMILIES:
                raise ValueError(f"famille R2 inconnue : {fam}")
            if fam not in out:
                out.append(fam)
    return out


def family_of(name: str) -> str | None:
    base = os.path.basename(name)
    for fam, spec in FAMILIES.items():
        if spec["regex"].match(base):
            return fam
    return None


def day_of(name: str) -> str | None:
    fam = family_of(name)
    if not fam:
        return None
    return FAMILIES[fam]["regex"].match(os.path.basename(name)).group(1)


class PreconditionFailed(Exception):
    """Écriture conditionnelle refusée (If-Match / If-None-Match)."""


class DivergentData(Exception):
    """Deux versions d'une partition qui ne se prolongent pas l'une l'autre."""


def _error_code(exc) -> str | None:
    return (getattr(exc, "response", None) or {}).get("Error", {}).get("Code")


# ── client S3 minimal (bibliothèque standard, SigV4) ─────────────────────────

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(method, url, headers, payload, access_key, secret_key,
                  region="auto", service="s3", now=None):
    """Renvoie les en-têtes signés (AWS Signature V4) pour une requête S3.

    `headers` : en-têtes à signer en plus de host/x-amz-*. Testé contre
    l'exemple officiel AWS « GET Object » (tests/test_r2_io.py)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    parsed = urllib.parse.urlsplit(url)
    payload_hash = _sha256_hex(payload or b"")
    signed = {k.lower(): str(v).strip() for k, v in (headers or {}).items()}
    signed["host"] = parsed.netloc
    signed["x-amz-content-sha256"] = payload_hash
    signed["x-amz-date"] = amz_date
    canonical_uri = urllib.parse.quote(urllib.parse.unquote(parsed.path or "/"),
                                       safe="/-_.~")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    canonical_query = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(query))
    names = sorted(signed)
    canonical_headers = "".join(f"{n}:{signed[n]}\n" for n in names)
    signed_headers = ";".join(names)
    canonical_request = "\n".join([method, canonical_uri, canonical_query,
                                   canonical_headers, signed_headers, payload_hash])
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope,
                         _sha256_hex(canonical_request.encode("utf-8"))])
    k = _hmac(("AWS4" + secret_key).encode("utf-8"), datestamp)
    k = _hmac(k, region)
    k = _hmac(k, service)
    k = _hmac(k, "aws4_request")
    signature = hmac.new(k, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    out = dict(signed)
    out["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                            f"SignedHeaders={signed_headers}, Signature={signature}")
    return out


class _HTTPError(Exception):
    def __init__(self, status, code, body=b""):
        super().__init__(f"HTTP {status} {code}")
        self.response = {"Error": {"Code": code},
                         "ResponseMetadata": {"HTTPStatusCode": status}}
        self.body = body


class MiniS3:
    """Sous-ensemble compatible boto3 (head_object, get_object, put_object,
    get_paginator('list_objects_v2')) en bibliothèque standard."""

    def __init__(self, endpoint, access_key, secret_key, timeout=60):
        self.endpoint = endpoint.rstrip("/")
        self.ak, self.sk, self.timeout = access_key, secret_key, timeout

    def _url(self, bucket, key="", query=None):
        url = f"{self.endpoint}/{bucket}"
        if key:
            url += "/" + urllib.parse.quote(key, safe="/-_.~")
        if query:
            url += "?" + urllib.parse.urlencode(sorted(query.items()))
        return url

    def _request(self, method, url, body=b"", headers=None):
        hdrs = sigv4_headers(method, url, headers or {}, body, self.ak, self.sk)
        hdrs.pop("host", None)
        req = urllib.request.Request(url, data=body if method == "PUT" else None,
                                     method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            data = exc.read() if hasattr(exc, "read") else b""
            code = str(exc.code)
            try:
                node = ElementTree.fromstring(data).find("Code")
                if node is not None and node.text:
                    code = node.text
            except ElementTree.ParseError:
                pass
            if exc.code == 404 and code == "404":
                code = "NoSuchKey"
            if exc.code == 412:
                code = "PreconditionFailed"
            raise _HTTPError(exc.code, code, data) from None

    def head_object(self, Bucket, Key):
        _, headers, _ = self._request("HEAD", self._url(Bucket, Key))
        low = {k.lower(): v for k, v in headers.items()}
        return {"ContentLength": int(low.get("content-length", 0)),
                "ETag": low.get("etag", "")}

    def get_object(self, Bucket, Key):
        import io
        _, headers, data = self._request("GET", self._url(Bucket, Key))
        low = {k.lower(): v for k, v in headers.items()}
        return {"Body": io.BytesIO(data), "ETag": low.get("etag", ""),
                "ContentLength": len(data)}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None,
                   Metadata=None, ContentType=None):
        headers = {}
        if IfMatch:
            headers["if-match"] = IfMatch
        if IfNoneMatch:
            headers["if-none-match"] = IfNoneMatch
        for k, v in (Metadata or {}).items():
            headers[f"x-amz-meta-{k}"] = v
        if ContentType:
            headers["content-type"] = ContentType
        _, rh, _ = self._request("PUT", self._url(Bucket, Key), bytes(Body), headers)
        low = {k.lower(): v for k, v in rh.items()}
        return {"ETag": low.get("etag", "")}

    def get_paginator(self, operation):
        if operation != "list_objects_v2":
            raise ValueError(operation)
        client = self

        class _Pages:
            def paginate(self, Bucket, Prefix=""):
                token = None
                while True:
                    q = {"list-type": "2", "prefix": Prefix}
                    if token:
                        q["continuation-token"] = token
                    _, _, data = client._request("GET", client._url(Bucket, query=q))
                    root = ElementTree.fromstring(data)
                    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
                    contents = [{"Key": c.findtext(f"{ns}Key"),
                                 "Size": int(c.findtext(f"{ns}Size") or 0)}
                                for c in root.findall(f"{ns}Contents")]
                    yield {"Contents": contents}
                    if root.findtext(f"{ns}IsTruncated") != "true":
                        return
                    token = root.findtext(f"{ns}NextContinuationToken")

        return _Pages()


# ── façade R2 ────────────────────────────────────────────────────────────────

class R2:
    """get / put / list / exists sur un bucket, avec compteur d'opérations."""

    def __init__(self, client, bucket=None, retries=3):
        self.client = client
        self.bucket = bucket or os.environ.get("R2_BUCKET") or DEFAULT_BUCKET
        self.retries = retries

    def _retry(self, fn):
        for attempt in range(self.retries):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                code = _error_code(exc)
                transient = code in {"InternalError", "ServiceUnavailable", "SlowDown",
                                     "RequestTimeout", "500", "502", "503", "504"} \
                    or isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))
                if not transient or attempt + 1 >= self.retries:
                    raise
                time.sleep(0.5 * (2 ** attempt))

    def get_with_etag(self, key):
        """(octets, etag) ou None si l'objet n'existe pas."""
        def op():
            OPS["B"] += 1
            try:
                resp = self.client.get_object(Bucket=self.bucket, Key=key)
            except Exception as exc:  # noqa: BLE001
                if _error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
                    return None
                raise
            data = resp["Body"].read()
            OPS["bytes_in"] += len(data)
            etag = (resp.get("ETag") or "").strip('"') or hashlib.md5(data).hexdigest()
            return data, etag
        return self._retry(op)

    def get(self, key):
        got = self.get_with_etag(key)
        return None if got is None else got[0]

    def exists(self, key) -> bool:
        def op():
            OPS["B"] += 1
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception as exc:  # noqa: BLE001
                if _error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
                    return False
                raise
        return self._retry(op)

    def list(self, prefix):
        """[(clé, taille)] — une opération classe A par page de 1 000."""
        out = []
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix)
        for page in pages:
            OPS["A"] += 1
            out.extend((o["Key"], o.get("Size", 0)) for o in page.get("Contents", []) or [])
        return out

    def put(self, key, data: bytes, create_only=False, if_match=None,
            content_type="application/octet-stream", metadata=None):
        """Écrit `data`. Contrôle d'intégrité : l'ETag renvoyé par R2 (MD5
        d'un envoi en une partie) doit égaler le MD5 local, sinon erreur.
        create_only=True : refuse d'écraser (If-None-Match: *).
        if_match=<etag> : n'écrit que si l'objet n'a pas changé depuis.
        Lève PreconditionFailed si la condition n'est pas remplie."""
        data = bytes(data)
        meta = {"sha256": _sha256_hex(data)}
        meta.update(metadata or {})
        kwargs = {"Bucket": self.bucket, "Key": key, "Body": data,
                  "Metadata": meta, "ContentType": content_type}
        if create_only:
            kwargs["IfNoneMatch"] = "*"
        if if_match:
            kwargs["IfMatch"] = if_match

        def op():
            OPS["A"] += 1
            try:
                resp = self.client.put_object(**kwargs)
            except Exception as exc:  # noqa: BLE001
                if _error_code(exc) in {"PreconditionFailed", "412",
                                        "ConditionalRequestConflict", "409"}:
                    raise PreconditionFailed(key) from exc
                raise
            OPS["bytes_out"] += len(data)
            etag = ((resp or {}).get("ETag") or "").strip('"')
            md5 = hashlib.md5(data).hexdigest()
            if etag and "-" not in etag and etag != md5:
                raise IOError(f"R2 : ETag {etag} ≠ MD5 local {md5} pour {key}")
            return etag or md5
        return self._retry(op)


_CLIENT_CACHE = {}


def client(environ=None, quiet=False):
    """R2 prêt à l'emploi, ou None (secrets absents / client impossible)."""
    environ = os.environ if environ is None else environ
    if "client" in _CLIENT_CACHE and environ is os.environ:
        return _CLIENT_CACHE["client"]
    required = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT")
    missing = [n for n in required if not environ.get(n)]
    result = None
    if missing:
        if not quiet:
            warn_once("creds", "R2 indisponible : secrets absents ("
                      + ", ".join(missing) + ") — lecture depuis les copies git.")
    else:
        raw = None
        try:
            import boto3  # noqa: F401
            from botocore.config import Config
            raw = boto3.client(
                "s3", endpoint_url=environ["R2_ENDPOINT"].rstrip("/"),
                aws_access_key_id=environ["R2_ACCESS_KEY_ID"],
                aws_secret_access_key=environ["R2_SECRET_ACCESS_KEY"],
                region_name="auto",
                config=Config(request_checksum_calculation="when_required",
                              response_checksum_validation="when_required",
                              connect_timeout=10, read_timeout=60,
                              retries={"max_attempts": 3, "mode": "standard"}))
        except ImportError:
            raw = MiniS3(environ["R2_ENDPOINT"], environ["R2_ACCESS_KEY_ID"],
                         environ["R2_SECRET_ACCESS_KEY"])
        except Exception as exc:  # noqa: BLE001
            warn_once("client", f"R2 indisponible : client impossible ({type(exc).__name__})")
        if raw is not None:
            result = R2(raw, environ.get("R2_BUCKET") or DEFAULT_BUCKET)
    if environ is os.environ:
        _CLIENT_CACHE["client"] = result
    return result


def reset_cache():
    """Pour les tests."""
    _CLIENT_CACHE.clear()
    _MANIFEST_CACHE.clear()
    _WARNED.clear()
    for k in OPS:
        OPS[k] = 0


# ── gzip concaténé : lignes, frontières de membres, fusion ───────────────────

def gz_lines(data: bytes) -> int:
    """Nombre de lignes non vides d'un gzip multi-membres (lecture COMPLÈTE :
    un décompresseur qui s'arrête au 1er membre en lirait 2 %). Lève une
    exception si les octets ne forment pas un gzip valide."""
    if not data:
        return 0
    text = gzip.decompress(data)
    return sum(1 for line in text.split(b"\n") if line.strip())


def gz_boundaries(data: bytes) -> list[int]:
    """Positions (octets) où se termine chaque membre gzip : [0, b1, b2, …]."""
    out, pos = [0], 0
    while pos < len(data):
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        d.decompress(data[pos:])
        if not d.eof:
            raise DivergentData("membre gzip tronqué")
        pos = len(data) - len(d.unused_data)
        out.append(pos)
        if not d.unused_data:
            break
    return out


def merge_gz(remote: bytes, local: bytes, base_size: int | None = None) -> bytes:
    """Version qui contient remote ET les ajouts de local.

    Les partitions ne font que grandir par ajout de membres gzip. Trois cas :
    remote prolonge local -> remote ; local prolonge remote -> local ; sinon
    les deux ont ajouté chacun des membres après un ancêtre commun : on garde
    remote et on lui ajoute les membres de local postérieurs à l'ancêtre.
    L'ancêtre est coupé sur une FRONTIÈRE DE MEMBRE (gz_append écrit des
    en-têtes identiques, mtime=0 : un préfixe commun octet par octet peut
    déborder dans un membre). Résultat vérifié (gzip lisible, comptes de
    lignes cohérents) ; sinon DivergentData."""
    if remote.startswith(local):
        return remote
    if local.startswith(remote):
        return local
    if base_size is not None and local[:base_size] == remote[:base_size]:
        cut = base_size
    else:
        common = os.path.commonprefix([remote, local])
        bounds = [b for b in gz_boundaries(local) if b <= len(common)]
        cut = bounds[-1] if bounds else 0
    if cut not in gz_boundaries(local):
        raise DivergentData("ancêtre commun hors frontière de membre")
    merged = remote + local[cut:]
    try:
        n = gz_lines(merged)
        expected = gz_lines(remote) + gz_lines(local) - gz_lines(local[:cut])
    except Exception as exc:  # noqa: BLE001
        raise DivergentData(f"fusion illisible ({type(exc).__name__})") from exc
    if n != expected:
        raise DivergentData(f"fusion incohérente ({n} lignes, attendu {expected})")
    return merged


# ── manifestes ───────────────────────────────────────────────────────────────

_MANIFEST_CACHE = {}


def empty_manifest(fam):
    return {"schema": 1, "family": fam, "updated_at": None, "files": {}}


def load_manifest(r2, fam, use_cache=True):
    """(manifeste, etag | None). Un manifeste illisible est traité comme
    vide, bruyamment : mieux vaut un rapatriement de moins qu'un crash."""
    if use_cache and fam in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[fam]
    got = r2.get_with_etag(FAMILIES[fam]["manifest"])
    if got is None:
        result = (empty_manifest(fam), None)
    else:
        try:
            man = json.loads(got[0].decode("utf-8"))
            man.setdefault("files", {})
            result = (man, got[1])
        except ValueError:
            log(f"manifeste {fam} illisible — traité comme vide")
            result = (empty_manifest(fam), got[1])
    _MANIFEST_CACHE[fam] = result
    return result


def save_manifest(r2, fam, updates: dict, etag=None, attempts=5):
    """Fusionne `updates` {nom: entrée} dans le manifeste distant, en écriture
    conditionnelle (If-Match / If-None-Match). Sur conflit : relit, refusionne.
    Une écriture classe A par tentative."""
    key = FAMILIES[fam]["manifest"]
    man, cur = load_manifest(r2, fam, use_cache=etag is not None)
    if etag is not None:
        cur = etag
    for attempt in range(attempts):
        merged = dict(man)
        files = dict(merged.get("files") or {})
        files.update(updates)
        merged["files"] = dict(sorted(files.items()))
        merged["updated_at"] = now_iso()
        merged.setdefault("schema", 1)
        merged["family"] = fam
        body = json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
        try:
            new_etag = r2.put(key, body, create_only=cur is None, if_match=cur,
                              content_type="application/json")
            _MANIFEST_CACHE[fam] = (merged, new_etag)
            return merged
        except PreconditionFailed:
            _MANIFEST_CACHE.pop(fam, None)
            man, cur = load_manifest(r2, fam, use_cache=False)
    raise RuntimeError(f"manifeste {fam} : conflits répétés, abandon")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def entry_for(fam, name, data: bytes, etag: str, lines: int):
    return {"key": FAMILIES[fam]["prefix"] + name, "size": len(data),
            "sha256": _sha256_hex(data), "lines": lines, "etag": etag,
            "updated_at": now_iso()}


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── matérialisation (lecteurs) ───────────────────────────────────────────────

def _git_pristine(paths) -> set:
    """Chemins SUIVIS par git et NON modifiés localement (copie du checkout)."""
    if not paths:
        return set()
    try:
        tracked = subprocess.run(["git", "ls-files", "--", *paths], capture_output=True,
                                 text=True, timeout=30)
        modified = subprocess.run(["git", "diff", "--name-only", "--", *paths],
                                  capture_output=True, text=True, timeout=30)
        if tracked.returncode or modified.returncode:
            return set()
    except (OSError, subprocess.SubprocessError):
        return set()
    t = {os.path.normpath(p) for p in tracked.stdout.split()}
    m = {os.path.normpath(p) for p in modified.stdout.split()}
    return t - m


def _write_atomic(path, data: bytes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.r2tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _in_window(name, days, today=None):
    if days is None or days <= 0:
        return True
    d = day_of(name)
    if not d:
        return False
    today = today or dt.datetime.now(dt.timezone.utc).date()
    try:
        return dt.date.fromisoformat(d) >= today - dt.timedelta(days=days)
    except ValueError:
        return False


def sync_from_r2(fams, parts_dir=PARTS_DIR, days=None, only_missing=False,
                 match=None, r2=None, environ=None, today=None) -> dict:
    """Rapatrie depuis R2 les partitions des familles `fams` dans parts/.

    - partition absente localement            -> téléchargée ;
    - copie git intacte mais plus ancienne    -> remplacée si R2 la prolonge
      (sauf only_missing=True) ;
    - fichier modifié localement (écrivain en cours de run) -> JAMAIS touché.
    Renvoie {nom: 'telecharge'|'rafraichi'|'a_jour'|'local_plus_recent'|'erreur'}.
    """
    r2 = r2 if r2 is not None else client(environ)
    if r2 is None:
        return {}
    report = {}
    for fam in fams:
        man, _ = load_manifest(r2, fam)
        win = days if days is not None else int(
            os.environ.get(FAMILIES[fam]["window_env"], FAMILIES[fam]["window_default"]))
        names = [n for n in man["files"]
                 if FAMILIES[fam]["regex"].match(n) and _in_window(n, win, today)
                 and (match is None or match(n))]
        paths = {n: os.path.join(parts_dir, n) for n in names}
        present = [p for p in paths.values() if os.path.exists(p)]
        pristine = _git_pristine(present) if (present and not only_missing) else set()
        for name, path in sorted(paths.items()):
            ent = man["files"][name]
            try:
                if not os.path.exists(path):
                    got = r2.get_with_etag(ent["key"])
                    if got is None:
                        report[name] = "erreur"
                        continue
                    # Le contenu peut être plus récent que le manifeste (un
                    # écrivain entre son PUT et son manifeste) : on l'accepte
                    # s'il est un gzip lisible, jamais un fichier corrompu.
                    gz_lines(got[0])
                    _write_atomic(path, got[0])
                    report[name] = "telecharge"
                    continue
                if only_missing:
                    report[name] = "present"
                    continue
                if os.path.normpath(path) not in pristine:
                    # Modifié pendant ce run (ou hors git) : on n'y touche pas.
                    report[name] = "local_modifie"
                    continue
                if file_sha256(path) == ent.get("sha256"):
                    report[name] = "a_jour"
                    continue
                got = r2.get_with_etag(ent["key"])
                if got is None:
                    report[name] = "erreur"
                    continue
                with open(path, "rb") as f:
                    local = f.read()
                if got[0].startswith(local):
                    _write_atomic(path, got[0])
                    report[name] = "rafraichi"
                elif local.startswith(got[0]):
                    report[name] = "local_plus_recent"
                else:
                    _write_atomic(path, merge_gz(got[0], local))
                    report[name] = "rafraichi"
            except Exception as exc:  # noqa: BLE001
                log(f"{name} : rapatriement impossible ({type(exc).__name__}: {exc})")
                report[name] = "erreur"
    return report


def materialize_glob(pattern: str, environ=None) -> dict:
    """Appelé par les lecteurs centraux (load_partitions, curves_parts) :
    en mode 'on' uniquement, rapatrie les partitions R2 correspondant au motif
    (ex. 'parts/pm_ticks_*.jsonl', 'parts/live_match_*.jsonl.gz').
    No-op en 'off'/'double' (git fait foi) ou sans secrets."""
    if mode(environ) != "on":
        return {}
    base = os.path.basename(pattern)
    # 'pm_ticks_*.jsonl' doit aussi couvrir les .jsonl.gz (convention de
    # load_partitions : motif SANS .gz, résolution faite à la lecture).
    pats = {base, base + ".gz"}

    def match(name):
        return any(fnmatch.fnmatch(name, p) for p in pats)

    head = base.split("*")[0]
    fams = []
    for fam, spec in FAMILIES.items():
        fam_head = os.path.basename(spec["glob"]).split("*")[0]
        if head.startswith(fam_head) or fam_head.startswith(head):
            fams.append(fam)
    if not fams:
        return {}
    parts_dir = os.path.dirname(pattern) or PARTS_DIR
    try:
        return sync_from_r2(fams, parts_dir=parts_dir, match=match, environ=environ)
    except Exception as exc:  # noqa: BLE001
        log(f"matérialisation {pattern} impossible ({type(exc).__name__}) — copies git")
        return {}


def materialize(path: str, environ=None) -> bool:
    """Une partition précise : True si elle existe localement au retour."""
    if os.path.exists(path):
        return True
    if mode(environ) != "on" or not family_of(path):
        return False
    name = os.path.basename(path)
    sync_from_r2([family_of(path)], parts_dir=os.path.dirname(path) or PARTS_DIR,
                 days=0, match=lambda n: n == name, environ=environ)
    return os.path.exists(path)


def get_object_to(key: str, path: str, environ=None) -> bool:
    """Télécharge un objet arbitraire (ex. parts/hist_* déposés par
    courbes_r2) vers `path`. False si R2 indisponible ou objet absent."""
    r2 = client(environ)
    if r2 is None:
        return False
    try:
        data = r2.get(key)
    except Exception as exc:  # noqa: BLE001
        log(f"{key} : lecture impossible ({type(exc).__name__})")
        return False
    if data is None:
        return False
    _write_atomic(path, data)
    return True


if __name__ == "__main__":
    print("Utiliser scripts/r2_parts.py (pull | push | gate | verify | status).",
          file=sys.stderr)
    sys.exit(2)
