import json
import sys
from pathlib import Path

def run_notebook(path):
    print(f"=== Executing Notebook: {path} ===")
    with open(path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    # Shared global namespace
    namespace = {}
    
    # Configure matplotlib backend to prevent blocking
    try:
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        pass
    
    # Run code cells
    for idx, cell in enumerate(nb.get('cells', [])):
        if cell.get('cell_type') == 'code':
            source = "".join(cell.get('source', []))
            if not source.strip():
                continue
            print(f"--- Running Cell {idx} ---")
            try:
                exec(source, namespace)
            except Exception as e:
                print(f"Error in Cell {idx}: {e}")
                import traceback
                traceback.print_exc()
                return False
    print(f"=== Successfully executed: {path} ===\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_notebook_remote.py <notebook_path>")
        sys.exit(1)
    
    success = run_notebook(sys.argv[1])
    sys.exit(0 if success else 1)
