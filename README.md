<p align="center">
  <img src="assets/logo.svg" width="112" alt="myminio logo">
</p>

<h1 align="center">myminio</h1>

<p align="center"><strong>A hand-rolled object store for people who want to see the inside.</strong></p>

<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

Split a blob into shards across ordinary directories, add one XOR parity shard, keep every version, and rebuild a lost shard on the next read — in about 600 lines of Python and NumPy.

> **Status: archive, first generation.** The erasure-coding core (`ec4.py`) is verified by `tests/smoke_ec.py`; the Flask API around it only partly works. This is **not** S3-compatible, not production software, and not maintained. It is kept as a readable reference and as the direct predecessor of `myminio2`.

## Quick start

The verified path is the Python library. It needs Python 3 and NumPy; Flask is only needed for the HTTP layer.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy flask

mkdir -p dat0 dat1 dat2

python3 - <<'PY'
import numpy as np
from ec4 import EC

ec = EC({f'./dat{i}/': 10**9 for i in range(3)})   # shard directory -> free bytes
ec.set('greeting', np.frombuffer(b'hello, shards', 'B'), t=1, chk=1)

print(np.concatenate(ec.get('greeting', chk=1)).tobytes())
# b'hello, shards'
PY
```

`chk=1` writes RAID-5: two data shards plus one XOR parity shard. Delete one data shard under `dat0/`–`dat2/`, read again with `chk=1`, and the shard is reconstructed and written back in place.

Run the verification (NumPy only, uses a temporary directory):

```bash
python3 tests/smoke_ec.py
```

To start the partial HTTP façade, pass each directory with its quota in bytes:

```bash
python3 s3svr.py ./dat0/1000000 ./dat1/1000000 ./dat2/1000000
# Flask serves http://localhost:5000
```

## What it can do now

| Capability | Where |
| --- | --- |
| **RAID-5 XOR erasure coding** — *n* data shards + 1 parity, tolerates one lost shard | `ec4.split`, `ec4.cat` |
| **RAID-0 striping** — no parity (`chk=0`, the default) | `ec4.split`, `ec4.cat` |
| **Timestamped versions** and point-in-time reads (“newest version older than *t*”) | `ec4.set`, `ec4.get` |
| **Version-filtered deletion** | `ec4.rm` |
| **Quota accounting** per directory and quota-aware shard placement | `ec4.EC.__init__`, `ec4.set` |
| **Self-healing reads** — rebuild a missing shard and repair it in place | `ec4.cat` |
| **Health scan** over every object, with an error counter | `ec4.gets` |
| **Bespoke Flask API** over the core, intentionally not S3 | `s3svr.py` |
| **Three-node MinIO compose file**, independent of the Python code | `docker-compose.yml` |
| **In-memory XOR experiments** — `ec5.py` runs; `ec6.py` crashes on a shape mismatch | `ec5.py`, `ec6.py` |

### The HTTP surface

The API is a small, incomplete wrapper — it is not the S3 protocol.

| Route | Method | What happens |
| --- | --- | --- |
| `/obj` | GET | JSON list of object keys |
| `/obj/<k>` | GET | JSON list of version timestamps for `k` |
| `/obj/<k>/<t>` | GET | bytes of the newest version older than `t` |
| `/obj/<k>/<t>` | POST | store the request body as version `t` (always RAID-0) |
| `/obj/<k>/<t>` | PUT | **broken** — calls the missing `EC.snap` → HTTP 500 |
| `/obj/<k>/<t>` | DELETE | delete versions older than `t` |
| `/objs` | GET | **broken** — returns a bare `int` → HTTP 500 |
| `/ec` | GET | JSON map of directory → remaining quota |

There is no authentication, no buckets, no multipart upload, no range GETs, no ETags and no error mapping: a missing object yields HTTP 500, not 404.

### What is not here

- **No S3 compatibility.** The name describes the intent, not protocol compliance.
- **No replication.** The only redundancy is single-parity XOR; it survives exactly one lost shard.
- **No network distribution.** Shards are local files in one process. Spreading them over HTTP backends is what `myminio2` does.
- **No snapshots.** The `[x] snapshot` checklist entry and the `PUT` route promise a method that was never written.
- **No packaging, configuration system or maintained test suite.** `tests/smoke_ec.py` is archival evidence, not CI.

## Architecture

A stored object is a set of shard files named `<unix-ts> <data-shards> <index>` inside one directory per shard store:

```text
dat0/greeting/1 2 0   # data shard 0
dat1/greeting/1 2 1   # data shard 1
dat2/greeting/1 2 2   # XOR parity shard
```

**Write path.** Pad the payload to a whole number of shards, split it into *n* data shards, XOR those shards into a parity shard when `chk=1`, order the directories by remaining quota, then write one shard per directory and decrement each quota.

**Read path.** Pick the newest version older than the requested timestamp, load the shards by index, and reconstruct a missing shard from the remaining data shards plus parity. The reconstruction is written back to disk. Finally the data shards are concatenated; with `chk=0` there is no parity and therefore no repair.

The shard stores are plain local directories, so the whole thing is inspectable with `ls`, `sha1sum` and a text editor — which is the point.

### The separate MinIO cluster

`docker-compose.yml` stands up stock MinIO and is **not used by the Python code**. It needs root credentials from the environment, and a distributed MinIO pool normally wants at least four drives, so the three-node layout may be rejected at startup; the commented `minio3`/`minio4` blocks restore the five-node layout the commands were written for.

```bash
export MINIO_ROOT_USER=myminio
export MINIO_ROOT_PASSWORD=replace-with-a-real-value
mkdir -p dat0 dat1 dat2
docker compose up -d        # S3 API on :9000, :9002, :9004
```

### Repository layout

| Path | Lines | What |
| --- | ---: | --- |
| [`ec.py`](ec.py) | 69 | first cut: `EC(list)`, XOR parity, `write/read/list/remove` |
| [`ec2.py`](ec2.py) | 139 | adds `split_xor`/`xor` helpers and timestamped versions |
| [`ec3.py`](ec3.py) | 92 | switches to `EC(dict)` (dir → free bytes) and quota-aware placement |
| [`ec4.py`](ec4.py) | 148 | the mature cut: RAID-5 + RAID-0, versioning, quota, health scan, error counter |
| [`ec5.py`](ec5.py) | 47 | in-memory array-level XOR coding (runs on import) |
| [`ec6.py`](ec6.py) | 41 | variant of `ec5.py`; crashes on a shape mismatch |
| [`s3svr.py`](s3svr.py) | 55 | Flask `/obj` REST wrapper around `ec4` |
| [`vector.py`](vector.py) | 34 | scratch growable `mmap` array; crashes on current NumPy |
| [`docker-compose.yml`](docker-compose.yml) | 70 | three-node stock MinIO cluster (repaired YAML) |
| [`tests/smoke_ec.py`](tests/smoke_ec.py) | 117 | archival verification of the `ec4` claims above |
| [`docs/project-status.md`](docs/project-status.md) | — | classification, evidence and boundaries |

## How to develop

There is no build step and no package to install. NumPy is the only dependency for the core; Flask is needed only by `s3svr.py`.

```bash
pip install numpy flask     # inside a virtualenv
python3 tests/smoke_ec.py   # exercises RAID-5, RAID-0, versions, repair, mismatch detection
```

The code is a ladder: each `ec*.py` is a self-contained stage of the same idea. When changing the core, keep `ec4.py` runnable and re-run the smoke check. `vector.py`, `ec5.py` and `ec6.py` are scratch experiments and are not part of the runnable path.

## How to contribute

This repository is an archive, not an actively maintained project, so feature pull requests are unlikely to be merged. Corrections to the docs, the archival evidence, or a failing check on a newer NumPy are welcome as issues. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for scope, the local check and PR expectations. If you want the same idea taken further, see `myminio2`.

## Roadmap

### Implemented

- XOR erasure coding: RAID-5 (one parity shard) and RAID-0 (striping only).
- Version history, point-in-time reads, and version-filtered deletion.
- Per-directory quotas and quota-aware placement.
- On-read reconstruction with in-place repair, plus shard-mismatch detection.
- Global health scan and error counter.
- In-memory XOR experiments and a partial Flask API.
- A repaired three-node MinIO compose file for comparison.

### Planned (not in this archive)

- Implement the missing `EC.snap` and `EC.ln`, or remove the routes and checklist entries that promise them.
- Give the HTTP layer real status codes (404 for missing keys, 400 for bad timestamps) and make `/objs` return JSON.
- Expose `chk` through `POST /obj/<k>/<t>` so the API can actually write RAID-5.
- Replace the scratch experiments with a small, maintained suite and a package layout.
- Move shards behind HTTP backends — carried out in `myminio2`.

### Future vision

`myminio` is a learning ladder: enough of an object store to make erasure coding, versioning, placement and repair concrete, with nothing hidden behind a framework. The next generation already exists in `myminio2`, where the same shard/parity idea is split across HTTP backends. If this code is revived, the useful direction is correctness and observability — a truthful HTTP layer, a real test suite, and shard movement over the network — not S3 feature parity.

## License

GNU Affero General Public License v3.0 only. See [`LICENSE`](LICENSE).
