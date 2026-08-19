import glob
import json
import os

def connect_loose_leaves():
    lab_dir = r'D:\workspace\omission\artifacts\.lab'

    # Map of explicit links to add for loose leaf nodes
    leaf_links = {
        "context-checkpoint-seal-20260726": [
            "context-manuscript-draft-v2",
            "context-data-21-session-audit",
            "context-supplement-tables",
            "mission"
        ],
        "context-data-21-session-audit": [
            "context-supplement-tables",
            "context-manuscript-draft-v2",
            "context-nwb-catalog-ready",
            "mission"
        ],
        "context-manuscript-draft-v2": [
            "context-data-21-session-audit",
            "context-supplement-tables",
            "context-concept-laminar-frequency-asymmetry",
            "context-concept-single-unit-selectivity",
            "mission"
        ],
        "context-supplement-tables": [
            "context-data-21-session-audit",
            "context-manuscript-draft-v2",
            "context-nwb-catalog-ready"
        ],
        "graph_metrics": ["mission"],
        "labyrinth-omission": ["mission"],
        "metrics": ["mission"],
        "suggestions": ["mission"]
    }

    modified_count = 0
    for node_id, targets in leaf_links.items():
        filepath = os.path.join(lab_dir, f"{node_id}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "generated" not in data or not isinstance(data["generated"], dict):
                data["generated"] = {"date": "2026-07-26", "links": []}

            existing_links = data["generated"].get("links", [])
            # Convert existing links to list of strings
            link_strs = set()
            for l in existing_links:
                if isinstance(l, str):
                    link_strs.add(l)
                elif isinstance(l, dict) and "target" in l:
                    link_strs.add(l["target"])

            for t in targets:
                if t not in link_strs:
                    existing_links.append({"to": t, "type": "supports"})

            data["generated"]["links"] = existing_links

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)


            modified_count += 1
            print(f"Connected loose leaf node: {node_id} -> {targets}")

    print(f"Successfully connected {modified_count} loose leaf nodes.")

if __name__ == '__main__':
    connect_loose_leaves()
