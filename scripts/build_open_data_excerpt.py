"""Build the small real NWB excerpt that `examples/tutorials/09_open_data.py` reads.

Source: DANDI 000253, version 0.240503.0152 (Allen Institute OpenScope, Global/Local Oddball
project), license CC-BY-4.0, https://doi.org/10.48324/dandi.000253/0.240503.0152. Two assets of
session 1232959154 (subject 649323) are read:

- ``sub-649323_ses-1232959154_ogen.nwb``: units, electrodes and stimulus intervals;
- ``sub-649323_ses-1232959154_probe-1_ecephys.nwb``: the LFP of probe B.

Download both from ``https://api.dandiarchive.org/api/assets/<asset id>/download/`` into one
directory, then

    python scripts/build_open_data_excerpt.py --source-dir <that directory>

The script refuses to run on a file whose size or SHA-256 differs from the published asset.

What the excerpt keeps, all copied without resampling or unit conversion:

- the probe's electrodes, with their source ids, and every units row whose peak channel is on
  that probe, with the source's quality metrics;
- spikes in three windows: the first ``--edge-s`` seconds after the probe's first spike, one
  stimulus block padded by ``--pad-s``, and the last ``--edge-s`` seconds before its last spike.
  Each unit's ``obs_intervals`` names those windows, so a gap between them reads as unobserved
  rather than silent;
- the grating presentations inside the block window;
- the LFP of the channels whose location starts with ``--area-prefix``, in three series: the
  first and last ``--edge-s`` of the recording by sample index, and the block window. The raw
  ``timestamps`` are copied verbatim. The two edge series carry the recording's first and last
  sample, so the clock can be derived from the excerpt over the full session span rather than
  over a window this script chose.

The provenance file beside the excerpt records the asset ids, the source digests, every window
and the source values the clock derivation depends on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "examples" / "data" / "dandi000253_excerpt.nwb"

DANDISET = {
    "identifier": "DANDI:000253",
    "version": "0.240503.0152",
    "name": "Allen Institute Openscope - Global/Local Oddball project",
    "doi": "10.48324/dandi.000253/0.240503.0152",
    "url": "https://dandiarchive.org/dandiset/000253/0.240503.0152",
    "license": "CC-BY-4.0",
    "citation": (
        "Westerberg, Jake; Durand, Severine; Cabasco, Hannah; Belski, Hannah; Loeffler, Henry; "
        "Bawany, Ahad; Peene, R. Carter; Han, Warren; Nguyen, Katrina; Ha, Vivian; Johnson, Tye; "
        "Grasso, Conor; Hardcastle, Ben; Young, Ahrial; Swapp, Jackie; Gillis, Ryan; "
        "Ouellette, Ben; Caldejon, Shiella; Williford, Ali; Groblewski, A. Peter; Olsen, Shawn; "
        "Kiselycznyk, Carly; Lecoq, Jerome; Maier, Alex; Bastos, Andre (2024) Allen Institute "
        "Openscope - Global/Local Oddball project (Version 0.240503.0152) [Data set]. DANDI "
        "archive. https://doi.org/10.48324/dandi.000253/0.240503.0152"
    ),
}

# Published asset metadata, from the DANDI API for this version.
ASSETS = {
    "units": {
        "asset_id": "81f9bcf2-d0e3-41a4-97e4-6371dafa3e71",
        "path": "sub-649323/sub-649323_ses-1232959154_ogen.nwb",
        "size": 2413138449,
        "sha256": "60f71391702854963d95ccb164a1d1a8724d1a385f29667e6dd1d2aa6ac00db1",
    },
    "lfp": {
        "asset_id": "56e98383-75da-4da3-a61d-39b6f814d9e5",
        "path": "sub-649323/sub-649323_ses-1232959154_probe-1_ecephys.nwb",
        "size": 1906777325,
        "sha256": "5727ccb88e6665b87cdacb8a0db0d1da0f9447268e832243d392cc104b934bd5",
    },
}

LFP_SERIES = "acquisition/probe_1_lfp/probe_1_lfp_data"
GRATINGS = "intervals/init_grating_presentations"
UNIT_COLUMNS = ("cluster_id", "peak_channel_id", "quality", "snr", "isi_violations",
                "presence_ratio", "amplitude_cutoff")
GRATING_COLUMNS = ("stimulus_name", "stimulus_block", "stimulus_index", "orientation",
                   "contrast", "spatial_frequency", "temporal_frequency")


def _text(values) -> np.ndarray:
    return np.array([v.decode() if isinstance(v, bytes) else str(v) for v in values])


def _scalar_text(ds) -> str:
    value = ds[()]
    return value.decode() if isinstance(value, bytes) else str(value)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(path: Path, expected: dict) -> str:
    if not path.is_file():
        raise SystemExit(f"missing source asset {path}")
    size = path.stat().st_size
    if size != expected["size"]:
        raise SystemExit(f"{path.name}: size {size} != published {expected['size']}")
    digest = sha256_of(path)
    if digest != expected["sha256"]:
        raise SystemExit(f"{path.name}: sha256 {digest} != published {expected['sha256']}")
    return digest


def read_units(path: Path, probe: str) -> dict:
    """Probe electrodes, their units' spike trains and the session metadata, from the source."""
    with h5py.File(path, "r") as h:
        el = h["general/extracellular_ephys/electrodes"]
        on_probe = _text(el["group_name"][:]) == probe
        electrodes = {
            "id": el["id"][:][on_probe],
            "location": _text(el["location"][:])[on_probe],
            "filtering": _text(el["filtering"][:])[on_probe],
            "x": el["x"][:][on_probe], "y": el["y"][:][on_probe], "z": el["z"][:][on_probe],
            "probe_vertical_position": el["probe_vertical_position"][:][on_probe],
            "probe_horizontal_position": el["probe_horizontal_position"][:][on_probe],
            "local_index": el["local_index"][:][on_probe],
            "valid_data": el["valid_data"][:][on_probe],
        }
        group = h[f"general/extracellular_ephys/{probe}"]
        device = h[f"general/devices/{probe}"]
        declared = {
            "device_sampling_rate_hz": float(device.attrs["sampling_rate"]),
            "electrode_group_lfp_sampling_rate_hz": float(group.attrs["lfp_sampling_rate"]),
        }
        u = h["units"]
        end = u["spike_times_index"][:]
        start = np.r_[0, end[:-1]]
        rows = np.flatnonzero(np.isin(u["peak_channel_id"][:], electrodes["id"]))
        spikes = u["spike_times"]
        trains = [np.asarray(spikes[start[i]:end[i]], dtype=np.float64) for i in rows]
        columns = {}
        for name in UNIT_COLUMNS:
            values = u[name][:][rows]
            columns[name] = _text(values) if values.dtype.kind in "OS" else values
        g = h[GRATINGS]
        gratings = {"id": g["id"][:], "start_time": g["start_time"][:],
                    "stop_time": g["stop_time"][:]}
        for name in GRATING_COLUMNS:
            values = g[name][:]
            gratings[name] = _text(values) if values.dtype.kind in "OS" else values
        subject = {k: _scalar_text(h["general/subject"][k])
                   for k in ("subject_id", "species", "sex", "age", "genotype", "strain")}
        session = {
            "identifier": _scalar_text(h["identifier"]),
            "session_start_time": _scalar_text(h["session_start_time"]),
            "institution": _scalar_text(h["general/institution"]),
            "stimulus": _scalar_text(h["general/stimulus"]),
            "device_description": str(device.attrs["description"]),
            "device_manufacturer": str(device.attrs.get("manufacturer", "")),
        }
        unit_ids = u["id"][:][rows]
    return {"electrodes": electrodes, "unit_ids": unit_ids, "trains": trains,
            "columns": columns, "gratings": gratings, "subject": subject,
            "session": session, "declared": declared}


