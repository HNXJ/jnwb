# `outputs/` — generated data and figure assets

**Purpose:** everything here is a build product of a script under `../scripts/` or
`../jnwb_ext/`. Nothing here is hand-authored, and (mostly) nothing here is git-tracked — see
`.gitignore` at the repo root for the small set of explicitly-tracked exceptions.

**Owns:** one subdirectory per analysis/pipeline run, named for what it computed
(`connectivity/`, `decoding/`, `lfp_band_census_v2/`, …). Multiple versioned subdirs for the same
analysis (`_v2`, `_v3`, `final`) are common — **the newest/most-referenced version is not
automatically the correct one**; check `../context/PROJECT_STATE.md` for which vintage is
current before citing a number from here.

**Does not own:** source code, scientific state, or manuscript figures (those live in
`../context/figures/`, which is deliberately git-tracked and separate from this gitignored
scratch space).

**How to apply:** treat every file here as regeneratable and disposable — if it disagrees with a
receipt or `PROJECT_STATE.md`, the generating script or its inputs changed, not the truth.
Re-run rather than hand-edit.
