#!/usr/bin/env python3
"""READ-ONLY: full R2 inventory (list only; no get/put/delete)."""
import hashlib, json, sys
sys.path.insert(0, "scripts")
import r2_partition_worker as w

c = w.create_worker_client()
out, tok = [], None
while True:
    kw = {"Bucket": w.BUCKET}
    if tok:
        kw["ContinuationToken"] = tok
    p = c.list_objects_v2(**kw)
    out += [{"k": o["Key"], "etag": o["ETag"], "size": o["Size"], "lm": o["LastModified"].isoformat()}
            for o in p.get("Contents", [])]
    if not p.get("IsTruncated"):
        break
    tok = p["NextContinuationToken"]
out.sort(key=lambda o: o["k"])
Path = __import__("pathlib").Path
Path("inventory.json").write_text(json.dumps(out))
arch = [o for o in out if o["k"].startswith("parts/v64-archive/")]
print("INVENTORY total", len(out), "| parts/v64-archive/ objects:", len(arch))
print("INVENTORY digest", hashlib.sha256(json.dumps([(o["k"], o["etag"], o["size"], o["lm"]) for o in out]).encode()).hexdigest())
for o in arch[:10]:
    print("ARCHIVE", o)
