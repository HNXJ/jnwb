# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 12-09 | One stack parser | P-232 and P-274: gates 15 and 17 read only `###` items and STEP 0a leaves four HTML heading forms unparsed; the stack editor has retry, fence-line and heading-depth edges. | The gates can only under-read, no HTML headings exist, and one call per edit reaches no editor edge. | deferred-0.2.12 |
| 12-01 | Gates in their own modules | `scripts/harness_gate.py` holds every gate, and P-218, P-219, P-235, P-295 (gate 14's pattern passes `items/06-55`, `P-1000` and `p-29`), P-311, P-301, P-342, P-198, P-304 and P-216 (gate part) leave gate edges unpinned or narrower than stated. | After 12-09; the live tree is clean for each and no verdict changes. | deferred-0.2.12 |
| 12-02 | The release gate reads the shared parser | STEP 0a keeps its own parser, and P-300, P-302, P-330, RP-2 and three readiness blind spots are open. | After 12-09; each fails closed or needs a deliberate edit. | deferred-0.2.12 |
| 12-03 | CI and release workflow | RP-7, P-352, P-353 (smoke half), P-309, P-328, P-191, P-197 and the workflow guard, floor, smoke and prepend-scanner edges are unchecked. | After 12-02; each fails closed, fails loudly in CI or needs a deliberate workflow edit. | deferred-0.2.12 |
| 12-05 | Process tests pruned and merged | Four process-test files to prune, four to merge and four weaker checks stay, P-290 is enforced by nothing and the apparatus bound of `artifacts/goal.md` section 10 has no check. | After 12-01; keeping tests cannot make evidence falsely pass. | deferred-0.2.12 |
| 12-04 | Mutation and contract gate reach | P-238 and P-266: `collect_selector` drops node ids containing a space and the contract gate accepts one correct path among several. | Both fail closed and the switch tests hold live behaviour. | deferred-0.2.12 |
| 12-08 | Every routed method cites a published source | The fact graph has no reference nodes or DOI-to-function edges, and the Science fact that every routed method cites a published source is not yet held. | Graph tooling only; the fact row lands on Hamm's approval. | deferred-0.2.12 |
| 09-07 | Checks for the defect classes review keeps finding | Five classes seen twice or cheap to check have no check: ruling-cited-not-recorded, rewrite-drops-obligation, second-home-contradiction, awareness in state and the typed ledger count. | Process evidence only; no shipped behaviour. | deferred-0.2.12 |
| 12-07 | Release and study-vocabulary facts held | R2 (a verify-pypi job after publish-pypi) and B2 (gate 6 over `jnwb/`, `docs/`, `skills/` and `tests/`) report UNHELD. | After 12-01, 12-03, 12-05 and 12-08; the upload step checks sha256 and shipped surfaces are scanned. | deferred-0.2.12 |
| 12-06 | No process identifiers outside the stacks | P-284: 113 identifiers in 6 `scripts/` files and 562 in 87 test files cite item and problem ids (P-209 and IB-71 merged); P-102 levels line endings if D3 rules it. | After 12-01, 12-02, 12-03, 12-04, 12-05, 12-07, 12-08 and 12-09; neither directory ships and P-102 waits on the D3 ruling. | deferred-0.2.12 |
| 11-01 | Every container `inspect` lists is readable | P-294, P-314, P-303, P-299, P-190, P-204, P-220, P-336, P-337, P-216 (reading part), P-289 and P-291 and the MCP signal reference edges leave containers unread or checks unpinned. | Each is loud or behaves correctly. | deferred-0.2.13 |
| 11-02 | Compression, unit tables and addressing edges | P-296 (dated comment), P-344, P-348, P-192 (page part), a `compress_fp32(select=...)` cast under one name and `classify_layer_from_depth` with no declared shallow end are open. | No behavioural effect, or stated; the last waits on the D10 ruling. | deferred-0.2.13 |
| 07-05 | A downstream paper agent can consume jnwb | `jnwb.preflight` outcomes are not scored as data, results do not name their input's sha256 and object path, `CONTRIBUTING.md` states no intake, and P-335 is unreviewed. | After 11-02; new downstream capability, not a defect. | deferred-0.2.13 |
| 11-05 | `ContainerTypeContradictionWarning` exported | P-221: `ContainerTypeContradictionWarning` is not in `jnwb.__all__`. | Changes no value. | deferred-0.2.13 |
| 07-21 | A public NWB mutation API | No public NWB mutation API exists. | Public API; Hamm rules the set from 08-08. | deferred-0.2.13 |
| 07-22 | A public execution and cache API | No public execution and cache API exists. | After 07-21; public API, Hamm rules the surface from 08-08. | deferred-0.2.13 |
| 11-03 | Design facts held | D1, D2 and D3 of the Design table report UNHELD. | After 07-22; nothing public claims them. | deferred-0.2.13 |
| 14-01 | Spectral and laminar figures | Welch and multitaper PSDs, coherence under zero-lag mixing, and the CSD with the vFLIP crossover are described in text only (inventory 10, 4, 6). | Documentation only; no number changes. | deferred-0.2.14 |
| 14-02 | Spiking figures | Causal against Gaussian smoothing of a step, and phase locking, have no figure (inventory 1, 9). | Documentation only; no number changes. | deferred-0.2.14 |
| 14-03 | Inference and directed-connectivity figures | The cluster permutation test, spectral Granger and the PSI trap have no figure (inventory 2, 8). | Documentation only; no number changes. | deferred-0.2.14 |
| 14-04 | Similarity and artifact figures | RDMs, jRSA windows and bad-channel and bad-trial detection have no figure (inventory 5, 7). | Documentation only; no number changes. | deferred-0.2.14 |
| 14-05 | Tutorial figures through the docs generator | Tutorials 00 to 09 show no figure, the open-data tutorial lacks its empirical figure (inventory 3), and `examples/tutorials/09_open_data.py` writes a light-only PNG outside the generator. | Documentation only; no number changes. | deferred-0.2.14 |
| 11-04 | Proposals for the pitfall estimators | Four estimators have no proposal: nonparametric Granger by spectral factorization, a time-reversed Granger control, partial coherence conditioned on a third signal, and a bias floor from randomly paired epochs. | After 10-11; public API, Hamm rules each shape. | deferred-0.2.14 |
| 14-06 | The pitfall estimators Hamm rules | The four estimators 11-04 proposes have no implementation. | After 11-04 and 14-03; public API, nothing lands before the ruling. | deferred-0.2.14 |
| 13-04 | A screen fitted to caller-supplied curation labels | No screen reports held-out agreement per session with a curator's labels, declines on degenerate inputs, or names its estimand. | After 14-03 and the collaborator's label-learning skill; public API, Hamm rules the screen in or deletes the item. | deferred-0.2.14 |
| 14-08 | Unit-curation rows only the lab pipeline holds | D1, D9 and the lab meaning of D3 are defined only in the lab pipeline (`yihan777/alpha_beta_mechanism@826e540`), which no one here can read. | Access to the lab pipeline's code; study-specific rows, jnwb's measures are unchanged. | deferred-0.2.14 |
| 14-07 | A trial-based noise correlation, if a user needs it | No trial-based noise correlation (Cohen and Kohn's $r_{sc}$) exists beside the time-bin form. | Hamm rules whether it is a mode or a function, and whether any user needs it. | deferred-0.2.14 |
