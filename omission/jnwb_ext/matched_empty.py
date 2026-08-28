"""omission.jnwb_ext.matched_empty -- canonical omission-vs-ordinary-empty-time trial table.

P3 of the 2026-08-27 causal SPK-LFP coupling + omission-vs-empty-time discrimination work
(Hamm). Builds ONE shared, modality-agnostic trial/window table -- SPK, LFP, and MUAe each
extract their own signal from these same windows downstream; this module only decides WHICH
windows are scientifically valid "omitted slot" vs "ordinary empty" comparisons and keeps their
provenance (position, sequence, preceding-stimulus history, subject, session) explicit.

Per Hamm's explicit instruction: reuse ``omission.jnwb_ext.unit_classification``'s selection/
matching logic where SCIENTIFICALLY IDENTICAL (the local pre-omission baseline window is reused
verbatim, same constants), but do NOT equate a classification criterion with a population
information analysis -- this module produces a trial table for downstream discriminability
testing, not a unit-level significance decision.

Comparator types produced (kept separate, never pre-pooled -- caller decides how to combine):

  "omission"                  the omitted slot itself, e.g. AAXB's p3 window.
  "local_pre_omission_delay"  [omit_onset-250, omit_onset-50] ms, SAME trial, immediately
                               preceding the omitted slot. Reuses
                               ``unit_classification.OM_BASE_LEAD_MS``/``OM_BASE_GAP_MS``
                               verbatim (same constants, not re-derived) -- genuinely empty
                               (delay periods carry no stimulus by paradigm construction).
  "post_omission_delay"       the delay window (dN) immediately FOLLOWING the omitted slot pN
                               (e.g. omission at p2 -> d2), SAME trial. Genuinely empty. Not
                               currently isolated anywhere in ``unit_classification`` (which
                               only computes a trial-wide d1-d4 MEAN, not this specific matched
                               window) -- new for this module.
  "trial_delay_mean"          mean across ALL FOUR delay windows (d1-d4) on the SAME trial.
                               Genuinely empty, but less spatially/temporally matched than the
                               two windows above. Reuses ``unit_classification.DELAY_WINDOW_MS``
                               verbatim (matches that module's existing ``om_vs_delay``
                               definition exactly, so results are directly comparable to the
                               existing O+/O++ classification).
  "stimulus_present_control"  the SAME slot window on the family control condition (e.g. AAAB's
                               p3 for an AAXB omission at p3), a DIFFERENT (unpaired) trial. This
                               is a REAL-STIMULUS window, NOT an empty comparator -- included for
                               completeness/secondary discrimination only. Per Hamm's explicit
                               instruction ("do not use stimulus-present trials as the only
                               control"), never treat this row as interchangeable with the three
                               empty comparators above; the ``is_empty`` column marks this
                               distinction so a caller cannot silently conflate them.

No "same-slot, empty-for-a-reason-other-than-omission" comparator exists in this paradigm --
every non-omission slot in every GLO condition carries a real stimulus letter (A/B/R), so a
fourth "matched-empty, different condition" comparator is mathematically undefined here, not
merely unbuilt. Reported as such rather than forced (per Hamm's explicit instruction to report
a genuinely confounded/undefined comparison rather than force it).

Behavioral variables: NOT populated by this module (per Hamm's explicit "behavioral extraction
is not P0" sequencing -- Gate 9 is a later, corpus-subset sensitivity analysis, not a blocking
dependency here). ``behavior_available`` is always False in this build; do not fabricate uniform
coverage by filling numeric behavior columns with NaN as if they were attempted and missing.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from jnwb.statistics import detect_trial_cycles
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from omission.jnwb_ext.trial_ontology import SLOT_INDEX
from omission.jnwb_ext.unit_classification import (
    CONTROL_CONDITION,
    DELAY_WINDOW_MS,
    OM_BASE_GAP_MS,
    OM_BASE_LEAD_MS,
    SLOT_WINDOW_MS,
    family_of,
    omission_events,
)

SLOT_TO_DELAY = {2: "d2", 3: "d3", 4: "d4"}  # the delay immediately FOLLOWING slot pN is dN
PHASE_FOR_P1_ALIGNMENT = 2


def _preceding_identity(condition_code: str, slot: int) -> str:
    """Identity one position before ``slot``, read directly from the condition-code string --
    immune to the documented OMISSION_IDENTITY_CONDITIONS p4 A/B dict-key swap (that bug is a
    dict-labeling issue, not a code-string issue; see omission_identity.py's own fix comment)."""
    if slot <= 1:
        return "none"
    return condition_code[slot - 2]


def build_matched_empty_table(session, *, slots: tuple[int, ...] = (2, 3, 4)) -> pd.DataFrame:
    """Long-form trial table: one row per (omission trial, comparator_type).

    Columns: subject, session_id, condition, omission_slot, sequence_family,
    preceding_identity, trial_role ("omission_trial"/"control_trial"), trial_index (pairs a
    control row back to the omission trial it was matched against -- unique only WITHIN a
    (condition, omission_slot) group, never globally; join on the full composite key, not
    trial_index alone -- see 2026-08-27 independent-verification note), comparator_type,
    is_empty (bool), window_ms (tuple, absolute ms from p1 onset), p1_onset_s (this trial's own
    start_time), cycle_id (session-wide, from jnwb.statistics.detect_trial_cycles on the
    deduplicated union of every physical trial's own onset -- omission AND matched-control
    trials together, since both occurred within the same session timeline and must share one
    block segmentation).

    Two-pass construction, in this fixed order (Hamm, 2026-08-27 matched-empty gate item 5):
    PASS 1 collects one row per DISTINCT PHYSICAL TRIAL (no comparator-type expansion yet) and
    assigns cycle_id once, over that deduplicated whole-session onset population. PASS 2 expands
    each physical trial into its comparator-type rows, attaching the already-known cycle_id.
    Comparator expansion happens strictly after cycle assignment, not interleaved with it -- this
    also structurally forecloses the original bug (598 "cycles" from ~340 trials, 2026-08-27),
    where cycle detection was fed the long-form duplicated-onset stream directly.
    """
    subject = getattr(session, "subject", None) or getattr(session, "subject_id", None)
    session_id = getattr(session, "session_id", None) or getattr(session, "stem", None)

    # PASS 1: one row per distinct physical trial (omission or matched-control), no expansion.
    trials: list[dict] = []
    for cond, slot in omission_events():
        if slot not in slots:
            continue
        fam = family_of(cond)
        ctrl_cond = CONTROL_CONDITION[fam]
        prec = _preceding_identity(cond, slot)

        om_epochs = session.get_epochs(phase=PHASE_FOR_P1_ALIGNMENT, condition=cond, correct_only=True)
        if len(om_epochs) == 0:
            continue
        ctrl_epochs = session.get_epochs(phase=PHASE_FOR_P1_ALIGNMENT, condition=ctrl_cond, correct_only=True)

        for trial_index, onset in enumerate(om_epochs["start_time"].to_numpy(dtype=float)):
            trials.append(dict(subject=subject, session_id=session_id, condition=cond,
                                omission_slot=slot, sequence_family=fam, preceding_identity=prec,
                                trial_role="omission_trial", trial_index=trial_index,
                                p1_onset_s=onset))

        if len(ctrl_epochs) > 0:
            # zlib.crc32, not builtin hash() -- hash() on a (str,int) tuple is salted per-process
            # (PYTHONHASHSEED), so the control-resampling RNG seed (and hence which control trial
            # matches which omission event) was NOT reproducible across separate script runs on
            # identical data (found by independent verification, 2026-08-27: same NWB file gave
            # 591/594/596 differing unique physical trial counts across 3 bare invocations).
            rng_local = np.random.default_rng(zlib.crc32(f"{cond}_{slot}".encode()))
            ctrl_onsets = ctrl_epochs["start_time"].to_numpy(dtype=float)
            n_om = len(om_epochs)
            idx = rng_local.choice(len(ctrl_onsets), size=n_om, replace=len(ctrl_onsets) < n_om)
            for trial_index, onset in zip(range(n_om), ctrl_onsets[idx]):
                trials.append(dict(subject=subject, session_id=session_id, condition=ctrl_cond,
                                    omission_slot=slot, sequence_family=fam, preceding_identity=prec,
                                    trial_role="control_trial", trial_index=trial_index,
                                    p1_onset_s=float(onset)))

    if not trials:
        return pd.DataFrame(trials)

    pool = pd.DataFrame(trials)
    # cycle assignment: deduplicated, whole-session (omission + control together), BEFORE any
    # comparator-type expansion -- see docstring. Onset uniqueness before this dedup is an
    # invariant of the underlying data (physical trial start times), verified empirically
    # against the real corpus, not merely assumed (2026-08-27 matched-empty gate item 4).
    unique_onsets = pool[["p1_onset_s"]].drop_duplicates().sort_values("p1_onset_s").reset_index(drop=True)
    unique_onsets["cycle_id"] = detect_trial_cycles(
        unique_onsets.rename(columns={"p1_onset_s": "start_time"})
    )
    onset_to_cycle = dict(zip(unique_onsets["p1_onset_s"], unique_onsets["cycle_id"]))

    # PASS 2: expand each physical trial into its comparator-type rows, cycle_id already known.
    rows: list[dict] = []
    for trial in trials:
        cycle_id = onset_to_cycle[trial["p1_onset_s"]]
        slot = trial["omission_slot"]
        if trial["trial_role"] == "omission_trial":
            win = SLOT_WINDOW_MS[slot]
            base_win = (win[0] - OM_BASE_LEAD_MS, win[0] - OM_BASE_GAP_MS)
            post_win = DELAY_WINDOW_MS[SLOT_TO_DELAY[slot]]
            d1234 = [DELAY_WINDOW_MS[d] for d in ("d1", "d2", "d3", "d4")]
            trial_mean_center = float(np.mean([w[0] for w in d1234]))  # nominal anchor time only
            common = {**trial, "cycle_id": cycle_id}
            rows.append({**common, "comparator_type": "omission", "is_empty": False,
                         "window_ms": win})
            rows.append({**common, "comparator_type": "local_pre_omission_delay", "is_empty": True,
                         "window_ms": base_win})
            rows.append({**common, "comparator_type": "post_omission_delay", "is_empty": True,
                         "window_ms": post_win})
            rows.append({**common, "comparator_type": "trial_delay_mean", "is_empty": True,
                         "window_ms": (trial_mean_center, trial_mean_center)})  # multi-window; see note below
        else:
            win = SLOT_WINDOW_MS[slot]
            rows.append({**trial, "cycle_id": cycle_id, "comparator_type": "stimulus_present_control",
                         "is_empty": False, "window_ms": win})

    return pd.DataFrame(rows)


TRIAL_DELAY_MEAN_WINDOWS_MS = tuple(
    (EPOCH_ONSETS_MS[d], EPOCH_ONSETS_MS[d] + 500.0) for d in ("d1", "d2", "d3", "d4")
)
"""The 4 windows actually averaged for comparator_type=="trial_delay_mean" (matches
unit_classification.DELAY_WINDOW_MS exactly). A single ``window_ms`` column cannot hold 4
disjoint windows, so this table-level constant is the source of truth for that comparator's
real extraction windows -- a caller computing this comparator's signal must average over
TRIAL_DELAY_MEAN_WINDOWS_MS, not treat the table row's placeholder ``window_ms`` as a real window.
"""
