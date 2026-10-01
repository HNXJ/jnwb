- Changelog entries are one fragment per change under `changelog.d/`, assembled into
  `CHANGELOG.md` at release by `scripts/assemble_changelog.py`.
- `scripts/release_gate.py` checks `artifacts/state.md` first and runs the test suite last, after
  the build, the installed-package smoke test and the tutorials; `vis` is now an extra the release
  environment must have.
