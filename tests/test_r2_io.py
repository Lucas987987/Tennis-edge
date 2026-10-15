"""Tests de r2_io : SigV4, get/put/list/exists, fusion gzip, matérialisation."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import http.server
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import r2_io  # noqa: E402


def gz(*lines):
    """Un membre gzip comme ceux de gz_append (mtime=0, en-têtes identiques)."""
    return gzip.compress(("".join(l + "\n" for l in lines)).encode(), mtime=0)


TODAY = dt.datetime.now(dt.timezone.utc).date()
D0 = TODAY.isoformat()
D1 = (TODAY - dt.timedelta(days=1)).isoformat()
D_OLD = (TODAY - dt.timedelta(days=30)).isoformat()


class SigV4Tests(unittest.TestCase):
    def test_official_aws_get_object_example(self):
        # Exemple « GET Object » de la documentation AWS SigV4 (S3).
        hdrs = r2_io.sigv4_headers(
            "GET", "https://examplebucket.s3.amazonaws.com/test.txt",
            {"Range": "bytes=0-9"}, b"",
            "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="us-east-1", now=dt.datetime(2013, 5, 24, tzinfo=dt.timezone.utc))
        self.assertIn("SignedHeaders=host;range;x-amz-content-sha256;x-amz-date",
                      hdrs["authorization"])
        self.assertTrue(hdrs["authorization"].endswith(
            "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"))


class FacadeTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeS3()
        install(self.fake, "double")
        self.r2 = r2_io.client()

    def tearDown(self):
        uninstall()

    def test_get_put_list_exists_and_op_counts(self):
        self.assertIsNone(self.r2.get("a/x"))
        self.assertFalse(self.r2.exists("a/x"))
        etag = self.r2.put("a/x", b"hello")
        self.assertEqual(etag, hashlib.md5(b"hello").hexdigest())
        self.assertEqual(self.r2.get("a/x"), b"hello")
        self.assertTrue(self.r2.exists("a/x"))
        self.assertEqual(self.r2.list("a/"), [("a/x", 5)])
        self.assertEqual(r2_io.OPS["A"], 2)          # 1 PUT + 1 LIST
        self.assertEqual(r2_io.OPS["B"], 4)          # 2 GET + 2 HEAD

    def test_create_only_and_if_match_conflicts(self):
        e1 = self.r2.put("k", b"v1", create_only=True)
        with self.assertRaises(r2_io.PreconditionFailed):
            self.r2.put("k", b"v2", create_only=True)
        e2 = self.r2.put("k", b"v2", if_match=e1)
        with self.assertRaises(r2_io.PreconditionFailed):
            self.r2.put("k", b"v3", if_match=e1)     # etag périmé
        self.assertEqual(self.r2.get("k"), b"v2")
        self.assertNotEqual(e1, e2)

    def test_put_detects_corrupted_upload_by_etag(self):
        self.fake.put_object = lambda **kw: {"ETag": '"00000000000000000000000000000000"'}
        with self.assertRaises(IOError):
            self.r2.put("k", b"data")

    def test_no_credentials_gives_none_and_one_clear_message(self):
        r2_io.reset_cache()
        env = {"R2_PRIMARY": "on"}
        with mock.patch("sys.stdout") as out:
            self.assertIsNone(r2_io.client(env))
            self.assertIsNone(r2_io.client(env))
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertEqual(printed.count("R2 indisponible"), 1)
        self.assertIn("copies git", printed)

    def test_mode_parsing(self):
        self.assertEqual(r2_io.mode({}), "off")
        self.assertEqual(r2_io.mode({"R2_PRIMARY": "ON "}), "on")
        self.assertEqual(r2_io.mode({"R2_PRIMARY": "n'importe"}), "off")


class GzipMergeTests(unittest.TestCase):
    def test_prefix_cases(self):
        base = gz("a", "b")
        self.assertEqual(r2_io.merge_gz(base + gz("c"), base), base + gz("c"))
        self.assertEqual(r2_io.merge_gz(base, base + gz("c")), base + gz("c"))

    def test_divergent_appends_are_grafted_on_member_boundary(self):
        # Deux runs ont ajouté chacun un membre après le même ancêtre ; les
        # en-têtes gzip identiques (mtime=0) font déborder le préfixe commun.
        base = gz("t1", "t2")
        remote = base + gz("r1", "r2")
        local = base + gz("l1")
        merged = r2_io.merge_gz(remote, local)
        text = gzip.decompress(merged).decode().split()
        self.assertEqual(text, ["t1", "t2", "r1", "r2", "l1"])
        self.assertEqual(r2_io.merge_gz(remote, local, base_size=len(base)), merged)

    def test_gz_lines_reads_all_members(self):
        data = b"".join(gz(f"l{i}") for i in range(50))
        self.assertEqual(r2_io.gz_lines(data), 50)
        self.assertEqual(r2_io.gz_boundaries(data)[-1], len(data))


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("parts")
        self.fake = FakeS3()

    def tearDown(self):
        os.chdir(self.cwd)
        uninstall()
        self.tmp.cleanup()

    def _seed(self, name, data, fam):
        key = r2_io.FAMILIES[fam]["prefix"] + name
        self.fake.put_raw(key, data)
        man = {"files": {name: {"key": key, "size": len(data),
                                "sha256": hashlib.sha256(data).hexdigest(),
                                "lines": r2_io.gz_lines(data), "etag": hashlib.md5(data).hexdigest()}}}
        import json
        self.fake.put_raw(r2_io.FAMILIES[fam]["manifest"], json.dumps(man).encode())

    def test_mode_on_downloads_missing_partitions_in_window(self):
        install(self.fake, "on")
        self._seed(f"pm_ticks_{D1}.jsonl.gz", gz("x", "y"), "pm")
        rep = r2_io.materialize_glob("parts/pm_ticks_*.jsonl")
        self.assertEqual(rep, {f"pm_ticks_{D1}.jsonl.gz": "telecharge"})
        self.assertEqual(r2_io.gz_lines(Path(f"parts/pm_ticks_{D1}.jsonl.gz").read_bytes()), 2)

    def test_out_of_window_partitions_are_not_downloaded(self):
        install(self.fake, "on")
        self._seed(f"pm_ticks_{D_OLD}.jsonl.gz", gz("x"), "pm")
        self.assertEqual(r2_io.materialize_glob("parts/pm_ticks_*.jsonl"), {})

    def test_double_and_off_are_no_ops_without_any_r2_call(self):
        for mode in ("double", "off"):
            install(self.fake, mode)
            self._seed(f"live_match_{D0}.jsonl.gz", gz("x"), "live")
            self.fake.calls.clear()
            self.assertEqual(r2_io.materialize_glob("parts/live_match_*.jsonl.gz"), {})
            self.assertEqual(self.fake.calls, [])

    def test_materialize_single_path(self):
        install(self.fake, "on")
        self._seed(f"kx_ticks_{D0}.jsonl.gz", gz("k"), "kx")
        self.assertTrue(r2_io.materialize(f"parts/kx_ticks_{D0}.jsonl.gz"))
        self.assertFalse(r2_io.materialize(f"parts/kx_ticks_{D1}.jsonl.gz"))

    def test_locally_modified_file_is_never_overwritten_pristine_one_is_refreshed(self):
        install(self.fake, "on")
        subprocess.run(["git", "init", "-q"], check=True)
        name_a, name_b = f"live_set1_{D0}.jsonl.gz", f"live_set2_{D0}.jsonl.gz"
        Path("parts", name_a).write_bytes(gz("old"))
        Path("parts", name_b).write_bytes(gz("old"))
        subprocess.run(["git", "add", "parts"], check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
                       check=True)
        # R2 a prolongé les deux partitions ; b est en cours d'écriture locale.
        import json
        man = {"files": {}}
        for n in (name_a, name_b):
            data = gz("old") + gz("new")
            key = "parts/live/" + n
            self.fake.put_raw(key, data)
            man["files"][n] = {"key": key, "size": len(data), "lines": 2,
                               "sha256": hashlib.sha256(data).hexdigest()}
        self.fake.put_raw("parts/live/_manifest.json", json.dumps(man).encode())
        Path("parts", name_b).write_bytes(gz("old") + gz("ecriture_en_cours"))
        rep = r2_io.materialize_glob("parts/live_*.jsonl.gz")
        self.assertEqual(rep[name_a], "rafraichi")
        self.assertEqual(rep[name_b], "local_modifie")
        self.assertIn(b"ecriture_en_cours", gzip.decompress(Path("parts", name_b).read_bytes()))
        self.assertIn(b"new", gzip.decompress(Path("parts", name_a).read_bytes()))


class _S3Handler(http.server.BaseHTTPRequestHandler):
    store = {}

    def log_message(self, *a):
        pass

    def _key(self):
        import urllib.parse
        return urllib.parse.unquote(self.path.split("?")[0].split("/", 2)[-1])

    def do_PUT(self):
        n = int(self.headers.get("content-length", 0))
        body = self.rfile.read(n)
        assert self.headers["authorization"].startswith("AWS4-HMAC-SHA256 ")
        assert self.headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
        key = self._key()
        if self.headers.get("if-none-match") == "*" and key in self.store:
            self.send_response(412); self.end_headers(); return
        self.store[key] = body
        self.send_response(200)
        self.send_header("ETag", f'"{hashlib.md5(body).hexdigest()}"')
        self.end_headers()

    def do_GET(self):
        if "list-type=2" in self.path:
            items = "".join(f"<Contents><Key>{k}</Key><Size>{len(v)}</Size></Contents>"
                            for k, v in sorted(self.store.items()))
            body = (f'<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/'
                    f'2006-03-01/">{items}<IsTruncated>false</IsTruncated></ListBucketResult>').encode()
        else:
            body = self.store.get(self._key())
            if body is None:
                self.send_response(404); self.end_headers()
                self.wfile.write(b"<Error><Code>NoSuchKey</Code></Error>"); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MiniS3Tests(unittest.TestCase):
    """Le client bibliothèque standard parle bien S3 (serveur HTTP local)."""

    def test_roundtrip_conditional_and_list(self):
        _S3Handler.store = {}
        srv = http.server.HTTPServer(("127.0.0.1", 0), _S3Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            env = {"R2_ACCESS_KEY_ID": "AK", "R2_SECRET_ACCESS_KEY": "SK",
                   "R2_ENDPOINT": f"http://127.0.0.1:{srv.server_port}"}
            r2_io.reset_cache()
            with mock.patch.dict(sys.modules, {"boto3": None}):
                r2 = r2_io.client(env)
            self.assertIsInstance(r2.client, r2_io.MiniS3)
            r2.put("parts/ticks/a b.gz", b"xyz", create_only=True)
            with self.assertRaises(r2_io.PreconditionFailed):
                r2.put("parts/ticks/a b.gz", b"xyz", create_only=True)
            self.assertEqual(r2.get("parts/ticks/a b.gz"), b"xyz")
            self.assertIsNone(r2.get("absent"))
            self.assertEqual(r2.list("parts/"), [("parts/ticks/a b.gz", 3)])
        finally:
            srv.shutdown()
            srv.server_close()
            r2_io.reset_cache()


if __name__ == "__main__":
    unittest.main()
