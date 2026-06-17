# A4 Trial-Count Validation Script
import sys, json, csv, argparse
from pathlib import Path
from collections import defaultdict

REQUIRED_CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

CONDITION_FAMILIES = {
    "AAAB": "A-family", "AXAB": "A-family", "AAXB": "A-family", "AAAX": "A-family",
    "BBBA": "B-family", "BXBA": "B-family", "BBXA": "B-family", "BBBX": "B-family",
    "RRRR": "R-family", "RXRR": "R-family", "RRXR": "R-family", "RRRX": "R-family",
}

OMISSION_POSITIONS = {
    "AAAB": None, "AXAB": "p2", "AAXB": "p3", "AAAX": "p4",
    "BBBA": None, "BXBA": "p2", "BBXA": "p3", "BBBX": "p4",
    "RRRR": None, "RXRR": "p2", "RRXR": "p3", "RRRX": "p4",
}

MATCHED_CONTROLS = {
    "AAAB": "AAAB", "AXAB": "AAAB", "AAXB": "AAAB", "AAAX": "AAAB",
    "BBBA": "BBBA", "BXBA": "BBBA", "BBXA": "BBBA", "BBBX": "BBBA",
    "RRRR": "RRRR", "RXRR": "RRRR", "RRXR": "RRRR", "RRRX": "RRRR",
}

def extract_trial_count_from_shape(shape_str):
    if not shape_str or shape_str == "blocked_format":
        return None
    try:
        shape_str = shape_str.strip("()")
        dims = [int(x.strip()) for x in shape_str.split(",")]
        return dims[0] if dims else None
    except:
        return None

