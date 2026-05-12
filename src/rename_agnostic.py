import os
import re

base_dir = r"D:\drive\outputs\oglo-8figs"

areas = ["FEF", "FST", "MST", "MT", "PFC", "TEO", "V1", "V2", "V3a", "V3d", "V4"]
# Use lower and upper variations just in case, though mostly they are upper
pattern = re.compile(r"-(" + "|".join(areas) + r")$", re.IGNORECASE)

def main():
    print("Starting area-agnostic renaming...")
    for d in os.listdir(base_dir):
        d_path = os.path.join(base_dir, d)
        if os.path.isdir(d_path) and re.match(r"^f\d{3}-", d):
            # Match fXXX-...
            new_name = pattern.sub("", d)
            
            # Additional manual fixes for better methodology names based on the list
            if new_name == "f003-S-plus":
                new_name = "f003-omission-psth"
            elif new_name == "f005-TFR":
                new_name = "f005-time-frequency-representation"
            elif new_name == "f009-individual-sfc":
                new_name = "f009-spike-field-coherence"
            elif new_name == "f011-laminar":
                new_name = "f011-laminar-mapping"

            if new_name != d:
                new_path = os.path.join(base_dir, new_name)
                # if new_path exists, it might mean we already have this methodology folder
                if not os.path.exists(new_path):
                    os.rename(d_path, new_path)
                    print(f"Renamed: '{d}' -> '{new_name}'")
                else:
                    # Need to merge contents if exists
                    print(f"Merge needed for '{d}' into '{new_name}', not implemented, assuming unique per figure ID")
                    import shutil
                    for f in os.listdir(d_path):
                        shutil.move(os.path.join(d_path, f), os.path.join(new_path, f))
                    os.rmdir(d_path)
                    print(f"Merged '{d}' into '{new_name}'")

    print("Area-agnostic renaming complete.")

if __name__ == "__main__":
    main()
