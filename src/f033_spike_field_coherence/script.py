import os
from src.analysis.io.logger import log
from src.f033_spike_field_coherence.analysis import analyze_spike_field_coherence
from src.f033_spike_field_coherence.plot import plot_spike_field_coherence

def run_f033():
    """
    Main execution entry for Figure 33: Spike-Field Coherence.
    """
    log.progress("Starting Analysis f033: Spike-Field Coherence")
    
    # Analyze SpSAM pipeline outputs
    spsam_dir = "outputs/spsam"
    results = analyze_spike_field_coherence(spsam_dir)
    
    if results:
        output_dir = "outputs/f033_spike_field_coherence"
        os.makedirs(output_dir, exist_ok=True)
        plot_spike_field_coherence(results, output_dir)
        log.progress("Analysis f033 complete.")
    else:
        log.warning("No SpSAM results found to plot for f033.")

if __name__ == "__main__":
    run_f033()
