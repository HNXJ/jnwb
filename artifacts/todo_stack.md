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

Scope ruled 2026-10-12 (`artifacts/rulings/2026-10-12.md`, full-release scope): 0.2.12 covers
cleaning, organizing, a major doc update and the dashboard's view of each work's replications. The release waits for 12-21, not for the contributed dashboard cards; pull request #31
(`jnwb-laminar`) merged into `dev` on 2026-10-13.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 3 | R release tooling | 12-03 | `scripts/release_gate.py`, `scripts/harness_gate.py`, `scripts/fact_gate.py`, `.github/workflows/` and their tests | none |
| 4 | H harness | 12-01, 12-05 | `scripts/harness_gate.py`, process tests | R |
| 5 | F figures and citations | 14-01 to 14-05, 12-08 | `docs/`, `examples/tutorials/` | none |
| any | J ground truth | 12-21 | the files 12-21 names | jaxfne's excerpt |
| any | D deprecation | 12-13's `gpu_pca` path | `jnwb/gpu_pca.py`, its test, `docs/api.md` | Hamm names the replacement |
| 5 | L laminar (focus, Hamm 2026-10-13) | 14-09, 15-01, 15-02, 15-03, 15-05, 15-06, 15-07 | `jnwb/laminar/`, `tests/test_vflip2*.py`, `tests/test_xflip*.py`, `tests/test_zflip*.py`, `skills/jnwb-laminar/`, their `docs/` rows | none; 15-05 to 15-07 wait for 14-09 |
| last | Z closure | `main` merged into `dev`; the blocker pass rerun at HEAD; `release_gate.py` | the receipt | every row above |

### 12-21 A jaxfne simulation as jnwb ground truth

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: jaxfne delivering the excerpt.
Writes: `examples/data/jaxfne_*.nwb`, `examples/data/jaxfne_*.provenance.json`, `tests/test_jaxfne_ground_truth.py`.
- No jnwb test recovers a known coupling, delay or spectrum from a jaxfne simulation (meet 204dfdaa item 8, 2026-10-12). Check: a small NWB excerpt with a provenance file, whose simulated directed coupling and delay are stated in it, is recovered by the jnwb connectivity call within a tolerance the provenance states, and a shuffled control is not. Waits: needs jaxfne's excerpt; nothing shipped changes.
Accept: the check passes.

### 14-09 `vflip2`, the published vFLIP2 estimator

Release: deferred-0.2.12. Rulings: 2026-10-13 (port, best window below the cut, defects documented).
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `jnwb/laminar/_vflip2.py`, `jnwb/laminar/__init__.py`, `jnwb/__init__.py`, `tests/test_vflip2.py`, `tests/data/vflip2_matlab_reference.json`, `docs/references.md`, `skills/jnwb-laminar/SKILL.md`, a changelog fragment.
- jnwb does not compute vFLIP2's omega or its acceptance. Parameters: `psd` (contacts x bins, power), `freqs` (Hz, bin k at k times the bin width), `contact_spacing` (um), `orientation` (`"both"`, `"upright"`, `"inverted"`), `layer4_thickness_mm` (default 0.586, O'Kusky and Colonnier 1982), `omega_cut` (default 6.0). Fixed as in vFLIP2.m: low band 4 to 70 Hz with at least 5 bins, high band 40 to 150 Hz with at least 20 bins and upper end at least 70 Hz, moving mean of 5 bins, both fits p < 0.05, window step round(0.1 mm / spacing), shortest window ceil(layer-4 thickness / spacing), quality cuts 6 and 12. Check: `tests/test_vflip2.py` matches vFLIP2.m (R2024a, sha256 465a1c2f) on the stored cases, omega and G at rtol 1e-9, rows, bands and orientation exactly. Waits: not stated.
Accept: the check passes; the 300-case and Dryad comparison (`E:/derived/vflip2_ref/compare.py`) reports 0 mismatches.

