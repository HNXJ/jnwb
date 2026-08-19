import pytest
import sys
import os

# Ensure src is in sys.path if not installed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_core_imports():
    """Verify that light core modules import cleanly."""
    try:
        from src.analysis.registry import FigureRegistry
        from src.analysis.io.logger import log
        from src.analysis.contracts import SessionManifest, SignalBlock
        # Check if basic attributes exist
        assert hasattr(FigureRegistry, 'FIGURE_DATA')
        # log is an instance of OmissionLogger
        assert hasattr(log, 'info')
        assert SessionManifest is not None
        assert SignalBlock is not None
    except ImportError as e:
        pytest.fail(f"Core module import failed: {e}")

def test_loader_definition():
    """Verify DataLoader can be imported (but not necessarily initialized with data)."""
    try:
        from src.analysis.io.loader import DataLoader
        assert DataLoader is not None
    except ImportError as e:
        pytest.fail(f"DataLoader import failed: {e}")

def test_script_guards():
    """Verify that scripts with main guards can be imported without execution."""
    # This test will only pass if the scripts are correctly guarded
    import src.cleanup_outputs
    import src.generate_readmes
    import src.rename_agnostic
    import src.f038_layer_granger.audit_rrxr_outlier
    
    # If these imports reach here without doing anything (like printing or erroring on missing data), 
    # it's a good sign the guards are working.
    assert True
