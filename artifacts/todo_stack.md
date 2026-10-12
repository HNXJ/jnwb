# 0.2.12

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only; the rest of 0.2.12 to 0.2.14 is one row per item in
`artifacts/roadmap.md`, and an item moves here with its full text when its lane opens. 0.2.11
closed on 2026-10-11 with every item done (`git log -- artifacts/todo_stack.md`).

Theme, ruled 2026-10-12: consumers first (`artifacts/evidence/0.2.12/plan.md`). Acceptance:
`artifacts/goal.md` and `AGENTS.md` §11.

Every item here carries `deferred-0.2.12`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.11 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; up to three lanes run in parallel, one Haiku worker each, when they share no file (Hamm 2026-10-10 and 2026-10-11); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify. An item holds one defect and one check, in at most eight
lines.

## Lanes

Three lanes run at once; a wave opens when the lanes it depends on have merged. Full suites run
one at a time through `C:/Users/nejath/.claude/bin/suite_lock.py`.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 1 | U consumer API | 12-18, 12-19 | the files each names, `jnwb/__init__.py`, `docs/api.md` | none |
| 1 | G release gate | 12-16 | the files 12-16 names | none |
| 1 | K docs reductions | 12-14 | the files 12-14 names | none |
| 2 | C changelog | 12-17 | the files 12-17 names | K |
| 2 | P pandas 3 | 12-20 | the files 12-20 names | G and K |
| 2 | Q closure findings | 12-15, then 12-12 (roadmap rows) | the files each names | U |
| 3 | R release tooling | 12-09, 12-02, 12-03 (roadmap rows) | `scripts/release_gate.py`, `scripts/harness_gate.py`, `.github/workflows/` and their tests | G and P |
| any | J ground truth | 12-21 | the files 12-21 names | jaxfne's excerpt |

The integrator writes `CHANGELOG.md` entries for U after C lands, in the template 12-17 enforces.

### 12-14 The audit's docs and CHANGELOG reductions

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `README.md`, `CHANGELOG.md`, `docs/common_mistakes.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/documentation_form.md`, `docs/install.md`, `docs/quickstart.md`, `docs/tutorials/00_your_own_file.md`, `.github/CONTRIBUTING.md`, `tests/test_prose_version_claims_are_live.py`, `artifacts/archive/changelog_0.1.0-0.2.9.md`.
- Steps 1 and 2 of the 2026-10-11 compression audit, built on branch `lane-k1` at `dae02ac0` and not landed before 0.2.11 shipped; duplicated docs passages become links (568 words), stale `CONTRIBUTING.md` paths, the version-claim test reads `docs/**`, and CHANGELOG blocks 0.2.9, 0.2.8, 0.2.4 and 0.1.0 to 0.1.7 move to an archive (816 lines). Check: on the rebased branch the docs tests, `scripts/docs_build.py` and the harness pass, and a script shows every moved CHANGELOG line exactly once. Waits: documentation only; no shipped number changes.
Accept: the check passes. Stop: a cut drops a fact, ruling or receipt a file cites.

