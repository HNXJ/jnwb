from pathlib import Path
# beta — restored from git history (commit 90c743d^, deleted 2026-05-05)
from src.analysis.io.loader import DataLoader
from src.analysis.io.logger import log
from src.f030_recurrence_dynamics.analysis import analyze_recurrence_dynamics
from src.f030_recurrence_dynamics.plot import plot_recurrence_dynamics

def run_f030():
    """
    Main execution entry for Figure 30.
    Restored from git history (commit 90c743d^, deleted 2026-05-05 in commit 90c743d).
    """
    log.progress("Starting Analysis f030: Recurrence & Feedback Dynamics")
    loader = DataLoader()
    output_dir = loader.get_output_dir("f030_recurrence_dynamics")

    sessions = ["230629", "230630", "230714", "230719"]
    areas = ["V1", "V4", "PFC", "FEF"]

    results = analyze_recurrence_dynamics(loader, sessions, areas)
    if results:
        plot_recurrence_dynamics(results, output_dir=output_dir)

    log.progress("Analysis f030 complete.")

if __name__ == "__main__":
    run_f030()
