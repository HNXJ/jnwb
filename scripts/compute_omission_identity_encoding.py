#!/usr/bin/env python3
"""
Compute Omission Identity ("what was omitted?") Noise-Controlled Decoding & GLMM Encoding.

Contrasts:
  - Omitted A (AXAB) vs. Omitted B (BXBA) at Slot P2 (1031-1562 ms)
  - Omitted A (AAXB) vs. Omitted B (BBXA) at Slot P3 (2062-2593 ms)
  - Omitted A (AAAX) vs. Omitted B (BBBX) at Slot P4 (3093-3624 ms)

Outputs:
  - outputs/classification/omission_identity_decoding_master.csv
  - outputs/classification/omission_identity_timecourse_master.csv
  - outputs/classification/omission_identity_glmm_coefficients.csv
"""

from __future__ import annotations

import os
import sys
import pathlib
import time
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa
from jnwb.omission_identity import (
    OMISSION_IDENTITY_CONDITIONS,
    decode_omission_identity_slot,
    build_noise_controlled_spike_matrix,
)

OUT_DIR = REPO_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DECODING_CSV = OUT_DIR / "omission_identity_decoding_master.csv"
TIMECOURSE_CSV = OUT_DIR / "omission_identity_timecourse_master.csv"
GLMM_CSV = OUT_DIR / "omission_identity_glmm_coefficients.csv"

AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]

# Time windows for timecourse (-500 to 4124 ms)
WIN_START = -500.0
WIN_END = 4124.0
WIN_SIZE = 100.0
WIN_STEP = 25.0
TIME_CENTERS = np.arange(WIN_START + WIN_SIZE / 2.0, WIN_END - WIN_SIZE / 2.0 + WIN_STEP, WIN_STEP)


def main():
    t0 = time.time()
    nwb_dir = pathlib.Path(r"D:\analysis\nwb")
    nwb_files = sorted(list(nwb_dir.glob("*.nwb")))
    
    print(f"Found {len(nwb_files)} NWB files in {nwb_dir}.")
    
    slot_results = []
    tc_results = []
    glmm_rows = []
    
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] Processing session {stem}...")
        
        session = oa.read(nwb_path)
        
        # 1. Slot-by-Slot Noise-Controlled Decoding
        for slot_key, cfg in OMISSION_IDENTITY_CONDITIONS.items():
            win_ms = (cfg["slot_onset_ms"], cfg["slot_end_ms"])
            for area in AREAS:
                res = decode_omission_identity_slot(
                    session=session,
                    area=area,
                    slot_key=slot_key,
                    contrast=("A", "B"),
                    time_window_ms=win_ms,
                    n_splits=5,
                    n_permutations=100,
                    random_state=42,
                )
                res["session"] = stem
                slot_results.append(res)
                
        # 2. Time-resolved Decoding (AXAB vs BXBA at P2)
        epochs_axab = session.get_epochs(condition="AXAB")
        epochs_bxba = session.get_epochs(condition="BXBA")
        
        for area in AREAS:
            units_df = session.get_units(area=area)
            if len(units_df) < 2:
                continue
                
            for t_c in TIME_CENTERS:
                w_start = t_c - WIN_SIZE / 2.0
                w_end = t_c + WIN_SIZE / 2.0
                
                X, labels, u_ids = build_noise_controlled_spike_matrix(
                    session, area, epochs_axab, epochs_bxba, (w_start, w_end), random_state=42
                )
                
                if len(u_ids) < 2 or len(labels) < 6:
                    continue
                    
                # Fast 5-fold CV score
                clf = LogisticRegression(C=1.0, max_iter=200)
                scaler = StandardScaler()
                
                from sklearn.model_selection import cross_val_score
                X_scaled = scaler.fit_transform(X)
                cv_accs = cross_val_score(clf, X_scaled, labels, cv=3)
                
                tc_results.append({
                    "session": stem,
                    "area": area,
                    "time_ms": t_c,
                    "accuracy": float(np.mean(cv_accs)),
                    "n_units": len(u_ids),
                    "n_trials": len(labels),
                })
                
        # 3. Spatial GLMM Feature Importance
        # Extract features at P2 slot (1031-1562 ms) across all available units
        all_units = session.get_units()
        if len(all_units) >= 4 and len(epochs_axab) >= 3 and len(epochs_bxba) >= 3:
            X_all, labels_all, unit_ids_all = build_noise_controlled_spike_matrix(
                session, "all", epochs_axab, epochs_bxba, (1031.0, 1562.0), random_state=42
            )
            if X_all.shape[1] >= 4:
                scaler = StandardScaler()
                X_s = scaler.fit_transform(X_all)
                clf = LogisticRegression(C=1.0, penalty="l2", random_state=42)
                clf.fit(X_s, labels_all)
                
                coefs = clf.coef_[0]
                for u_idx, u_id in enumerate(unit_ids_all):
                    u_row = all_units[all_units["unit_id"] == u_id].iloc[0]
                    glmm_rows.append({
                        "session": stem,
                        "unit_id": u_id,
                        "area": u_row.get("area", "unknown"),
                        "coefficient_beta": float(coefs[u_idx]),
                        "abs_beta": float(np.abs(coefs[u_idx])),
                        "quality": u_row.get("quality", "unknown"),
                    })

    # Save outputs
    df_slot = pd.DataFrame(slot_results)
    df_slot.to_csv(DECODING_CSV, index=False)
    print(f"Saved slot decoding master table: {DECODING_CSV}")
    
    df_tc = pd.DataFrame(tc_results)
    df_tc.to_csv(TIMECOURSE_CSV, index=False)
    print(f"Saved timecourse decoding master table: {TIMECOURSE_CSV}")
    
    df_glmm = pd.DataFrame(glmm_rows)
    df_glmm.to_csv(GLMM_CSV, index=False)
    print(f"Saved GLMM coefficients master table: {GLMM_CSV}")
    
    print(f"\nTotal calculation completed in {time.time() - t0:.2f} seconds.")

if __name__ == "__main__":
    main()
