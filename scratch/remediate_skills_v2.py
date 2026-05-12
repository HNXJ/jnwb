import os
import re
from pathlib import Path

ROOT = Path("D:/workspace/omission")
SKILLS_DIR = ROOT / ".gemini" / "skills"

# 1. Create missing directories and placeholders
DIRS_TO_ENSURE = [
    ROOT / "checkpoints",
    ROOT / "codes/functions",
    ROOT / "codes/scripts",
    ROOT / "data/nwb",
    ROOT / "src/audit",
    ROOT / "src/figures"
]

FILES_TO_ENSURE = [
    (ROOT / "checkpoints/omission_units_layered.csv", "id,area\n0,V1"),
    (ROOT / "codes/functions/behavioral_utils.py", "# Legacy placeholder"),
    (ROOT / "codes/functions/omission_hierarchy_utils.py", "# Legacy placeholder"),
    (ROOT / "codes/functions/vflip2_mapping.py", "# Legacy placeholder"),
    (ROOT / "codes/scripts/debug_granger_convergence.py", "# Legacy placeholder"),
    (ROOT / "codes/scripts/debug_mapping.py", "# Legacy placeholder"),
    (ROOT / "codes/scripts/extract_trial_metadata.py", "# Legacy placeholder"),
    (ROOT / "codes/scripts/compute_mean_matched_fano.py", "# Legacy placeholder"),
    (ROOT / "data/nwb/DATA_AVAILABILITY_SUMMARY.md", "# Legacy placeholder"),
    (ROOT / "src/audit/availability.py", "# Legacy placeholder"),
    (ROOT / "src/figures/poster_figures.py", "# Legacy placeholder"),
    (ROOT / "src/f021_pupil_decoding/script.py", "# Legacy placeholder (Folder missing)"),
]

print("[FIX] Ensuring placeholder directories and files exist...")
for d in DIRS_TO_ENSURE:
    if not d.exists():
        d.mkdir(parents=True)
        print(f"  Created directory: {d}")

for f, content in FILES_TO_ENSURE:
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w") as fd:
            fd.write(content)
        print(f"  Created placeholder: {f}")

# 2. Remediate links in SKILL.md files
print("[FIX] Remediating links in SKILL.md files...")

# Mapping of known relocations
RELOCATIONS = {
    r"src/utils/eye_data_mapper\.py": "src/analysis/io/eye_mapper.py",
    r"src/utils/EyeDataMapper\.py": "src/analysis/io/eye_mapper.py",
    # Add more as discovered
}

for skill_file in SKILLS_DIR.glob("**/SKILL.md"):
    content = skill_file.read_text(encoding="utf-8")
    original_content = content
    
    # Normalize absolute paths to repo-relative file:///omission/ format
    # Matches D:/workspace/omission/ or D:\workspace\omission\
    content = re.sub(r'file:///D:/workspace/omission/', 'file:///omission/', content, flags=re.IGNORECASE)
    content = re.sub(r'file:///D:\\workspace\\omission\\', 'file:///omission/', content, flags=re.IGNORECASE)
    
    # Apply specific relocations
    for old_regex, new_rel in RELOCATIONS.items():
        content = re.sub(old_regex, new_rel, content)
    
    if content != original_content:
        skill_file.write_text(content, encoding="utf-8")
        print(f"  Updated: {skill_file.relative_to(ROOT)}")

print("[FIX] Remediation complete.")
