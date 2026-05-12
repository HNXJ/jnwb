import pandas as pd
from src.analysis.io.loader import DataLoader

def check_mapping_details():
    loader = DataLoader()
    for i in range(50):
        area, status, caveat = loader.resolve_unit_area('230630', 2, i, allow_heuristic=True)
        print(f"Unit {i}: Area={area}, Status={status}")

if __name__ == "__main__":
    check_mapping_details()
