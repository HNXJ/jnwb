import os
from src.analysis.io.logger import log
from src.f031_spike_phase_locking.analysis import analyze_spike_phase_locking
from src.f031_spike_phase_locking.plot import plot_spike_phase_locking

def run_f031():
    """
    Main execution entry for Figure 31: Spike-Field Phase Locking.
    """
    log.progress("Starting Analysis f031: Spike-Field Phase Locking")
    
    # Analyze SpSAM pipeline outputs
    spsam_dir = "outputs/spsam"
    results = analyze_spike_phase_locking(spsam_dir)
    
    if results:
        output_dir = "outputs/f031_spike_phase_locking"
        os.makedirs(output_dir, exist_ok=True)
        plot_spike_phase_locking(results, output_dir)
        log.progress("Analysis f031 complete.")
    else:
        log.warning("No SpSAM results found to plot for f031.")

if __name__ == "__main__":
    run_f031()
