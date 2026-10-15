# myminio — a hand-rolled object store, first generation

**Title:** myminio

**One-line what:** A from-scratch, dependency-light object-storage experiment that
implements XOR erasure coding (RAID-5 and RAID-0) over plain local directories,
plus per-directory quota accounting, quota-aware placement, timestamped versioning
with point-in-time reads, on-read shard repair and a health scan — behind a minimal
Flask `/obj` REST API.

**Why it exists / what problem it solves:** To have a small private object store
whose internals are understood rather than trusted. The archived material starts
from a `docker-compose.yml` that stands up a real distributed MinIO cluster, and
then reimplements the interesting core of such a system by hand — sharding a blob,
computing an XOR parity shard, choosing where shards go based on free space,
keeping versions, rebuilding a lost shard on read — without depending on MinIO,
`boto3` or any S3 server framework. It is the predecessor of
`myminio2`, where the same idea was carried over the network.

**Status:** archive — first-generation prototype, not production, not maintained.
The erasure-coding core (`ec4.py`) is verified working (see
[`docs/project-status.md`](docs/project-status.md)); the HTTP layer around it is only
partially working. Kept for reference.

**License:** GNU AGPL v3 (see [`LICENSE`](LICENSE)).

---

## How to run

The repository contains **two independent things that do not talk to each other**:

1. `docker-compose.yml` — a stock MinIO cluster (upstream image), and
2. the hand-rolled Python store — `s3svr.py` + `ec4.py` — which runs on local
   directories and never contacts the MinIO containers.

### Part 1 — the MinIO cluster from `docker-compose.yml`

The archived copy of this file had spaces injected into every `command:` and
`volumes:` line, so it was not valid YAML. That corruption has been reverted
(topology, ports and volume layout are unchanged) and MinIO's required root
credentials are now read from the environment. See
[`docs/project-status.md`](docs/project-status.md) for the original broken lines.

```bash
export MINIO_ROOT_USER=myminio                       # placeholder, >= 3 chars
export MINIO_ROOT_PASSWORD=replace-with-a-real-value # placeholder, >= 8 chars

mkdir -p dat0 dat1 dat2                        # bind-mount sources
docker compose config                          # validate
docker compose up -d
docker compose ps
# S3 API:   localhost:9000 (node0), localhost:9002 (node1), localhost:9004 (node2)
# Console:  localhost:9001, localhost:9003, localhost:9005
docker compose down
```

Ports and volume layout (unchanged from the archive):

| service | S3 API (host) | console (host) | volume        |
| ------- | ------------- | -------------- | ------------- |
| minio0  | 9000          | 9001           | `./dat0:/dat` |
| minio1  | 9002          | 9003           | `./dat1:/dat` |
| minio2  | 9004          | 9005           | `./dat2:/dat` |

Caveats, honestly stated: this was **not runtime-verified** during archival (the
image could not be pulled here), and a distributed MinIO pool normally requires at
least 4 drives, so the 3-node layout may be rejected at startup — the commented
`minio3`/`minio4` blocks restore the 5-node layout the commands were written for.

### Part 2 — the hand-rolled store

Each command-line argument is `<directory>/<quota-in-bytes>`. The directories must
already exist; the quota is decremented by the size of any data already inside.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy flask

mkdir -p dat0 dat1 dat2
python s3svr.py ./dat0/1000000 ./dat1/1000000 ./dat2/1000000
# -> serves on localhost:5000 (Flask's default; s3svr.py calls Flask.run() with no args)
```

The HTTP surface (all bespoke — this is **not** the S3 API):

| route                     | method | behaviour                                                        |
| ------------------------- | ------ | ---------------------------------------------------------------- |
| `/obj`                    | GET    | JSON list of object keys                                          |
| `/obj/<k>`                | GET    | JSON list of version timestamps for `k`                           |
| `/obj/<k>/<t>`            | GET    | bytes of the newest version with timestamp `< t` (point-in-time)  |
| `/obj/<k>/<t>`            | POST   | store the request body as version `t` (**striped only**, no parity) |
| `/obj/<k>/<t>`            | PUT    | snapshot — **broken**, `ec4.EC` has no `snap` method → HTTP 500   |
| `/obj/<k>/<t>`            | DELETE | delete versions with timestamp `< t`                              |
| `/objs`                   | GET    | health scan — **broken**, returns a bare `int` → HTTP 500          |
| `/ec`                     | GET    | JSON map of directory → remaining quota                           |

To use the erasure-coding core directly (this is where RAID-5 is actually reachable
— the HTTP `POST` route never passes `chk`):

```python
import numpy as np
from ec4 import EC