def load_a3_outputs(a3_dir):
    a3_path = Path(a3_dir)
    signal_inventory = {}
    signal_file = a3_path / "signal_file_inventory.csv"
    if signal_file.exists():
        with open(signal_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                session_id = row['session_id']
                condition = row['condition_inferred']
                if condition and condition != 'None':
                    key = (session_id, condition)
                    if key not in signal_inventory:
                        signal_inventory[key] = []
                    trial_count = extract_trial_count_from_shape(row['shape_if_safe'])
                    signal_inventory[key].append({'basename': row['basename'], 'signal_class': row['signal_class_inferred'], 'shape': row['shape_if_safe'], 'trial_count': trial_count})
    return signal_inventory

def build_trial_count_matrix(signal_inventory):
    matrix = []
    for (session_id, condition), files in sorted(signal_inventory.items()):
        if condition not in REQUIRED_CONDITIONS:
            continue
        family = CONDITION_FAMILIES.get(condition, "unknown")
        omission_pos = OMISSION_POSITIONS.get(condition)
        matched_ctrl = MATCHED_CONTROLS.get(condition, "unknown")
        trial_counts = [f['trial_count'] for f in files if f['trial_count'] is not None]
        signal_classes = set(f['signal_class'] for f in files)
        basenames = [f['basename'] for f in files]
        trial_count = None
        trial_count_status = "inferred_from_file_inventory"
        warning = ""
        if trial_counts:
            if len(set(trial_counts)) == 1:
                trial_count = trial_counts[0]
                trial_count_status = "from_shape_metadata"
            else:
                trial_count = trial_counts[0]
                trial_count_status = "ambiguous_across_signals"
                warning = f"Inconsistent trial counts: {trial_counts}"
        matrix.append({'session_id': session_id, 'condition': condition, 'family': family, 'omission_position': omission_pos if omission_pos else "", 'matched_control': matched_ctrl, 'n_trial_count_sources': len(files), 'trial_count': trial_count if trial_count else "", 'trial_count_status': trial_count_status, 'source_basenames': "; ".join(basenames), 'signal_classes_with_condition': ",".join(sorted(signal_classes)), 'warnings': warning, 'truth_status': 'truth_safe_unverified'})
    return matrix

def build_condition_balance_summary(matrix):
    balance = defaultdict(lambda: defaultdict(dict))
    for row in matrix:
        key = (row['session_id'], row['family'], (row['omission_position'] if row['omission_position'] else "control"), row['condition'], row['matched_control'])
        if row['omission_position']:
            balance[key]['omission_trial_count'] = row['trial_count']
            balance[key]['omission_condition'] = row['condition']
        else:
            balance[key]['control_trial_count'] = row['trial_count']
    summary = []
    for (session_id, family, omission_pos, omission_cond, matched_ctrl), counts in sorted(balance.items()):
        if omission_pos != "control":
            omission_count = counts.get('omission_trial_count')
            control_count = counts.get('control_trial_count')
            balance_status = "unknown"
            ratio = None
            warning = ""
            if omission_count and control_count:
                ratio = round(omission_count / control_count, 2) if control_count > 0 else None
                if omission_count == control_count:
                    balance_status = "balanced"
                elif abs(omission_count - control_count) <= 2:
                    balance_status = "nearly_balanced"
                else:
                    balance_status = "imbalanced"
                    warning = f"Ratio: {ratio}"
            elif omission_count and not control_count:
                balance_status = "missing_control"
                warning = f"Control condition {matched_ctrl} not found"
            elif not omission_count:
                balance_status = "missing_omission"
                warning = f"Omission condition {omission_cond} has no trial count"
            summary.append({'session_id': session_id, 'family': family, 'omission_position': omission_pos, 'omission_condition': omission_cond, 'matched_control': matched_ctrl, 'omission_trial_count': omission_count if omission_count else "", 'control_trial_count': control_count if control_count else "", 'balance_status': balance_status, 'ratio_omission_to_control': ratio if ratio else "", 'warnings': warning, 'truth_status': 'truth_safe_unverified'})
    return summary

def build_completeness_summary(matrix):
    sessions_data = defaultdict(lambda: {'conditions_detected': set()})
    for row in matrix:
        sessions_data[row['session_id']]['conditions_detected'].add(row['condition'])
    summary = []
    for session_id in sorted(sessions_data.keys()):
        detected = sorted(sessions_data[session_id]['conditions_detected'])
        missing = set(REQUIRED_CONDITIONS) - sessions_data[session_id]['conditions_detected']
        has_a = all(c in detected for c in ["AAAB", "AXAB", "AAXB", "AAAX"])
        has_b = all(c in detected for c in ["BBBA", "BXBA", "BBXA", "BBBX"])
        has_r = all(c in detected for c in ["RRRR", "RXRR", "RRXR", "RRRX"])
        has_p2 = all(c in detected for c in ["AXAB", "BXBA", "RXRR"])
        has_p3 = all(c in detected for c in ["AAXB", "BBXA", "RRXR"])
        has_p4 = all(c in detected for c in ["AAAX", "BBBX", "RRRX"])
        readiness = "ready_for_A5" if (len(detected) == 12 and has_a and has_b and has_r) else "incomplete"
        warning = f"Missing: {','.join(sorted(missing))}" if missing else ""
        summary.append({'session_id': session_id, 'n_conditions_detected': len(detected), 'conditions_detected': ",".join(detected), 'missing_conditions': ",".join(sorted(missing)) if missing else "none", 'has_all_A_family': "yes" if has_a else "no", 'has_all_B_family': "yes" if has_b else "no", 'has_all_R_family': "yes" if has_r else "no", 'has_all_p2_omissions': "yes" if has_p2 else "no", 'has_all_p3_omissions': "yes" if has_p3 else "no", 'has_all_p4_omissions': "yes" if has_p4 else "no", 'readiness_for_A5': readiness, 'warnings': warning, 'truth_status': 'truth_safe_unverified'})
    return summary

def write_csv(filepath, fieldnames, rows):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="A4 Trial-Count Validation")
    parser.add_argument("--data-root", default="D:\\workspace\\data")
    parser.add_argument("--a3-dir", default="reports/analysis_A3_dataset_census")
    parser.add_argument("--out-dir", default="reports/analysis_A4_trial_count_validation")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    print(f"[A4] Loading A3 outputs from {args.a3_dir}...")
    signal_inventory = load_a3_outputs(args.a3_dir)
    print(f"[A4] Loaded {len(signal_inventory)} session-condition combinations")
    matrix = build_trial_count_matrix(signal_inventory)
    print(f"[A4] Generated {len(matrix)} matrix rows")
    balance = build_condition_balance_summary(matrix)
    print(f"[A4] Generated {len(balance)} balance rows")
    completeness = build_completeness_summary(matrix)
    print(f"[A4] Generated {len(completeness)} completeness rows")
    write_csv(out_dir / "trial_count_matrix.csv", ['session_id', 'condition', 'family', 'omission_position', 'matched_control', 'n_trial_count_sources', 'trial_count', 'trial_count_status', 'source_basenames', 'signal_classes_with_condition', 'warnings', 'truth_status'], matrix)
    write_csv(out_dir / "condition_balance_summary.csv", ['session_id', 'family', 'omission_position', 'omission_condition', 'matched_control', 'omission_trial_count', 'control_trial_count', 'balance_status', 'ratio_omission_to_control', 'warnings', 'truth_status'], balance)
    write_csv(out_dir / "session_condition_completeness.csv", ['session_id', 'n_conditions_detected', 'conditions_detected', 'missing_conditions', 'has_all_A_family', 'has_all_B_family', 'has_all_R_family', 'has_all_p2_omissions', 'has_all_p3_omissions', 'has_all_p4_omissions', 'readiness_for_A5', 'warnings', 'truth_status'], completeness)
    ready = sum(1 for r in completeness if r['readiness_for_A5'] == 'ready_for_A5')
    print(f"[A4] ✅ Complete. {ready}/{len(completeness)} sessions ready for A5")

if __name__ == "__main__":
    main()
