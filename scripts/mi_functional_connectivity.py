import os
import glob
import time
import h5py
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from concurrent.futures import ProcessPoolExecutor
from src.analysis.io.logger import log

NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/mi_connectivity"
METADATA_CSV = "outputs/spsam/grand_unit_metadata.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 12 conditions mapping
FAMILIES = {
    "A": {
        "codes": {
            "AAAB": [1, 2],
            "AXAB": [3],
            "AAXB": [4],
            "AAAX": [5],
        }
    },
    "B": {
        "codes": {
            "BBBA": [6, 7],
            "BXBA": [8],
            "BBXA": [9],
            "BBBX": [10],
        }
    },
    "R": {
        "codes": {
            "RRRR": list(range(11, 27)),
            "RXRR": list(range(27, 35)),
            "RRXR": [35, 37, 39, 41],
            "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
        }
    }
}

ALL_CONDITIONS = [
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX"
]

# 11 Canonical areas
CANONICAL_AREAS = [
    "V1", "V2", "V3", "V3a", "V3d", "V4", "FEF", "PFC", "MT", "MST", "TEO"
]

LAYERS = ["Superficial (L2/3)", "Deep (L5/L6)"]

# 22 Groups mapping
GROUPS_22 = []
for area in CANONICAL_AREAS:
    for layer in LAYERS:
        GROUPS_22.append(f"{area}_{layer}")

def get_onsets(intervals_df, allowed_codes):
    correct_val = pd.to_numeric(intervals_df['correct'], errors='coerce')
    stim_num_val = pd.to_numeric(intervals_df['stimulus_number'], errors='coerce')
    cond_num_val = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce')
    matched = (correct_val == 1.0) & (stim_num_val == 2.0) & (cond_num_val.isin(allowed_codes))
    return intervals_df.loc[matched, 'start_time'].values

def get_nwb_file_map():
    m = {}
    for f in glob.glob(f"{NWB_DIR}/*.nwb"):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m

# Vectorized MI calculation between two matrices
def compute_vectorized_mi_matrix(X, Y, K):
    c11 = X.T @ Y
    c10 = X.T @ (1.0 - Y)
    c01 = (1.0 - X).T @ Y
    c00 = (1.0 - X).T @ (1.0 - Y)
    
    p11 = c11 / K
    p10 = c10 / K
    p01 = c01 / K
    p00 = c00 / K
    
    px1 = np.mean(X, axis=0, keepdims=True).T # (N_x, 1)
    px0 = 1.0 - px1
    py1 = np.mean(Y, axis=0, keepdims=True)   # (1, N_y)
    py0 = 1.0 - py1
    
    mi = np.zeros((X.shape[1], Y.shape[1]), dtype=np.float32)
    
    def add_mi_term(pxy, px, py):
        pprod = px @ py
        pprod = np.maximum(pprod, 1e-12)
        ratio = pxy / pprod
        ratio = np.maximum(ratio, 1e-12)
        term = pxy * np.log2(ratio)
        term[pxy < 1e-12] = 0.0
        return term
        
    mi += add_mi_term(p11, px1, py1)
    mi += add_mi_term(p10, px1, py0)
    mi += add_mi_term(p01, px0, py1)
    mi += add_mi_term(p00, px0, py0)
    
    return np.maximum(mi, 0.0)

# Optimized spike binning function
def bin_spikes(spike_times, onsets, bin_size=0.100, bin_step=0.010, T=600):
    K = len(onsets)
    binned = np.zeros((K, T), dtype=np.float32)
    for k, onset in enumerate(onsets):
        t_min_val = onset - 1.0
        t_max_val = onset + 5.0
        trial_spikes = spike_times[(spike_times >= t_min_val) & (spike_times <= t_max_val)]
        rel_spikes = trial_spikes - onset
        for spk in rel_spikes:
            r = spk + 1.0
            if r < 0:
                continue
            base_idx = int(np.floor(r * 100.0))
            t_start = max(0, base_idx - 9)
            t_end = min(T - 1, base_idx)
            if t_start <= t_end:
                binned[k, t_start:t_end + 1] = 1.0
    return binned

