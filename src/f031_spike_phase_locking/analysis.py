import pandas as pd
import numpy as np
import os
from src.analysis.io.logger import log

def analyze_spike_phase_locking(spsam_dir: str = "outputs/spsam"):
    """
    Loads grand_unit_lfp_coupling.csv and computes mean + SEM of PLV across 7 frequency bands.
    Returns nested dictionary of PLV profiles grouped by context and waveform class.
    """
    coupling_path = os.path.join(spsam_dir, "grand_unit_lfp_coupling.csv")
    if not os.path.exists(coupling_path):
        log.warning(f"Grand coupling table not found at {coupling_path}")
        return None
        
    log.info(f"Loading SpSAM coupling data from {coupling_path}")
    df = pd.read_csv(coupling_path)
    
    bands = ["theta", "alpha", "beta1", "beta2", "gamma1", "gamma2", "gamma3"]
    freq_centers = [6.0, 10.0, 16.0, 25.0, 42.5, 72.5, 120.0]
    
    results = {}
    
    # Analyze by Context & Waveform Class
    for context in df["context"].unique():
        results[context] = {}
        for wf in ["narrow", "wide"]:
            sub = df[(df["context"] == context) & (df["wf_class"] == wf)]
            if len(sub) == 0:
                continue
                
            means = []
            sems = []
            for b in bands:
                col = f"{b}_plv"
                vals = sub[col].dropna()
                if len(vals) > 0:
                    means.append(vals.mean())
                    sems.append(vals.std() / np.sqrt(len(vals)))
                else:
                    means.append(0.0)
                    sems.append(0.0)
            
            results[context][wf] = {
                "freqs": freq_centers,
                "plv_mean": np.array(means),
                "plv_sem": np.array(sems),
                "count": len(sub)
            }
            log.action(f"Context: {context} | Class: {wf} | N={len(sub)} units")
            
    return results
