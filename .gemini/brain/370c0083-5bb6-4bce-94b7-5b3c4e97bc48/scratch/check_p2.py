import pandas as pd
from src.analysis.io.loader import DataLoader

def check_230630_p2():
    loader = DataLoader()
    units = []
    for i in range(50):
        area, status, caveat = loader.resolve_unit_area('230630', 2, i, allow_heuristic=True)
        units.append({'unit': i, 'area': area, 'status': status})
    df = pd.DataFrame(units)
    print("--- 230630 Probe 2 Area Counts ---")
    print(df['area'].value_counts())
    print("\n--- 230630 Probe 2 Status Counts ---")
    print(df['status'].value_counts())

if __name__ == "__main__":
    check_230630_p2()