def select_neurons(df):
    df_valid = df[df["is_stable"] & df["layer"].isin(LAYERS)].copy()
    
    df_deep = df_valid[df_valid["layer"] == "Deep (L5/L6)"].copy()
    df_sup = df_valid[df_valid["layer"] == "Superficial (L2/3)"].copy()
    
    df_sup_selected = []
    sup_by_area = {a: df_sup[df_sup["area"] == a].sort_values("snr", ascending=False).to_dict("records") for a in df_sup["area"].unique()}
    areas_sup = sorted(list(sup_by_area.keys()))
    
    while len(df_sup_selected) < 50 and any(len(lst) > 0 for lst in sup_by_area.values()):
        for area in areas_sup:
            if len(df_sup_selected) >= 50:
                break
            if sup_by_area[area]:
                df_sup_selected.append(sup_by_area[area].pop(0))
                
    df_deep_selected = []
    deep_by_area = {a: df_deep[df_deep["area"] == a].sort_values("snr", ascending=False).to_dict("records") for a in df_deep["area"].unique()}
    areas_deep = sorted(list(deep_by_area.keys()))
    
    while len(df_deep_selected) < 50 and any(len(lst) > 0 for lst in deep_by_area.values()):
        for area in areas_deep:
            if len(df_deep_selected) >= 50:
                break
            if deep_by_area[area]:
                df_deep_selected.append(deep_by_area[area].pop(0))
                
    selected = pd.DataFrame(df_sup_selected + df_deep_selected)
    return selected

# Global worker job for pickling compatibility
def worker_job(task):
    cond_idx, t, sess_id_str, X, Y, K = task
    mi_mat = compute_vectorized_mi_matrix(X, Y, K)
    return cond_idx, t, sess_id_str, mi_mat

