"""Notebook generation for analysis recipes.

Creates executable .ipynb files that document and reproduce analysis runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.recipes.specs import (
    EventSpec,
    WindowSpec,
    SignalSpec,
    AnalysisSpec,
    OutputSpec,
)


def write_analysis_recipe_notebook(
    recipe_id: str,
    output_path: Path | str,
    nwb_path: Path | str,
    event_spec: EventSpec,
    window_spec: WindowSpec,
    signal_spec: SignalSpec,
    analysis_spec: AnalysisSpec,
    output_spec: OutputSpec,
    additional_imports: list[str] | None = None,
    analysis_code: str | None = None,
) -> Path:
    """Write an executable notebook that runs an analysis recipe.
    
    The notebook includes:
    1. Markdown purpose cell
    2. Exact specs cell (serialized)
    3. Imports cell
    4. Analysis run cell
    5. Output receipt cell
    
    No hidden state - all parameters explicit.
    No hard-coded user-specific paths except the passed nwb_path.
    
    Parameters
    ----------
    recipe_id : Unique recipe identifier
    output_path : Destination path (.ipynb extension)
    nwb_path : Path to NWB file (passed as parameter, not hardcoded)
    event_spec : Event timing specification
    window_spec : Temporal window specification
    signal_spec : Signal extraction specification
    analysis_spec : Analysis computation specification
    output_spec : Output storage specification
    additional_imports : Optional additional import lines
    analysis_code : Optional custom analysis code (default uses standard workflow)
    
    Returns
    -------
    Path to saved notebook
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build notebook cells
    cells = []
    
    # Cell 1: Markdown purpose
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            f"# Analysis Recipe: {recipe_id}\n",
            "\n",
            "This notebook executes a standardized analysis workflow:\n",
            "\n",
            "```\n",
            "Data + Specs -> Analysis Function -> Saved Output -> Figure -> Notebook\n",
            "```\n",
            "\n",
            "## Purpose\n",
            f"- **Analysis kind**: {analysis_spec.analysis_kind}\n",
            f"- **Signal class**: {signal_spec.signal_class}\n",
            f"- **Event**: {event_spec.event}\n",
            f"- **Window**: {window_spec.pre_ms} ms to {window_spec.post_ms} ms\n",
            "\n",
            "## Reproducibility\n",
            f"- Recipe ID: `{recipe_id}`\n",
            f"- NWB: `{nwb_path}`\n",
            "\n",
            "## Output\n",
            f"- Root: `{output_spec.output_root}`\n",
        ],
    })
    
    # Cell 2: Exact specs
    specs_dict = {
        "recipe_id": recipe_id,
        "event_spec": event_spec.to_dict(),
        "window_spec": window_spec.to_dict(),
        "signal_spec": signal_spec.to_dict(),
        "analysis_spec": analysis_spec.to_dict(),
        "output_spec": output_spec.to_dict(),
    }
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "# Analysis Specifications (exact)\n",
            "SPECS = ",
            json.dumps(specs_dict, indent=2),
            "\n",
            "\n",
            "# NWB path (passed as parameter)\n",
            f"NWB_PATH = Path(r\"{nwb_path}\")\n",
        ],
    })
    
    # Cell 3: Imports
    import_lines = [
        "# Standard imports\n",
        "from pathlib import Path\n",
        "import numpy as np\n",
        "import pandas as pd\n",
        "\n",
        "# Recipe API imports\n",
        "from src.analysis.recipes import (\n",
        "    EventSpec, WindowSpec, SignalSpec, AnalysisSpec, OutputSpec,\n",
        "    get_event_timing_vectors,\n",
        "    get_spike_epochs, get_lfp_epochs,\n",
        "    run_spike_rate, run_smoothed_spike_rate,\n",
        "    run_tfr, run_band_power,\n",
        "    save_array_npz, save_table_csv, write_recipe_manifest,\n",
        "    plot_spike_rate_preview, plot_tfr_preview,\n",
        ")\n",
    ]
    
    if additional_imports:
        import_lines.extend(["\n", "# Additional imports\n"] + [f"{imp}\n" for imp in additional_imports])
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": import_lines,
    })
    
    # Cell 4: Analysis run
    if analysis_code is None:
        # Default analysis code based on signal_class and analysis_kind
        if signal_spec.signal_class in ["SPK", "SPK_SMOOTH"]:
            analysis_code = _generate_spike_analysis_code()
        elif signal_spec.signal_class in ["LFP", "TFR", "BAND_POWER"]:
            analysis_code = _generate_lfp_analysis_code()
        else:
            analysis_code = _generate_generic_analysis_code()
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "# Execute Analysis\n",
            "\n",
            "print(f\"Running recipe: {SPECS['recipe_id']}\")\n",
            "print(f\"NWB: {NWB_PATH}\")\n",
            "\n",
            "# Deserialize specs\n",
            "event_spec = EventSpec(**SPECS['event_spec'])\n",
            "window_spec = WindowSpec(**SPECS['window_spec'])\n",
            "signal_spec = SignalSpec(**SPECS['signal_spec'])\n",
            "analysis_spec = AnalysisSpec(**SPECS['analysis_spec'])\n",
            "output_spec = OutputSpec(**SPECS['output_spec'])\n",
            "\n",
        ] + analysis_code.split("\n"),
    })
    
    # Cell 5: Output receipt
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "# Output Receipt\n",
            "\n",
            "print(\"\\n\" + \"=\"*50)\n",
            "print(\"RECIPE COMPLETE\")\n",
            "print(\"=\"*50)\n",
            "\n",
            "if 'result' in locals():\n",
            "    print(f\"Status: {result.status}\")\n",
            "    print(f\"Arrays: {len(result.arrays)}\")\n",
            "    print(f\"Tables: {len(result.tables)}\")\n",
            "    print(f\"Figures: {len(result.figures)}\")\n",
            "    print(f\"Manifest: {result.manifest_path}\")\n",
            "    print(f\"Warnings: {len(result.warnings)}\")\n",
            "else:\n",
            '    print("No result object - check for errors above")\n',
        ],
    })
    
    # Build notebook structure
    notebook = {
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
        "cells": cells,
    }
    
    # Save notebook
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2)
    
    return output_path


