import pandas as pd
import glob

gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")

# Check some actual rows with different is_quality_good values
print("Units with is_quality_good=True:")
good = gdb[gdb['is_quality_good'] == True][['unit_id', 'session_id', 'area', 'is_stable', 'stable_plus', 'firing_rate', 'waveform_duration']].head(3)
print(good)

print("\nUnits with is_quality_good=False:")
bad = gdb[gdb['is_quality_good'] == False][['unit_id', 'session_id', 'area', 'is_stable', 'stable_plus', 'firing_rate', 'waveform_duration']].head(3)
print(bad)

print("\nCorrelation between is_quality_good and other metrics:")
print("is_quality_good vs is_stable:")
ct = pd.crosstab(gdb['is_quality_good'], gdb['is_stable'])
print(ct)

print("\nis_quality_good vs stable_plus:")
ct2 = pd.crosstab(gdb['is_quality_good'], gdb['stable_plus'])
print(ct2)

# Look for quality-related columns
print("\nAll columns in grand database:")
print(gdb.columns.tolist())

# Check NWB to see if quality comes from there
print("\n\nChecking NWB units table for quality-related columns...")
nwb_files = glob.glob("D:/analysis/nwb/*.nwb")
if nwb_files:
    from pynwb import NWBHDF5IO
    try:
        with NWBHDF5IO(nwb_files[0], "r") as io:
            nwb = io.read()
            units_df = nwb.units.to_dataframe()
            print(f"NWB units columns: {units_df.columns.tolist()}")
            if 'quality' in units_df.columns:
                print(f"Quality values in NWB: {units_df['quality'].unique()}")
    except Exception as e:
        print(f"Could not read NWB: {e}")
else:
    print("No NWB files found")