def _py(value):
    """A numpy scalar as the Python scalar pynwb expects; anything else unchanged."""
    return value.item() if isinstance(value, np.generic) else value


def build(source_dir: Path, out: Path, probe: str, area_prefix: str, channel_stride: int,
          block: float, pad_s: float, edge_s: float, skip_hash: bool) -> dict:
    units_path = source_dir / Path(ASSETS["units"]["path"]).name
    lfp_path = source_dir / Path(ASSETS["lfp"]["path"]).name
    digests = {}
    for key, path in (("units", units_path), ("lfp", lfp_path)):
        if skip_hash:
            digests[key] = None
        else:
            digests[key] = verify_source(path, ASSETS[key])
            print(f"verified {path.name}: sha256 {digests[key]}")

    src = read_units(units_path, probe)
    trains = src["trains"]
    nonempty = [t for t in trains if t.size]
    first_spike = min(float(t[0]) for t in nonempty)
    last_spike = max(float(t[-1]) for t in nonempty)

    g = src["gratings"]
    in_block = g["stimulus_block"] == block
    if not in_block.any():
        raise SystemExit(f"no grating presentations in stimulus_block {block}")
    w0 = float(g["start_time"][in_block].min()) - pad_s
    w1 = float(g["stop_time"][in_block].max()) + pad_s
    windows_s = [(first_spike, first_spike + edge_s), (w0, w1), (last_spike - edge_s, last_spike)]
    keep_rows = (g["start_time"] >= w0) & (g["stop_time"] <= w1)

    with h5py.File(lfp_path, "r") as h:
        series = h[LFP_SERIES]
        ticks = series["timestamps"]
        n = int(ticks.shape[0])
        first_tick, last_tick = float(ticks[0]), float(ticks[-1])
        # The whole array, not a prefix: the tutorial sees only three segments, and its
        # span-based rate is right only if no step between them differs.
        tick_steps = np.unique(np.diff(ticks[:]))
        if tick_steps.size != 1:
            raise SystemExit(f"LFP timestamps are not uniformly stepped: {tick_steps[:5]}")
        tick_step = float(tick_steps[0])
        devices = sorted(h["general/devices"].keys())
        if devices != [probe]:
            raise SystemExit(f"LFP asset records devices {devices}, expected [{probe!r}]")
        lel = h["general/extracellular_ephys/electrodes"]
        lfp_ids = lel["id"][:]
        lfp_loc = _text(lel["location"][:])
        region = series["electrodes"][:]
        region_ids = lfp_ids[region]
        channels = np.flatnonzero(np.char.startswith(lfp_loc[region].astype(str), area_prefix))
        channels = channels[::channel_stride]
        if channels.size == 0:
            raise SystemExit(f"no LFP channel location starts with {area_prefix!r}")
        by_id = dict(zip(src["electrodes"]["id"], src["electrodes"]["location"]))
        for cid, loc in zip(region_ids[channels], lfp_loc[region][channels]):
            if by_id.get(cid) != loc:
                raise SystemExit(f"electrode {cid}: LFP asset says {loc!r}, units asset "
                                 f"says {by_id.get(cid)!r}")
        # The builder needs a clock only to decide which samples cover the block window. It is
        # derived here the same way the tutorial derives it, from the recording's edges, and the
        # window is padded so that a residual of tens of milliseconds cannot clip it.
        tick_rate = (last_tick - first_tick) / (last_spike - first_spike)
        fs_est = tick_rate / tick_step
        margin = int(np.ceil(0.5 * fs_est))
        n_edge = int(round(edge_s * fs_est))
        k0 = max(int(np.floor((w0 - first_spike) * fs_est)) - margin, 0)
        k1 = min(int(np.ceil((w1 - first_spike) * fs_est)) + margin, n)
        sample_ranges = {"start": (0, n_edge), "window": (k0, k1), "end": (n - n_edge, n)}
        lfp = {}
        for name, (a, b) in sample_ranges.items():
            data = series["data"][a:b, :][:, channels].astype(np.float32)
            lfp[name] = (data, np.asarray(ticks[a:b], dtype=np.float64))
        unit_attr = series["data"].attrs
        lfp_meta = {"unit": str(unit_attr["unit"]), "conversion": float(unit_attr["conversion"]),
                    "offset": float(unit_attr.get("offset", 0.0))}
        timestamps_unit_label = str(ticks.attrs.get("unit", ""))

    _write_nwb(out, src, windows_s, keep_rows, lfp, region_ids[channels], lfp_meta, probe)

    size = out.stat().st_size
    provenance = {
        "dandiset": DANDISET,
        "assets": {k: {**ASSETS[k], "sha256_verified_locally": digests[k]} for k in ASSETS},
        "builder": "scripts/build_open_data_excerpt.py",
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software": {"python": sys.version.split()[0], "numpy": np.__version__,
                     "h5py": h5py.__version__, "pynwb": __import__("pynwb").__version__},
        "selection": {
            "probe": probe,
            "lfp_area_prefix": area_prefix,
            "lfp_channel_stride": channel_stride,
            "stimulus_block": block,
            "n_units": int(len(trains)),
            "n_electrodes": int(src["electrodes"]["id"].size),
            "lfp_channel_ids": [int(c) for c in region_ids[channels]],
            "n_grating_rows": int(keep_rows.sum()),
        },
        "windows_spike_clock_s": {"start": list(windows_s[0]), "window": list(windows_s[1]),
                                  "end": list(windows_s[2])},
        "lfp_sample_ranges": {k: list(v) for k, v in sample_ranges.items()},
        "source_values": {
            "lfp_n_samples": n,
            "lfp_first_timestamp": first_tick,
            "lfp_last_timestamp": last_tick,
            "lfp_timestamp_step": tick_step,
            "lfp_timestamp_step_is_uniform_over_all_samples": True,
            "lfp_timestamps_unit_label": timestamps_unit_label,
            "probe_first_spike_s": first_spike,
            "probe_last_spike_s": last_spike,
            "declared_rates_hz": src["declared"],
        },
        "builder_clock_estimate": {
            "note": "used only to choose the window's samples; the tutorial re-derives it",
            "tick_rate_per_s": tick_rate,
            "lfp_rate_hz": fs_est,
        },
        "excerpt": {"path": "examples/data/" + out.name, "size_bytes": size,
                    "sha256": sha256_of(out)},
    }
    prov_path = out.with_name(out.name.replace(".nwb", ".provenance.json"))
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out} ({size / 1e6:.2f} MB) and {prov_path.name}")
    return provenance


