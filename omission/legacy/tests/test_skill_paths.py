import re
from pathlib import Path
import pytest

def test_skill_paths():
    """
    Validates that all file:/// links within SKILL.md files point to existent paths.
    Enforces repo-relative portability by dynamically resolving the root.
    """
    repo_root = Path(__file__).parent.parent.absolute()
    skills_dir = repo_root / ".gemini" / "skills"
    
    # If skills are absent, we skip rather than failing or returning early silently
    if not skills_dir.exists():
        pytest.skip("No .gemini/skills directory found for this environment.")

    failed_links = []
    
    # Regex to find standard markdown file links like [name](file:///path/to/file)
    # We capture the path part after file:///
    link_pattern = re.compile(r'\[.*?\]\(file:///([a-zA-Z]:/.*?|/.*?)\)')
    
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
            
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
            
        content = skill_file.read_text(encoding="utf-8")
        links = link_pattern.findall(content)
        
        for link in links:
            print(f"[debug] Found link: {link}")
            # We assume the link should be absolute on the host or relative to root
            # Most Antigravity links are absolute. We check if they exist.
            # To make it portable, we check if the link *contains* the repo root's basename 
            # or if it's already a valid path on this machine.
            link_path = Path(link)
            
            if not link_path.exists():
                # Try to resolve it relative to current repo_root if it looks like a project path
                # e.g. if it has 'omission' in it but the prefix is wrong
                if "omission" in link:
                    rel_parts = link.split("omission")[-1].lstrip("/\\")
                    resolved_path = repo_root / rel_parts
                    if resolved_path.exists():
                        continue
                
                failed_links.append(f"{skill_dir.name}: {link}")

    assert not failed_links, f"The following skill links are broken: {failed_links}"

if __name__ == "__main__":
    # Allow manual execution
    try:
        test_skill_paths()
        print("Success: All skill paths verified.")
    except Exception as e:
        print(f"Error: {e}")


def test_skill_required_sections_selected():
    """Validate that the four relevant SKILL.md files contain the mandatory subsections.

    Required subsections (case‑insensitive):
    - Trigger / Scope
    - Required Tools / Commands
    - Stop Conditions / Blocker Codes
    - Final Report Requirements
    """
    repo_root = Path(__file__).parent.parent.absolute()
    skills_dir = repo_root / ".gemini" / "skills"

    selected = {
        "analysis-nwb-read-guardrails",
        "analysis-nwb-data-availability-report",
        "analysis-manifest-validation",
        "theta-report-receipt-audit",
    }

    required = [
        r"Trigger / Scope",
        r"Required Tools / Commands",
        r"Stop Conditions / Blocker Codes",
        r"Final Report Requirements",
    ]

    missing = []
    for skill_dir in skills_dir.iterdir():
        if skill_dir.name not in selected:
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            missing.append(f"{skill_dir.name}: SKILL.md missing")
            continue
        content = skill_file.read_text(encoding="utf-8")
        for pattern in required:
            if not re.search(pattern, content, flags=re.IGNORECASE):
                missing.append(f"{skill_dir.name}: missing '{pattern}'")
    assert not missing, f"Required subsections missing: {missing}"
