# core
import numpy as np
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.cluster import KMeans
from sklearn.metrics import mutual_info_score
from src.analysis.io.logger import log

def compute_unit_metrics(spk_arr: np.ndarray, baseline_window=(500, 1000), response_window=(1000, 1531)):
    """
    Computes quality metrics for units.
    spk_arr: (trials, units, time)
    Returns: {unit_idx: {"snr": float, "presence": float, "fr": float}}
    """
    n_trials, n_units, n_time = spk_arr.shape
    results = {}
    
    # overall FR (Hz assuming 1000Hz sampling)
    overall_fr = np.mean(spk_arr, axis=(0, 2)) * 1000.0
    
    # Presence Ratio: fraction of trials with at least one spike
    presence_ratio = np.mean(np.any(spk_arr > 0, axis=2), axis=0)
    
    # SNR: (mean response - mean baseline) / std baseline
    # baseline window (e.g., fx)
    fr_base = np.mean(spk_arr[:, :, baseline_window[0]:baseline_window[1]], axis=2) # (trials, units)
    fr_resp = np.mean(spk_arr[:, :, response_window[0]:response_window[1]], axis=2)
    
    m_base = np.mean(fr_base, axis=0)
    s_base = np.std(fr_base, axis=0) + 1e-6
    m_resp = np.mean(fr_resp, axis=0)
    snr = (m_resp - m_base) / s_base
    
    for u in range(n_units):
        results[u] = {
            "snr": float(snr[u]),
            "presence": float(presence_ratio[u]),
            "fr": float(overall_fr[u])
        }
    return results

def compute_mutual_info(spk_binary: np.ndarray, lfp_power: np.ndarray, n_bins=10):
    """
    Computes MI between binary spikes and continuous LFP power.
    spk_binary: (samples,)
    lfp_power: (samples,)
    """
    # Discretize LFP power
    if np.std(lfp_power) < 1e-10: return 0.0
    lfp_bins = np.digitize(lfp_power, bins=np.histogram_bin_edges(lfp_power, bins=n_bins))
    return mutual_info_score(spk_binary, lfp_bins)

def compute_connectivity_matrix(spk_data: np.ndarray, lfp_data: np.ndarray, mode="mi"):
    """
    Generalized connectivity engine.
    spk_data: (samples,) binary or rate
    lfp_data: (samples,) power or phase
    """
    if mode == "mi":
        return compute_mutual_info(spk_data, lfp_data)
    elif mode == "corr":
        return np.corrcoef(spk_data, lfp_data)[0, 1]
    return 0.0

def fast_mi_plugin(x_binary: np.ndarray, y_binned: np.ndarray, n_bins=10):
    """
    Computes MI between a binary vector (spikes) and a discretized continuous vector (LFP bins).
    x_binary: (N_samples,)
    y_binned: (N_samples,) with values in [0, n_bins-1]
    Faster than sklearn's mutual_info_score for this specific case.
    """
    N = len(x_binary)
    if N == 0: return 0.0
    
    # Joint counts (2 x n_bins)
    # x is binary, so we can split y into two groups
    y_x0 = y_binned[x_binary == 0]
    y_x1 = y_binned[x_binary > 0]
    
    c_x0 = np.bincount(y_x0, minlength=n_bins)
    c_x1 = np.bincount(y_x1, minlength=n_bins)
    counts = np.vstack([c_x0, c_x1]) # (2, n_bins)
    
    # Probabilities
    p_xy = counts / N
    p_x = np.sum(p_xy, axis=1, keepdims=True)
    p_y = np.sum(p_xy, axis=0, keepdims=True)
    
    # MI = sum P(x,y) log( P(x,y) / (P(x)P(y)) )
    p_prod = p_x @ p_y
    mask = p_xy > 0
    mi = np.sum(p_xy[mask] * np.log2(p_xy[mask] / p_prod[mask]))
    return max(0.0, float(mi))

