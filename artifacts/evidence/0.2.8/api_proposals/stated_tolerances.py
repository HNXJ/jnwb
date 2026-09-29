"""Print the docstring paragraphs of each switch-taking export that state a tolerance or device."""
import inspect
import pathlib
import re
import sys

WT = pathlib.Path(r"C:/workspace/jnwb/.claude/worktrees/lane-c-08-06")
sys.path.insert(0, str(WT))
import jnwb  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TARGETS = {
    "ComplexTFR": jnwb.ComplexTFR, "TFRAccumulator": jnwb.TFRAccumulator,
    "UnitAnalyzer.autocorrelogram": jnwb.UnitAnalyzer.autocorrelogram,
    "PopulationAnalyzer.population_trajectory": jnwb.PopulationAnalyzer.population_trajectory,
}
for n in ["band_power", "cluster_permutation_test", "complex_tfr", "compute_population_trajectory",
          "cross_area_coherence", "directed_network", "granger_causality", "harmonic_analysis",
          "imaginary_coherency", "jrsa", "rdm", "relative_power", "spectral_tilt", "vflip",
          "vflip_from_lfp", "wpli"]:
    TARGETS[n] = getattr(jnwb, n)
PAT = re.compile(r"toleran|rtol|atol|bit[- ]for[- ]bit|identical|agree|rounding|n_jobs|device|backend|dtype|precision", re.I)
for name, obj in TARGETS.items():
    doc = inspect.getdoc(obj) or ""
    hits = [" ".join(p.split()) for p in re.split(r"\n\s*\n", doc) if PAT.search(p)]
    print(f"== {name}")
    for h in hits:
        print("   ", h[:500])