### 15-01 Omega's dependence on every `vflip2` parameter

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09.
Writes: `artifacts/evidence/0.2.12/vflip2_sensitivity.md`, its script, `tests/test_vflip2_sensitivity.py`.
- Omega is ln(G x S_d x B_d x channel span x n_low x n_high x bin width^2); S_d is unnormalized and the band minima count bins, so omega and acceptance move with bin width and frequency range (vFLIP2.m lines 238, 264, 454, 474 to 476). Check: on the Dryad `power_example` and 50 seeded synthetic probes, one parameter varied at a time (bin width 0.5, 1, 2 Hz; upper frequency 150, 200, 250 Hz; spacing 50, 100, 200 um by resampling; layer-4 thickness 0.4, 0.586, 0.8 mm; orientation; `omega_cut` 4, 6, 8), the evidence file tables omega, its change from the default, and acceptance flips, each value written by the script; the test pins the bin-width shift of omega to 2 ln(ratio) plus the band-count terms. Waits: not stated.
Accept: the table regenerates; the docstring states each dependence with its measured size. Ruling after: which fixed constants become parameters, defaults staying vFLIP2.m's.

### 15-02 `vflip2_from_lfp`, vFLIP2's raw path

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09.
Writes: `jnwb/laminar/_vflip2.py`, `tests/test_vflip2.py`, the reference JSON.
- vFLIP2.m's `raw` and `raw_cut` inputs (Hanning-window PSD, trial split) have no port. Check: `vflip2_from_lfp(lfp, fs, contact_spacing=100.0)` on the Dryad raw test data gives omega 11.659 and bands 5 to 43 and 44 to 149 Hz, matching `reference.mat` at rtol 1e-9; a non-integer `fs` is accepted where vFLIP2.m prompts. Waits: not stated.
Accept: the check passes.

### 15-03 `vflip2` recovers a known layer 4 in simulation

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09; Andre Bastos's simulation code for the second half.
Writes: `tests/test_vflip2_simulation.py`, `artifacts/evidence/0.2.12/vflip2_simulation.md`.
- No test shows `vflip2` finds a planted crossover. Check: on 100 seeded probes with a planted alpha-beta/gamma crossover at a known contact (32 contacts, 100 um), the accepted crossover lies within one contact of it in at least 90; on 100 probes with no laminar gradient, at most 5 are accepted. When Andre's simulation code arrives, the same table runs on it. Waits: not stated.
Accept: both rates hold and the evidence file names seeds and counts.

### 15-05 `xflip` on `vflip2`'s frame

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09.
Writes: `jnwb/laminar/_xflip.py`, `tests/test_xflip.py`, the skill row.
- `xflip` reports boundaries as contact indices on its own rows; it cannot be run inside the window `vflip2` chose or report um. Proposal: `window=` takes a `VFlip2Result` or (proximal, distal) rows and restricts the correlation matrix to them; `contact_spacing` (um) adds `boundaries_um`; the shortest block defaults to the layer-4 thickness in contacts, as `vflip2`'s shortest window. Check: on a probe with an artefact block outside the window, `xflip(window=v2)` reports the in-window boundary, in probe rows, within one contact of `vflip2`'s crossover. Waits: not stated.
Accept: the check passes. Ruling: Hamm 2026-10-13, all three proposal points.

### 15-06 `zflip` on `vflip2`'s frame

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09.
Writes: `jnwb/laminar/_zflip.py`, `tests/test_zflip.py`, the skill row.
- `zflip` fits its phase gradient over every contact and requires `orientation` by name (ruling 2026-09-24). Proposal: `window=` as in 15-05; the orientation of an accepted `VFlip2Result` may be passed as the `orientation` argument's source (`"upright"` maps to `"superficial_to_deep"`); a rejected result is refused. Check: on a probe with a planted delay gradient inside the window and none outside, `zflip(window=v2)` recovers the planted delay within its stated tolerance and the whole-probe fit does not. Waits: not stated.
Accept: the check passes. Ruling: Hamm 2026-10-13, an accepted `vflip2` result may supply the orientation.

### 15-07 Laminar anchors take `vflip2`

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: 14-09, 15-05.
Writes: `jnwb/laminar_curation.py`, its tests.
- `fuse_laminar_anchors` takes `vflip_um` and `xflip_um` but not `vflip2`'s crossover. Proposal: `vflip2_um`, set only from an accepted result, reported beside `vflip_um` and fused under the same rule. Check: an accepted `vflip2` crossover moves the fused anchor as `vflip_um` would at the same position; a rejected one leaves it unchanged. Waits: not stated.
Accept: the check passes. Ruling: Hamm 2026-10-13, `vflip2_um` sits beside `vflip_um`.
