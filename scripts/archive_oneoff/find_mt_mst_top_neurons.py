import pathlib
import pandas as pd

csv_path = pathlib.Path(r"D:\workspace\omission\outputs\classification\grand_s_and_o_units.csv")
df = pd.read_csv(csv_path)

# Filter for MT and MST
mt_mst = df[df["area"].isin(["MT", "MST"])].copy()

top_s_plus = mt_mst.sort_values(by="r_Splus", ascending=False).head(10)
top_s_minus = mt_mst.sort_values(by="r_Sminus", ascending=False).head(10)

print("=== TOP 10 MT/MST S+ NEURONS (Stimulus-Driven) ===")
for i, (idx, r) in enumerate(top_s_plus.iterrows(), 1):
    print(f"Rank #{i:02d} | Session: {r['session_prefix']} | Row: {r['unit_row_idx']} (ID: {r['unit_id']}) | Area: {r['area']} | r_S+: {r['r_Splus']:.3f} (p={r['p_Splus']:.2e}) | Rate: {r['overall_rate']:.2f} Hz")

print("\n=== TOP 10 MT/MST S- NEURONS (Stimulus-Suppressed / Delay-Active) ===")
for i, (idx, r) in enumerate(top_s_minus.iterrows(), 1):
    print(f"Rank #{i:02d} | Session: {r['session_prefix']} | Row: {r['unit_row_idx']} (ID: {r['unit_id']}) | Area: {r['area']} | r_S-: {r['r_Sminus']:.3f} (p={r['p_Sminus']:.2e}) | Rate: {r['overall_rate']:.2f} Hz")

# Save detailed MT/MST summary CSV
out_csv = pathlib.Path(r"D:\workspace\omission\outputs\classification\mt_mst_top_s_plus_s_minus_units.csv")
combined = pd.concat([
    top_s_plus.assign(cell_type="S+"),
    top_s_minus.assign(cell_type="S-")
], ignore_index=True)
combined.to_csv(out_csv, index=False)
print(f"\nSaved MT/MST top units table: {out_csv}")
