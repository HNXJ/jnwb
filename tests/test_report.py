import os
import shutil
import pytest
from pathlib import Path
import jnwb as oa

def test_generate_report_success(tmp_path):
    # Use the real test session (fastest loading file ~21GB)
    nwb_path = "D:/analysis/nwb/sub-V198o_ses-230629_rec.nwb"
    
    if not Path(nwb_path).exists():
        pytest.skip(f"Test NWB session file {nwb_path} is missing.")
        
    output_dir = tmp_path / "reports"
    
    # Run the report generator
    report_dir = oa.generate_report(nwb_path, output_parent_dir=output_dir)
    
    # Check directory structure
    assert report_dir.exists()
    assert (report_dir / "report-suite.ipynb").exists()
    assert (report_dir / "report-suite.html").exists()
    
    # Check figures folder
    fig_svg_dir = report_dir / "figures" / "svg"
    assert fig_svg_dir.exists()
    
    # Check generated svg files
    svgs = list(fig_svg_dir.glob("*.svg"))
    expected_figures = [
        "session_metadata.svg",
        "unit_quality_census.svg",
        "evoked_psth_raster.svg",
        "lfp_psd.svg",
        "evoked_tfr.svg",
        "spectrolaminar_motif.svg",
        "waveform_classification.svg",
        "granger_network.svg",
        "single_unit_acg.svg",
        "population_decoding.svg"
    ]
    for fig_name in expected_figures:
        assert (fig_svg_dir / fig_name).exists(), f"Missing figure: {fig_name}"
    
    assert len(svgs) == len(expected_figures)
    
    # Verify notebook contains JSON structure
    with open(report_dir / "report-suite.ipynb", "r") as f:
        import json
        nb_data = json.load(f)
        assert "cells" in nb_data
        assert nb_data["nbformat"] == 4
