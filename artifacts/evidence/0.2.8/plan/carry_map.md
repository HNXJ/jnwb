# Carry map: 0.2.7 stack to the 0.2.8 draft

Generated from `artifacts/todo_stack.md` at `fe14858d` and `todo_stack_0.2.8.md` by a scratch
script that fails when a unit resolves to nothing. Full original text: `git show
fe14858d:artifacts/todo_stack.md`.

The `Now` column resolves each row at `47235371` (Hamm, 2026-09-29): the live item
that holds the unit, the commit that finished its work, or the stated drop. A lane's merge
commit stands for the work it merged.

| Disposition | Units |
|---|---|
| carried | 170 |
| dissolved | 4 |
| done | 2 |
| dropped | 7 |
| merged | 2 |
| moved | 5 |
| out of scope | 1 |
| split | 9 |
| added (not in the 0.2.7 stack) | 43 |

## From the 0.2.7 stack

| From | Unit | Disposition | Destination or reason | Now |
|---|---|---|---|---|
| 07-26 | (item) | dissolved | container dissolved; each bullet mapped below | its bullets, below |
| 07-26 | P-01 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-26 | P-08 | dropped | record counts in two review findings; P-63's count is restated with its method in `artifacts/evidence/0.2.7/package_inventory.md` | stated drop |
| 07-26 | P-20 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-36 | carried | 08-01 (0.2.8) | live: 08-07, moved in `3e479dcd` |
| 07-26 | P-76 | carried | 08-04 (0.2.8) | finished in `531c28f5` |
| 07-26 | P-84 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-26 | P-90 | dropped | the compact format requires every `Writes:` token backticked, and a gate for prose targets would grow the apparatus that `artifacts/goal.md` §10 bounds | stated drop |
| 07-26 | P-102 | carried | 12-06 (0.2.12) | live: 12-06 |
| 07-26 | P-119 | dropped | the integrator allocates ids (`artifacts/cooperation.md`); the collision was renumbered on integration | stated drop |
| 07-26 | P-154 | dropped | the blocker-names-no-live-item half is gate 17 today (`check_stack_pointers_resolve`); the remaining shapes were repaired by hand and the compact form has one field per label | stated drop |
| 07-26 | P-155 | dropped | a backlink gate grows the apparatus; the compact items cite their evidence files forward | stated drop |
| 07-26 | P-162 | dropped | lanes run in separate worktrees, where overlap surfaces as a merge conflict; this draft's lane sets were checked disjoint by expanding every token against `git ls-files` | stated drop |
| 07-26 | P-167 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-26 | P-171 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-190 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-191 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-26 | P-192 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-196 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-26 | P-197 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-26 | P-198 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-199 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-203 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-204 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-209 | merged | into P-284 on 2026-09-27; carried inside 12-06 | live: 12-06 |
| 07-26 | P-216 | split | 10-08 (0.2.10), 10-09 (0.2.10), 11-01 (0.2.11), 11-02 (0.2.11), 12-01 (0.2.12) | live: 10-08, 10-09, 11-01, 11-02, 12-01 |
| 07-26 | P-218 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-219 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-220 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-221 | carried | 11-01 (0.2.11) | live: 11-05, moved in `3e479dcd` |
| 07-26 | P-227 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-26 | P-228 | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-26 | P-229 | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-26 | P-230 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-231 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-232 | carried | 12-01 (0.2.12) | live: 12-09, moved in `3e479dcd` |
| 07-26 | P-235 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-238 | carried | 12-04 (0.2.12) | live: 12-04 |
| 07-26 | P-241 | carried | 08-02 (0.2.8) | finished in `fdf434f8` (figures lane B) |
| 07-26 | P-242 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-244 | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-26 | P-245 | carried | 11-02 (0.2.11) | dropped by ruling D8 (2026-09-29) in `3e479dcd` |
| 07-26 | P-246 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-254 | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-26 | P-255 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-256 | split | 10-06 (0.2.10), 10-08 (0.2.10) | live: 10-06, 10-08 |
| 07-26 | P-257 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-259 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-264 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-26 | P-265 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-266 | carried | 12-04 (0.2.12) | live: 12-04 |
| 07-26 | P-267 | carried | 07-12 (0.2.9) | live: 07-12 |
| 07-26 | P-268 | out of scope | the capability matrix stays on the out-of-scope list, which now names P-268 | stated drop |
| 07-26 | P-269 | carried | 09-01 (0.2.9) | live: 09-01 |
| 07-26 | P-274 | carried | 12-01 (0.2.12) | live: 12-09, moved in `3e479dcd` |
| 07-26 | P-275 | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-26 | P-276 | carried | 08-02 (0.2.8) | finished in `fdf434f8` (figures lane B) |
| 07-26 | P-277 | carried | 09-01 (0.2.9) | live: 09-01 |
| 07-26 | P-278 | carried | 09-01 (0.2.9) | live: 09-01 |
| 07-26 | P-279 | carried | 07-12 (0.2.9) | live: 07-12 |
| 07-26 | P-280 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-281 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-26 | P-282 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-26 | P-283 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-284 | carried | 12-06 (0.2.12) | live: 12-06 |
| 07-26 | P-285 | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-26 | P-287 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-288 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-26 | P-289 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-290 | carried | 12-05 (0.2.12) | live: 12-05 |
| 07-26 | P-291 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-292 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-294 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-295 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-296 | carried | 10-08 (0.2.10) | live: 10-13, moved in `3e479dcd` |
| 07-26 | P-297 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-298 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-299 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-300 | carried | 12-02 (0.2.12) | live: 12-02 |
| 07-26 | P-301 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-302 | carried | 12-02 (0.2.12) | live: 12-02 |
| 07-26 | P-303 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-304 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-305 | carried | 10-01 (0.2.10) | live: 10-01 |
| 07-26 | P-307 | carried | 08-02 (0.2.8) | live: 08-02 |
| 07-26 | P-309 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-26 | P-311 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-312 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-313 | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-26 | P-314 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-315 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-317 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-319 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-320 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-321 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-322 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-323 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-324 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-326 | dropped | stale text in archived 0.2.6 evidence, which is kept as written | stated drop |
| 07-26 | P-328 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-26 | P-329 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-330 | carried | 12-02 (0.2.12) | live: 12-02 |
| 07-26 | P-331 | split | 10-03 (0.2.10), 10-06 (0.2.10) | live: 10-03, 10-06 |
| 07-26 | P-332 | split | 10-06 (0.2.10), 10-08 (0.2.10), 10-09 (0.2.10) | live: 10-06, 10-08, 10-09 |
| 07-26 | P-333 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-334 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-335 | carried | 07-05 (0.2.11) | live: 07-05 |
| 07-26 | P-336 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-337 | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-26 | P-338 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-340 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-341 | carried | 09-02 (0.2.9) | live: 09-02 |
| 07-26 | P-342 | carried | 12-01 (0.2.12) | live: 12-01 |
| 07-26 | P-343 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-344 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-346 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-347 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-26 | P-348 | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-26 | P-349 | split | 09-02 (0.2.9), 10-03 (0.2.10) | live: 09-02, 10-03 |
| 07-26 | P-350 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-26 | P-351 | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-26 | P-352 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-26 | P-353 | split | 10-04 (0.2.10), 12-03 (0.2.12) | live: 10-04, 12-03 |
| 07-27 | (item) | dissolved | container dissolved; each bullet mapped below | its bullets, below |
| 07-27 | RP-1 | carried | 12-03 (0.2.12) | live: 08-07, moved in `3e479dcd` |
| 07-27 | RP-2 | carried | 12-02 (0.2.12) | live: 12-02 |
| 07-27 | RP-3 | carried | 08-07 (0.2.8) | live: 08-07 |
| 07-27 | RP-4 | carried | 08-07 (0.2.8) | live: 08-07 |
| 07-27 | RP-7 | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | CI guard hardening | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | RNG surface | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-27 | Depth declaration guard | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-27 | `classify_layer_from_depth` reads electrode z as | carried | 11-02 (0.2.11) | live: 11-02 |
| 07-27 | Deprecations to complete | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-27 | Response-significance wording | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-27 | Readiness blind spots | carried | 12-02 (0.2.12) | live: 12-02 |
| 07-27 | Peak-memory reset evidence | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | Floor coverage | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | One smoke definition | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | Release workflow edges | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | Load-sensitive workflow test | carried | 08-07 (0.2.8) | live: 08-07 |
| 07-27 | Load-sensitive state generation | carried | 08-07 (0.2.8) | live: 08-07 |
| 07-27 | xflip calibration wall time | carried | 08-07 (0.2.8) | live: 08-07 |
| 07-27 | Figure checks | carried | 08-02 (0.2.8) | finished in `fdf434f8` (figures lane B) |
| 07-27 | Legend check reach | carried | 08-02 (0.2.8) | finished in `fdf434f8` (figures lane B) |
| 07-27 | Nav check edges | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-27 | Stack editor edges | carried | 12-01 (0.2.12) | live: 12-09, moved in `3e479dcd` |
| 07-27 | PSI segment count and conditional networks | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-27 | Vis label edges | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-27 | Tie-width test reach | split | 10-04 (0.2.10), 10-06 (0.2.10) | live: 10-04, 10-06 |
| 07-27 | Prepend scanner reach | carried | 12-03 (0.2.12) | live: 12-03 |
| 07-27 | Vis range edges | carried | 10-09 (0.2.10) | live: 10-09 |
| 07-27 | Directed estimator edges | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-27 | Zflip long ramps | carried | 10-04 (0.2.10) | live: 10-04 |
| 07-27 | MCP signal reference edges | carried | 11-01 (0.2.11) | live: 11-01 |
| 07-27 | Sweep site fingerprint | carried | 12-04 (0.2.12) | dropped by ruling D11 (2026-09-29) in `3e479dcd` |
| 07-27 | Process tests to prune or merge | carried | 12-05 (0.2.12) | live: 12-05 |
| 07-27 | Exports and modules outside the routing | carried | 07-12 (0.2.9) | live: 07-12 |
| 07-27 | `jrsa` resampling fallback | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-27 | Generator seeds and `jrsa` axes | split | 10-03 (0.2.10), 10-04 (0.2.10), 10-06 (0.2.10) | live: 10-03, 10-04, 10-06 |
| 07-28 | (item) | dissolved | container dissolved; each bullet mapped below | its bullets, below |
| 07-28 | IA-19 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-28 | IA-23 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-28 | IA-28 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-28 | IA-29 | carried | 10-08 (0.2.10) | live: 10-08 |
| 07-28 | IB-44 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-28 | IB-45 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-28 | IB-48 | carried | 10-06 (0.2.10) | live: 10-06 |
| 07-28 | IB-56 | carried | 09-03 (0.2.9) | live: 09-03 |
| 07-28 | IB-60 | carried | 10-03 (0.2.10) | live: 10-03 |
| 07-28 | IB-61 | carried | 07-12 (0.2.9) | live: 07-12 |
| 07-28 | IB-63 | carried | 07-12 (0.2.9) | live: 07-12 |
| 07-28 | IB-71 | merged | into P-284 on 2026-09-27; carried inside 12-06 | live: 12-06 |
| 07-05 | (item) | carried | 07-05 in 0.2.11 | live: 07-05 |
| 07-05 | a. A script scores decline accuracy from `jnwb.p | carried | 07-05 a | live: 07-05 |
| 07-05 | b. A result names the exact input it came from | carried | 07-05 b | live: 07-05 b, reworded |
| 07-05 | c. `CONTRIBUTING.md` states the intake | carried | 07-05 c | live: 07-05 |
| 07-08 | (item) | carried | 07-08 in 0.2.9 | live: 07-08 |
| 07-09 | (item) | carried | 07-09 in 0.2.9 | live: 07-09 |
| 07-10 | (item) | carried | 07-10 in 0.2.9 | live: 07-10 |
| 07-11 | (item) | carried | 07-11 in 0.2.9 | live: 07-11 |
| 07-12 | (item) | carried | 07-12 in 0.2.9 | live: 07-12 |
| 07-13 | (item) | carried | 07-13 in 0.2.8 | finished in `c4053bbc` (skills lane C) |
| 07-18 | (item) | carried | 07-18 in 0.2.8 | finished in `c4053bbc` (skills lane C) |
| 07-21 | (item) | carried | 07-21 in 0.2.11 | live: 07-21 |
| 07-22 | (item) | carried | 07-22 in 0.2.11 | live: 07-22 |
| 07-30 | (item) | carried | 07-30 in 0.2.8 | finished in `c4053bbc` (skills lane C) |
| 07-30 | Role files point to one contract | carried | 07-30 (0.2.8) | finished in `33980a50` (skills lane A) |
| 07-30 | One line ending across `skills/` and `artifacts/ | split | the `skills/` half is done (coordinator, 2026-09-28); the `artifacts/skills/` half stays in 07-30 | `skills/` finished in `af086401` (skills lane B); `artifacts/skills/` under ruling D3, live as P-102 in 12-06 |
| 07-30 | `artifacts/skills/jnwb-review` holds the review  | carried | 07-30 (0.2.8) | finished in `33980a50` (skills lane A) |
| 07-30 | Trigger and table repair | done | passed review (coordinator, 2026-09-28) | finished in `af086401` (skills lane B) |
| 07-30 | Verification lines for figures (render at final  | done | passed review (coordinator, 2026-09-28) | finished in `af086401` (skills lane B) |
| 07-30 | `tests/test_figure_form.py` adds text-overlap an | moved | 08-02 QC-3, so lanes B and C share no file | finished in `fdf434f8` (figures lane B) |
| 07-30 | Docs form F8 | carried | 07-30 (0.2.8) | finished in `852277dd` |
| 07-30 | `.claude/agents/jnwb-verifier.md` as a thin rout | moved | a local step noted in 07-30: `.claude/` is git-ignored | a local file outside the tree (ruling of 2026-09-29, review home and verifier dispatch) |
| 07-30 | 07-10 and 07-11 accept on the `docs/agents.md` r | carried | 07-30 (0.2.8) | dropped: did not reproduce (`852277dd`) |
| 07-31 | (item) | dissolved | dissolved: fragments to 08-05, the `AGENTS.md` draft to 08-06, the compaction to 08-01 (this draft) | its bullets, below |
| 07-31 | CHANGELOG fragments | moved | 08-05 | live: 08-05 |
| 07-31 | A draft `AGENTS.md` of about 1500 words | moved | 08-06 | finished in `39a51b14` (lane C) |
| 07-31 | Compact the todo stack to one line per item (id, | moved | 08-01, which lands this draft | landed in `1dd61cf4` |

## Added

| Item | Cycle | Unit | Source | Now |
|---|---|---|---|---|
| 08-02 | 0.2.8 | QC-1 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-2 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-3 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-4 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-5 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-6 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-7 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-8 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-9 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-10 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-11 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-02 | 0.2.8 | QC-12 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig01 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig02 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig03 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig04 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig05 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig06 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig07 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig08 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig09 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | fig10 | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-03 | 0.2.8 | Cross-figure style | figure QC report | finished in `fdf434f8` (figures lane B) |
| 08-04 | 0.2.8 | Quickstart QC row | figure QC report | finished in `531c28f5` |
| 08-06 | 0.2.8 | A draft of about 1500 words (4403 at `fe14858d`) | carried text from 07-31 and 07-30, and RP-1's remainder | finished in `39a51b14` (lane C) |
| 08-06 | 0.2.8 | The §7 line 07-30 asks for | carried text from 07-31 and 07-30, and RP-1's remainder | finished in `33980a50` (skills lane A) |
| 08-06 | 0.2.8 | The P-36 sentence reported by 08-01, and RP-1's  | carried text from 07-31 and 07-30, and RP-1's remainder | live: 08-07 (P-36, RP-1), moved in `3e479dcd` |
| 08-08 | 0.2.8 | 07-21 base | `artifacts/goal.md` §5 names the two APIs as 0.2.8 work; the items' own minimal bases | finished in `39a51b14` (lane C) |
| 08-08 | 0.2.8 | 07-22 base | `artifacts/goal.md` §5 names the two APIs as 0.2.8 work; the items' own minimal bases | finished in `39a51b14` (lane C) |
| 07-30 | 0.2.8 | `artifacts/skills/` line endings levelled, with  | coordinator, 2026-09-28 | under ruling D3, live as P-102 in 12-06 |
| 07-30 | 0.2.8 | Landmark-viz checks | coordinator, 2026-09-28 | finished in `852277dd` |
| 07-30 | 0.2.8 | One skill table | coordinator, 2026-09-28 | finished in `852277dd` |
| 07-30 | 0.2.8 | Unit-quality wording | coordinator, 2026-09-28 | finished in `852277dd` |
| 07-30 | 0.2.8 | Router-reach parser | coordinator, 2026-09-28 | finished in `852277dd` |
| 07-30 | 0.2.8 | `jnwb/vis/canvas.py | coordinator, 2026-09-28 | finished in `852277dd` |
| 09-01 | 0.2.9 | Nav regrouped into Start, Analyse, Tutorials, Us | `restructure_plan.md` (c) | live: 09-01 |
| 09-01 | 0.2.9 | `01_architecture_and_philosophy.md` merged into  | `restructure_plan.md` (c) | live: 09-01 |
| 09-01 | 0.2.9 | `02` split | `restructure_plan.md` (c) | live: 09-01 |
| 09-01 | 0.2.9 | `04` split | `restructure_plan.md` (c) | live: 09-01 |
| 10-01 | 0.2.10 | Path derivation | `restructure_plan.md` (a): measured path literals in shared tests | live: 10-01 |
| 10-04 | 0.2.10 | 06-97 residue | `artifacts/planned_post_0.2.6.md` (at `47235371`): a documented call site for `xflip` | live: 10-04 |
| 10-06 | 0.2.10 | IB-58 | `artifacts/rulings/2026-09-28.md`: windowing by default is 0.2.8 work (integrator, 70) | live: 10-06 |
| 12-05 | 0.2.12 | Apparatus bound | `artifacts/goal.md` §10: the apparatus bound has no check | live: 12-05 |
