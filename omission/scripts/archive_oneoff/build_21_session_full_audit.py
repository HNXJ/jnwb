import os
import glob
import h5py
import json
import pandas as pd
import numpy as np

# Canonical 12-condition mapping in the omission paradigm
CONDITION_MAP_12 = {
    'AAAB': [1.0, 2.0],
    'AXAB': [3.0],
    'AAXB': [4.0],
    'AAAX': [5.0],
    'BBBA': [6.0, 7.0],
    'BXBA': [8.0],
    'BBXA': [9.0],
    'BBBX': [10.0],
    'RRRR': [float(x) for x in range(11, 27)],
    'RXRR': [float(x) for x in range(27, 35)],
    'RRXR': [35.0, 37.0, 39.0, 41.0],
    'RRRX': [36.0, 38.0, 40.0] + [float(x) for x in range(42, 51)]
}

CODE_TO_COND12 = {}
for cond_name, codes in CONDITION_MAP_12.items():
    for c in codes:
        CODE_TO_COND12[c] = cond_name

ORDERED_AREAS = ['V1', 'V2', 'V3a-d-v', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']


def resolve_ch_area(loc_str, ch_within_probe, n_chs_in_probe):
    """
    Applies canonical dual-area probe slicing rules across 10 ordered separate areas:
    V1, V2, V3a-d-v, V4, MT, MST, TEO, FST, FEF, PFC.
    Replaces DP with V4 wherever it occurs.
    """
    if not loc_str or loc_str == 'nan':
        return 'Unknown'
    
    loc_str = loc_str.replace('DP', 'V4')
    parts = [p.strip() for p in loc_str.replace('/', ',').split(',') if p.strip()]
    
    if len(parts) == 1:
        raw_part = parts[0]
    else:
        half = n_chs_in_probe / len(parts)
        idx = min(int(ch_within_probe // half), len(parts) - 1)
        raw_part = parts[idx]
        
    p_up = raw_part.upper()
    if p_up == 'V1':
        return 'V1'
    elif p_up == 'V2':
        return 'V2'
    elif any(k in p_up for k in ['V3', 'V3D', 'V3A', 'V3V']):
        return 'V3a-d-v'
    elif p_up == 'V4':
        return 'V4'
    elif p_up == 'MT':
        return 'MT'
    elif p_up == 'MST':
        return 'MST'
    elif p_up == 'TEO':
        return 'TEO'
    elif p_up == 'FST':
        return 'FST'
    elif p_up == 'FEF':
        return 'FEF'
    elif p_up == 'PFC':
        return 'PFC'
    return raw_part


def audit_single_nwb(fpath):
    fname = os.path.basename(fpath)
    subject = fname.split('_')[0].replace('sub-', '')
    session_id = fname.replace('.nwb', '')
    file_size_mb = os.path.getsize(fpath) / (1024 * 1024)

    with h5py.File(fpath, 'r') as f:
        # 1. Electrodes & Channels per area
        elec_grp = f['general/extracellular_ephys/electrodes']
        locs_raw = [l.decode('utf-8') if isinstance(l, bytes) else str(l) for l in elec_grp['location'][:]]
        group_names = [g.decode('utf-8') if isinstance(g, bytes) else str(g) for g in elec_grp['group_name'][:]] if 'group_name' in elec_grp else []
        n_electrodes = len(locs_raw)

        probe_ch_counts = {}
        for g in group_names:
            probe_ch_counts[g] = probe_ch_counts.get(g, 0) + 1

        probe_ch_curr = {}
        probe_ch_map = {}
        global_ch_map = {}

        area_elec_counts = {a: 0 for a in ORDERED_AREAS}

        for i, loc_s in enumerate(locs_raw):
            g = group_names[i] if i < len(group_names) else 'probe0'
            ch_within = probe_ch_curr.get(g, 0)
            n_in_p = probe_ch_counts.get(g, 128)
            probe_ch_curr[g] = ch_within + 1

            area = resolve_ch_area(loc_s, ch_within, n_in_p)
            global_ch_map[i] = area
            probe_ch_map[(g, ch_within)] = area
            if area in area_elec_counts:
                area_elec_counts[area] += 1

        # 2. Units & Tiers
        u_grp = f['units']
        n_units = len(u_grp['id'])

        def get_u_arr(col, default_val=0.0):
            if col in u_grp:
                arr = u_grp[col][:]
                if len(arr) > 0 and isinstance(arr[0], bytes):
                    arr = [x.decode('utf-8') for x in arr]
                return np.array(arr, dtype=object)
            return np.array([default_val] * n_units, dtype=object)

        q_raw = get_u_arr('quality', 0.0)
        q_vals = [float(x) if x != 'nan' and x is not None and str(x).replace('.', '', 1).isdigit() else (1.0 if str(x).lower() == 'good' else 0.0) for x in q_raw]

        pr = np.array([float(x) if x != 'nan' and x is not None else 0.0 for x in get_u_arr('presence_ratio', 0.0)])
        fr = np.array([float(x) if x != 'nan' and x is not None else 0.0 for x in get_u_arr('firing_rate', 0.0)])
        snr = np.array([float(x) if x != 'nan' and x is not None else 0.0 for x in get_u_arr('snr', 0.0)])
        isi = np.array([float(x) if x != 'nan' and x is not None else 0.0 for x in get_u_arr('isi_violations', 0.0)])

        eg_raw = get_u_arr('electrode_group', 'probe0')
        pk_raw = get_u_arr('peak_channel_id', 0)
        if len(pk_raw) == 0 or pk_raw[0] == 0:
            pk_raw = get_u_arr('peak_channel', 0)

        unit_areas = {a: 0 for a in ORDERED_AREAS}
        unit_good_areas = {a: 0 for a in ORDERED_AREAS}
        unit_stable_areas = {a: 0 for a in ORDERED_AREAS}
        unit_mua_areas = {a: 0 for a in ORDERED_AREAS}

        n_good_units = 0
        n_stable_units = 0
        n_mua_units = 0

        for u_i in range(n_units):
            eg = str(eg_raw[u_i])
            if hasattr(eg, 'name'): eg = eg.name.split('/')[-1]
            try:
                pk_ch = int(float(str(pk_raw[u_i])))
            except Exception:
                pk_ch = 0

            area = probe_ch_map.get((eg, pk_ch), global_ch_map.get(pk_ch, 'Unknown'))

            is_good = (q_vals[u_i] == 1.0)
            is_stable = (pr[u_i] >= 0.98) and (fr[u_i] > 0.5) and (snr[u_i] > 0.5)
            is_mua = ((fr[u_i] > 5.0) and (isi[u_i] > 0.005) and (pr[u_i] > 0.98)) or (q_vals[u_i] == 0.0)

            if is_good: n_good_units += 1
            if is_stable: n_stable_units += 1
            if is_mua: n_mua_units += 1

            if area in unit_areas:
                unit_areas[area] += 1
                if is_good: unit_good_areas[area] += 1
                if is_stable: unit_stable_areas[area] += 1
                if is_mua: unit_mua_areas[area] += 1

        # 3. Behavioral Epochs / 12-Condition Matrix
        cond_counts = {c: 0 for c in CONDITION_MAP_12.keys()}
        total_correct_trials = 0
        total_raw_rows = 0

        if 'intervals/omission_glo_passive' in f:
            grp = f['intervals/omission_glo_passive']
            total_raw_rows = len(grp['start_time']) if 'start_time' in grp else 0

            def read_col(col_name):
                if col_name in grp:
                    arr = grp[col_name][:]
                    if len(arr) > 0 and isinstance(arr[0], bytes):
                        arr = [x.decode('utf-8') for x in arr]
                    return pd.to_numeric(arr, errors='coerce')
                return np.array([])

            task_cond = read_col('task_condition_number')
            correct = read_col('correct')
            stim_num = read_col('stimulus_number')
            trial_num = read_col('trial_num')

            if len(task_cond) > 0:
                df_intervals = pd.DataFrame({
                    'trial_num': trial_num if len(trial_num) == len(task_cond) else np.arange(len(task_cond)),
                    'task_condition_number': task_cond,
                    'correct': correct if len(correct) == len(task_cond) else 1.0,
                    'stimulus_number': stim_num if len(stim_num) == len(task_cond) else 1.0
                })

                df_correct = df_intervals[df_intervals['correct'] == 1.0]
                df_onsets = df_correct[df_correct['stimulus_number'] == 1.0]
                if len(df_onsets) == 0:
                    df_onsets = df_correct[df_correct['stimulus_number'] == 2.0]

                total_correct_trials = int(len(df_onsets))

                for code, cname in CODE_TO_COND12.items():
                    c_rows = df_onsets[df_onsets['task_condition_number'] == code]
                    cond_counts[cname] += len(c_rows)

    return {
        'session_id': session_id,
        'subject': subject,
        'filename': fname,
        'size_mb': round(file_size_mb, 2),
        'n_total_units': n_units,
        'n_good_units': n_good_units,
        'n_stable_units': n_stable_units,
        'n_mua_units': n_mua_units,
        'unit_areas': unit_areas,
        'unit_good_areas': unit_good_areas,
        'unit_stable_areas': unit_stable_areas,
        'unit_mua_areas': unit_mua_areas,
        'area_elec_counts': area_elec_counts,
        'n_electrodes': n_electrodes,
        'total_correct_trials': total_correct_trials,
        'total_raw_rows': total_raw_rows,
        'cond_counts': cond_counts
    }


def main():
    nwb_files = sorted(glob.glob(r'D:\analysis\nwb\*.nwb'))
    print(f"Auditing all {len(nwb_files)} NWB files with 10 ordered separate areas & quality==1.0...")

    results = []
    for fpath in nwb_files:
        res = audit_single_nwb(fpath)
        results.append(res)

    out_json = r'D:\workspace\omission\artifacts\data\all_21_sessions_audit.json'
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"Saved complete audit JSON -> {out_json}")

if __name__ == '__main__':
    main()
