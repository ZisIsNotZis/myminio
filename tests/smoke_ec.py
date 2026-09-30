#!/usr/bin/env python3
"""Archival verification for myminio's XOR erasure-coding core (``ec4.EC``).

This is **not** a maintained test suite: it was added during the 2026-09-30
migration to reproduce the "implemented" claims in ``README.md`` and
``docs/project-status.md``. It needs only ``numpy`` and a writable temp dir.

    python3 tests/smoke_ec.py

Exits non-zero if any check fails.
"""

import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec4 import EC  # noqa: E402

FAILURES = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(name)


def fresh(root, n=3, quota=10**9):
    for i in range(n):
        os.makedirs(f"{root}/dat{i}", exist_ok=True)
    return EC({f"{root}/dat{i}/": quota for i in range(n)})


def layout(ec, key):
    return {d.split("/")[-2]: sorted(os.listdir(d + key)) for d in ec if os.path.isdir(d + key)}


def as_bytes(ec, key, **kw):
    return np.concatenate(ec.get(key, **kw)).tobytes()


def main():
    # --- RAID-5: n data shards + 1 XOR parity ------------------------------
    root = tempfile.mkdtemp(prefix="myminio-smoke-")
    try:
        ec = fresh(root)
        divisible = bytes(range(256)) * 3          # 768 B, 768 % 2 == 0
        indivisible = bytes(range(101))            # 101 B, 101 % 2 == 1

        ec.set("div", np.frombuffer(divisible, "B"), t=1000, chk=1)
        check("RAID-5 writes 3 shards over 3 dirs", len(layout(ec, "div")) == 3)
        check("RAID-5 round-trip, divisible payload", as_bytes(ec, "div") == divisible)

        ec.set("ind", np.frombuffer(indivisible, "B"), t=1001, chk=1)
        check("RAID-5 round-trip, indivisible payload", as_bytes(ec, "ind") == indivisible)

        # Drop one data shard: the read must rebuild it and repair it on disk.
        victim_dir = next(d for d in ec if os.path.isdir(d + "div"))
        victim = os.path.join(victim_dir, "div", os.listdir(victim_dir + "div")[0])
        os.remove(victim)
        check("RAID-5 rebuild after 1 lost shard", as_bytes(ec, "div", chk=1) == divisible)
        check("RAID-5 repaired the shard on disk", os.path.exists(victim))

        # --- RAID-0: striping only, no parity -----------------------------
        ec = fresh(root)
        ec.set("r0", np.frombuffer(divisible, "B"), t=2000, chk=0)
        files = sum(len(v) for v in layout(ec, "r0").values())
        check("RAID-0 writes 2 data shards and no parity", files == 2)
        check("RAID-0 round-trip", as_bytes(ec, "r0") == divisible)

        # --- versioning / point-in-time reads / deletion ------------------
        ec.set("r0", np.frombuffer(b"v2", "B"), t=3000, chk=0)
        check("versions are listed", sorted(ec.stat("r0")) == [2000, 3000])
        check("newest version wins", as_bytes(ec, "r0") == b"v2")
        check("point-in-time read (t=2500)", as_bytes(ec, "r0", t=2500) == divisible)
        ec.rm("r0", t=2500)
        check("version-filtered deletion", sorted(ec.stat("r0")) == [3000])

        # --- shard-mismatch detection -------------------------------------
        ec = fresh(root)
        payload = bytes(range(256)) * 2
        ec.set("bad", np.frombuffer(payload, "B"), t=4000, chk=1)
        parity = next(
            os.path.join(d, "bad", f)
            for d in ec
            for f in (os.listdir(d + "bad") if os.path.isdir(d + "bad") else [])
            if f.split()[2] == "2"  # shard index 2 == the parity shard
        )
        with open(parity, "r+b") as fh:
            fh.seek(0)
            fh.write(bytes([fh.read(1)[0] ^ 0xFF]))
        ec.e = 0
        as_bytes(ec, "bad", chk=1)
        check("shard-mismatch detection", ec.e == 1)

        # --- health scan over every key -----------------------------------
        ec = fresh(root)
        ec.set("h", np.frombuffer(payload, "B"), t=5000, chk=1)
        ec.gets()
        check("health scan completes", True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