def compute_omission_connectivity_tensor(loader, sessions, areas, bands, frame_keys, frames, conditions=["AAAB", "AXAB"], n_bins=10):
    """
    Optimized high-dimensional connectivity engine.
    Pre-bins LFP power and uses fast_mi_plugin.
    """
    from src.analysis.lfp.lfp_preproc import preprocess_lfp
    from src.analysis.lfp.lfp_tfr import get_band_power, compute_multitaper_tfr
    
    all_unit_data = []
    
    for ses in sessions:
        log.info(f"Processing Optimized Connectivity: {ses}")
        
        # PRE-BIN LFP DATA
        # {cond: {fk: {area_band: binned_array(N_samples)}}}
        binned_lfp = {c: {fk: {} for fk in frame_keys} for c in conditions}
        
        for cond in conditions:
            for area_l in areas:
                lfp_matches = loader.get_signal(mode="lfp", condition=cond, area=area_l, session=ses)
                if not lfp_matches: continue
                
                # Preprocess and TFR once per area-condition
                lfp_clean = preprocess_lfp(lfp_matches[0])
                freqs, times, power = compute_multitaper_tfr(lfp_clean) # (trials, freq, time)
                
                for b_name, b_lims in bands.items():
                    pwr = get_band_power(freqs, power, b_lims)[:, 0, :] # (trials, time)
                    
                    # Bin power across all trials/time for this area-band
                    # Discretize using global histogram for this session-cond-area-band
                    pwr_flat = pwr.flatten()
                    if np.std(pwr_flat) < 1e-10:
                        bins = np.zeros_like(pwr_flat, dtype=int)
                    else:
                        bins = np.digitize(pwr_flat, bins=np.histogram_bin_edges(pwr_flat, bins=n_bins))
                    
                    # Reshape and slice into frames
                    bins_reshaped = bins.reshape(pwr.shape)
                    for fk, f_slice in frames.items():
                        binned_lfp[cond][fk][f"{area_l}_{b_name}"] = bins_reshaped[:, f_slice].flatten()
                        
        # PROCESS UNITS
        for area_u in areas:
            spk_filter = loader.get_signal(mode="spk", condition="AAAB", area=area_u, session=ses)
            if not spk_filter: continue
            metrics = compute_unit_metrics(spk_filter[0])
            valid_units = [u for u, m in metrics.items() if m["snr"] > 1.0 and m["presence"] > 0.96 and 2.0 <= m["fr"] <= 20.0]
            
            for u_idx in valid_units:
                u_mi = {c: {fk: {} for fk in frame_keys} for c in conditions}
                for cond in conditions:
                    spk_cond_matches = loader.get_signal(mode="spk", condition=cond, area=area_u, session=ses)
                    if not spk_cond_matches: continue
                    u_spk = spk_cond_matches[0][:, u_idx, :] # (trials, time)
                    
                    for fk, f_slice in frames.items():
                        u_spk_f = u_spk[:, f_slice].flatten()
                        
                        # MI against all pre-binned LFP area-bands
                        for key, lfp_bins_f in binned_lfp[cond][fk].items():
                            u_mi[cond][fk][key] = fast_mi_plugin(u_spk_f, lfp_bins_f, n_bins=n_bins)
                            
                all_unit_data.append({"area": area_u, "mi": u_mi})
                
    # Aggregate results into Area-by-Area matrices
    tensor = {c: {fk: aggregate_connectivity_matrix(all_unit_data, areas, bands.keys(), c, fk) for fk in frame_keys} for c in conditions}
    return tensor, all_unit_data

def aggregate_connectivity_matrix(unit_mi_list, areas, bands, cond, frame):
    """
    Aggregates unit-level MI into an Area-by-Area matrix.
    unit_mi_list: List of {"area": str, "mi": {cond: {frame: {area_band: val}}}}
    Returns: {band: matrix(n_areas, n_areas)}
    """
    n = len(areas)
    area_idx = {a: i for i, a in enumerate(areas)}
    results = {b: np.zeros((n, n)) for b in bands}
    counts = {b: np.zeros((n, n)) for b in bands}
    
    for entry in unit_mi_list:
        u_area = entry["area"]
        if u_area not in area_idx: continue
        i = area_idx[u_area]
        
        mi_map = entry["mi"].get(cond, {}).get(frame, {})
        for area_l in areas:
            if area_l not in area_idx: continue
            j = area_idx[area_l]
            for b in bands:
                key = f"{area_l}_{b}"
                if key in mi_map:
                    results[b][i, j] += mi_map[key]
                    counts[b][i, j] += 1
                    
    # Average
    for b in bands:
        results[b] = np.divide(results[b], counts[b], out=np.zeros_like(results[b]), where=counts[b]>0)
        
    return results

def detect_ramping_units(spk_arr: np.ndarray, window=(1531, 2031)):
    """
    Identifies units with significant anticipatory ramping before an event.
    Calculates the slope of the firing rate in the specified window.
    spk_arr: (trials, units, time)
    """
    n_trials, n_units, n_time = spk_arr.shape
    t = np.arange(window[0], window[1])
    
    slopes = []
    r_squared = []
    
    for u in range(n_units):
        # Mean FR across trials in the window
        y = np.mean(spk_arr[:, u, window[0]:window[1]], axis=0) * 1000.0
        
        # Linear fit
        slope, intercept = np.polyfit(t, y, 1)
        
        # R-squared
        y_pred = slope * t + intercept
        ss_res = np.sum((y - y_pred)**2)
        ss_tot = np.sum((y - np.mean(y))**2) + 1e-10
        r2 = 1 - (ss_res / ss_tot)
        
        slopes.append(slope)
        r_squared.append(r2)
        
    return np.array(slopes), np.array(r_squared)

