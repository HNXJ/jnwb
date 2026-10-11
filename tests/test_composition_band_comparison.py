"""The band comparison between two conditions, run as one chain of public calls.

The chain takes the skills in the order `skills/jnwb/SKILL.md` names them for this task:

- `jnwb-nwb-data` reads each LFP channel and the trials table, the load before any reading;
- `jnwb-paradigm` turns the trials table into one condition label and one onset per trial, and
  epochs the LFP at those onsets;
- `jnwb-lfp-spectral` measures the band power of each trial on each channel;
- `jnwb-statistics` compares conditions A and B per channel, with one FDR family across channels;
- `jnwb-figures` plots the channel profile of the A-to-B difference in dB;
- `jnwb-qc` records what ran, on which input file, with which seed.

**Unequal dimensions throughout**: 12 trials, 5 channels and 500 window samples. On a square
fixture a transposed hand-off has the same shape as a correct one, so the shape assertions below
would not catch it. The seed fixes the noise, the condition order and the spike counts.

**Killing mutation** (applied in `test_the_chain_refuses_condition_labels_swapped...`): the
condition labels are swapped at the paradigm hand-off. The planted 20 Hz tone then sits on the
trials labelled B, so the separation check on the planted channels fails. The same check also
refuses two other wrong compositions: spike counts in place of the LFP trace, and epochs handed
over transposed (refused at the hand-off assertion inside the chain).

The chain is correct today, so the first test passes; the other three show that the check can
fail on the composition it names.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import numpy as np
import pytest
from matplotlib.figure import Figure

import jnwb

SEED = 7
FS = 1000.0
N_TRIALS = 12
N_A = 7
N_CHANNELS = 5
SESSION_SAMPLES = 20_000
WIN_S = (0.0, 0.5)
WIN_SAMPLES = int(round((WIN_S[1] - WIN_S[0]) * FS))
BAND = (8.0, 30.0)
TONE_HZ = 20.0
PLANTED = (0, 1, 2)
IDENTIFIER = "band-comparison-fixture"

assert len({N_TRIALS, N_CHANNELS, WIN_SAMPLES}) == 3, "the fixture must have unequal dimensions"


def _write_session(path):
    """A session whose trials labelled A carry a 20 Hz tone on the planted channels."""
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries

    rng = np.random.default_rng(SEED)
    onsets = 1.0 + 1.5 * np.arange(N_TRIALS)
    codes = rng.permutation(np.array(["A"] * N_A + ["B"] * (N_TRIALS - N_A)))
    lfp = rng.normal(0.0, 1.0, size=(SESSION_SAMPLES, N_CHANNELS))
    tone = np.sin(2 * np.pi * TONE_HZ * np.arange(WIN_SAMPLES) / FS)
    for onset, code in zip(onsets, codes):
        if code == "A":
            start = int(round(onset * FS))
            lfp[start:start + WIN_SAMPLES, list(PLANTED)] += tone[:, None]

    nwb = NWBFile(
        session_description="band comparison fixture", identifier=IDENTIFIER,
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="shank0", description="d", location="unknown",
                                       device=device)
    for channel in range(N_CHANNELS):
        nwb.add_electrode(group=group, location="unknown", x=0.0, y=0.0, z=float(channel))
    region = nwb.create_electrode_table_region(list(range(N_CHANNELS)), "all")
    nwb.add_acquisition(ElectricalSeries(name="lfp", data=lfp, electrodes=region,
                                         starting_time=0.0, rate=FS))
    nwb.add_trial_column(name="stimulus", description="condition label")
    for onset, code in zip(onsets, codes):
        nwb.add_trial(start_time=float(onset), stop_time=float(onset) + WIN_S[1],
                      stimulus=str(code))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return codes, onsets


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    path = tmp_path_factory.mktemp("band_comparison") / "session.nwb"
    codes, onsets = _write_session(path)
    counts = (int(np.sum(codes == "A")), int(np.sum(codes == "B")))
    assert counts == (N_A, N_TRIALS - N_A), f"fixture must hold 7 A and 5 B trials, not {counts}"
    return path, codes, onsets


def band_comparison(path, *, n_channels=N_CHANNELS, seed=SEED):
    """The chain. Each hand-off asserts the shape the next public call documents."""
    # jnwb-nwb-data: one trace per LFP channel, with the rate read from the file
    traces = []
    for channel in range(n_channels):
        data, rate = jnwb.acquisition_channel(path, name="lfp", channel=channel)
        assert rate == FS, f"acquisition rate {rate}"
        traces.append(np.asarray(data, dtype=float))
    lfp = np.column_stack(traces)

    # jnwb-paradigm: one condition label and one onset per trial
    table = jnwb.events(path, table="trials", code_column="stimulus", onset_column="start_time")
    codes = np.asarray(table.codes)
    onsets = np.asarray(table.onsets, dtype=float)

    # jnwb-paradigm epochs each channel; jnwb-lfp-spectral: band power per trial (rows) and
    # per channel (columns)
    power = np.empty((onsets.size, n_channels))
    for channel in range(n_channels):
        epochs, time_s = jnwb.epoch_continuous(lfp[:, channel], onsets, win_s=WIN_S, fs=FS)
        assert epochs.shape == (onsets.size, time_s.size), (
            f"epochs {epochs.shape}, expected ({onsets.size}, {time_s.size}) trials by time")
        for trial in range(onsets.size):
            power[trial, channel] = jnwb.band_power(epochs[trial], fs=FS, freq_range=BAND,
                                                    normalize=False)

    # jnwb-statistics: condition A against B per channel; one FDR family across channels
    a = codes == "A"
    b = codes == "B"
    p = np.array([
        jnwb.StatisticalAnalysis.exploratory_compare(
            power[a, c], power[b, c], test="parametric")["parametric"]["pval"]
        for c in range(n_channels)
    ])
    q = np.asarray(jnwb.fdr_correct(p))
    # average raw power across trials, divide, and take the logarithm once
    db = np.asarray(jnwb.to_db(power[a].mean(axis=0) / power[b].mean(axis=0)))

    # jnwb-figures: the channel profile, x = channel index
    figure = Figure()
    ax = figure.add_subplot(1, 1, 1)
    ax.plot(np.arange(n_channels), db, marker="o")
    jnwb.apply_tight_auto_axis(ax, x_span=(-0.5, n_channels - 0.5))

    # jnwb-qc: the record of what ran, on which input file, with which seed
    result = jnwb.Result(
        question=jnwb.Question(
            hypothesis="LFP band power differs between conditions A and B",
            signals=["lfp"], contrast="condition A vs condition B",
            inference_unit="session", signal_units={"lfp": "V"},
            axes={"lfp": "time x channels"}, conditions=["A", "B"],
        ),
        statistics={"db": db.tolist(), "q": q.tolist()},
        provenance=jnwb.Provenance(
            software_version=jnwb.__version__, backend="cpu", random_seed=seed,
            parameters={"band_hz": list(BAND), "win_s": list(WIN_S)},
        ),
        lineage=jnwb.Lineage(source_type="nwb", source_id=str(path),
                             parents=["lfp", "trials"], operation="band_comparison"),
    )
    return {"power": power, "codes": codes, "db": db, "p": p, "q": q,
            "figure": figure, "result": result}


def _assert_planted_effect(out, path):
    power, codes, db, q = out["power"], out["codes"], out["db"], out["q"]
    assert power.shape == (N_TRIALS, N_CHANNELS), f"power is {power.shape}"
    a = codes == "A"
    planted = list(PLANTED)
    for channel in planted:
        assert power[a, channel].min() > power[~a, channel].max(), (
            f"channel {channel}: the tone is not on the trials labelled A")
    assert np.all(db[planted] > 6.0), f"dB on the planted channels: {db[planted]}"
    assert np.all(q[planted] < 0.01), f"q on the planted channels: {q[planted]}"
    line = out["figure"].axes[0].lines[0]
    np.testing.assert_array_equal(line.get_xdata(), np.arange(N_CHANNELS))
    np.testing.assert_allclose(line.get_ydata(), db)
    result = out["result"]
    assert result.lineage.source_id == str(path), result.lineage.source_id
    assert result.provenance.random_seed == SEED
    np.testing.assert_allclose(result.statistics["db"], db)


def test_the_band_comparison_chain_recovers_the_planted_effect(session):
    path, _, _ = session
    _assert_planted_effect(band_comparison(path), path)


def test_the_chain_refuses_condition_labels_swapped_at_the_paradigm_hand_off(session, monkeypatch):
    path, codes, _ = session
    real_events = jnwb.events
    flip = {"A": "B", "B": "A"}

    def swapped(*args, **kwargs):
        table = real_events(*args, **kwargs)
        return dataclasses.replace(table, codes=tuple(flip[str(c)] for c in table.codes))

    monkeypatch.setattr(jnwb, "events", swapped)
    seen = [str(c) for c in jnwb.events(path, table="trials", code_column="stimulus",
                                        onset_column="start_time").codes]
    assert seen != [str(c) for c in codes], "the mutation did not swap the labels"
    with pytest.raises(AssertionError, match="tone is not on the trials labelled A"):
        _assert_planted_effect(band_comparison(path), path)


def test_the_chain_refuses_spike_counts_in_place_of_the_lfp(session, monkeypatch):
    path, _, _ = session
    counts = np.random.default_rng(SEED + 1).poisson(
        0.05, size=(SESSION_SAMPLES, N_CHANNELS)).astype(float)

    def spike_counts(path_or_nwb, name=None, channel=0):
        return counts[:, channel], FS

    monkeypatch.setattr(jnwb, "acquisition_channel", spike_counts)
    assert counts.shape == (SESSION_SAMPLES, N_CHANNELS)
    with pytest.raises(AssertionError, match="tone is not on the trials labelled A"):
        _assert_planted_effect(band_comparison(path), path)


def test_the_chain_refuses_epochs_handed_over_transposed(session, monkeypatch):
    path, _, _ = session
    real_epochs = jnwb.epoch_continuous

    def transposed(*args, **kwargs):
        epochs, time_s = real_epochs(*args, **kwargs)
        return epochs.T, time_s

    monkeypatch.setattr(jnwb, "epoch_continuous", transposed)
    with pytest.raises(AssertionError, match="epochs"):
        band_comparison(path)