def _write_nwb(out: Path, src: dict, windows_s, keep_rows, lfp: dict, lfp_ids, lfp_meta,
               probe: str) -> None:
    from hdmf.backends.hdf5.h5_utils import H5DataIO
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import LFP, ElectricalSeries
    from pynwb.epoch import TimeIntervals
    from pynwb.file import Subject

    session = src["session"]
    start = datetime.fromisoformat(session["session_start_time"])
    nwb = NWBFile(
        session_description=(
            f"Excerpt of DANDI:{DANDISET['identifier'].split(':')[1]} version "
            f"{DANDISET['version']}, session {session['identifier']}, {probe} only. "
            f"License {DANDISET['license']}; cite {DANDISET['doi']}."
        ),
        identifier=f"{session['identifier']}-{probe}-excerpt",
        session_start_time=start,
        timestamps_reference_time=start,
        institution=session["institution"],
        experiment_description=session["stimulus"],
        session_id=session["identifier"],
        subject=Subject(**src["subject"]),
    )
    declared = src["declared"]
    device = nwb.create_device(
        name=probe,
        description=f"{session['device_description']} ({session['device_manufacturer']})",
    )
    group = nwb.create_electrode_group(
        name=probe, device=device, location="See electrode locations",
        description=(
            f"Source metadata declares device sampling_rate={declared['device_sampling_rate_hz']} "
            f"and lfp_sampling_rate={declared['electrode_group_lfp_sampling_rate_hz']}."
        ),
    )
    el = src["electrodes"]
    for name, desc in (
        ("probe_vertical_position", "Length-wise position of the contact on the probe (microns)"),
        ("probe_horizontal_position", "Width-wise position of the contact on the probe (microns)"),
        ("local_index", "Index of the contact on its probe"),
        ("valid_data", "Whether the source marks this contact's data usable"),
    ):
        nwb.add_electrode_column(name=name, description=desc)
    for i in range(el["id"].size):
        nwb.add_electrode(
            id=int(el["id"][i]), group=group, location=str(el["location"][i]),
            filtering=str(el["filtering"][i]),
            x=float(el["x"][i]), y=float(el["y"][i]), z=float(el["z"][i]),
            probe_vertical_position=int(el["probe_vertical_position"][i]),
            probe_horizontal_position=int(el["probe_horizontal_position"][i]),
            local_index=int(el["local_index"][i]), valid_data=bool(el["valid_data"][i]),
        )

    col_desc = {
        "cluster_id": "Spike-sorter cluster id",
        "peak_channel_id": "Electrode id of the contact with the largest waveform",
        "quality": "Source curation label",
        "snr": "Waveform signal-to-noise ratio, computed by the source over the full session",
        "isi_violations": "ISI violation rate, computed by the source over the full session",
        "presence_ratio": "Presence ratio, computed by the source over the full session",
        "amplitude_cutoff": "Amplitude cutoff, computed by the source over the full session",
    }
    for name in UNIT_COLUMNS:
        nwb.add_unit_column(name=name, description=col_desc[name])
    obs = [list(w) for w in windows_s]
    for j, train in enumerate(src["trains"]):
        kept = np.concatenate([train[(train >= a) & (train <= b)] for a, b in windows_s])
        row = {name: _py(src["columns"][name][j]) for name in UNIT_COLUMNS}
        nwb.add_unit(id=int(src["unit_ids"][j]), spike_times=kept, obs_intervals=obs, **row)

    g = src["gratings"]
    table = TimeIntervals(
        name="init_grating_presentations",
        description="Grating presentations of the source table inside the excerpt window",
    )
    for name in GRATING_COLUMNS:
        table.add_column(name=name, description=f"Copied from the source column '{name}'")
    for r in np.flatnonzero(keep_rows):
        row = {name: _py(g[name][r]) for name in GRATING_COLUMNS}
        table.add_row(id=int(g["id"][r]), start_time=float(g["start_time"][r]),
                      stop_time=float(g["stop_time"][r]), **row)
    nwb.add_time_intervals(table)

    nwb.units.spike_times.set_data_io(H5DataIO, {"compression": "gzip",
                                                 "compression_opts": 6, "shuffle": True})

    rows = [int(np.flatnonzero(el["id"] == cid)[0]) for cid in lfp_ids]
    container = LFP(name="probe_1_lfp")
    nwb.add_acquisition(container)
    for name, (data, ticks) in lfp.items():
        region = nwb.create_electrode_table_region(rows, f"{probe} LFP channels in the excerpt")
        container.add_electrical_series(ElectricalSeries(
            name=f"probe_1_lfp_{name}",
            data=H5DataIO(data, compression="gzip", compression_opts=6, shuffle=True),
            timestamps=H5DataIO(ticks, compression="gzip", compression_opts=6, shuffle=True),
            electrodes=region,
            conversion=lfp_meta["conversion"],
            offset=lfp_meta["offset"],
            description=f"Source LFP, {name} segment; timestamps copied verbatim",
        ))

    out.parent.mkdir(parents=True, exist_ok=True)
    with NWBHDF5IO(str(out), "w") as io:
        io.write(nwb)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="directory holding the two source assets")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--probe", default="probeB")
    parser.add_argument("--area-prefix", default="VISpm",
                        help="keep LFP channels whose location starts with this")
    parser.add_argument("--channel-stride", type=int, default=2,
                        help="keep every n-th of those channels, in probe order")
    parser.add_argument("--block", type=float, default=1.0,
                        help="stimulus_block of the grating table to excerpt")
    parser.add_argument("--pad-s", type=float, default=1.0)
    parser.add_argument("--edge-s", type=float, default=10.0)
    parser.add_argument("--skip-hash", action="store_true",
                        help="skip source verification; the provenance then records no digest")
    args = parser.parse_args(argv)
    build(args.source_dir, args.out, args.probe, args.area_prefix, args.channel_stride,
          args.block, args.pad_s, args.edge_s, args.skip_hash)
    return 0


if __name__ == "__main__":
    sys.exit(main())