def classify_omission_units(spk_dict: dict = None, baseline_window=(531, 1031), omission_window=(1031, 1531), rates=None):
    """
    Classifies units as Omission-Positive (O+) based on the prediction error window.
    Supports either a spk_dict (for single array analysis) or pre-calculated rates.
    
    Unified criteria:
    1. Omission rate > 2.0 Hz
    2. Omission rate > 1.2 * Baseline rate (20% increase)
    3. Omission rate - Control rate > 2.0 Hz (Effect size)
    
    NOTE: This is a broad descriptive screen. It is NOT equivalent to robust X-neuron 
    classification. It indicates a candidate omission-sensitive response in a 500ms window.
    """
    if rates is not None:
        om_rate = rates.get('omission', 0)
        base_rate = rates.get('baseline', 0)
        ctrl_rate = rates.get('control', om_rate) # Default to om_rate if no control
        
        is_o_plus = (om_rate > 2.0) and (om_rate > 1.2 * base_rate) and (om_rate - ctrl_rate > 2.0)
        return is_o_plus

    if spk_dict is None or "AXAB" not in spk_dict:
        log.warning("AXAB missing for O+ classification")
        return {}
        
    arr = spk_dict["AXAB"]
    n_trials, n_units, n_time = arr.shape
    
    # Calculate Mean FR in windows
    fr_base = np.mean(arr[:, :, baseline_window[0]:baseline_window[1]], axis=(0, 2)) * 1000.0
    fr_omit = np.mean(arr[:, :, omission_window[0]:omission_window[1]], axis=(0, 2)) * 1000.0
    
    classification = {}
    for u in range(n_units):
        # We don't have control rate here, so we just use base/omit
        is_o_plus = (fr_omit[u] > 1.2 * fr_base[u]) and (fr_omit[u] > 2.0)
        classification[u] = "O+" if is_o_plus else "Other"
        
    return classification

def compute_statistics(data: any, stat_type: str, **kwargs):
    """
    Canonical signal-agnostic statistics computation.
    """
    log.action(f"[action] Computing statistics for type: {stat_type} with args {kwargs}")
    
    if stat_type == "fano":
        log.progress(f"[action] Computing Fano Factor...")
        return _compute_fano(data, **kwargs)
    elif stat_type == "zscore":
        log.progress(f"[action] Computing Z-Score...")
        return _compute_zscore(data, **kwargs)
    elif stat_type == "kmeans":
        log.progress(f"[action] Computing KMeans Clustering...")
        return _compute_kmeans(data, **kwargs)
    elif stat_type == "gmm":
        log.progress(f"[action] Computing Gaussian Mixture Model Clustering...")
        return _compute_gmm(data, **kwargs)
    elif stat_type == "pca":
        log.progress(f"[action] Computing Principal Component Analysis...")
        return _compute_pca(data, **kwargs)
    else:
        log.error(f"[action] Invalid stat_type: {stat_type}")
        raise ValueError(f"Unsupported stat_type: {stat_type}")

def _compute_fano(data, **kwargs):
    """Internal Fano Factor logic."""
    log.action(f"[action] _compute_fano invoked")
    if isinstance(data, np.ndarray):
        var = np.var(data, axis=0)
        mean = np.mean(data, axis=0) + 1e-10
        return var / mean
    return None

def _compute_zscore(data, **kwargs):
    """Internal Z-Score logic."""
    log.action(f"[action] _compute_zscore invoked")
    if isinstance(data, np.ndarray):
        mean = np.mean(data, axis=kwargs.get('axis', 0), keepdims=True)
        std = np.std(data, axis=kwargs.get('axis', 0), keepdims=True) + 1e-10
        return (data - mean) / std
    return None

def _compute_kmeans(data, n_clusters=4, **kwargs):
    log.action(f"[action] _compute_kmeans invoked with {n_clusters} clusters")
    model = KMeans(n_clusters=n_clusters, random_state=kwargs.get('random_state', 42), n_init="auto")
    labels = model.fit_predict(data)
    return labels, model

def _compute_gmm(data, n_components=4, **kwargs):
    log.action(f"[action] _compute_gmm invoked with {n_components} components")
    model = GaussianMixture(n_components=n_components, random_state=kwargs.get('random_state', 42))
    labels = model.fit_predict(data)
    probs = model.predict_proba(data)
    return labels, probs, model

def _compute_pca(data, n_components=0.95, **kwargs):
    log.action(f"[action] _compute_pca invoked with {n_components} components target")
    model = PCA(n_components=n_components, random_state=kwargs.get('random_state', 42))
    reduced_data = model.fit_transform(data)
    return reduced_data, model