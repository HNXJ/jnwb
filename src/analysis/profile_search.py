import numpy as np
import pandas as pd
from pathlib import Path
from src.analysis.io.loader import DataLoader
from src.analysis.io.logger import log
import scipy.signal as signal

def get_band_power(lfp, fs=1000):
    """Computes power in canonical bands."""
    bands = {'Theta': (4, 8), 'Alpha': (8, 12), 'Beta': (13, 30), 'Gamma': (30, 80)}
    powers = {}
    nyq = 0.5 * fs
    for name, (low, high) in bands.items():
        b, a = signal.butter(3, [low/nyq, high/nyq], btype='band')
        filtered = signal.filtfilt(b, a, lfp, axis=-1)
        powers[name] = np.mean(np.square(filtered), axis=-1)
    return powers

class ProfileSearcher:
    """
    Optimized utility to identify omission-selectivity profiles.
    Uses batch session processing to minimize NPY load overhead.
    """
    
    OMISSION_FAMILIES = {
        'p2': {'omission': ["AXAB", "BXBA", "RXRR"], 'control': ["AAAB", "BBBA", "RRRR"], 'onset': 1031.0},
        'p3': {'omission': ["AAXB", "BBXA", "RRXR"], 'control': ["AAAB", "BBBA", "RRRR"], 'onset': 2062.0},
        'p4': {'omission': ["AAAX", "BBBX", "RRRX"], 'control': ["AAAB", "BBBA", "RRRR"], 'onset': 3093.0}
    }

    def __init__(self, loader=None):
        self.loader = loader or DataLoader()
        self.BASE_OFFSET = 1000

    def _get_windows(self, onset_ms):
        om_start = self.BASE_OFFSET + int(onset_ms)
        return {'omission': slice(om_start, om_start + 515), 'baseline': slice(om_start - 515, om_start)}

    def search_omission_profiles(self, mode="spk", areas=None):
        """Batch-optimized search for omission sensitivity."""
        areas = areas or self.loader.CANONICAL_AREAS
        results = []
        
        # 1. Build a map of session-probe to areas (for LFP which still uses area-based averaging)
        sp_map = {}
        for area in areas:
            for entry in self.loader.area_map.get(area, []):
                key = (entry['session'], entry['probe'])
                if key not in sp_map: sp_map[key] = []
                sp_map[key].append(entry)

        # 2. Iterate through session-probes
        for (ses, probe), entries in sp_map.items():
            print(f"""[action] Processing {mode} batch: Session {ses}, Probe {probe}""")
            
            for family, cfg in self.OMISSION_FAMILIES.items():
                wins = self._get_windows(cfg['onset'])
                
                # Load all conditions for this probe
                om_data = self._load_probe_batch(ses, probe, cfg['omission'], mode)
                ctrl_data = self._load_probe_batch(ses, probe, cfg['control'], mode)
                
                if not om_data or not ctrl_data: continue
                
                if mode == "spk":
                    # SPK: Process ALL units in the probe and resolve their area
                    n_units = om_data[0].shape[1]
                    for u_idx in range(n_units):
                        # Resolve mapping status
                        res_area, status, caveat = self.loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
                        
                        # Filter for requested areas if specified
                        if areas and res_area not in areas:
                            continue
                            
                        uid = f"{ses}-probe{probe}-unit{u_idx}"
                        # Average across trials (0) and time (2) for this unit (1)
                        om_rate = np.mean([np.mean(arr[:, u_idx, wins['omission']]) for arr in om_data]) * 1000
                        ctrl_rate = np.mean([np.mean(arr[:, u_idx, wins['omission']]) for arr in ctrl_data]) * 1000
                        effect = om_rate - ctrl_rate
                        
                        results.append({
                            'type': 'spk', 
                            'id': uid, 
                            'session': ses,
                            'probe': probe,
                            'unit': u_idx,
                            'area': res_area, # Figure-grade area
                            'resolved_area': res_area,
                            'mapping_status': status,
                            'mapping_caveat': caveat,
                            'is_figure_grade': status.startswith("metadata_resolved"),
                            'family': family,
                            'omission_rate': om_rate, 
                            'control_rate': ctrl_rate, 
                            'effect_size': effect,
                            'is_omission_positive': effect > 2.0 and om_rate > 1.0
                        })
                else:
                    # LFP branch (Average across channels in area) - remains based on inherited map
                    for entry in entries:
                        area = entry.get('area') or [a for a, e in self.loader.area_map.items() if any(x == entry for x in e)][0]
                        ch_start, ch_end = entry['start_ch'], entry['end_ch']
                        for b_name in ['Theta', 'Alpha', 'Beta', 'Gamma']:
                            om_p = np.mean([list(get_band_power(np.mean(arr[:, ch_start:ch_end, wins['omission']], axis=(0,1)).reshape(1, -1))[b_name])[0] for arr in om_data])
                            ctrl_p = np.mean([list(get_band_power(np.mean(arr[:, ch_start:ch_end, wins['omission']], axis=(0,1)).reshape(1, -1))[b_name])[0] for arr in ctrl_data])
                            ratio = om_p / ctrl_p if ctrl_p > 0 else 1.0
                            results.append({
                                'type': 'lfp', 'id': f"{area}_{b_name}", 'area': area, 'family': family, 'band': b_name,
                                'omission_power': om_p, 'control_power': ctrl_p, 'ratio': ratio, 'is_suppressed': ratio < 0.8
                            })
        return pd.DataFrame(results)

    def _load_probe_batch(self, ses, probe, conditions, mode):
        """Loads all arrays for a probe-condition set."""
        arrays = []
        for cond in conditions:
            filename = f"ses{ses}-{'units-probe'+str(probe)+'-spk' if mode=='spk' else 'probe'+str(probe)+'-lfp'}-{cond}.npy"
            path = self.loader.data_dir / filename
            if path.exists():
                try:
                    arrays.append(np.load(path, mmap_mode='r'))
                except: pass
        return arrays

    def search_repetition_profiles(self, mode="spk", areas=None):
        """
        Primary analysis for sequence-position scaling (Repetition Profile).
        Compares p3 vs p1 and d3 vs d1 within the same trial/condition.
        Includes activity guards to prevent near-zero denominator artifacts.
        """
        areas = areas or self.loader.CANONICAL_AREAS
        results = []
        
        # Repetition Scaling Families (all are p2 omission sequences)
        families = ["AXAB", "BXBA", "RXRR"]
        
        # Windows (ms relative to BASE_OFFSET)
        wins = {
            'p1': slice(self.BASE_OFFSET, self.BASE_OFFSET + 515),
            'd1': slice(self.BASE_OFFSET + 515, self.BASE_OFFSET + 1031),
            'p3': slice(self.BASE_OFFSET + 2062, self.BASE_OFFSET + 2577),
            'd3': slice(self.BASE_OFFSET + 2577, self.BASE_OFFSET + 3093)
        }
        
        # Activity Guard Threshold (Hz)
        MIN_ACTIVITY = 1.0 
        
        # For repetition, we use the session-probe map to iterate over data
        sp_map = self._get_sp_map(areas)
        for (ses, probe), _ in sp_map.items():
            print(f"""[action] Processing {mode} Repetition batch: Session {ses}, Probe {probe}""")
            
            for cond in families:
                data_list = self._load_probe_batch(ses, probe, [cond], mode)
                if not data_list: continue
                arr = data_list[0] 
                
                if mode == "spk":
                    n_units = arr.shape[1]
                    for u_idx in range(n_units):
                        # Resolve mapping status
                        res_area, status, caveat = self.loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
                        
                        # Filter for requested areas if specified
                        if areas and res_area not in areas:
                            continue
                            
                        uid = f"{ses}-probe{probe}-unit{u_idx}"
                        
                        p1 = np.mean(arr[:, u_idx, wins['p1']]) * 1000
                        d1 = np.mean(arr[:, u_idx, wins['d1']]) * 1000
                        p3 = np.mean(arr[:, u_idx, wins['p3']]) * 1000
                        d3 = np.mean(arr[:, u_idx, wins['d3']]) * 1000
                        
                        # Denominator safety
                        if (p1 + p3) < MIN_ACTIVITY: continue 
                        
                        p3_over_p1 = p3 / p1 if p1 > 0.1 else (p3 / 0.1 if p3 > 0 else 1.0)
                        d3_over_d1 = d3 / d1 if d1 > 0.1 else (d3 / 0.1 if d3 > 0 else 1.0)
                        
                        results.append({
                            'family': cond, 
                            'id': uid, 
                            'session': ses,
                            'probe': probe,
                            'unit': u_idx,
                            'area': res_area,
                            'resolved_area': res_area,
                            'mapping_status': status,
                            'mapping_caveat': caveat,
                            'is_figure_grade': status.startswith("metadata_resolved"),
                            'p1_value': p1, 'p3_value': p3,
                            'd1_value': d1, 'd3_value': d3,
                            'p3_over_p1': p3_over_p1, 'd3_over_d1': d3_over_d1,
                            'p3_minus_p1': p3 - p1, 'd3_minus_d1': d3 - d1,
                            'gt_1': p3_over_p1 > 1.0,
                            'gt_1p5': p3_over_p1 > 1.5,
                            'gt_2': p3_over_p1 > 2.0,
                            'lt_1': p3_over_p1 < 1.0,
                            'lt_0p67': p3_over_p1 < 0.67,
                            'lt_0p5': p3_over_p1 < 0.5,
                            'd_gt_1': d3_over_d1 > 1.0,
                            'd_gt_1p5': d3_over_d1 > 1.5,
                            'd_gt_2': d3_over_d1 > 2.0,
                            'd_lt_1': d3_over_d1 < 1.0,
                            'd_lt_0p67': d3_over_d1 < 0.67,
                            'd_lt_0p5': d3_over_d1 < 0.5
                        })
                else:
                    # LFP branch... (remains simplified for now, uses entries to average)
                    entries = sp_map.get((ses, probe), [])
                    for entry in entries:
                        area = entry['area']
                        # ... existing LFP logic could go here if needed
                        pass
        return pd.DataFrame(results)

    def _get_sp_map(self, areas):
        sp_map = {}
        for area in areas:
            for entry in self.loader.area_map.get(area, []):
                key = (entry['session'], entry['probe'])
                if key not in sp_map: sp_map[key] = []
                # Ensure entry has area field for easier access
                e_copy = entry.copy()
                e_copy['area'] = area
                sp_map[key].append(e_copy)
        return sp_map
