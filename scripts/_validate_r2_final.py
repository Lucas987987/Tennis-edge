#!/usr/bin/env python3
"""Temporary real-R2 validation. Writes ONLY under parts/v64-archive-test/final-<run>/."""
import concurrent.futures as cf
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import datetime as dt
from pathlib import Path

sys.path.insert(0, "scripts")
import r2_partition_worker as w  # noqa: E402
from partitioned_store import stable_tick_record  # noqa: E402

RUN = os.environ.get("GITHUB_RUN_ID", "local")
BASE = f"parts/v64-archive-test/final-{RUN}"
REF = "FETCH_HEAD"
RESULTS: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""), flush=True)


def new_store():
    return w.ArchiveStore(w.create_worker_client())


def list_keys(prefix, exclude=None):
    client = w.create_worker_client()
    out, token = {}, None
    while True:
        kw = {"Bucket": w.BUCKET, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        page = client.list_objects_v2(**kw)
        for obj in page.get("Contents", []):
            if exclude and obj["Key"].startswith(exclude):
                continue
            out[obj["Key"]] = (obj["ETag"], obj["Size"])
        if not page.get("IsTruncated"):
            return out
        token = page["NextContinuationToken"]


def worker(*args):
    cmd = [sys.executable, "scripts/r2_partition_worker.py", "--git-ref", REF, *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def norm(data: bytes, provider: str):
    rows = []
    with gzip.GzipFile(fileobj=__import__("io").BytesIO(data)) as s:
        for raw in s:
            if raw.strip():
                rows.append(stable_tick_record(provider, json.loads(raw))[1])
    return sorted(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)


def git_bytes(blob):
    return w.read_git_blob(Path("."), blob)


def main():
    commit, parts = w.list_published_partitions(Path("."), REF)
    now = dt.datetime.now(dt.timezone.utc)
    frozen = [p for p in parts if w.is_frozen(p["day"], now, 6.0)]
    kx = [p for p in frozen if p["provider"] == "kalshi"]
    pm = [p for p in frozen if p["provider"] == "polymarket"]
    print(f"main commit {commit}; frozen kalshi={len(kx)} polymarket={len(pm)}; base={BASE}")
    print("kalshi days:", [p["day"] for p in kx])
    check("setup: frozen kalshi partitions exist", len(kx) >= 2)

    before = list_keys("parts/", exclude=BASE + "/")
    print(f"historical objects before: {len(before)}")

    # 1+3. Real Kalshi partitions: sync into isolated root, restore, compare.
    root_a = BASE + "/a-kalshi"
    r = worker("--mode", "sync", "--root", root_a, "--provider", "kalshi",
               "--max-seconds", "900", "--report-file", "rep_a.json")
    check("kalshi sync exit 0", r.returncode == 0, r.stderr[-300:])
    rep = json.loads(Path("rep_a.json").read_text())
    print("kalshi sync summary", rep["summary"], "created", rep.get("r2_objects_created"),
          "retries", rep.get("r2_retries"))
    check("kalshi sync: no error/conflict, no deletions/overwrites",
          rep["success"] and rep["deletions_performed"] == 0 and rep["overwrites_performed"] == 0)
    store = new_store()
    tmp = Path(tempfile.mkdtemp())
    for i, p in enumerate(kx):
        dest = tmp / f"k{i}"
        r = worker("--mode", "restore", "--root", root_a, "--provider", "kalshi",
                   "--day", p["day"], "--destination", str(dest))
        short = dest / f"kx_ticks_{p['day']}.jsonl.gz"
        if r.returncode != 0:
            check(f"restore kalshi {p['day']}", False, r.stderr[-300:] + r.stdout[-300:])
            continue
        got, want = short.read_bytes(), git_bytes(p["blob"])
        sha_ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(want).hexdigest()
        n_got, n_want = norm(got, "kalshi"), norm(want, "kalshi")
        check(f"restore kalshi {p['day']} sha256+normalized",
              sha_ok and n_got == n_want,
              f"sha256={hashlib.sha256(got).hexdigest()[:16]} bytes={len(got)} records={len(n_got)}")
        if i == 0:
            r2 = worker("--mode", "restore", "--root", root_a, "--provider", "kalshi",
                        "--day", p["day"], "--destination", str(dest))
            check("restore refuses overwrite", r2.returncode != 0 and short.read_bytes() == got)
    # polymarket sample (latest frozen) for completeness
    if pm:
        p = pm[-1]
        root_p = BASE + "/a-poly"
        r = worker("--mode", "sync", "--root", root_p, "--provider", "polymarket",
                   "--max-partitions", "1", "--report-file", "rep_p.json")
        check("polymarket sync (oldest 1) exit 0", r.returncode == 0, r.stderr[-300:])
        item = json.loads(Path("rep_p.json").read_text())["partitions"][0]
        d = tmp / "pm"
        r = worker("--mode", "restore", "--root", root_p, "--provider", "polymarket",
                   "--day", item["key"].split("/")[1], "--blob", item["blob"],
                   "--destination", str(d))
        f = next(d.glob("*.jsonl.gz"))
        check("restore polymarket sha256+normalized",
              r.returncode == 0 and f.read_bytes() == git_bytes(item["blob"])
              and norm(f.read_bytes(), "polymarket") == norm(git_bytes(item["blob"]), "polymarket"))
    # verify mode, read-only, on kalshi root
    r = worker("--mode", "verify", "--root", root_a, "--provider", "kalshi")
    vr = json.loads(r.stdout)
    st = {}
    for row in vr["partitions"]:
        st[row["status"]] = st.get(row["status"], 0) + 1
    print("verify statuses", st)
    check("verify: all synced partitions verified, none mismatch/error",
          r.returncode == 0 and st.get("verified", 0) == len(kx) and not st.get("mismatch")
          and not st.get("error"))
    # unfrozen day must remain absent
    check("no unfrozen partition archived",
          all(row["status"] in {"verified", "absent"} for row in vr["partitions"]))

    # 2. Concurrent raw writes
    key_same = BASE + "/raw/same.bin"
    body = os.urandom(4096)

    def put_same(_):
        return new_store().put_if_absent(key_same, body, "application/octet-stream")
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(put_same, range(8)))
    check("raw concurrent identical writes: exactly 1 created, others idempotent",
          res.count(True) == 1 and res.count(False) == 7, str(res))
    key_diff = BASE + "/raw/diff.bin"
    bodies = [os.urandom(2048) for _ in range(8)]

    def put_diff(b):
        try:
            return "created" if new_store().put_if_absent(key_diff, b, "application/octet-stream") else "same"
        except w.ConflictError:
            return "conflict"
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(put_diff, bodies))
    final = new_store().get(key_diff)
    check("raw concurrent differing writes: 1 winner, 7 conflicts, no overwrite",
          res.count("created") == 1 and res.count("conflict") == 7 and final in bodies, str(res))

    # 4. Several partitions at once: parallel workers, same root, both providers
    root_b = BASE + "/b-parallel"
    with cf.ThreadPoolExecutor(4) as ex:
        procs = list(ex.map(lambda i: worker(
            "--mode", "sync", "--root", root_b, "--max-partitions", "6",
            "--max-seconds", "900", "--report-file", f"rep_b{i}.json"), range(4)))
    check("4 parallel workers same root: all exit 0", all(p.returncode == 0 for p in procs),
          str([p.returncode for p in procs]))
    reps = [json.loads(Path(f"rep_b{i}.json").read_text()) for i in range(4)]
    print("parallel summaries", [r_["summary"] for r_ in reps],
          "created", [r_.get("r2_objects_created") for r_ in reps])
    check("parallel: no conflict/error, no deletions/overwrites",
          all(r_["success"] and r_["deletions_performed"] == 0 and r_["overwrites_performed"] == 0
              for r_ in reps))
    keys_b = list_keys(root_b + "/")
    synced = {p["key"] for p in reps[0]["partitions"] if p.get("status") in {"archived", "created", "verified"}}
    by_prefix = {}
    for k in keys_b:
        by_prefix.setdefault(k.rsplit("/", 1)[0], []).append(k.rsplit("/", 1)[1])
    check("parallel: every partition prefix has exactly data+manifest",
          all(sorted(v) == ["data.jsonl.gz", "manifest.json"] for v in by_prefix.values())
          and len(by_prefix) == 6, f"prefixes={len(by_prefix)}")
    total_created = sum(r_.get("r2_objects_created") or 0 for r_ in reps)
    check("parallel: total objects created == objects present (no duplicates)",
          total_created == len(keys_b), f"created={total_created} present={len(keys_b)}")
    r = worker("--mode", "verify", "--root", root_b)
    vr = json.loads(r.stdout)
    ok_rows = [x for x in vr["partitions"] if x["status"] == "verified"]
    check("parallel: verify clean", r.returncode == 0 and len(ok_rows) == 6
          and not [x for x in vr["partitions"] if x["status"] in {"mismatch", "error"}])
    # disjoint providers simultaneously
    root_c = BASE + "/c-providers"
    with cf.ThreadPoolExecutor(2) as ex:
        pr = list(ex.map(lambda prov: worker(
            "--mode", "sync", "--root", root_c, "--provider", prov, "--max-partitions", "3"),
            ["kalshi", "polymarket"]))
    check("2 simultaneous provider workers exit 0", all(p.returncode == 0 for p in pr))
    r = worker("--mode", "verify", "--root", root_c)
    vr = json.loads(r.stdout)
    check("provider workers verify clean", r.returncode == 0 and
          sum(x["status"] == "verified" for x in vr["partitions"]) == 6)

    # Historical objects untouched
    after = list_keys("parts/", exclude=BASE + "/")
    for k in sorted(set(before) | set(after)):
        if before.get(k) != after.get(k):
            print("DIFF", k, before.get(k), "->", after.get(k))
    check("historical R2 objects unchanged (keys, etags, sizes)", before == after,
          f"before={len(before)} after={len(after)}")
    written = list_keys(BASE + "/")
    check("all writes confined to test prefix", all(k.startswith(BASE + "/") for k in written),
          f"{len(written)} objects under {BASE}/")

    bad = [r_ for r_ in RESULTS if not r_[1]]
    print(f"\nRESULT {len(RESULTS) - len(bad)}/{len(RESULTS)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
