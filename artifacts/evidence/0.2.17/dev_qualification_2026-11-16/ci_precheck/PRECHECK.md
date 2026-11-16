# CI/CD pre-check before re-enabling the workflow (2026-11-16)

Question: would a CI/CD run at `dev` = `fabe3c021f26a0b8d8d9b5fe0ceb33cdc26986b0` pass? Hamm 2026-11-16:
enable CI/CD only, and only when as sure as possible that it passes. This record is local
reproduction, not CI verification; the CI run itself is the verification.

Last green CI/CD on `dev`: run 43462038382 at `9252d0cd` (2026-11-13). Its job logs are the reference.

## What changed since that run

| Source | Change | How it was read |
|---|---|---|
| Repository | `9252d0cd..fabe3c02`: 9 files, 21 tests added to `tests/test_push_guard.py` | `git diff --stat` |
| Dependencies, matrix legs | `numpy` 2.5.4 → 2.5.5, `python-multipart` 0.0.33 → 0.0.34 | `scripts/py/drift.py`: each job log's `Successfully installed` line against a resolve taken today (`packages/`) |
| Dependencies, floors leg | `python-multipart` only; every declared floor resolves to itself | `scripts/ci_wsl_floors_setup.sh` |
| Interpreters | none: 3.12.16, 3.13.18, 3.14.10, 3.15.2 are still the newest in `actions/python-versions` | the logs' `platform` lines against the manifest |
| Runner images | unknown | no route reads the image a new run would get |

`wrapt` shows as 2.6.0.dev1 → 2.5.2 in the uv resolves and is unchanged in the pip freeze of the
Windows venv: a resolver difference, no drift.

## Reproduced legs

Every run: fresh venv, the workflow's install line, no pip config file, an empty home directory, an
empty global git config, `GITHUB_ACTIONS=true`, `CI=true`, `JNWB_REQUIRE_BROWSER=1`, the Liberation
Sans 2.1.5 font, `python scripts/ci_pytest.py tests/`. Linux is WSL Ubuntu 24.04 (the runner's
`ubuntu-latest` is 26.04); Chrome there is choreographer's download, named through `BROWSER_PATH`.
"depth 1" is a checkout made as `actions/checkout` makes it (`scripts/ci_shallow_clone.sh`).

| Leg | Interpreter | Checkout | Result | Last green CI leg | Difference |
|---|---|---|---|---|---|
| Test, ubuntu 3.12 (builds `state.md`) | 3.12.3 | full | 10872 passed, 93 skipped, 38 xfailed | 10849 / 95 / 38 | +21 new tests; 2 history tests of `test_learning_gate.py` run in a full clone |
| Test, ubuntu 3.13 | 3.13.18 | depth 1 | 10868 / 97 / 38 | 10847 / 97 / 38 | +21 new tests |
| Test, ubuntu 3.15 | 3.15.2 | depth 1 | 10868 / 97 / 38 | 10847 / 97 / 38 | +21 new tests |
| Test, windows 3.14, figures compared, `matplotlib==3.11.2` | 3.14.3 | full | 10874 / 91 / 38 | 10849 / 95 / 38 | +21 new tests; 2 history tests and 2 other-interpreter tests run here |
| Dependency floors | 3.12.0 | full | 10799 / 166 / 38 | 10776 / 168 / 38 | +21 new tests; 2 history tests |
| Build: gate, strict docs, sdist and wheel, `twine check`, manifest, clean-venv smoke | 3.12.3 | depth 1 | all steps pass | all steps pass | none |
| Build: suite against the installed wheel | 3.12.3 | depth 1 | 10870 / 95 / 38 | 10849 / 95 / 38 | +21 new tests |
| Build: tutorials against the wheel | 3.12.3 | depth 1 | 11 of 11 pass | pass | none |

Zero failed and zero errored tests in every run (`results.txt`). The start of the build log was
overwritten by interleaved output; the workspace was read afterwards at `fabe3c02`, shallow.

The 47 test files that read git, the push scripts or the README (`scripts/ci_git_subset.sh`), in a
depth-1 checkout:

| Commit | Linux 3.12.3 | Windows 3.14.3 |
|---|---|---|
| `fabe3c02` | 1908 passed, 11 skipped | 1911 passed, 8 skipped |
| `4dfb398d` (17-152, the commit to push next) | 1924 passed, 11 skipped | 1927 passed, 8 skipped |

## Not reproduced

- Windows 3.12 and 3.13, ubuntu 3.14, and the non-blocking pandas 3 leg.
- The exact interpreter patch of the ubuntu 3.12 (3.12.16) and windows 3.14 (3.14.10) legs.
- The runner images, the runner's own Chrome, four runner cores (these runs used 24 workers).
- The full suite at `4dfb398d` in these environments; it passed in the machine's own environment
  (10901 passed, 82 skipped, 38 xfailed), and the files it changes are in the subset above.

## Files

`results.txt` (one verdict block per log), `packages/` (resolves and freezes), `scripts/` (every
script used; the workflow's inline Python is under `scripts/py/`). The verbose logs stay on the
machine that ran them.