ec = EC({f'./dat{i}/': 10**9 for i in range(3)})   # dir -> free bytes
ec.set('k', np.frombuffer(b'payload', 'B'), t=1000, chk=1)   # chk=1 -> RAID-5
data = np.concatenate(ec.get('k', chk=1))                     # rebuilds 1 lost shard
```

## Implemented vs not

Verified in this repository by `tests/smoke_ec.py` (Python 3.12, NumPy 2.x) unless
marked otherwise.

**Implemented**

- XOR erasure coding over local directories: **RAID-5** (n data shards + 1 XOR
  parity, tolerates one lost shard) and **RAID-0** (`chk=0`, striping only, no
  redundancy) — `ec4.py:104` `split`, `ec4.py:122` `cat`.
- On-read reconstruction and **in-place repair** of a missing shard, plus
  shard-mismatch detection — `ec4.py:54` `get`, `ec4.py:122` `cat`.
- Timestamped versions (`<unix-ts> <n> <i>` filenames), point-in-time reads
  ("newest version older than `t`") and version-filtered deletion — `ec4.py:51`
  `stat`, `ec4.py:68` `set`, `ec4.py:80` `rm`.
- Per-directory quota accounting and quota-aware placement (writes to the
  directory with the most free bytes) — `ec4.py:40` `EC.__init__`, `ec4.py:68` `set`.
- Global health scan with an error counter — `ec4.py:90` `gets`.
- In-memory, array-level XOR coding experiments: `ec5.py` runs; `ec6.py` is a
  variant that currently crashes on a shape mismatch.
- A minimal Flask REST wrapper over `ec4` — `s3svr.py`.
- A three-node MinIO topology in `docker-compose.yml`.

**Not implemented**

- **Not S3-compatible.** No authentication at all (no AWS SigV4), no buckets, no
  `ListObjects` XML, no multipart upload, no presigned URLs, no ACL/policy/
  lifecycle/object-lock, no range GETs, no ETags or conditional requests. The API
  is the bespoke `/obj/...` surface above. The name `myminio` describes the
  *intent*, not protocol compliance.
- **No replication of any kind** (no mirroring, no multi-copy, no quorum). The only
  redundancy is single-parity XOR, which tolerates exactly one shard loss.
- **No network distribution in the hand-rolled store.** Shards are local filesystem
  paths handled by one process; there is no node, gossip, consensus or failover
  layer. Moving the shards across HTTP backends is exactly what `myminio2` does.
- **No snapshot support**, despite the `[x] snapshot` checklist entry in `ec4.py:35`
  and the `PUT` route calling it: `ec4.EC.snap` does not exist, and the related
  `EC.ln` (`ec4.py:95`) calls an unimported `os.link`.
- **No HTTP error handling**: a missing object or a bad version yields HTTP 500, not
  404; `/objs` returns a bare `int` and cannot be serialised as a response.
- **No tests, packaging, configuration or CI in the archive.** The only test file
  (`tests/smoke_ec.py`) was added during archival to reproduce the verification in
  this document; it is archive evidence, not a maintained suite.
- `vector.py` (a growable `mmap`-backed `ndarray`) crashes on current NumPy with
  `BufferError: mmap can't resize with extant buffers exported`. It and `ec6.py`
  are scratch files, not part of the runnable path.

## Erasure coding / replication: this generation vs `myminio2`

| | this repo (`myminio`) | `myminio2` |
| --- | --- | --- |
| XOR erasure coding | yes — RAID-5 + RAID-0, the bigger of the two implementations | yes — fixed 2 data + 1 parity per blob |
| versioning / point-in-time reads | yes | no |
| quota + placement policy | yes | no |
| on-read repair + health scan | yes | rebuild-from-parity, no scan |
| shards live on | local directories, one process | three HTTP backends behind a gateway |
| transport | Flask route decorators | custom `asyncio` HTTP/1.1 server, raw sockets |
| replication | **no** | **no** |

So: **erasure coding is present in this generation and is more developed than in
`myminio2`; replication is absent from both.** What `myminio2` adds is the network
split (custom socket server + gateway) and higher-performance file I/O, not
redundancy beyond single parity.

## Distinguishing this from `myminio2`

`myminio2` is the second pass. This repository is the first generation and the
relationship is visible in the code: here the sharding/parity logic is an array of
small `EC` classes (`ec.py` → `ec2.py` → `ec3.py` → `ec4.py`) that write shard files
into local directories, with a thin Flask façade in `s3svr.py`. `myminio2` keeps only
the final shape of that idea and rewrites the transport by hand (`mysock.py`,
`myhttp.py`, `mysvr.py`, `myminios.py`) so the shards are spread across three HTTP
backends. `myminio2` has no `docker-compose.yml`, no Flask and no versioning; this
repository has a real MinIO cluster compose file that the Python code never uses.

## Repository layout

| path | lines | what |
| --- | --- | --- |
| [`ec.py`](ec.py) | 69 | first cut: `EC(list)`, XOR parity, `write/read/list/remove` |
| [`ec2.py`](ec2.py) | 139 | adds `split_xor`/`xor` helpers and timestamped versions |
| [`ec3.py`](ec3.py) | 92 | switches to `EC(dict)` (dir → free bytes) and quota-aware placement |
| [`ec4.py`](ec4.py) | 148 | the mature cut: RAID-5 + RAID-0, versioning, quota, health scan, error counter |
| [`ec5.py`](ec5.py) | 47 | in-memory array-level XOR coding (runs on import) |
| [`ec6.py`](ec6.py) | 41 | variant of `ec5.py`; crashes on shape mismatch |
| [`s3svr.py`](s3svr.py) | 55 | Flask `/obj` REST wrapper around `ec4` |
| [`vector.py`](vector.py) | 34 | scratch growable `mmap` array; crashes on current NumPy |
| [`vector`](vector), [`a`](a) | — | scratch `memmap` data blobs left by the scripts above |
| [`docker-compose.yml`](docker-compose.yml) | 70 | three-node stock MinIO cluster (repaired YAML) |
| [`tests/smoke_ec.py`](tests/smoke_ec.py) | — | archival verification (added during migration) |
| [`docs/project-status.md`](docs/project-status.md) | — | classification / status / evidence / boundaries |

625 lines of Python across the eight `.py` files of the archive (549 non-blank;
`tests/` excluded).

## Reproducing the verification

```bash
python3 tests/smoke_ec.py      # needs numpy; exits non-zero on failure
```

It checks the RAID-5 and RAID-0 round-trips (divisible and indivisible payloads),
rebuild after a lost shard, versioning / point-in-time reads / version deletion, and
shard-mismatch detection — all inside a temporary directory.
