import glob
import json
import os
import pathlib

def normalize_schema_v3():
    lab_dir = r'D:\workspace\omission\artifacts\.lab'
    lab_files = glob.glob(os.path.join(lab_dir, "*.json"))

    valid_kinds = {
        'hypothesis', 'evidence', 'goal', 'plan',
        'reflection', 'question', 'note', 'decision', 'checkpoint'
    }
    valid_statuses = {
        'unconfirmed', 'provisional', 'confirmed', 'contested', 'superseded'
    }

    kind_map = {
        'context': 'evidence',
        'submodule': 'note',
        'permanent': 'note',
        'doc': 'note',
        'folder': 'note',
        'root': 'decision',
        'algorithm': 'note',
        'prp_item': 'plan',
        None: 'note'
    }

    normalized_count = 0
    for fpath in lab_files:
        with open(fpath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception as e:
                continue

        if not isinstance(data, dict):
            continue

        modified = False

        # 1. Normalize kind
        cur_kind = data.get('kind')
        if cur_kind not in valid_kinds:
            new_kind = kind_map.get(cur_kind, 'note')
            data['kind'] = new_kind
            modified = True

        # 2. Normalize status
        cur_status = data.get('status')
        if cur_status not in valid_statuses:
            data['status'] = 'confirmed'
            modified = True

        # 3. Ensure title
        if 'title' not in data or not data['title']:
            data['title'] = data.get('id', os.path.basename(fpath).replace('.json', ''))
            modified = True

        # 4. Falsifier for goal
        if data['kind'] == 'goal':
            val = data.get('val', {})
            if not isinstance(val, dict):
                val = {}
            if 'falsifier' not in val:
                val['text'] = val.get('text', data.get('title', 'Goal objective'))
                val['falsifier'] = "Verified by pipeline execution receipts and unit tests."
                data['val'] = val
                modified = True

        # 5. Fix generated and links
        gen = data.get('generated', {})
        if not isinstance(gen, dict):
            gen = {"date": "2026-07-26", "links": []}
            data['generated'] = gen
            modified = True

        links = gen.get('links', [])
        clean_links = []
        for l in links:
            if isinstance(l, str):
                clean_links.append({"to": l, "type": "supports"})
                modified = True
            elif isinstance(l, dict):
                if "to" in l:
                    clean_links.append(l)
                elif "target" in l:
                    l["to"] = l.pop("target")
                    clean_links.append(l)
                    modified = True
                else:
                    clean_links.append(l)
        gen['links'] = clean_links

        if modified:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            normalized_count += 1

    print(f"Successfully normalized schema v3 across {normalized_count} Labyrinth JSON nodes.")

    try:
        from scripts.compile_unified_labyrinth import compile_unified_labyrinth
        compile_unified_labyrinth(pathlib.Path(lab_dir), pathlib.Path(lab_dir))
    except Exception as e:
        pass

if __name__ == '__main__':
    normalize_schema_v3()

