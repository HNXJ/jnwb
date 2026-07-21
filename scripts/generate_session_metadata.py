"""
generate_session_metadata.py — Session Unit Metadata Tables A and B Generator
Generates Table A (primary metrics) and Table B (advanced metrics + classifications)
for all 17 NWB sessions, saving them under D:\\workspace\\data\\metadata\\.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import h5py

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
GRAND_TABLE_CSV = REPO_ROOT / "outputs/classification/grand_unit_table_shuffle_sso.csv"
METADATA_DIR = Path("D:/workspace/data/metadata")

def get_probe_letter(probe_name: str) -> str:
    """Map probeA/probeB/probeC to A/B/C."""
    if not isinstance(probe_name, str):
        return ""
    if "probeA" in probe_name:
        return "A"
    elif "probeB" in probe_name:
        return "B"
    elif "probeC" in probe_name:
        return "C"
    return probe_name

def coerce_to_int_ch(val) -> int:
    """Safely coerce any input to an integer channel ID."""
    if val is None or pd.isna(val):
        return -1
    if isinstance(val, bytes):
        val = val.decode('utf-8')
    val_str = str(val).strip()
    if val_str.lower() in ["nan", "null", "none", ""]:
        return -1
    try:
        return int(float(val_str))
    except Exception:
        return -1

def load_metadata_via_h5py(nwb_path: Path):
    """Load units and electrodes DataFrames directly from NWB via h5py."""
    with h5py.File(str(nwb_path), "r") as f:
        # Load units columns
        units_group = f["units"]
        units_df = pd.DataFrame()
        
        # Read id
        unit_ids = units_group["id"][:]
        units_df["id"] = unit_ids
        
        for k in units_group.keys():
            if k in ["spike_times", "spike_times_index", "waveform_mean", "spike_amplitudes"]:
                continue
            val = units_group[k][:]
            # Decode bytes if needed
            if val.dtype.kind in ['S', 'O', 'U']:
                val = [v.decode('utf-8') if isinstance(v, bytes) else v for v in val]
            units_df[k] = val
            
        # Load electrodes columns
        elec_group = f["general/extracellular_ephys/electrodes"]
        electrodes = pd.DataFrame()
        elec_ids = elec_group["id"][:]
        electrodes["id"] = elec_ids
        
        for k in elec_group.keys():
            val = elec_group[k][:]
            if val.dtype.kind in ['S', 'O', 'U']:
                val = [v.decode('utf-8') if isinstance(v, bytes) else v for v in val]
            electrodes[k] = val
            
        electrodes.set_index("id", inplace=True)
        
    return units_df, electrodes

def main():
    if not READINESS_CSV.exists():
        print(f"Readiness CSV not found at {READINESS_CSV}")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    grand = pd.read_csv(GRAND_TABLE_CSV) if GRAND_TABLE_CSV.exists() else None
    
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Looping over {len(readiness)} sessions...")
    
    for _, row in readiness.iterrows():
        stem = row["stem"]
        nwb_path = Path(row["nwb_path"])
        
        if not nwb_path.exists():
            print(f"Skipping {stem}: NWB file not found at {nwb_path}")
            continue
            
        print(f"Processing session: {stem}...")
        
        try:
            units_df, electrodes = load_metadata_via_h5py(nwb_path)
                
            # Construct Table A in NWB index order
            table_a = pd.DataFrame()
            table_a["unit_index"] = range(len(units_df))
            # Some sessions use 'id' as index, others as column. Coerce safely.
            table_a["unit_id"] = units_df.index if units_df.index.name == "id" else units_df["id"] if "id" in units_df.columns else range(len(units_df))
            
            # Map electrode group / probe attributes
            peak_ch_ids = units_df["peak_channel_id"].values
            
            probe_ids = []
            local_channels = []
            areas = []
            
            for ch_raw in peak_ch_ids:
                ch_id = coerce_to_int_ch(ch_raw)
                if ch_id in electrodes.index:
                    elec_row = electrodes.loc[ch_id]
                    probe_ids.append(get_probe_letter(elec_row.get("probe", "")))
                    local_channels.append(ch_id % 128)
                    areas.append(elec_row.get("location", ""))
                else:
                    probe_ids.append("")
                    local_channels.append(-1)
                    areas.append("")
                    
            table_a["probe_id"] = probe_ids
            table_a["peak_channel_id"] = peak_ch_ids
            table_a["local_channel"] = local_channels
            table_a["area"] = areas
            
            # Primary metrics
            table_a["quality"] = units_df.get("quality", np.nan).values
            table_a["firing_rate"] = units_df.get("firing_rate", np.nan).values
            table_a["snr"] = units_df.get("snr", np.nan).values
            table_a["presence_ratio"] = units_df.get("presence_ratio", np.nan).values
            table_a["waveform_duration"] = units_df.get("waveform_duration", np.nan).values
            
            # Construct Table B
            table_b = table_a.copy()
            
            # Advanced metrics
            table_b["PT_ratio"] = units_df.get("PT_ratio", np.nan).values
            table_b["amplitude"] = units_df.get("amplitude", np.nan).values
            table_b["isolation_distance"] = units_df.get("isolation_distance", np.nan).values
            table_b["silhouette_score"] = units_df.get("silhouette_score", np.nan).values
            table_b["d_prime"] = units_df.get("d_prime", np.nan).values
            table_b["isi_violations"] = units_df.get("isi_violations", np.nan).values
            
            # Merge with grand classification table on unit_id
            if grand is not None:
                sub_grand = grand[grand["nwb_stem"] == stem]
                if len(sub_grand) > 0:
                    cols_to_merge = ["unit_id", "display_class", "is_s_plus", "is_s_minus", "is_o_plus"]
                    sub_grand_slice = sub_grand[cols_to_merge]
                    # Merge on unit_id
                    table_b = pd.merge(table_b, sub_grand_slice, on="unit_id", how="left")
                    # Fill NaNs for sessions not classified
                    table_b["display_class"] = table_b["display_class"].fillna("Other")
                    table_b["is_s_plus"] = table_b["is_s_plus"].fillna(False).astype(bool)
                    table_b["is_s_minus"] = table_b["is_s_minus"].fillna(False).astype(bool)
                    table_b["is_o_plus"] = table_b["is_o_plus"].fillna(False).astype(bool)
                    
            # Save Table A and Table B to D:\workspace\data\metadata\
            a_path = METADATA_DIR / f"{stem}_A.csv"
            b_path = METADATA_DIR / f"{stem}_B.csv"
            
            table_a.to_csv(a_path, index=False)
            table_b.to_csv(b_path, index=False)
            print(f"  Saved Table A to {a_path.name}")
            print(f"  Saved Table B to {b_path.name}")
            
            # Also update existing sidecar units.csv in session folder D:\workspace\data\metadata\<session_stem>/units.csv
            session_folder = METADATA_DIR / stem
            if session_folder.exists():
                sidecar_path = session_folder / "units.csv"
                table_b.to_csv(sidecar_path, index=False)
                print(f"  Improved existing sidecar units.csv at {sidecar_path}")
                
        except Exception as e:
            print(f"Error processing session {stem}: {e}")
            
    print("Metadata Table generation completed successfully.")

if __name__ == "__main__":
    main()
