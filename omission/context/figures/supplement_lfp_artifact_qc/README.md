# Supplement — LFP artifact rejection (bad channels, bad trials)

Hamm's ask (2026-08-17): report % trials excluded per monkey/session and % channels excluded
due to noise/flatness, plus document the exclusion method (channel correlation to find
deviant/damaged/detached-contact channels).

**This did not exist anywhere in the repo before this build.** An Explore-agent search found no
partial-correlation channel QC, no deviant-channel detection, and no corpus-wide trial-exclusion
table anywhere in `jnwb/`, `scripts/`, or `context/figures/` — the "6x RMS, ~40/960 trials"
figure quoted in `context/analysis_spec_SPK.md` §0.2 has no code behind it in this repo. Built
from scratch per Hamm's direct method description.

## Method

**Bad channels** (`jnwb.artifact_detection.bad_channels_from_correlation`): channel x channel
Pearson correlation matrix on a 120s continuous raw segment per probe. Per-channel summary =
median off-diagonal correlation (how well that channel agrees with the rest of the probe). A
channel is flagged if its summary is a robust (MAD-based) low-outlier relative to the OTHER
channels' summaries on that probe/session — not a fixed correlation cutoff, since baseline
channel-to-channel correlation varies by session/probe/reference scheme. This directly targets
damaged/detached sensor contacts: a disconnected contact records its own noise, uncorrelated
with the shared local field every other good channel on the probe picks up.

**Bad trials** (`jnwb.artifact_detection.bad_trials_single_channel` +
`consensus_bad_trials`): for each channel surviving the channel QC, a trial x trial Pearson
correlation matrix of that channel's peri-p1-onset waveform (−200…+800 ms). A trial is a
single-channel candidate flag if its median correlation to all other trials on that channel is a
low robust-z outlier, OR its own max |amplitude| is a high robust-z outlier. A trial is only
**excluded** by cross-channel **consensus** — flagged on at least 50% of that session's good
channels independently. Per Hamm: "artifacts appear in all good channels always, if they exist"
— a genuine artifact (movement, cable jerk) is a shared physical event, not one channel's quirk,
so requiring multi-channel agreement is what separates real artifacts from a single imperfectly-
screened channel's own noise.

Thresholds: z = 5.0 (MAD-based) for both channel and trial arms; consensus requires ≥ 50% of
good channels. All in `scripts/detect_lfp_bad_channels_trials.py`.

## Self-tests and positive control

`tests/test_artifact_detection.py`, 7/7 passing: synthetic bad channels (pure independent noise
among correlated good channels) recovered exactly with zero false positives; synthetic artifact
trials (large injected deflection) recovered 5/5 with near-zero false positives; single-channel
flags confirmed **not** to reach consensus alone (a shared 5/6-channel artifact does, a
1/6-channel quirk does not); determinism confirmed (pure function of input, no internal RNG).

**Positive control on real data**: this corpus's own prior documented finding
(`jnwb/artifact_repair.py`'s receipt) is that raw-LFP movement artifacts are a V182o/V198o
phenomenon, **not** C31o. This detector reproduces that asymmetry from raw data with no prior
knowledge encoded in the method — see Result below. That the specificity matches an
independently-established finding is stronger evidence than the synthetic self-tests alone.

## Result

| Monkey | Sessions | % channels excluded (pooled) | % trials excluded (pooled) |
|---|---|---|---|
| Cajal (C31o) | 7 | 3.98% | 0.10% |
| Ivan (V182o) | 10 | 5.76% | 7.86% |
| Joule (V198o) | 5 | 8.95% | 2.09% |

Per-session and per-probe breakdowns: `supplement_lfp_artifact_qc_stats.json`. Full detail
(per session × probe, which channel indices were flagged, which trial indices) in
`outputs/artifact_qc/lfp_bad_channels_trials_per_session.csv` and the upstream
`lfp_bad_channels_trials_stats.json`.

Cajal's near-zero trial-exclusion rate and Ivan/Joule's much higher rates match the corpus's
already-documented movement-artifact asymmetry exactly — read as a positive control on this
detector's specificity, not as a new finding.

## Known limitations (disclosed, not fixed here)

- Channel QC uses a single 120s continuous segment per probe, not the full recording — a
  channel that degrades partway through a session would not be caught by this pass.
- Trial QC window (−200…+800 ms around p1 onset) does not cover the full ~4.6s trial; an
  artifact landing entirely outside that window on all channels would be missed. Chosen for
  tractable runtime on a 22-session corpus at "quickly implement" priority, not because later
  parts of the trial are known to be artifact-free.
- z = 5.0 and the 50% consensus threshold are defensible round numbers, not tuned/validated
  against a labeled ground-truth set of real artifacts (no such labels exist in this corpus).
  The positive-control check above (Cajal near-zero, Ivan/Joule elevated) supports the
  thresholds' rough calibration but is not a formal sensitivity/specificity analysis.
- This is trial-level EXCLUSION (drop the whole trial), a different action from the existing
  `jnwb/artifact_repair.py` sample-level REPAIR (interpolate/substitute within a kept trial).
  The two are not yet reconciled into one pipeline — a trial excluded here could in principle
  already have been repaired by the other mechanism; whether to run repair-then-exclude,
  exclude-then-repair, or pick one is an open design question, not resolved by this build.

Outputs: `supplement_lfp_artifact_qc.svg` / `.png` / `.pdf`, `supplement_lfp_artifact_qc_stats.json`,
`supplement_lfp_artifact_qc_manifest.json`.
