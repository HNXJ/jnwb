import glob
import json
import os

def fix_lab_links():
    lab_dir = r'D:\workspace\omission\artifacts\.lab'
    json_files = glob.glob(os.path.join(lab_dir, "*.json"))

    fixed_count = 0
    for fpath in json_files:
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Error reading {fpath}: {e}")
                continue

        if not isinstance(data, dict):
            continue

        gen = data.get("generated", {})
        if not isinstance(gen, dict):
            continue

        links = gen.get("links", [])
        if not links:
            continue

        new_links = []
        modified = False
        for l in links:
            if isinstance(l, str):
                new_links.append({"to": l, "type": "supports"})
                modified = True
            elif isinstance(l, dict):
                if "to" in l:
                    new_links.append(l)
                elif "target" in l:
                    l["to"] = l.pop("target")
                    new_links.append(l)
                    modified = True
                else:
                    new_links.append(l)

        if modified:
            data["generated"]["links"] = new_links
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            fixed_count += 1

    print(f"Fixed link format in {fixed_count} Labyrinth JSON files.")

if __name__ == '__main__':
    fix_lab_links()
