"""Tutorial 10: WaveMAP on the DANDI 000253 excerpt -- align, normalize, choose, cluster, plot.

Run: python examples/tutorials/10_wavemap.py [figure_dir]

Reads each unit's mean waveform from `examples/data/dandi000253_excerpt.nwb` (units/waveform_mean,
one row per unit, the source's own waveform), aligns it on its trough, normalizes it, runs the
resolution sweep of Lee et al. (2021), clusters at the resolution that rule picks, and draws the
result with `jnwb.vis.plot_wavemap`. With `figure_dir`, the figure is written there as HTML.

The resolution rule: round each resolution's mean modularity to 3 decimals, keep the resolutions
whose smallest cluster holds more than 20 units in every run, and take the highest. A tie at 3
decimals goes to the smaller resolution.

The unit 'volts' is the source's label for `units/waveform_mean`, kept as the source states it.
The peak-to-peak values (31 to 483) are the range of extracellular spikes in microvolts, not volts,
so they are read as microvolts; the script prints the range it reads.

A cluster is a group of units whose normalized mean waveforms share a shape at this resolution.
It is not a cell type. This excerpt holds no ground truth for one, and the classifier and SHAP
interpretation of Lee et al. (2021) are not part of this tutorial.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import h5py
import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb, as tutorial
# 09 does. A run that is deliberately qualifying an installed copy sets JNWB_EXPECTED_PACKAGE_ROOT.
_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb
from jnwb import vis

EXCERPT = _CHECKOUT / "examples" / "data" / "dandi000253_excerpt.nwb"
PROVENANCE = EXCERPT.with_name("dandi000253_excerpt.provenance.json")

RESOLUTIONS = (0.5, 1.0, 1.5, 2.0, 2.5)
N_RUNS = 3          # random unit subsets in the sweep; its default is 25 (Lee et al., 2021, Fig. 3B)
MIN_CLUSTER = 20    # the rule of Lee et al. (2021): every cluster holds more than 20 units


def read_mean_waveforms(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """``(n_units, n_samples)`` mean waveforms, as the source stores them (no unit conversion),
    and the units table's ``id`` of each row."""
    with h5py.File(path, "r") as h:
        waveforms = np.asarray(h["units/waveform_mean"][()], dtype=float)
        ids = np.asarray(h["units/id"][()])
    assert ids.shape[0] == waveforms.shape[0], "one unit id per waveform row"
    return waveforms, ids


def choose_resolution(sweep: dict) -> float:
    """The resolution with the highest mean modularity, rounded to 3 decimals, among those whose
    smallest cluster, in every run, holds more than MIN_CLUSTER units (the rule
    `wavemap_resolution_sweep` reports its inputs for). A tie at 3 decimals goes to the smaller
    resolution."""
    large = sweep["min_cluster_size"].min(axis=1) > MIN_CLUSTER
    assert large.any(), f"no tested resolution keeps every cluster above {MIN_CLUSTER} units"
    score = np.where(large, np.round(sweep["modularity"].mean(axis=1), 3), -np.inf)
    tied = sweep["resolution"][score == score.max()]
    return float(tied.min())


def main() -> None:
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    # The source's declared device rate sets the window in samples only: 12 samples before the
    # trough and 36 after it at 30 kHz. The waveform samples themselves are not resampled.
    fs = float(provenance["source_values"]["declared_rates_hz"]["device_sampling_rate_hz"])
    unit = provenance["waveform_mean"]["unit_label_in_source"]

    raw, unit_ids = read_mean_waveforms(EXCERPT)
    p2p = np.ptp(raw, axis=1)
    print(f"{raw.shape[0]} units, {raw.shape[1]} samples each, labelled '{unit}' by the source; "
          f"peak-to-peak {p2p.min():.0f} to {p2p.max():.0f}, read as microvolts")

    # 1. Align on the trough. A unit whose window leaves the stored samples is marked invalid,
    #    and a row that does not normalize (a flat trace) is dropped. Nothing is padded.
    aligned, valid = jnwb.align_waveforms(raw, fs)
    finite = np.all(np.isfinite(jnwb.normalize_waveforms(aligned[valid])), axis=1)
    used = np.flatnonzero(valid)[finite]
    aligned = aligned[used]
    x = jnwb.normalize_waveforms(aligned)
    print(f"{int(valid.sum())} units have their window inside the stored samples; "
          f"{used.size} have finite normalized waveforms")
    assert used.size > 2 * MIN_CLUSTER, "too few units to cluster"

    # 2. Choose the resolution by the sweep's rule.
    sweep = jnwb.wavemap_resolution_sweep(x, RESOLUTIONS, n_runs=N_RUNS, rng=0)
    for i, r in enumerate(sweep["resolution"]):
        print(f"  resolution {r:4.2f}: modularity {sweep['modularity'][i].mean():.3f}, "
              f"clusters {sweep['n_clusters'][i].mean():.1f}, "
              f"smallest cluster (min over runs) {int(sweep['min_cluster_size'][i].min())}")
    resolution = choose_resolution(sweep)
    print(f"chosen resolution {resolution:g}: the highest mean modularity, rounded to 3 decimals, "
          f"with every cluster above {MIN_CLUSTER} units in every run; a tie goes to the smaller "
          "resolution")

    # 3. Cluster all the units at that resolution, and draw the result.
    result = jnwb.wavemap(x, resolution=resolution, rng=0)
    sizes = np.bincount(result.labels).tolist()
    print(f"{result.n_clusters} clusters with {sizes} units; modularity {result.modularity:.3f}")
    assert result.n_clusters >= 2, "the chosen resolution does not split the units"
    # `result.labels[i]` is the cluster of row i of `x`, which is unit `unit_ids[used[i]]`.
    for k in range(result.n_clusters):
        members = unit_ids[used[result.labels == k]]
        print(f"  cluster {k}: {members.size} units, ids {members[:5].tolist()} ...")

    # A cluster is not a cell type: each one is a shape group at this resolution, and the
    # colors tie the embedding (panel A) to the mean normalized waveform of the group (panel B).
    canvas = vis.plot_wavemap(result, aligned)
    normalized = jnwb.normalize_waveforms(aligned)
    for trace in canvas.fig.data:
        if trace.xaxis == "x2":
            k = int(trace.legendgroup.split()[1])
            assert np.allclose(trace.y, normalized[result.labels == k].mean(axis=0)), k

    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
        out.mkdir(parents=True, exist_ok=True)
        path = out / "10_wavemap.html"
        canvas.fig.write_html(str(path), include_plotlyjs="cdn")
        print(f"Figure: {path}")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "10_wavemap.html"
            canvas.fig.write_html(str(path), include_plotlyjs="cdn")
            assert path.stat().st_size > 0, "no figure was written"
        print("Figure rendered; pass a directory to keep it")


if __name__ == "__main__":
    main()
