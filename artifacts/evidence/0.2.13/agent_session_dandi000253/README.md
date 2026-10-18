# A blind agent session on DANDI 000253 (12-10, 2026-10-17)

A Haiku 5.5 worker answered five questions about `examples/data/dandi000253_excerpt.nwb` from the skills alone, starting at `skills/jnwb/SKILL.md`, with `examples/tutorials/`, `docs/tutorials/`, `tests/` and `artifacts/` closed to it (`packet.md`). Its final script is `answer.py`, and `stdout.txt` is that script re-run by the dispatcher at 0a7b1763. Reference: `examples/tutorials/09_open_data.py` `analyze()` at the same commit.

| Question | Session | Tutorial | Agree |
|---|---|---|---|
| Units; quality `good` | 297; 246 | 297; 246 | yes |
| Stored LFP rate; derived rate | None; 1250.0 Hz (12500 samples over the 10.000 s observation interval) | None; 1249.9987 Hz, first sample at 3.5692 s (tick step against spike-time ticks) | no |
| Grating rows; drawn gratings | 125; 100 (rows with NaN orientation, contrast and frequencies are blank) | 125; 100 | yes |
| High gamma (50 to 80 Hz) post against pre, dB, 10 VISpm channels | +0.07 to +1.40 | +0.15 to +1.51 | no: 0.08 to 0.21 dB lower on every channel |

The dB difference follows from the clock: the session placed the LFP samples on a clock it chose without a rule to check it against, and reported the choice as a guess.

Gaps the session reported, each checked against the skills by the dispatcher:

1. No skill page says how to put timestamps that are labelled seconds but hold acquisition ticks onto session time. The tutorial derives that clock in its own code (`derive_clock`, checked by spike-LFP lag), and no public function does it.
2. No skill page states the edges of `CANONICAL_BANDS`; the session read them from `jnwb/spectral/_common.py`.
3. A script run by path imported an installed jnwb 0.2.11 from site-packages, not the checkout.

The routing reached `skills/jnwb-nwb-data/references/per_file_discovery_and_events.md`, section 3 of `skills/jnwb-paradigm/SKILL.md`, `skills/jnwb-lfp-spectral/references/power_and_decibels.md` and section 3 of `skills/jnwb-qc/SKILL.md`, and chose `ratio_of_means` for aggregating across trials, as the tutorial does.
