# myminio project status

## Classification

Archive: first-generation hand-rolled object store, migrated out of the private
`~/my` collection (2026-09-30) so it is inspectable instead of rotting. It is the
direct predecessor of `myminio2`. Copied — the original was not modified.

## Status

Archive — not maintained. The erasure-coding core (`ec4.py`) is functional and was
verified during migration; the HTTP layer over it (`s3svr.py`) only partially works
(two routes raise). Not production, no maintained test suite (`tests/smoke_ec.py`
is archival verification, not CI), no packaging; licensed under GNU AGPL v3
(`LICENSE`).

## Evidence

- Source: `~/my/myminio` (private archive), copied verbatim with
  `rsync -a --exclude=.git --exclude=__pycache__ --exclude=*.pyc --exclude=.venv`.
  Every source, doc and test file remains. During the public-facing polish the two
  scratch artifacts were removed: `a` (a generated `memmap` data blob) and `vector`
  (a stray duplicate of an earlier `vector.py`).
- Erasure coding verified with NumPy 2.x / Python 3.12 by driving `ec4.EC` against
  three temporary directories:
  - RAID-5 (`chk=1`) writes 2 data + 1 parity shard and round-trips payloads that
    are divisible and indivisible by the shard count;
  - removing a data shard and reading again reconstructs the payload and repairs the
    shard on disk in place;
  - RAID-0 (`chk=0`, the `set` default) writes 2 data shards and **no parity**;
  - versioning, point-in-time reads and version-filtered deletion behave as
    documented (`get(k, t)` returns the newest version with timestamp `< t`);
  - shard-mismatch detection fires when the parity shard disagrees.
  Reproduce with `python3 tests/smoke_ec.py` (added during migration).
- HTTP layer exercised with Flask 3.1 via a test client (no sockets): `POST /obj/k/t`
  then `GET /obj`, `GET /obj/k`, `GET /obj/k/<t>` and `DELETE /obj/k/t` return 200;
  `PUT /obj/k/t` fails with `AttributeError: 'EC' object has no attribute 'snap'`;
  `GET /objs` fails because the view returns a bare `int`; `GET /ec` returns the
  quota map. The Flask `POST` route never passes `chk`, so the HTTP API always
  writes RAID-0 (no redundancy) even though the library supports RAID-5.
- `docker-compose.yml`: the archived copy was **invalid YAML** —
  `docker compose config` failed with `go-yaml load error in scanner at L5.C49:
  mapping values are not allowed in this context`, because every `command:` and
  `volumes:` line had spaces injected by a copy/paste from a rendered document, e.g.
  `command: minio server - -console-address: 9001 http: // minio{0...2}/dat` and
  `- ./dat0: / dat`. The commented-out `minio3`/`minio4` blocks were *not* corrupted,
  which confirms the diagnosis. During migration the whitespace was reverted, the
  root credentials were moved to environment lookups, and `docker compose config`
  now exits 0. Topology, ports and volume layout are unchanged.
- Not verified: the MinIO cluster itself was never started here (the `minio/minio`
  image could not be pulled during migration), and no network runs of the
  hand-rolled store were done.

## Boundaries

Not S3-compatible: the `/obj/...` REST surface is bespoke, with no authentication
(no AWS SigV4), no buckets, no `ListObjects` XML, no multipart upload, no presigned
URLs, no ACL/policy/lifecycle, no range GETs and no ETag/conditional requests. No
replication in any form — single-parity XOR tolerates exactly one shard loss. No
network distribution: shards are local filesystem paths in one process (moving them
across HTTP backends is what `myminio2` does). The `docker-compose.yml` deploys stock
MinIO and is unrelated to the Python code; its 3-node distributed layout may be
rejected at startup because MinIO wants at least 4 drives. `vector.py` and `ec6.py`
are scratch files that currently crash. Any credentials/datasets found during
migration were dropped, not carried over. Licensed under GNU AGPL v3 (`LICENSE`).
