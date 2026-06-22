import os
import shutil
import datetime
from pathlib import Path

OUTPUTS_DIR = Path("D:/workspace/omission/outputs")
ARCHIVE_DIR = OUTPUTS_DIR / "archive"

# Folder renames mapping
RENAMES = {
    "f005": "time_frequency_representation",
    "f031_spike_phase_locking": "spike_phase_locking",
    "f033_spike_field_coherence": "spike_field_coherence"
}

# Cutoff date: 06/20/2026
CUTOFF_DATE = datetime.datetime(2026, 6, 20, 0, 0, 0)
CUTOFF_TIMESTAMP = CUTOFF_DATE.timestamp()

def organize():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    # 1. Rename numeric folders
    print("=== Step 1: Renaming Numeric Folders ===")
    for old_name, new_name in RENAMES.items():
        old_path = OUTPUTS_DIR / old_name
        new_path = OUTPUTS_DIR / new_name
        if old_path.exists() and old_path.is_dir():
            print(f"Renaming {old_name} -> {new_name}")
            try:
                shutil.move(str(old_path), str(new_path))
            except Exception as e:
                print(f"Error renaming {old_name}: {e}")
                
    # 2. Archive items modified before 06/20/2026
    print("\n=== Step 2: Archiving Legacy Items ===")
    for item in OUTPUTS_DIR.iterdir():
        # Skip the archive folder itself
        if item == ARCHIVE_DIR:
            continue
            
        mtime = item.stat().st_mtime
        mtime_date = datetime.datetime.fromtimestamp(mtime)
        
        if mtime < CUTOFF_TIMESTAMP:
            print(f"Archiving legacy item: {item.name} (Modified: {mtime_date})")
            dest = ARCHIVE_DIR / item.name
            try:
                # If destination already exists, remove it first to avoid collision
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
            except Exception as e:
                print(f"Error archiving {item.name}: {e}")

if __name__ == "__main__":
    organize()
