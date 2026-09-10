# Contributing to jnwb

Everything you need to make a change and get it merged. The scientific and code rules live
in [`docs/11_extending_and_development.md`](docs/11_extending_and_development.md); the
working rules for agents and the repository map live in [`AGENTS.md`](AGENTS.md). This file
is the mechanics.

## Setup

Python 3.12 or newer. CI runs 3.12 and 3.14 on Ubuntu and Windows, so a change must work on
both ends of that range.

```bash
git clone git@github.com:HNXJ/jnwb.git
cd jnwb
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate  elsewhere
pip install -e ".[test,docs]"
```

Optional extras: `mcp` (the MCP server), `torch` and `gpu` (CuPy) for the accelerated
paths, `all` for everything. The GPU paths fall back to CPU with a warning when their
dependency is absent, so you can work on most of the library without them.

Verify the install:

```bash
python -m pytest tests/ -q
```

Around 610 tests, about three minutes. A handful skip without the optional extras.

## Branches

`dev` is where work lands. `main` holds releases and is fast-forwarded to `dev` when one
is cut — no merge commits, so the two never diverge.

Branch from `dev`, and open the pull request against `dev`. Push directly to `dev` only for
work you have run the full checks on. Never force-push either branch.

## Before you push

Four checks, in this order. All four run in CI, so running them locally only saves you a
round trip.

```bash
python -m pytest tests/ -q
python scripts/harness_gate.py
mkdocs build --strict
python scripts/release_gate.py
```

- **The suite** — every test, on the interpreter you ran. Run it on 3.12 as well if your
  change touches anything version-sensitive.
- **`harness_gate.py`** — 12 repository gates: the project boundary, skills, paths, the
  root allowlist, docs, the public API set, version agreement, the Python policy, import
  shadowing, and project identifiers in code. It fails on structure, not behaviour.
- **`mkdocs build --strict`** — Read the Docs sets `fail_on_warning`, so a warning here is
  a failed publish.
- **`release_gate.py`** — builds the wheel, installs it in a clean venv, and smoke-tests
  the installed package. Only needed before tagging, but it catches packaging mistakes
  (a module missing from the wheel, a broken extra) that the suite cannot see.

Stage exact paths. `git add .` sweeps in build output and scratch files.

## What goes in a change

- **Smallest change that reaches the acceptance you defined.** No drive-by edits.
- **A test for every fix.** A corrected bug gets a regression test that fails without the
  fix — see `docs/11_extending_and_development.md` §4 for the probe classes expected.
- **Docs and skills in lockstep.** Changing a public symbol means updating `docs/` and
  `skills/` in the same commit.
- **A `CHANGELOG.md` entry** for anything a user would notice. Breaking changes say what
  breaks and how to keep the old behaviour.
- **A citation** for a published method, in the docstring and in `docs/references.md`,
  with a DOI you resolved rather than one you recalled.

## Where the work is queued

[`artifacts/todo_stack.md`](artifacts/todo_stack.md) holds the remaining work, grouped by
the version that will carry it, most consequential first. It holds only what is not yet
done — a finished item is deleted, because git and the changelog already record it. If you
finish something, delete it from the stack in the same commit.

## Releasing

Maintainers only, and only from a clean `dev` with all four checks green.

1. Bump the version in `pyproject.toml` and `jnwb/__init__.py`; write the `CHANGELOG.md`
   entry.
2. Commit to `dev`, push, and wait for CI to pass on that exact commit.
3. Fast-forward `main` to `dev` and push it.
4. Tag `vX.Y.Z` and push the tag. The tag push runs CI (test + build) only — it does **not**
   upload to PyPI.
5. Create a **GitHub Release** for that tag (non-prerelease). The workflow's `publish-pypi`
   job runs on `release: published` and uploads to production PyPI via trusted publishing.
6. Verify the result from PyPI in a fresh venv, rather than trusting the workflow's green
   tick. PyPI versions are immutable: a bad upload can never be replaced, only superseded.

**TestPyPI:** push an `rc` tag (`vX.Y.ZrcN`) or publish a GitHub Release marked prerelease;
either path runs the `publish-testpypi` job. `workflow_dispatch` with target `testpypi` is
also available for maintainers.

## Reporting a problem

Open an issue with the jnwb version, the interpreter, the platform, and the smallest script
that reproduces it. If it involves an NWB file, say what is unusual about the file — jnwb
carries repairs for malformed ones, and which repair applies matters.
