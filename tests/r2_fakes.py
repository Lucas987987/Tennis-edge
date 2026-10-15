"""Faux R2 (sous-ensemble boto3) partagé par les tests de migration R2.

Reproduit ce dont dépend r2_io : ETag = MD5, écritures conditionnelles
If-Match / If-None-Match (412), pagination LIST, et compte chaque appel."""
from __future__ import annotations

import hashlib
import io
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import r2_io  # noqa: E402


def _err(code):
    exc = RuntimeError(code)
    exc.response = {"Error": {"Code": code}}
    return exc


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def head_object(self, Bucket, Key):
        self.calls.append(("HEAD", Key))
        body = self.objects.get((Bucket, Key))
        if body is None:
            raise _err("NoSuchKey")
        return {"ContentLength": len(body), "ETag": f'"{hashlib.md5(body).hexdigest()}"'}

    def get_object(self, Bucket, Key):
        self.calls.append(("GET", Key))
        body = self.objects.get((Bucket, Key))
        if body is None:
            raise _err("NoSuchKey")
        return {"Body": io.BytesIO(body), "ETag": f'"{hashlib.md5(body).hexdigest()}"'}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None, **_):
        self.calls.append(("PUT", Key))
        cur = self.objects.get((Bucket, Key))
        if IfNoneMatch == "*" and cur is not None:
            raise _err("PreconditionFailed")
        if IfMatch is not None and (cur is None or hashlib.md5(cur).hexdigest() != IfMatch.strip('"')):
            raise _err("PreconditionFailed")
        self.objects[(Bucket, Key)] = bytes(Body)
        return {"ETag": f'"{hashlib.md5(bytes(Body)).hexdigest()}"'}

    def get_paginator(self, op):
        assert op == "list_objects_v2"
        fake = self

        class P:
            def paginate(self, Bucket, Prefix=""):
                fake.calls.append(("LIST", Prefix))
                yield {"Contents": [{"Key": k, "Size": len(v)}
                                    for (b, k), v in sorted(fake.objects.items())
                                    if b == Bucket and k.startswith(Prefix)]}
        return P()

    # aides de test
    def put_raw(self, key, data, bucket=r2_io.DEFAULT_BUCKET):
        self.objects[(bucket, key)] = bytes(data)

    def raw(self, key, bucket=r2_io.DEFAULT_BUCKET):
        return self.objects.get((bucket, key))

    def count(self, verb):
        return sum(1 for v, _ in self.calls if v == verb)


def install(fake, mode="double"):
    """Branche le faux R2 comme client du processus et règle le mode."""
    r2_io.reset_cache()
    r2_io._CLIENT_CACHE["client"] = r2_io.R2(fake, r2_io.DEFAULT_BUCKET)
    os.environ["R2_PRIMARY"] = mode


def uninstall():
    r2_io.reset_cache()
    os.environ.pop("R2_PRIMARY", None)
