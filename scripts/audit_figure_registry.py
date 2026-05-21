import sys
import os

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.registry import FigureRegistry

def audit_registry():
    print("Auditing Figure Registry...")
    registry = FigureRegistry.get_all()
    missing_modules = []
    
    for fig in registry:
        mod_path = fig['module'].replace('/', os.sep)
        if not os.path.exists(mod_path):
            if not os.path.exists(mod_path + ".py"):
                missing_modules.append(fig)
                print(f"MISSING: {fig['id']} -> {fig['module']}")
        else:
            print(f"FOUND: {fig['id']} -> {fig['module']}")
            
    if missing_modules:
        print(f"\nAudit complete. Found {len(missing_modules)} missing modules.")
    else:
        print("\nAudit complete. All modules present.")

if __name__ == "__main__":
    audit_registry()
