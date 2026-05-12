"""
F038 Outlier Audit: RRXR/Omission FB=19.5 Diagnostic
=====================================================
Protocol:
1. Raw Trace Inspection — check for artifacts, clipping, step-functions
2. Trial Count & Subsampling — verify Stable-Plus survival count
3. Lag Distribution — which lag produced the 19.5 F-stat
4. Bootstrap confidence — resample with replacement to check stability
"""
import numpy as np
import pandas as pd
from scipy import linalg
from statsmodels.tsa.stattools import grangercausalitytests
import os
import sys
from pathlib import Path

# Ensure repo root is in path
root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from src.analysis.io.loader import DataLoader
from src.analysis.io.logger import log

def main():
    print(f"""[action] === F038 OUTLIER AUDIT: RRXR/Omission FB=19.5 ===""")
    print(f"""[action] Initializing DataLoader""")
    loader = DataLoader()

    # ========================================================================
    # 1. Raw Trace Inspection
    # ========================================================================
    print(f"""\n{'='*70}""")
    print(f"""[AUDIT-1] RAW TRACE INSPECTION""")
    print(f"""{'='*70}""")

    cond = "RRXR"
    omission_onset = loader.get_omission_onset(cond)
    print(f"""[info] Condition: {cond}, Omission onset: {omission_onset}ms""")

    # Window used in f038
    win_start = 1000 + int(omission_onset)
    win_end = win_start + 500
    print(f"""[info] Omission window: [{win_start}, {win_end}]ms""")

    # Load LFP for V1 and PFC
    print(f"""[action] Loading LFP for V1 and PFC, condition={cond}""")
    lfp_v1 = loader.get_signal(mode="lfp", area="V1", condition=cond, align_to="omission")
    lfp_pfc = loader.get_signal(mode="lfp", area="PFC", condition=cond, align_to="omission")

    if lfp_v1:
        print(f"""[info] V1 LFP: {len(lfp_v1)} sessions""")
        for i, sess in enumerate(lfp_v1):
            print(f"""  Session {i}: shape={sess.shape}, dtype={sess.dtype}""")
            # Check for artifacts
            flat = sess.flatten()
            print(f"""  min={flat.min():.4f}, max={flat.max():.4f}, std={flat.std():.4f}""")
            # Amplifier clipping detection (values at rail)
            clip_threshold = np.percentile(np.abs(flat), 99.9)
            n_clipped = np.sum(np.abs(flat) >= clip_threshold * 0.99)
            print(f"""  Clip check: 99.9th pct={clip_threshold:.4f}, near-rail samples={n_clipped}""")
            # Step function detection (large jumps in np.diff)
            if sess.ndim >= 2:
                mean_trace = np.mean(sess, axis=tuple(range(sess.ndim - 1)))
                diffs = np.diff(mean_trace)
                max_jump = np.max(np.abs(diffs))
                jump_std = np.std(diffs)
                print(f"""  Max single-sample jump: {max_jump:.6f} (std of diffs: {jump_std:.6f})""")
                if max_jump > 5 * jump_std:
                    print(f"""  [WARNING] Step function detected: max_jump/std_ratio = {max_jump/jump_std:.1f}""")
                else:
                    print(f"""  [OK] No step functions detected""")
    else:
        print(f"""[warning] No V1 LFP data""")

    if lfp_pfc:
        print(f"""\n[info] PFC LFP: {len(lfp_pfc)} sessions""")
        for i, sess in enumerate(lfp_pfc):
            print(f"""  Session {i}: shape={sess.shape}, dtype={sess.dtype}""")
            flat = sess.flatten()
            print(f"""  min={flat.min():.4f}, max={flat.max():.4f}, std={flat.std():.4f}""")
            clip_threshold = np.percentile(np.abs(flat), 99.9)
            n_clipped = np.sum(np.abs(flat) >= clip_threshold * 0.99)
            print(f"""  Clip check: 99.9th pct={clip_threshold:.4f}, near-rail samples={n_clipped}""")
            if sess.ndim >= 2:
                mean_trace = np.mean(sess, axis=tuple(range(sess.ndim - 1)))
                diffs = np.diff(mean_trace)
                max_jump = np.max(np.abs(diffs))
                jump_std = np.std(diffs)
                print(f"""  Max jump: {max_jump:.6f} (std: {jump_std:.6f}, ratio: {max_jump/jump_std:.1f})""")

    # ========================================================================
    # 2. Trial Count & Subsampling
    # ========================================================================
    print(f"""\n{'='*70}""")
    print(f"""[AUDIT-2] TRIAL COUNT & SUBSAMPLING""")
    print(f"""{'='*70}""")

    # Load spike data for the FB pathway: PFC_Deep -> V1_Deep
    print(f"""[action] Loading spike data for V1 and PFC, condition={cond}""")
    spk_v1 = loader.get_signal(mode="spk", area="V1", condition=cond, align_to="omission")
    spk_pfc = loader.get_signal(mode="spk", area="PFC", condition=cond, align_to="omission")

    if spk_v1:
        print(f"""[info] V1 spike data: {len(spk_v1)} sessions""")
        for i, sess in enumerate(spk_v1):
            print(f"""  Session {i}: shape={sess.shape} (trials x units x time)""")
            n_trials = sess.shape[0]
            n_units = sess.shape[1] if sess.ndim > 1 else 0
            print(f"""  Trials: {n_trials}, Units: {n_units}""")
            # Check which units are "Deep" (idx >= 64)
            if sess.ndim == 3:
                deep_units = sess[:, 64:, :]  # Deep layer
                n_deep = deep_units.shape[1]
                # Trial-wise firing rate for deep population
                deep_rates = np.sum(deep_units, axis=(1,2)) / (deep_units.shape[2] / 1000.0)
                print(f"""  Deep units: {n_deep}""")
                print(f"""  Deep population FR per trial: mean={np.mean(deep_rates):.2f}, std={np.std(deep_rates):.2f} Hz""")
                # Stable-Plus approximation: trials where all units fire
                active_trials = np.sum(np.sum(deep_units, axis=2) > 0, axis=1)
                print(f"""  Trials with >50% deep units active: {np.sum(active_trials > n_deep * 0.5)}/{n_trials}""")

    if spk_pfc:
        print(f"""\n[info] PFC spike data: {len(spk_pfc)} sessions""")
        for i, sess in enumerate(spk_pfc):
            print(f"""  Session {i}: shape={sess.shape}""")
            n_trials = sess.shape[0]
            n_units = sess.shape[1] if sess.ndim > 1 else 0
            print(f"""  Trials: {n_trials}, Units: {n_units}""")
            if sess.ndim == 3:
                deep_units = sess[:, 64:, :]
                n_deep = deep_units.shape[1]
                deep_rates = np.sum(deep_units, axis=(1,2)) / (deep_units.shape[2] / 1000.0)
                print(f"""  Deep units: {n_deep}""")
                print(f"""  Deep population FR: mean={np.mean(deep_rates):.2f}, std={np.std(deep_rates):.2f} Hz""")

    # ========================================================================
    # 3. Lag Distribution — Reproduce the 19.5 and identify the winning lag
    # ========================================================================
    print(f"""\n{'='*70}""")
    print(f"""[AUDIT-3] LAG DISTRIBUTION ANALYSIS""")
    print(f"""{'='*70}""")

    # Reconstruct the exact population signals used in f038
    print(f"""[action] Reconstructing f038 population signals for RRXR/Omission""")
    # Segment: V1 Deep and PFC Deep
    # V1: source_units for FB are PFC_Deep, target is V1_Deep
    # So we need PFC_Deep -> V1_Deep (the FB pathway that yielded 19.5)

    # Use the same segmentation logic as f038
    v1_units = loader.get_units_by_area("V1")
    pfc_units = loader.get_units_by_area("PFC")
    print(f"""[info] V1 total units: {len(v1_units) if v1_units else 0}""")
    print(f"""[info] PFC total units: {len(pfc_units) if pfc_units else 0}""")

    # Segment into layers (same logic as f038)
    v1_deep = [u for u in (v1_units or []) if int(u.split("-unit")[1]) >= 64]
    pfc_deep = [u for u in (pfc_units or []) if int(u.split("-unit")[1]) >= 64]
    print(f"""[info] V1_Deep: {len(v1_deep)} units""")
    print(f"""[info] PFC_Deep: {len(pfc_deep)} units""")

    # Load unit data and reconstruct population signals
    maxlag = 20
    print(f"""[action] Loading individual unit spike trains for RRXR (maxlag={maxlag})""")

    src_signals = []  # PFC Deep (source of FB)
    tgt_signals = []  # V1 Deep (target of FB)

    for u in pfc_deep[:50]:  # Cap at 50 for diagnostic
        data = loader.load_unit_spikes(u, condition=cond)
        if data is not None:
            if win_end <= data.shape[-1]:
                src_signals.append(data[:, win_start:win_end])

    for u in v1_deep[:50]:
        data = loader.load_unit_spikes(u, condition=cond)
        if data is not None:
            if win_end <= data.shape[-1]:
                tgt_signals.append(data[:, win_start:win_end])

    print(f"""[info] FB: PFC_Deep ({len(src_signals)} units) -> V1_Deep ({len(tgt_signals)} units)""")

    if src_signals and tgt_signals:
        src_pop = np.mean(np.concatenate(src_signals, axis=0), axis=0)
        tgt_pop = np.mean(np.concatenate(tgt_signals, axis=0), axis=0)
        print(f"""[info] Raw population shapes: src={src_pop.shape}, tgt={tgt_pop.shape}""")
        print(f"""[info] src range: [{src_pop.min():.6f}, {src_pop.max():.6f}], var={np.var(src_pop):.8f}""")
        print(f"""[info] tgt range: [{tgt_pop.min():.6f}, {tgt_pop.max():.6f}], var={np.var(tgt_pop):.8f}""")
        
        # Rate-match
        rate_src = np.mean(src_pop)
        rate_tgt = np.mean(tgt_pop)
        print(f"""[info] Pre-match rates: src={rate_src:.6f}, tgt={rate_tgt:.6f}""")
        if rate_src > rate_tgt and rate_src > 0:
            src_pop = src_pop * (rate_tgt / rate_src)
        elif rate_tgt > rate_src and rate_tgt > 0:
            tgt_pop = tgt_pop * (rate_src / rate_tgt)
        
        # Stationarity
        src_d = np.diff(src_pop)
        tgt_d = np.diff(tgt_pop)
        print(f"""[info] Post-diff: src var={np.var(src_d):.8f}, tgt var={np.var(tgt_d):.8f}""")
        
        if np.var(src_d) < 1e-9 or np.var(tgt_d) < 1e-9:
            print(f"""[CRITICAL] Near-zero variance after differencing — the 19.5 may be from numerically degenerate input!""")
        else:
            # Run full GC with per-lag results
            data_gc = np.stack([tgt_d, src_d], axis=1)
            print(f"""[action] Running GC with data shape {data_gc.shape}""")
            
            try:
                gc_res = grangercausalitytests(data_gc, maxlag=maxlag, verbose=False)
                
                print(f"""\n[AUDIT-3] Full Lag Scan Results:""")
                print(f"""{'Lag':>4} {'F-stat':>10} {'p-value':>12} {'df_denom':>10} {'df_num':>8}""")
                print(f"""{'-'*48}""")
                
                best_f = 0.0
                best_p = 1.0
                best_lag = 1
                
                for lag in range(1, maxlag + 1):
                    f_val = gc_res[lag][0]['ssr_ftest'][0]
                    p_val = gc_res[lag][0]['ssr_ftest'][1]
                    df_denom = gc_res[lag][0]['ssr_ftest'][2]
                    df_num = gc_res[lag][0]['ssr_ftest'][3]
                    
                    flag = ""
                    if f_val > 10:
                        flag = " <-- HIGH"
                    if p_val < 0.001:
                        flag += " ***"
                    elif p_val < 0.01:
                        flag += " **"
                    elif p_val < 0.05:
                        flag += " *"
                        
                    print(f"""{lag:>4} {f_val:>10.4f} {p_val:>12.6f} {df_denom:>10.0f} {df_num:>8.0f}{flag}""")
                    
                    if p_val < best_p:
                        best_f = f_val
                        best_p = p_val
                        best_lag = lag
                
                print(f"""\n[result] Optimal: lag={best_lag}, F={best_f:.4f}, p={best_p:.6f}""")
                
                # Volume conduction check
                if best_lag == 1:
                    print(f"""[WARNING] Lag=1 selected (2ms at 500Hz). This is within volume conduction latency.""")
                    print(f"""[WARNING] True top-down neural transmission V1->PFC should require lag >= 3 (6ms+).""")
                elif best_lag <= 2:
                    print(f"""[CAUTION] Lag={best_lag} is borderline. Check if lag=3+ also has significant F.""")
                else:
                    print(f"""[OK] Lag={best_lag} is physiologically plausible for cortico-cortical transmission.""")
                    
            except Exception as e:
                print(f"""[error] GC failed: {e}""")
        
        # ====================================================================
        # 4. Bootstrap Stability
        # ====================================================================
        print(f"""\n{'='*70}""")
        print(f"""[AUDIT-4] BOOTSTRAP STABILITY (100 iterations)""")
        print(f"""{'='*70}""")
        
        n_boot = 100
        boot_f_values = []
        boot_lags = []
        
        # Get trial-level data for bootstrapping
        src_trials = np.concatenate(src_signals, axis=0) if src_signals else np.array([])
        tgt_trials = np.concatenate(tgt_signals, axis=0) if tgt_signals else np.array([])
        n_trials_total = min(src_trials.shape[0], tgt_trials.shape[0]) if len(src_trials) > 0 else 0
        
        print(f"""[info] Total trials for bootstrap: src={src_trials.shape[0] if len(src_trials)>0 else 0}, tgt={tgt_trials.shape[0] if len(tgt_trials)>0 else 0}""")
        
        if n_trials_total >= 10:
            for b in range(n_boot):
                # Resample with replacement
                idx_src = np.random.choice(src_trials.shape[0], src_trials.shape[0], replace=True)
                idx_tgt = np.random.choice(tgt_trials.shape[0], tgt_trials.shape[0], replace=True)
                
                s = np.mean(src_trials[idx_src], axis=0)
                t = np.mean(tgt_trials[idx_tgt], axis=0)
                
                # Rate match
                rs, rt = np.mean(s), np.mean(t)
                if rs > rt and rs > 0: s = s * (rt / rs)
                elif rt > rs and rt > 0: t = t * (rs / rt)
                
                sd = np.diff(s)
                td = np.diff(t)
                
                if np.var(sd) < 1e-9 or np.var(td) < 1e-9:
                    boot_f_values.append(0.0)
                    boot_lags.append(0)
                    continue
                    
                dgc = np.stack([td, sd], axis=1)
                try:
                    gc_b = grangercausalitytests(dgc, maxlag=maxlag, verbose=False)
                    bf, bp, bl = 0, 1, 1
                    for lag in range(1, maxlag + 1):
                        pv = gc_b[lag][0]['ssr_ftest'][1]
                        if pv < bp:
                            bf = gc_b[lag][0]['ssr_ftest'][0]
                            bp = pv
                            bl = lag
                    boot_f_values.append(bf)
                    boot_lags.append(bl)
                except:
                    boot_f_values.append(0.0)
                    boot_lags.append(0)
            
            boot_arr = np.array(boot_f_values)
            lag_arr = np.array(boot_lags)
            
            print(f"""[result] Bootstrap F-stat distribution (n={n_boot}):""")
            print(f"""  Mean:   {np.mean(boot_arr):.4f}""")
            print(f"""  Median: {np.median(boot_arr):.4f}""")
            print(f"""  Std:    {np.std(boot_arr):.4f}""")
            print(f"""  95% CI: [{np.percentile(boot_arr, 2.5):.4f}, {np.percentile(boot_arr, 97.5):.4f}]""")
            print(f"""  Min:    {np.min(boot_arr):.4f}""")
            print(f"""  Max:    {np.max(boot_arr):.4f}""")
            
            # Lag distribution
            print(f"""\n[result] Bootstrap lag distribution:""")
            for lag_val in sorted(set(lag_arr)):
                count = np.sum(lag_arr == lag_val)
                print(f"""  Lag {lag_val}: {count}/{n_boot} ({100*count/n_boot:.0f}%)""")
            
            # Is 19.5 within the bootstrap distribution?
            above_195 = np.sum(boot_arr >= 19.5)
            print(f"""\n[result] Bootstrap iterations with F >= 19.5: {above_195}/{n_boot}""")
            
            if np.std(boot_arr) > np.mean(boot_arr):
                print(f"""[WARNING] High CV ({np.std(boot_arr)/np.mean(boot_arr):.2f}). Result is UNSTABLE.""")
            elif above_195 < 5:
                print(f"""[WARNING] F=19.5 is a rare outlier even under bootstrap. Likely driven by specific trial subset.""")
            else:
                print(f"""[OK] F=19.5 is within the stable range of bootstrap distribution.""")
        else:
            print(f"""[CRITICAL] Insufficient trials ({n_trials_total}) for bootstrap analysis.""")
    else:
        print(f"""[CRITICAL] Could not reconstruct population signals for RRXR/Omission FB pathway.""")

    # ========================================================================
    # 5. Context: Compare RRXR to all other conditions
    # ========================================================================
    print(f"""\n{'='*70}""")
    print(f"""[AUDIT-5] COMPARATIVE CONTEXT""")
    print(f"""{'='*70}""")

    df = pd.read_csv("D:/drive/outputs/oglo-8figs/f038/f038_granger_results.csv")
    fb_vals = df['fb_flow'].values
    print(f"""[info] All FB values across conditions:""")
    print(f"""  Mean: {np.mean(fb_vals):.4f}""")
    print(f"""  Std:  {np.std(fb_vals):.4f}""")
    print(f"""  RRXR/Omission = {19.5074:.4f}""")
    print(f"""  Z-score: {(19.5074 - np.mean(fb_vals)) / np.std(fb_vals):.2f}""")
    print(f"""  Next highest FB: {sorted(fb_vals)[-2]:.4f}""")

    # Check if RRXR/Stimulus is also elevated
    rrxr_stim = df[(df['condition']=='RRXR') & (df['window']=='Stimulus')]['fb_flow'].values[0]
    print(f"""  RRXR/Stimulus FB: {rrxr_stim:.4f}""")
    print(f"""  Omission/Stimulus ratio: {19.5074/rrxr_stim:.1f}x""")

    print(f"""\n{'='*70}""")
    print(f"""[action] === AUDIT COMPLETE ===""")
    print(f"""{'='*70}""")

if __name__ == "__main__":
    main()
