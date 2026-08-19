import os
import shutil
import pytest
from pathlib import Path
import omission as oa

def test_session_disk_caching(tmp_path):
    # Use real test session
    nwb_path = "D:/analysis/nwb/sub-V198o_ses-230629_rec.nwb"
    if not Path(nwb_path).exists():
        pytest.skip("Test session NWB file is missing.")
        
    cache_dir = Path("artifacts/developer/.cache")
    session_name = Path(nwb_path).stem
    
    # 1. Clear any existing cache for this session
    for suffix in ["_units.pkl", "_electrodes.pkl", "_intervals.pkl", "_metadata.json"]:
        p = cache_dir / f"{session_name}{suffix}"
        if p.exists():
            p.unlink()
            
    # 2. First load: should trigger NWB load and save to cache
    session1 = oa.OmissionSession(nwb_path)
    
    # Assert cache files are created
    assert (cache_dir / f"{session_name}_units.pkl").exists()
    assert (cache_dir / f"{session_name}_electrodes.pkl").exists()
    assert (cache_dir / f"{session_name}_intervals.pkl").exists()
    assert (cache_dir / f"{session_name}_metadata.json").exists()
    
    # 3. Second load: should load from disk cache
    session2 = oa.OmissionSession(nwb_path)
    assert len(session2.get_units()) == len(session1.get_units())
    assert len(session2.get_electrodes()) == len(session1.get_electrodes())