### 12-16 STEP 8 asserts the tutorials import the wheel

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/release_gate.py`, `tests/test_workflow_release_policy.py`.
- `release_gate.py` STEP 8 sets `JNWB_EXPECTED_PACKAGE_ROOT` but, unlike CI's tutorial step (`workflow.yml`, `assert 'clean_env' in jnwb.__file__`), never checks where `jnwb` resolves, so a tutorial that fell back to the checkout would pass. Check: before the loop, the venv run of `import jnwb` with `tutorial_env` from the staging dir prints a path under `purelib`, and a test that drops the variable makes STEP 8's check fail. Waits: at `424a11be` no path makes a tutorial fall back; the guard stands aside whenever the variable is set (review of `424a11be`, 2026-10-11).
Accept: the check passes.

### 12-17 Internal vocabulary leaves `CHANGELOG.md`

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: 12-14.
Writes: `CHANGELOG.md`, `scripts/harness_gate.py`, `tests/test_harness_gate.py`.
- `AGENTS.md` keeps internal process terms out of `CHANGELOG.md`, but gate 14 checks only `docs/`, and the CHANGELOG carries them (counted in the built dashboard data at `d4e6a710`: "receipt" 30, "AGENTS.md" 35, "agent" 13, "worker" 10, and kinds "Closure (second audit RG)", "Fixed (final independent audit)"); the dashboard republishes the CHANGELOG verbatim. Check: gate 14 also reads `CHANGELOG.md` with its own term list, fails on the current text and passes after the rewording, and every kind heading is one of Breaking, Added, Changed, Deprecated, Removed, Fixed. The same check holds the shared template of meet 204dfdaa (adopted by Hamm 2026-10-12, with the last five releases kept and older ones archived): one line per change of at most about 120 characters naming its test or file, and a `[results change]` marker that names the seed kind affected (int seed or Generator). Waits: the CHANGELOG is already public; no shipped behaviour changes (dashboard review, 2026-10-12).
Accept: the check passes. Stop: a rewording changes what an entry says shipped.


### 12-18 A unit's peak channel mapped to its curated layer

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `jnwb/laminar_curation.py`, `tests/test_laminar_curation.py`, `skills/jnwb-lfp-spectral/SKILL.md`.
- No public call maps a unit's peak channel to the label `curate_and_label` gave that channel; `classify_layer_from_depth` is geometric only (omission JNWB-012, 2026-10-12). Check: on a synthetic `LaminarCurationResult` with known labels, every unit gets its peak channel's label, a channel absent from the result gets "na", and a units table without a peak-channel column is refused by name. Signature ruled 2026-10-12: `map_peak_channel_to_layer(units_df, curation)` returns one label or "na" per unit. Waits: new public API, announced in the changelog with its tests.
Accept: the check passes.

### 12-19 A causal Gaussian smoother that states its lag

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: none.
Writes: `jnwb/onset_fitting.py`, `tests/test_onset_fitting.py`, `skills/jnwb-spiking/SKILL.md`.
- jnwb offers only `causal_exp_smooth`; omission carries its own past-only Gaussian and its figures cannot state the display lag (omission request, 2026-10-12). Check: an impulse at bin k gives zero output before k; the reported mean lag equals the kernel's centroid and matches sigma*sqrt(2/pi) bins within the kernel's truncation error; a step's half-rise falls at the reported lag within one bin. Signature ruled 2026-10-12: `causal_gaussian_smooth(rate, sigma_bins)` returns `(smoothed, mean_lag_bins)`, past-only kernel, edge-padded. Waits: new public API, announced in the changelog with its tests.
Accept: the check passes.

### 12-20 Units tables under pandas 3

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `.github/workflows/workflow.yml`, `docs/install.md`, `tests/test_workflow_release_policy.py`.
- jnwb declares `pandas>=2.2.2` uncapped, but hdmf's `pandas<3` downgrades pandas on install, while omission's units tables build only on pandas 3.0.5 (omission JNWB-010). Check: a non-blocking CI leg installs pandas 3 over hdmf's cap and runs the suite, and `docs/install.md` states the hdmf cap and the override. Waits: no shipped behaviour changes; the leg reports, it does not gate.
Accept: the leg ran once on dev and its result is recorded.

### 12-21 A jaxfne simulation as jnwb ground truth

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: jaxfne delivering the excerpt.
Writes: `examples/data/jaxfne_*.nwb`, `examples/data/jaxfne_*.provenance.json`, `tests/test_jaxfne_ground_truth.py`.
- No jnwb test recovers a known coupling, delay or spectrum from a jaxfne simulation (meet 204dfdaa item 8, 2026-10-12). Check: a small NWB excerpt with a provenance file, whose simulated directed coupling and delay are stated in it, is recovered by the jnwb connectivity call within a tolerance the provenance states, and a shuffled control is not. Waits: needs jaxfne's excerpt; nothing shipped changes.
Accept: the check passes.
