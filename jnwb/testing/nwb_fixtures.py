"""Deterministic synthetic NWB builders aligned with nwb_structural_authority_0.1.8.md.

Fixture structure (interval tables, acquisition packaging, column names) is separate from
synthetic numerical content (signals, spikes, onset times). All values are analytically known.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence, Union

import numpy as np
import pynwb
from dateutil.tz import tzutc
from pynwb import NWBFile, NWBHDF5IO
from pynwb.epoch import TimeIntervals

# Neutral interval table names (not project-specific omission/RF/flash names).
TASK_TABLE = "test_synth_task"
RF_TABLE = "test_synth_rf"
FLASH_TABLE = "test_synth_flash"

CODE_LABEL_A = "test-synth-1"
CODE_LABEL_B = "test-synth-2"
CODE_NUMERIC_A = 1.0
CODE_NUMERIC_B = 2.0

AcquisitionStyle = Literal["electrical_series", "lfp_wrapped"]
CodesDtype = Literal["string", "numeric"]
IntervalLayout = Literal["co_resident", "task_only"]

DEFAULT_FS_HZ = 1000.0
DEFAULT_N_CHANNELS = 10
DEFAULT_N_EVENTS = 10
DEFAULT_SEED = 0


@dataclass(frozen=True)
class SynthNWBBuildOptions:
    acquisition_style: AcquisitionStyle = "electrical_series"
    codes_dtype: CodesDtype = "string"
    interval_layout: IntervalLayout = "co_resident"
    n_channels: int = DEFAULT_N_CHANNELS
    fs_hz: float = DEFAULT_FS_HZ
    n_events_per_table: int = DEFAULT_N_EVENTS
    seed: int = DEFAULT_SEED


@dataclass(frozen=True)
class SynthNWBReceipt:
    """Analytically known outputs for a built fixture."""

    options: SynthNWBBuildOptions
    task_table: str
    rf_table: str | None
    flash_table: str | None
    interval_table_names: tuple[str, ...]
    task_onsets_s: np.ndarray
    rf_onsets_s: np.ndarray | None
    flash_onsets_s: np.ndarray | None
    task_codes: tuple[Union[str, float], ...]
    rf_codes: tuple[Union[str, float], ...] | None
    flash_codes: tuple[Union[str, float], ...] | None
    fs_hz: float
    n_channels: int
    acquisition_style: AcquisitionStyle
    lfp_acquisition_name: str


def canonical_co_resident_options(**kwargs) -> SynthNWBBuildOptions:
    return SynthNWBBuildOptions(**kwargs)


def lfp_wrapped_options(**kwargs) -> SynthNWBBuildOptions:
    return SynthNWBBuildOptions(acquisition_style="lfp_wrapped", **kwargs)


def numeric_codes_options(**kwargs) -> SynthNWBBuildOptions:
    return SynthNWBBuildOptions(codes_dtype="numeric", **kwargs)


def task_only_options(**kwargs) -> SynthNWBBuildOptions:
    return SynthNWBBuildOptions(interval_layout="task_only", **kwargs)


def _code_pair(dtype: CodesDtype, index: int) -> Union[str, float]:
    even = (index % 2) == 0
    if dtype == "string":
        return CODE_LABEL_A if even else CODE_LABEL_B
    return CODE_NUMERIC_A if even else CODE_NUMERIC_B


def _expected_onsets(base: float, step: float, n: int) -> np.ndarray:
    return base + step * np.arange(n, dtype=np.float64)


def _expected_codes(dtype: CodesDtype, n: int) -> tuple[Union[str, float], ...]:
    return tuple(_code_pair(dtype, i) for i in range(n))


def _synthetic_lfp(
    n_samples: int,
    n_channels: int,
    fs_hz: float,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples, dtype=np.float64) / fs_hz
    data = np.empty((n_samples, n_channels), dtype=np.float32)
    for ch in range(n_channels):
        freq = 8.0 + ch
        phase = rng.uniform(0.0, 2.0 * np.pi)
        data[:, ch] = np.sin(2.0 * np.pi * freq * t + phase).astype(np.float32)
    return data


def _add_electrodes(nwb: NWBFile, n_channels: int) -> pynwb.ElectrodeTable:
    device = nwb.create_device(name="synth_device_0")
    eg = nwb.create_electrode_group(
        name="synth_probe_0",
        description="synthetic probe",
        location="site-0",
        device=device,
    )
    for ch in range(n_channels):
        nwb.add_electrode(
            x=float(ch),
            y=0.0,
            z=float(ch * 10),
            imp=1.0,
            location=f"site-0/layer-{ch % 3}",
            filtering="none",
            group=eg,
        )
    return nwb.electrodes


def _add_lfp_acquisition(
    nwb: NWBFile,
    data: np.ndarray,
    fs_hz: float,
    style: AcquisitionStyle,
) -> str:
    region = nwb.create_electrode_table_region(
        region=list(range(data.shape[1])),
        description="all synthetic electrodes",
    )
    if style == "electrical_series":
        es = pynwb.ecephys.ElectricalSeries(
            name="probe_0_lfp",
            data=data,
            electrodes=region,
            rate=float(fs_hz),
            starting_time=0.0,
        )
        nwb.add_acquisition(es)
        return "probe_0_lfp"
    inner = pynwb.ecephys.ElectricalSeries(
        name="probe_0_lfp_data",
        data=data,
        electrodes=region,
        rate=float(fs_hz),
        starting_time=0.0,
    )
    lfp = pynwb.ecephys.LFP(name="probe_0_lfp")
    lfp.add_electrical_series(inner)
    nwb.add_acquisition(lfp)
    return "probe_0_lfp"


def _add_units(
    nwb: NWBFile,
    spike_times_by_unit: Sequence[Sequence[float]],
    n_channels: int,
) -> None:
    for unit_idx, spike_times in enumerate(spike_times_by_unit):
        nwb.add_unit(
            spike_times=np.asarray(spike_times, dtype=np.float64),
            electrodes=[unit_idx % n_channels],
        )


def _add_task_intervals(
    nwb: NWBFile,
    options: SynthNWBBuildOptions,
    onsets: np.ndarray,
) -> TimeIntervals:
    table = TimeIntervals(name=TASK_TABLE, description="synthetic task-like intervals")
    table.add_column(name="codes", description="event codes")
    table.add_column(name="task_condition_number", description="condition index")
    table.add_column(name="stimulus_number", description="stimulus phase index")
    table.add_column(name="trial_num", description="trial counter")
    table.add_column(name="correct", description="response correctness")
    table.add_column(name="marker_flag", description="neutral boolean marker")
    for i, onset in enumerate(onsets):
        code = _code_pair(options.codes_dtype, i)
        table.add_row(
            start_time=float(onset),
            stop_time=float(onset),
            codes=code,
            task_condition_number=float((i % 2) + 1),
            stimulus_number=float((i % 3) + 1),
            trial_num=float(i + 1),
            correct=1.0,
            marker_flag=float(i % 2),
        )
    nwb.add_time_intervals(table)
    return table


def _add_rf_intervals(
    nwb: NWBFile,
    options: SynthNWBBuildOptions,
    onsets: np.ndarray,
) -> TimeIntervals:
    table = TimeIntervals(name=RF_TABLE, description="synthetic RF-mapping-like intervals")
    for col in (
        "codes",
        "x_position",
        "y_position",
        "x_position_negative",
        "y_position_negative",
        "contrast",
        "size",
        "spatial_frequency",
        "phase",
        "gabor",
        "shape",
        "trial_num",
        "correct",
        "task_sequence",
        "stimulus_number",
    ):
        table.add_column(name=col, description=f"synthetic {col}")
    for i, onset in enumerate(onsets):
        code = _code_pair(options.codes_dtype, i)
        is_stim = (i % 2) == 0
        table.add_row(
            start_time=float(onset),
            stop_time=float(onset),
            codes=code,
            x_position=0.5 if is_stim else np.nan,
            y_position=1.0 if is_stim else np.nan,
            x_position_negative=-0.5 if is_stim else np.nan,
            y_position_negative=-1.0 if is_stim else np.nan,
            contrast=0.8 if is_stim else np.nan,
            size=0.5 if is_stim else np.nan,
            spatial_frequency=2.0 if is_stim else np.nan,
            phase=0.0 if is_stim else np.nan,
            gabor=1.0 if is_stim else np.nan,
            shape=1.0 if is_stim else np.nan,
            trial_num=float(i + 1),
            correct=1.0,
            task_sequence=float((i % 4) + 1),
            stimulus_number=float(1.0) if is_stim else np.nan,
        )
    nwb.add_time_intervals(table)
    return table


def _add_flash_intervals(
    nwb: NWBFile,
    options: SynthNWBBuildOptions,
    onsets: np.ndarray,
    *,
    flash_duration_s: float = 0.05,
) -> TimeIntervals:
    table = TimeIntervals(name=FLASH_TABLE, description="synthetic flash-like intervals")
    for col in (
        "codes",
        "stimulus_number",
        "task_condition_number",
        "trial_num",
        "correct",
        "task_block_number",
    ):
        table.add_column(name=col, description=f"synthetic {col}")
    for i, onset in enumerate(onsets):
        code = _code_pair(options.codes_dtype, i)
        stop = float(onset) + flash_duration_s
        table.add_row(
            start_time=float(onset),
            stop_time=stop,
            codes=code,
            stimulus_number=float((i % 2) + 1),
            task_condition_number=float((i % 2) + 1),
            trial_num=float(i + 1),
            correct=1.0,
            task_block_number=float((i // options.n_events_per_table) + 1),
        )
    nwb.add_time_intervals(table)
    return table


def _add_auxiliary_intervals(nwb: NWBFile, n_rows: int = 3) -> None:
    for name in ("photodiode_1_detected_changes", "reward_1_detected"):
        table = TimeIntervals(name=name, description="synthetic auxiliary events")
        for i in range(n_rows):
            t0 = float(i) * 0.1
            table.add_row(start_time=t0, stop_time=t0)
        nwb.add_time_intervals(table)


def build_synth_nwb(options: SynthNWBBuildOptions | None = None) -> tuple[NWBFile, SynthNWBReceipt]:
    opts = options or SynthNWBBuildOptions()
    n_events = opts.n_events_per_table

    task_onsets = _expected_onsets(1.0, 0.5, n_events)
    rf_onsets = _expected_onsets(10.0, 0.3, n_events)
    flash_onsets = _expected_onsets(20.0, 0.2, n_events)

    last_time = max(
        float(task_onsets[-1]),
        float(rf_onsets[-1]),
        float(flash_onsets[-1]) + 0.05,
    )
    n_samples = int(np.ceil((last_time + 1.0) * opts.fs_hz))

    nwb = NWBFile(
        session_description="Synthetic multi-table NWB for jnwb fixtures",
        identifier="TEST_SYNTH_CANONICAL",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    _add_electrodes(nwb, opts.n_channels)
    lfp = _synthetic_lfp(n_samples, opts.n_channels, opts.fs_hz, opts.seed)
    acq_name = _add_lfp_acquisition(nwb, lfp, opts.fs_hz, opts.acquisition_style)

    spike_times = [
        [float(t + 0.01) for t in task_onsets],
        [float(t + 0.02) for t in flash_onsets],
    ]
    _add_units(nwb, spike_times, opts.n_channels)

    interval_names: list[str] = []
    rf_table: str | None = None
    flash_table: str | None = None
    rf_onsets_out: np.ndarray | None = None
    flash_onsets_out: np.ndarray | None = None
    rf_codes: tuple[Union[str, float], ...] | None = None
    flash_codes: tuple[Union[str, float], ...] | None = None

    _add_task_intervals(nwb, opts, task_onsets)
    interval_names.append(TASK_TABLE)

    if opts.interval_layout == "co_resident":
        _add_rf_intervals(nwb, opts, rf_onsets)
        _add_flash_intervals(nwb, opts, flash_onsets)
        _add_auxiliary_intervals(nwb)
        interval_names.extend([RF_TABLE, FLASH_TABLE, "photodiode_1_detected_changes", "reward_1_detected"])
        rf_table = RF_TABLE
        flash_table = FLASH_TABLE
        rf_onsets_out = rf_onsets
        flash_onsets_out = flash_onsets
        rf_codes = _expected_codes(opts.codes_dtype, n_events)
        flash_codes = _expected_codes(opts.codes_dtype, n_events)

    task_codes = _expected_codes(opts.codes_dtype, n_events)
    receipt = SynthNWBReceipt(
        options=opts,
        task_table=TASK_TABLE,
        rf_table=rf_table,
        flash_table=flash_table,
        interval_table_names=tuple(interval_names),
        task_onsets_s=task_onsets,
        rf_onsets_s=rf_onsets_out,
        flash_onsets_s=flash_onsets_out,
        task_codes=task_codes,
        rf_codes=rf_codes,
        flash_codes=flash_codes,
        fs_hz=opts.fs_hz,
        n_channels=opts.n_channels,
        acquisition_style=opts.acquisition_style,
        lfp_acquisition_name=acq_name,
    )
    return nwb, receipt


def write_synth_nwb(
    path: Union[str, Path],
    options: SynthNWBBuildOptions | None = None,
) -> SynthNWBReceipt:
    nwb, receipt = build_synth_nwb(options)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return receipt
