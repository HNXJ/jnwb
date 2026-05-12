import os
import shutil
import re

base_dir = r"D:\drive\outputs\oglo-8figs"


def main():
    print("1. Replacing spaces with hyphens in directory names...")
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            new_name = item.replace(" ", "-")
            if new_name != item:
                os.rename(item_path, os.path.join(base_dir, new_name))
                print(f"Renamed: '{item}' -> '{new_name}'")

    # Re-read items after rename
    items = os.listdir(base_dir)

    print("2. Moving root HTML files into appropriate directories...")
    for item in items:
        item_path = os.path.join(base_dir, item)
        if os.path.isfile(item_path) and item.endswith(".html"):
            match = re.match(r"(fig|f)(\d+)[_-](.+)\.html", item)
            if match:
                num = int(match.group(2))
                desc = match.group(3).replace("_", "-").replace(" ", "-")
                desc_words = [w for w in desc.split("-") if w][:3]
                desc_clean = "-".join(desc_words)
                folder_name = f"f{num:03d}-{desc_clean}"
                
                existing_folder = None
                for d in os.listdir(base_dir):
                    if os.path.isdir(os.path.join(base_dir, d)) and d.startswith(f"f{num:03d}-"):
                        existing_folder = d
                        break
                
                target_folder = existing_folder if existing_folder else folder_name
                target_path = os.path.join(base_dir, target_folder)
                
                os.makedirs(target_path, exist_ok=True)
                shutil.move(item_path, os.path.join(target_path, item))
                print(f"Moved: '{item}' -> '{target_folder}/'")

    print("3. Handling improperly named directories like 'fig16'...")
    for d in os.listdir(base_dir):
        d_path = os.path.join(base_dir, d)
        if os.path.isdir(d_path) and re.match(r"^(fig|f)\d+$", d):
            num = int(re.match(r"^(fig|f)(\d+)$", d).group(2))
            existing_folder = None
            for cand in os.listdir(base_dir):
                if cand != d and os.path.isdir(os.path.join(base_dir, cand)) and cand.startswith(f"f{num:03d}-"):
                    existing_folder = cand
                    break
            
            if existing_folder:
                target = os.path.join(base_dir, existing_folder)
                for f in os.listdir(d_path):
                    shutil.move(os.path.join(d_path, f), os.path.join(target, f))
                try:
                    os.rmdir(d_path)
                    print(f"Merged '{d}' into '{existing_folder}'")
                except OSError as e:
                    print(f"Merged '{d}' into '{existing_folder}' but could not delete '{d}': {e}")
            else:
                new_name = f"f{num:03d}-placeholder"
                os.rename(d_path, os.path.join(base_dir, new_name))
                print(f"Renamed '{d}' -> '{new_name}'")

    print("4. Fixing f041 directory name...")
    for d in os.listdir(base_dir):
        d_path = os.path.join(base_dir, d)
        if os.path.isdir(d_path) and d.startswith("f041-"):
            new_path = os.path.join(base_dir, "f041-laminar-analysis")
            if d_path != new_path:
                if not os.path.exists(new_path):
                    os.rename(d_path, new_path)
                    print(f"Renamed '{d}' -> 'f041-laminar-analysis'")
                else:
                    for f in os.listdir(d_path):
                        shutil.move(os.path.join(d_path, f), os.path.join(new_path, f))
                    os.rmdir(d_path)
                    print(f"Merged '{d}' into 'f041-laminar-analysis'")

    print("5. Ensuring f001 to f041 exist continuously...")
    existing_nums = set()
    for d in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, d)):
            match = re.match(r"^f(\d+)-", d)
            if match:
                existing_nums.add(int(match.group(1)))

    for i in range(1, 42):
        if i not in existing_nums:
            folder_name = f"f{i:03d}-placeholder"
            os.makedirs(os.path.join(base_dir, folder_name), exist_ok=True)
            print(f"Created missing folder: '{folder_name}'")

    print("Cleanup complete.")

if __name__ == "__main__":
    main()

