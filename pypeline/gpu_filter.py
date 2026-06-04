import numpy as np
import scipy.signal as signal

try:
    import cupy as cp
    import cupyx.scipy.signal as cupy_signal
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

def get_filter_sos(fs):
    """
    Generate Second-Order Sections (SOS) for Butterworth filters.
    """
    # MUAe Bandpass: 500 - 5000 Hz, 2nd order
    muae_sos = signal.butter(2, [500, 5000], btype='bandpass', fs=fs, output='sos')
    
    # MUAe Lowpass (power): 200 Hz, 4th order
    muae_power_sos = signal.butter(4, 200, btype='low', fs=fs, output='sos')
    
    # LFP Bandpass: 0.1 - 500 Hz, 2nd order
    lfp_sos = signal.butter(2, [0.1, 500], btype='bandpass', fs=fs, output='sos')
    
    return muae_sos, muae_power_sos, lfp_sos

def filter_batch(data, sos, use_gpu=True):
    """
    Filters a 2D data matrix of shape (channels, samples) along the samples axis (axis=1).
    """
    if use_gpu and CUPY_AVAILABLE:
        try:
            # Transfer data and coefficients to GPU
            d_data = cp.asarray(data, dtype=cp.float32)
            d_sos = cp.asarray(sos, dtype=cp.float32)
            # Perform batch zero-phase filtering
            filtered = cupy_signal.sosfiltfilt(d_sos, d_data, axis=1)
            # Gather back to CPU memory
            return cp.asnumpy(filtered)
        except Exception as e:
            print(f"Warning: GPU filtering failed ({e}). Falling back to CPU.")
            
    # CPU fallback using scipy.signal
    return signal.sosfiltfilt(sos, data, axis=1)

def process_channel_batch(raw_data, fs, downsample_factor, use_gpu=True):
    """
    Processes a batch of raw channel data to LFP and MUAe.
    raw_data: shape (channels, samples)
    """
    muae_sos, muae_power_sos, lfp_sos = get_filter_sos(fs)
    
    # 1. Process LFP
    print("Filtering LFP...")
    lfp_filtered = filter_batch(raw_data, lfp_sos, use_gpu=use_gpu)
    # Downsample
    lfp = lfp_filtered[:, ::downsample_factor]
    
    # 2. Process MUAe
    print("Filtering MUAe bandpass...")
    muae_bp = filter_batch(raw_data, muae_sos, use_gpu=use_gpu)
    muae_rectified = np.abs(muae_bp)
    
    print("Filtering MUAe lowpass...")
    muae_lp = filter_batch(muae_rectified, muae_power_sos, use_gpu=use_gpu)
    muae = muae_lp[:, ::downsample_factor]
    
    return lfp, muae
