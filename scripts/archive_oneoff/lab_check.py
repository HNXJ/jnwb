"""lab_check.py — Single-Command Friction-Reduction Verification Runner

Executes the complete Labyrinth verification sequence:
  1. Pytest Unit Test Suite (fast -W error mode).
  2. Labyrinth Knowledge Graph Continuous Optimizer & Graph Metrics.
  3. Labyrinth Interactive HTML Canvas Visualizer Compilation.
"""

import sys
import time
import io
import subprocess
from pathlib import Path

# Force UTF-8 encoding for standard output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGET = Path(r"D:\workspace\omission")

def main():
    t0 = time.time()
    print("==========================================================")
    print("      LABYRINTH FRICTION-REDUCTION CHECK & OPTIMIZER      ")
    print("==========================================================")

    # Step 1: Run Pytest
    print("\n[Step 1/3] Running Pytest Unit Test Suite (-W error)...")
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "-W", "error"], cwd=TARGET)
    if res.returncode != 0:
        print("❌ ERROR: Pytest test suite failed!")
        sys.exit(res.returncode)
    print("✅ Pytest test suite PASSED cleanly (0 warnings, 0 failures).")

    # Step 2: Run Continuous Optimizer
    print("\n[Step 2/3] Running Labyrinth Knowledge Graph Continuous Optimizer...")
    import optimize_lab_graph
    optimize_lab_graph.main()

    # Step 3: Compile Interactive HTML Graph
    print("\n[Step 3/3] Compiling Interactive HTML Graph Visualizer...")
    compiler_path = Path(r"C:\Users\nejath\.gemini\antigravity\scratch\labyrinth\clients\lab_compile.py")
    lab_dir = TARGET / "artifacts" / ".lab"
    out_html = TARGET / "artifacts" / "lab_graph.html"
    subprocess.run([sys.executable, str(compiler_path), "--lab", str(lab_dir), "--format", "html", "--out", str(out_html)], cwd=TARGET, check=True)
    print(f"✅ HTML Canvas Graph compiled: {out_html}")

    elapsed = time.time() - t0
    print("\n==========================================================")
    print(f"  FRICTION-REDUCTION VERIFICATION COMPLETE ({elapsed:.2f}s)   ")
    print("==========================================================")

if __name__ == "__main__":
    main()
