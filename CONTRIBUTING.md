# Contributing to myminio

## Scope

This repository is a **first-generation archive**, not an actively maintained
project. It is the direct predecessor of `myminio2`, kept because the erasure-coding
core is small enough to read end to end.

What is welcome:

- corrections to the docs, the README or `docs/project-status.md`;
- a report that `tests/smoke_ec.py` fails on a newer Python or NumPy, with the
  traceback and both versions;
- a fix that makes a documented claim true or removes a claim that cannot be made
  true (for example the missing `EC.snap` behind `PUT /obj/<k>/<t>`).

What is out of scope: S3 protocol compatibility, replication, network-distributed
shards, packaging, and new features. Those belong in `myminio2` or nowhere.

## Running the check

There is no build step, no package and no CI. NumPy is the only dependency of the
core; Flask is needed only to import `s3svr.py`.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy flask
python3 tests/smoke_ec.py    # exits non-zero if a check fails
```

No formatter or linter is configured, and the existing files use a deliberately
terse style (`s` for `self`, one-letter shard variables). Do not reformat them;
matching the local style keeps the diff reviewable.

## Pull requests

- One concern per pull request, with a message in Conventional Commits
  (`docs: …`, `test: …`, `fix: …`).
- Keep `ec4.py` runnable and re-run `python3 tests/smoke_ec.py` before pushing.
- If a change alters a behaviour stated in `README.md` or
  `docs/project-status.md`, change the statement in the same pull request —
  the documents are expected to stay true, not to lag.
- Expect an archive-speed review, or none at all.

## Issues

Include the Python and NumPy versions (`python3 -c 'import numpy; print(numpy.__version__)'`),
the exact command, and the full traceback. For shard-repair or quota problems,
describe the directory layout (`ls` of the shard directories) — object placement
depends on the remaining quota of each directory, so the same payload can be laid
out differently on two machines.
