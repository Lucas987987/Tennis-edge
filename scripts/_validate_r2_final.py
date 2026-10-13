#!/usr/bin/env python3
"""READ-ONLY diagnostic: no put/delete. Classifies R2 objects under parts/."""
import hashlib, json, re, subprocess, sys, datetime as dt
sys.path.insert(0, "scripts")
import r2_partition_worker as w

c = w.create_worker_client()
objs = []
tok = None
while True:
    kw = {"Bucket": w.BUCKET, "Prefix": "parts/"}
    if tok:
        kw["ContinuationToken"] = tok
    p = c.list_objects_v2(**kw)
    objs += p.get("Contents", [])
    if not p.get("IsTruncated"):
        break
    tok = p["NextContinuationToken"]
print("bucket", w.BUCKET, "total objects under parts/:", len(objs))

def cls(k):
    if k.startswith("parts/v64-archive-test/final-"): return "test-final(mine)"
    if k.startswith("parts/v64-archive-test/"): return "test-other(mine)"
    if k.startswith("parts/v64-archive/"): return "PROD-v64-archive"
    if k.startswith("parts/v64/"): return "v64-shadow/other"
    if k == "parts/_manifest.json": return "courbes-manifest"
    if re.match(r"parts/(live|hist)_", k): return "courbes-partition"
    return "other"
cnt = {}
for o in objs:
    cnt[cls(o["Key"])] = cnt.get(cls(o["Key"]), 0) + 1
print("classes", cnt)

win_start = dt.datetime(2026, 10, 13, 17, 33, 0, tzinfo=dt.timezone.utc)
win_end = dt.datetime(2026, 10, 13, 17, 41, 46, tzinfo=dt.timezone.utc)
print("\n== objects NOT mine modified >= 2026-10-13T17:00Z ==")
for o in sorted(objs, key=lambda o: o["LastModified"]):
    k = o["Key"]
    if cls(k).startswith("test-"):
        continue
    if o["LastModified"] >= dt.datetime(2026, 10, 13, 17, 0, tzinfo=dt.timezone.utc):
        body = c.get_object(Bucket=w.BUCKET, Key=k)
        data = body["Body"].read()
        meta = body.get("Metadata", {})
        inwin = win_start <= o["LastModified"] <= win_end
        # compare with Git main
        gitmatch = "n/a"
        if cls(k) == "courbes-partition":
            r = subprocess.run(["git", "cat-file", "blob", f"FETCH_HEAD:{k}"], capture_output=True)
            gitmatch = ("identical-to-main" if r.returncode == 0 and r.stdout == data
                        else ("differs-from-main(size %d vs %d)" % (len(data), len(r.stdout)) if r.returncode == 0 else "not-in-main"))
        print(f"{k} | {cls(k)} | LastModified={o['LastModified'].isoformat()} | in_run1_window={inwin} | size={len(data)} | etag={o['ETag']} | sha256={hashlib.sha256(data).hexdigest()} | meta={meta} | git={gitmatch}")

print("\n== test objects (mine) outside final-38439592968/38440773125 : immutability ==")
bad = 0
for o in objs:
    k = o["Key"]
    if cls(k) == "test-other(mine)" or (cls(k) == "test-final(mine)" and k.endswith("manifest.json")):
        pass
    if cls(k).startswith("test-") and k.endswith("data.jsonl.gz"):
        d = c.get_object(Bucket=w.BUCKET, Key=k)["Body"].read()
        m = json.loads(c.get_object(Bucket=w.BUCKET, Key=k.rsplit("/",1)[0] + "/manifest.json")["Body"].read())
        if hashlib.sha256(d).hexdigest() != m["data_sha256"]:
            bad += 1; print("MISMATCH", k)
print("test archive data objects verified against manifests; mismatches =", bad)
print("\n== PROD v64-archive (parts/v64-archive/) objects ==", [o["Key"] for o in objs if cls(o["Key"]) == "PROD-v64-archive"][:5])
print("\n== versioning ==")
try:
    v = c.list_object_versions(Bucket=w.BUCKET, Prefix="parts/_manifest.json")
    print("versions:", [(x["VersionId"], x["LastModified"].isoformat()) for x in v.get("Versions", [])])
except Exception as e:
    print("list_object_versions unsupported:", type(e).__name__, str(e)[:120])