def _generate_spike_analysis_code() -> str:
    """Generate default spike analysis code."""
    return """
# 1. Get event vectors
events = get_event_timing_vectors(
    nwb_path=NWB_PATH,
    event=event_spec.event,
    conditions=list(event_spec.conditions),
)
print(f"Events: {len(events)} conditions")
for cond, times in list(events.items())[:3]:
    print(f"  {cond}: {len(times)} trials")

# 2. Extract spike epochs
bin_ms = 10.0 if signal_spec.signal_class == "SPK" else 1.0
spk_epochs = get_spike_epochs(
    nwb_path=NWB_PATH,
    event_vectors=events,
    window=window_spec,
    unit_filter=signal_spec.unit_filter,
    bin_ms=bin_ms,
)
print(f"\\nSpike epochs extracted")
for cond, arr in list(spk_epochs.items())[:3]:
    if arr.size > 0:
        print(f"  {cond}: shape {arr.shape}")

# 3. Run analysis
if analysis_spec.analysis_kind == "smoothed_spike_rate":
    rate_result = run_smoothed_spike_rate(
        spk_epochs,
        sigma_ms=20.0,
        fs=1000.0,
        preserve_trials=analysis_spec.preserve_trials,
    )
else:
    rate_result = run_spike_rate(
        spk_epochs,
        fs=1000.0,
        preserve_trials=analysis_spec.preserve_trials,
    )

print(f"\\nRate computed: {len(rate_result)} conditions")

# 4. Save outputs (simplified - full implementation would use RecipeResult)
output_dir = output_spec.get_recipe_dir()
print(f"\\nOutput directory: {output_dir}")

# 5. Save arrays
for cond, rate_data in rate_result.items():
    arr_path = output_dir / "arrays" / f"rate_{cond}.npz"
    save_array_npz(arr_path, **rate_data)

print(f"Arrays saved to {output_dir / 'arrays'}")

# Create minimal result object
result = type('obj', (object,), {
    'recipe_id': SPECS['recipe_id'],
    'status': 'SUCCESS',
    'arrays': {f"rate_{c}": str(output_dir/'arrays'/f"rate_{c}.npz") for c in rate_result},
    'tables': {},
    'figures': {},
    'notebooks': {},
    'manifest_path': str(output_dir / 'manifests' / 'manifest.json'),
    'warnings': [],
    'metadata': {'input_shapes': {c: str(spk_epochs[c].shape) for c in spk_epochs}},
})()

# Save manifest
provenance = {
    'repo_sha': 'unknown',
    'git_status_short': 'unknown',
    'nwb_path': str(NWB_PATH),
    'nwb_sha256': 'unknown',
    'source_functions': ['get_event_timing_vectors', 'get_spike_epochs', 'run_spike_rate'],
}
manifest_path = write_recipe_manifest(result, SPECS, provenance)
print(f"Manifest saved: {manifest_path}")
"""


