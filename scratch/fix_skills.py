import os
import re
from pathlib import Path

def fix_skill_paths():
    repo_root = Path(r"D:\workspace\omission")
    skills_dir = repo_root / ".gemini" / "skills"
    
    if not skills_dir.exists():
        print("No skills directory found.")
        return

    # Pattern to find old absolute paths
    # We want to replace D:/drive/omission/ with the current repo_root
    old_prefix = "D:/drive/omission/"
    new_prefix = str(repo_root).replace("\\", "/") + "/"
    
    print(f"Replacing {old_prefix} with {new_prefix}")

    count = 0
    for skill_file in skills_dir.rglob("SKILL.md"):
        content = skill_file.read_text(encoding="utf-8")
        if old_prefix in content:
            new_content = content.replace(old_prefix, new_prefix)
            # Also handle backslashes if any
            new_content = new_content.replace(old_prefix.replace("/", "\\"), str(repo_root) + "\\")
            
            skill_file.write_text(new_content, encoding="utf-8")
            print(f"Fixed {skill_file.relative_to(repo_root)}")
            count += 1
            
    print(f"Total files fixed: {count}")

if __name__ == "__main__":
    fix_skill_paths()