def main():
    t_start_all = time.time()
    
    if not os.path.exists(METADATA_CSV):
        print("Metadata file not found.")
        return
        
    metadata = pd.read_csv(METADATA_CSV)
    selected_units = select_neurons(metadata)
    selected_units.to_csv(os.path.join(OUTPUT_DIR, "selected_neurons.csv"), index=False)
    print(f"Selected {len(selected_units)} neurons: {len(selected_units[selected_units['layer'] == 'Superficial (L2/3)'])} superficial, {len(selected_units[selected_units['layer'] == 'Deep (L5/L6)'])} deep.")
    
    nwb_map = get_nwb_file_map()
    session_data = {}
    grouped_units = selected_units.groupby("session_id")
    
    T = 600
    
    log.action("Loading spike times and binning trials...")
    for sess_id, sess_units in grouped_units:
        sess_id_str = str(sess_id)
        if sess_id_str not in nwb_map:
            print(f"Session {sess_id_str} NWB not found.")
            continue
        
        nwb_path = nwb_map[sess_id_str]
        print(f"Processing session {sess_id_str} with {len(sess_units)} selected units...")
        
        with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
            nwb = io.read()
            intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
            units_df = nwb.units.to_dataframe()
            
            session_data[sess_id_str] = {}
            
            for cond_idx, cond in enumerate(ALL_CONDITIONS):
                codes = None
                for fam_name, fam_cfg in FAMILIES.items():
                    if cond in fam_cfg["codes"]:
                        codes = fam_cfg["codes"][cond]
                        break
                
                ons = get_onsets(intervals_df, codes)
                if len(ons) == 0:
                    continue
                
                K_trials = min(40, len(ons))
                ons = ons[:K_trials]
                
                N_sess_units = len(sess_units)
                binned = np.zeros((K_trials, N_sess_units, T), dtype=np.float32)
                
                for u_idx, (_, u_row) in enumerate(sess_units.iterrows()):
                    uid = int(u_row["unit_id"])
                    spike_times = units_df.loc[uid, "spike_times"]
                    binned[:, u_idx, :] = bin_spikes(spike_times, ons, T=T)
                
                session_data[sess_id_str][cond] = binned

    tau = 1
    N_total = len(selected_units)
    conn_tensor = np.zeros((N_total, N_total, len(ALL_CONDITIONS), T), dtype=np.float32)
    
    tasks = []
    
    log.action("Preparing parallel mutual information jobs...")
    for cond_idx, cond in enumerate(ALL_CONDITIONS):
        for t in range(tau, T):
            for sess_id_str, sess_units in grouped_units:
                sess_id_str = str(sess_id_str)
                if cond not in session_data[sess_id_str]:
                    continue
                
                binned = session_data[sess_id_str][cond] # (K_trials, N_sess_units, T)
                K_trials = binned.shape[0]
                
                X = binned[:, :, t]
                Y = binned[:, :, t - tau]
                
                tasks.append((cond_idx, t, sess_id_str, X, Y, K_trials))
                
    log.action(f"Launching {len(tasks)} mutual information slices using ProcessPoolExecutor...")
    t_start_calc = time.time()
    
    with ProcessPoolExecutor(max_workers=12) as executor:
        results = executor.map(worker_job, tasks, chunksize=100)
        
        sess_to_global_indices = {}
        for sess_id_str, sess_units in grouped_units:
            sess_id_str = str(sess_id_str)
            global_indices = []
            for _, u_row in sess_units.iterrows():
                g_idx = selected_units[(selected_units["session_id"] == u_row["session_id"]) & 
                                       (selected_units["unit_id"] == u_row["unit_id"])].index[0]
                global_indices.append(g_idx)
            sess_to_global_indices[sess_id_str] = global_indices
            
        for cond_idx, t, sess_id_str, mi_mat in results:
            g_indices = sess_to_global_indices[sess_id_str]
            for i_local, i_global in enumerate(g_indices):
                for j_local, j_global in enumerate(g_indices):
                    conn_tensor[i_global, j_global, cond_idx, t] = mi_mat[i_local, j_local]

    t_calc = time.time() - t_start_calc
    print(f"Completed MI computations in {t_calc:.2f} seconds.")

    log.action("Computing group-to-group (22 in 22) connectivity...")
    group_conn = np.zeros((22, 22, len(ALL_CONDITIONS), T), dtype=np.float32)
    
    unit_groups = []
    for _, u_row in selected_units.iterrows():
        g_name = f"{u_row['area']}_{u_row['layer']}"
        if g_name in GROUPS_22:
            unit_groups.append(GROUPS_22.index(g_name))
        else:
            unit_groups.append(-1)
            
    unit_groups = np.array(unit_groups)
    
    for gi in range(22):
        i_mask = unit_groups == gi
        if not np.any(i_mask):
            continue
        for gj in range(22):
            j_mask = unit_groups == gj
            if not np.any(j_mask):
                continue
            
            sub_mat = conn_tensor[np.ix_(np.where(i_mask)[0], np.where(j_mask)[0])]
            
            same_session_mask = np.zeros((np.sum(i_mask), np.sum(j_mask)), dtype=bool)
            gi_indices = np.where(i_mask)[0]
            gj_indices = np.where(j_mask)[0]
            for i_idx, i_g in enumerate(gi_indices):
                sess_i = selected_units.loc[i_g, "session_id"]
                for j_idx, j_g in enumerate(gj_indices):
                    sess_j = selected_units.loc[j_g, "session_id"]
                    if sess_i == sess_j:
                        same_session_mask[i_idx, j_idx] = True
            
            if np.any(same_session_mask):
                for cond_idx in range(len(ALL_CONDITIONS)):
                    for t in range(T):
                        vals = sub_mat[:, :, cond_idx, t][same_session_mask]
                        group_conn[gi, gj, cond_idx, t] = np.mean(vals)
            else:
                group_conn[gi, gj, :, :] = 0.0

    h5_path = os.path.join(OUTPUT_DIR, "mi_functional_connectivity.h5")
    log.action(f"Saving tensors to HDF5 at {h5_path}...")
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("neuron_connectivity", data=conn_tensor, compression="gzip", compression_opts=4)
        f.create_dataset("group_connectivity", data=group_conn, compression="gzip", compression_opts=4)
        f.create_dataset("group_names", data=np.array(GROUPS_22, dtype="S"))
        neuron_ids = selected_units["unit_id"].values
        sessions = selected_units["session_id"].values.astype("S")
        areas = selected_units["area"].values.astype("S")
        layers = selected_units["layer"].values.astype("S")
        f.create_dataset("neuron_id", data=neuron_ids)
        f.create_dataset("neuron_session", data=sessions)
        f.create_dataset("neuron_area", data=areas)
        f.create_dataset("neuron_layer", data=layers)

    t_total = time.time() - t_start_all
    print(f"Functional connectivity analysis finished successfully in {t_total:.2f} seconds.")

if __name__ == '__main__':
    main()