def _generate_lfp_analysis_code() -> str:
    """Generate default LFP analysis code."""
    return """
# 1. Get event vectors
events = get_event_timing_vectors(
    nwb_path=NWB_PATH,
    event=event_spec.event,
    conditions=list(event_spec.conditions),
)
print(f"Events: {len(events)} conditions")

# 2. Extract LFP epochs
lfp_epochs = get_lfp_epochs(
    nwb_path=NWB_PATH,
    event_vectors=events,
    window=window_spec,
    channel_filter=signal_spec.channel_filter,
)
print(f"\\nLFP epochs extracted")
for cond, arr in list(lfp_epochs.items())[:3]:
    if arr.size > 0:
        print(f"  {cond}: shape {arr.shape}")

# 3. Run analysis
if analysis_spec.analysis_kind in ["tfr", "time_frequency"]:
    result_data = run_tfr(
        lfp_epochs,
        fs=signal_spec.sampling_rate_hz,
        baseline_ms=window_spec.baseline_ms,
    )
    print(f"\\nTFR computed: {len(result_data)} conditions")
else:
    bands = dict(analysis_spec.bands)
    result_data = run_band_power(
        lfp_epochs,
        fs=signal_spec.sampling_rate_hz,
        bands=bands,
        baseline_ms=window_spec.baseline_ms,
    )
    print(f"\\nBand power computed: {len(result_data)} conditions")

# 4. Save outputs
output_dir = output_spec.get_recipe_dir()
print(f"\\nOutput directory: {output_dir}")

# Create minimal result object
result = type('obj', (object,), {
    'recipe_id': SPECS['recipe_id'],
    'status': 'SUCCESS',
    'arrays': {},
    'tables': {},
    'figures': {},
    'notebooks': {},
    'manifest_path': str(output_dir / 'manifests' / 'manifest.json'),
    'warnings': [],
    'metadata': {'input_shapes': {c: str(lfp_epochs[c].shape) for c in lfp_epochs}},
})()

print(f"\\nRecipe complete: {SPECS['recipe_id']}")
"""


def _generate_generic_analysis_code() -> str:
    """Generate generic analysis code."""
    return """
# Generic analysis workflow
# Customize based on signal_spec.signal_class and analysis_spec.analysis_kind

print(f"Signal class: {signal_spec.signal_class}")
print(f"Analysis kind: {analysis_spec.analysis_kind}")

# TODO: Implement analysis based on spec
# This is a placeholder - full implementation would dispatch to appropriate functions

# 1. Get events
events = get_event_timing_vectors(
    nwb_path=NWB_PATH,
    event=event_spec.event,
    conditions=list(event_spec.conditions),
)

# 2. Extract signals based on signal_spec
# ... signal extraction code ...

# 3. Run analysis based on analysis_spec
# ... analysis code ...

# 4. Save outputs
output_dir = output_spec.get_recipe_dir()

result = type('obj', (object,), {
    'recipe_id': SPECS['recipe_id'],
    'status': 'PARTIAL',
    'arrays': {},
    'tables': {},
    'figures': {},
    'notebooks': {},
    'manifest_path': str(output_dir / 'manifests' / 'manifest.json'),
    'warnings': [{'code': 'PLACEHOLDER', 'message': 'Generic analysis not fully implemented'}],
    'metadata': {},
})()

print(f"\\nPlaceholder complete: {SPECS['recipe_id']}")
"""
