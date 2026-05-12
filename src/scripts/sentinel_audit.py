import os
import json
import re
from datetime import datetime
from pathlib import Path

# --- Configuration ---
OUTPUT_DIR = Path("outputs/oglo-8figs")
DASHBOARD_DATA = Path("dashboard/src/data")
SCOREBOARD_FILE = DASHBOARD_DATA / "scoreboard.json"
MANIFEST_FILE = DASHBOARD_DATA / "manifest.json"

WEIGHTS = {
    "aesthetic": 20,
    "integrity": 30,
    "labels": 20,
    "documentation": 30
}

MADELANE_COLORS = ["#CFB87C", "#9400D3", "#FFFFFF", "#000000"]

def audit_figure(figure_path: Path, code_ref: str):
    print(f"""[action] Auditing figure: {figure_path}""")
    
    score = 100
    notes = []
    status = "awesome"
    
    # 1. Documentation Audit (30 points)
    has_readme = (figure_path / "README.md").exists()
    if not has_readme:
        score -= WEIGHTS["documentation"]
        notes.append("Missing README.md")
    
    # 2. Existence & Aesthetic Audit (20 points)
    html_files = list(figure_path.glob("*.html"))
    if not html_files:
        return 0, "fail", "No HTML figure found", "N/A"
    
    # We audit the first HTML file found
    target_html = html_files[0]
    try:
        content = target_html.read_text(errors='ignore')
        
        # Check background
        # Plotly usually has "paper_bgcolor":"white" or "rgba(0,0,0,0)"
        if '"paper_bgcolor":"white"' not in content and '"paper_bgcolor":"#ffffff"' not in content.lower():
            # Sometimes it's just 'white'
            if '"paper_bgcolor":"#FFFFFF"' not in content:
                score -= 10
                notes.append("Non-white background detected")
        
        # Check for labels (20 points)
        # Using flexible regex to find "text":"..." inside title/xaxis/yaxis regardless of key order
        has_title = re.search(r'"title":\s*\{[^}]*"text":\s*"[^"]+"', content) is not None
        has_xaxis = re.search(r'"xaxis\d*":\s*\{[^}]*"title":\s*\{[^}]*"text":\s*"[^"]+"', content) is not None
        has_yaxis = re.search(r'"yaxis\d*":\s*\{[^}]*"title":\s*\{[^}]*"text":\s*"[^"]+"', content) is not None
        
        if not (has_title and has_xaxis and has_yaxis):
            score -= WEIGHTS["labels"]
            notes.append("Missing essential labels (Title/X/Y)")
            
        # 3. Data Integrity Audit (30 points)
        # Extract the JSON payload (usually the second or third argument to Plotly.newPlot)
        # We look for the data array [ ... ] and layout object { ... }
        json_match = re.search(r'Plotly\.newPlot\(\s*"[^"]+",\s*(\[.*?\]),\s*(\{.*?\})', content, re.DOTALL)
        if json_match:
            data_json = json_match.group(1)
            layout_json = json_match.group(2)
            
            # Use negative lookbehind/lookahead to find ONLY unquoted NaN/Infinity
            # This avoids false positives in base64 'bdata' strings
            has_nan = re.search(r'(?<!["\w])NaN(?!["\w])', data_json) or re.search(r'(?<!["\w])NaN(?!["\w])', layout_json)
            has_inf = re.search(r'(?<!["\w])Infinity(?!["\w])', data_json) or re.search(r'(?<!["\w])Infinity(?!["\w])', layout_json)
            
            if has_nan or has_inf:
                 score -= WEIGHTS["integrity"]
                 notes.append("Corrupt Data (Literal NaN/Infinity detected in JSON)")
        else:
            # Fallback if regex fails, but be more specific
            # Check if NaN/Infinity appear as literals
            if re.search(r'(?<!["\w])NaN(?!["\w])', content) or re.search(r'(?<!["\w])Infinity(?!["\w])', content):
                score -= WEIGHTS["integrity"]
                notes.append("Corrupt Data (Literal NaN/Infinity detected via fallback)")

    except Exception as e:
        print(f"""[error] Failed to read {target_html}: {e}""")
        return 0, "fail", f"Read Error: {e}", "N/A"

    if score < 70:
        status = "fail"
    elif score < 90:
        status = "pass"
    else:
        status = "awesome"
        
    if not notes:
        notes.append("All Sentinel checks passed.")
        
    return score, status, "; ".join(notes), target_html.name

def run_audit():
    print(f"""[action] Starting Sentinel Audit...""")
    
    with open(MANIFEST_FILE, 'r') as f:
        manifest = json.load(f)
        
    with open(SCOREBOARD_FILE, 'r') as f:
        scoreboard = json.load(f)
        
    new_ledger = []
    
    # Map manifest figures to ledger
    for fig in manifest["figures"]:
        fig_id = fig["id"]
        # Find folder in outputs
        fig_folders = list(OUTPUT_DIR.glob(f"{fig_id}-*"))
        if not fig_folders:
            # Check for exact match if hyphen logic fails
            fig_folders = [OUTPUT_DIR / fig_id] if (OUTPUT_DIR / fig_id).exists() else []
            
        if fig_folders:
            fig_path = fig_folders[0]
            # Try to find the code reference from source
            # fig_id like 'f001'
            code_path = f"src/{fig_id}_{fig['title'].lower().replace(' ', '_')}/script.py"
            # Fallback if specific script not found
            if not Path(code_path).exists():
                code_path = f"src/main.py (via {fig_id})"
                
            score, status, notes, html_file = audit_figure(fig_path, code_path)
            
            new_ledger.append({
                "analysis": f"{fig_id} - {fig['title']}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M"),
                "file": f"{fig_path.name}/{html_file}",
                "code": code_path,
                "status": status,
                "score": score,
                "notes": notes
            })
        else:
            new_ledger.append({
                "analysis": f"{fig_id} - {fig['title']}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M"),
                "file": "N/A",
                "code": "N/A",
                "status": "queued",
                "score": 0,
                "notes": "Figure output directory not found."
            })
            
    scoreboard["ledger"] = new_ledger
    scoreboard["last_updated"] = datetime.now().isoformat()
    
    with open(SCOREBOARD_FILE, 'w') as f:
        json.dump(scoreboard, f, indent=2)
        
    print(f"""[action] Sentinel Audit complete. Ledger updated with {len(new_ledger)} entries.""")

if __name__ == "__main__":
    run_audit()
