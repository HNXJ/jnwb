"""
Integrates all 166 Labyrinth knowledge graph nodes from G:/My Drive/Documents/Papers/artifacts/.lab/
directly into the omission project Labyrinth under artifacts/.lab/.
Avoids overwriting existing omission project nodes unless updated.
"""

import json
import pathlib
import shutil

REPO = pathlib.Path(r'D:\workspace\omission')
OMISSION_LAB = REPO / 'artifacts' / '.lab'
PAPERS_LAB = pathlib.Path(r'G:\My Drive\Documents\Papers\artifacts\.lab')

imported_count = 0
skipped_count = 0

for json_file in PAPERS_LAB.glob('*.json'):
    dest_file = OMISSION_LAB / json_file.name
    if not dest_file.exists():
        shutil.copy2(json_file, dest_file)
        imported_count += 1
    else:
        # Merge notes if missing
        try:
            p_data = json.loads(json_file.read_text(encoding='utf-8'))
            o_data = json.loads(dest_file.read_text(encoding='utf-8'))
            o_notes = set(o_data.get('notes', []))
            p_notes = p_data.get('notes', [])
            modified = False
            for pn in p_notes:
                if pn not in o_notes:
                    o_data.setdefault('notes', []).append(pn)
                    modified = True
            if modified:
                dest_file.write_text(json.dumps(o_data, indent=2, ensure_ascii=False), encoding='utf-8')
                imported_count += 1
            else:
                skipped_count += 1
        except Exception:
            skipped_count += 1

print(f"Successfully imported/merged {imported_count} paper nodes from Papers Labyrinth into {OMISSION_LAB}")
print(f"Skipped {skipped_count} identical nodes.")
