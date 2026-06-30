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
    assert len(svgs) > 0
    
    # Verify notebook contains JSON structure
    with open(report_dir / "report-suite.ipynb", "r") as f:
        nb_data = json_data = pytest.importorskip("json").load(f)
        assert "cells" in nb_data
        assert nb_data["nbformat"] == 4
