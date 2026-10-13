#!/usr/bin/env python3
"""POST-WRITE CHECK (read-only: list/get only). Not executed yet.

Usage (needs R2_* env, run from a checkout of main):
  python post_write_check.py inventory_before.json
"""
import gzip, hashlib, io, json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, "scripts")
import r2_partition_worker as w
from partitioned_store import stable_tick_record

BLOB = "e49ed8b622b03d89ffc8a26914520a7a0849445c"
PREFIX = f"parts/v64-archive/polymarket/2026-10-06/{BLOB}/"
EXPECT = {
    "data_sha256": "0b593c46dde9fb72c5df8d5c5c98ecafd439d3501b540e6b7f2d19f71fdc4a13",
    "data_size_bytes": 6269828,
    "stats": {"lines": 371924, "malformed_lines": 0, "unique_ticks": 371906,
              "duplicate_lines": 18, "ts_min": "2026-10-06T00:00:03.767Z",
              "ts_max": "2026-10-06T23:44:08.177Z", "ts_outside_day_lines": 0,
              "tick_ids_sha256": "24786edc7b71963be7042eccb6234c627842d1e2b0c8b80452d7a07dc10bcaf2"},
    "manifest_sha256": "ea09be38d88847d5d48d6843da6e9dfeb9ba73193fc2e4ac45238a64f4ed208c",
}
res = []
def check(n, ok, d=""):
    res.append(ok); print(("PASS " if ok else "FAIL "), n, d, flush=True)

c = w.create_worker_client()
objs, tok = [], None
while True:
    kw = {"Bucket": w.BUCKET}
    if tok: kw["ContinuationToken"] = tok
    p = c.list_objects_v2(**kw); objs += p.get("Contents", [])
    if not p.get("IsTruncated"): break
    tok = p["NextContinuationToken"]
after = {o["Key"]: (o["ETag"], o["Size"], o["LastModified"].isoformat()) for o in objs}
json.dump([{"k":k,"etag":v[0],"size":v[1],"lm":v[2]} for k,v in after.items()], open("inventory.json","w"))
before = {o["k"]: (o["etag"], o["size"], o["lm"]) for o in json.load(open(sys.argv[1]))}
new = sorted(set(after) - set(before))
check("exactly 2 new objects, both under the target prefix",
      new == [PREFIX + "data.jsonl.gz", PREFIX + "manifest.json"], str(new))
check("no object deleted", not (set(before) - set(after)))
check("no pre-existing object modified",
      all(after[k] == before[k] for k in before if k in after))
check("nothing else under parts/v64-archive/",
      sorted(k for k in after if k.startswith("parts/v64-archive/")) == new)

store = w.ArchiveStore(c)
data = store.get(PREFIX + "data.jsonl.gz")
manifest = w.validate_manifest_bytes(store.get(PREFIX + "manifest.json"))
git = w.read_git_blob(Path("."), BLOB)
check("R2 data bytes == Git blob bytes", data == git)
check("SHA-256 equals expected", hashlib.sha256(data).hexdigest() == EXPECT["data_sha256"])
check("size equals expected", len(data) == EXPECT["data_size_bytes"])
check("git blob id of R2 data", w.git_blob_sha(data) == BLOB)
check("manifest self-checksum + expected value", manifest["manifest_sha256"] == EXPECT["manifest_sha256"])
st = w.analyze("polymarket", "2026-10-06", data)
for k, v in EXPECT["stats"].items():
    check(f"stats.{k}", st[k] == v, str(st[k]))
check("manifest stats == recomputed from R2", manifest["stats"] == st)

def norm(b):
    rows = [stable_tick_record("polymarket", json.loads(l))[1]
            for l in gzip.GzipFile(fileobj=io.BytesIO(b)) if l.strip()]
    return sorted(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)
check("normalized records identical (Git vs R2)", norm(data) == norm(git))

dest = Path(tempfile.mkdtemp()) / "restore"
r = subprocess.run([sys.executable, "scripts/r2_partition_worker.py", "--mode", "restore",
                    "--git-ref", "FETCH_HEAD", "--root", "parts/v64-archive",
                    "--provider", "polymarket", "--day", "2026-10-06", "--blob", BLOB,
                    "--destination", str(dest)], capture_output=True, text=True)
f = dest / "pm_ticks_2026-10-06.jsonl.gz"
check("restore into temp dir succeeds, byte-identical",
      r.returncode == 0 and f.read_bytes() == git, r.stderr[-200:])
print(f"RESULT {sum(res)}/{len(res)}")
sys.exit(0 if all(res) else 1)
