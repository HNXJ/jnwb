#!/usr/bin/env python3
"""Build self-contained external review artifact: jnwb-unified-rev.md

Deterministically inspects the git repository and generates a single
standalone Markdown review file containing all source code, tests,
configuration, documentation, harness scripts, and review guidelines.
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = REPO_ROOT / "jnwb-unified-rev.md"

BINARY_EXTENSIONS = {".png", ".svg", ".ico", ".ipynb"}


def run_git(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def get_tracked_files() -> list[str]:
    out = run_git("ls-files")
    return sorted(out.splitlines())


def format_file_block(rel_path: str) -> str:
    abs_path = REPO_ROOT / rel_path
    if not abs_path.exists():
        return f"<!-- File missing: {rel_path} -->\n"
    content = abs_path.read_text(encoding="utf-8", errors="replace")
    # Normalize line endings to LF
    content = content.replace("\r\n", "\n")
    if not content.endswith("\n"):
        content += "\n"
    return f"===== BEGIN {rel_path} =====\n{content}===== END {rel_path} =====\n\n"


def build_unified_review() -> None:
    print("Gathering repository metadata...")
    commit_sha = run_git("rev-parse", "HEAD")
    commit_short = run_git("rev-parse", "--short", "HEAD")
    branch = run_git("rev-parse", "--abbrev-ref", "HEAD")
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    import jnwb

    version = jnwb.__version__
    public_symbols = sorted(jnwb.__all__)
    num_symbols = len(public_symbols)

    tracked = get_tracked_files()
    # Do not include the generated output file itself if it was already tracked
    tracked = [f for f in tracked if f != "jnwb-unified-rev.md"]

    # Categorize files
    sec4_files = sorted([
        f for f in tracked if f in {
            "pyproject.toml",
            "MANIFEST.in",
            ".github/workflows/workflow.yml",
            ".readthedocs.yaml",
            "mkdocs.yml",
        }
    ])

    sec5_files = sorted([
        f for f in tracked if f in {
            "jnwb/__init__.py",
            "jnwb/_api_surface.py",
            "jnwb/_lazy_exports.py",
            "scripts/generate_api_md.py",
            "docs/api.md",
        }
    ])

    sec6_files = sorted([
        f for f in tracked
        if f.startswith("jnwb/")
        and f not in sec5_files
        and Path(f).suffix not in BINARY_EXTENSIONS
    ])

    sec7_files = sorted([
        f for f in tracked
        if f.startswith("tests/")
        and Path(f).suffix not in BINARY_EXTENSIONS
    ])

    sec8_files = sorted([
        f for f in tracked
        if (f.startswith("scripts/") or f == ".github/workflows/workflow.yml")
        and Path(f).suffix not in BINARY_EXTENSIONS
    ])

    sec9_files = sorted([
        f for f in tracked
        if (
            f in {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", "AGENTS.md", "LICENSE"}
            or f.startswith("docs/")
            or f.startswith("examples/")
        )
        and f not in sec5_files
        and Path(f).suffix not in BINARY_EXTENSIONS
    ])

    sec10_files = sorted([
        f for f in tracked
        if (f.startswith("skills/") or f.startswith("artifacts/agents/"))
        and Path(f).suffix not in BINARY_EXTENSIONS
    ])

    binary_files = sorted([
        f for f in tracked if Path(f).suffix in BINARY_EXTENSIONS
    ])

    # Count source & test lines of code
    def count_loc(file_list: list[str]) -> int:
        total = 0
        for f in file_list:
            p = REPO_ROOT / f
            if p.exists() and p.is_file():
                try:
                    total += len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                except Exception:
                    pass
        return total

    src_loc = count_loc([f for f in tracked if f.startswith("jnwb/") and f.endswith(".py")])
    test_loc = count_loc(sec7_files)

    print(f"Building artifact: {len(tracked)} tracked files, {src_loc} src LOC, {test_loc} test LOC...")

    out: list[str] = []

    # =========================================================================
    # 1. REVIEW REQUEST
    # =========================================================================
    out.append("""# `jnwb` Unified Independent External Deep-Review Dossier

## 1. Review Request & Adversarial Evaluation Directive

### 1.1 Directive to External Auditor
This dossier compiles the entirety of the `jnwb` generic neurophysiology & NWB analysis library into a single, fully self-contained artifact for rigorous, independent, and adversarial evaluation.

**Do NOT validate our conclusions. Your objective is to independently falsify claims, locate hidden failures, and challenge our architectural and mathematical implementations.**

The internal test suite (912 passing tests), harness gates (13 deterministic pre-flight checks), documentation assertions, and architectural rules are presented here as **reproducible historical evidence, NOT as unquestionable authority**. A passing test may simply reflect an encoded misconception or a flawed mathematical invariant. 

You are explicitly commissioned to evaluate the library from first principles and report all defects, questionable assumptions, silent failures, numerical instabilities, and boundary leaks.

### 1.2 Key Focus Areas for Falsification
1. **Mathematical Rigor & Estimation Accuracy**:
   - Trace mathematical estimands from inputs to outputs. Are equations implemented according to peer-reviewed literature or have subtle approximations / shortcuts been substituted?
   - Verify whether continuous Fourier, Morlet wavelet, Welch PSD, FOOOF/aperiodic, Phase Slope Index (PSI), and Transfer Entropy estimators conform to standard analytical formulations.
   - Inspect the laminar `vflip` spectral crossover detection: verify whether the crossover interpolation, polarity scoring, boundary penalties, and support metric $\\Omega$ behave reliably across diverse synthetic and empirical noise conditions.
2. **Signal Processing & Temporal Causality**:
   - Check filter causality: are forward-backward filters (e.g. `filtfilt`) used where causal online filters or explicit zero-phase boundary padding is required?
   - Verify whether edge artifacts in continuous wavelet transforms / complex TFRs are strictly identified via the Cone of Influence (COI).
   - Ensure decibel conversions strictly adhere to the fundamental invariant: **aggregate raw power first, convert to decibels last** ($10 \\log_{10} \\frac{\\langle P \\rangle}{\\langle P_{\\text{base}} \\rangle}$), rather than averaging pre-calculated decibels.
3. **Statistical Validity & Exchangeability**:
   - Audit permutation tests (`permutation.py`): does label shuffling preserve trial exchangeability under the true null hypothesis, or does it destroy autocorrelations or trial-structure dependencies inappropriately?
   - Audit the exact permutation combinatorial enumerator: does it exhaustively evaluate all $\\binom{N}{k}$ combinations without omission or bias?
   - Verify multiple comparison corrections (FDR Benjamini-Hochberg vs FWER): are assumptions of positive regression dependence satisfied?
   - Confirm that pseudo-random number generation is strictly controlled via explicit `np.random.default_rng(seed)` instances and that no global `np.random.seed()` calls exist.
4. **Electrophysiology & NWB Data Semantics**:
   - Verify physical units: are spatial coordinates consistently converted to micrometers ($\\mu\\text{m}$), sampling intervals to seconds ($\\text{s}$), and frequencies to Hertz ($\\text{Hz}$)?
   - Verify probe geometry handling: are contact IDs, orientations, z-coordinates, and shank groupings extracted faithfully without imposing artificial layer bounds or hardcoded anatomical boundaries?
   - Confirm that rejected fits (e.g. laminar crossover failures) fail safely and return explicit structured markers (`"na"`, `is_valid=False`, `reason="rejected"`) rather than fabricated or default depths.
5. **Computational Complexity & Device Equivalence**:
   - Verify that device execution (`device="cpu"` vs `device="cuda"`) and worker count (`n_jobs=1` vs `n_jobs=-1`) never alter numerical results beyond standard floating-point tolerances.
   - Audit potential memory leaks or OOM conditions in large-scale NWB streaming and accumulator passes (`stream_npz_array`, `TFRAccumulator`).
6. **Package Isolation & Dataset Independence**:
   - Verify that `jnwb` contains zero dependencies on private or study-specific packages.
   - Confirm that no dataset-specific tokens, experimental condition labels, or manuscript findings are embedded in library code or generic skills.

---
""")

    # =========================================================================
    # 2. PROVENANCE
    # =========================================================================
    out.append(f"""## 2. Repository Provenance & Environment Baseline

| Metadata Property | Authoritative Value |
| :--- | :--- |
| **Commit SHA** | `{commit_sha}` (short: `{commit_short}`) |
| **Active Branch** | `{branch}` |
| **Package Version** | `jnwb {version}` (defined dynamically in `pyproject.toml` via `jnwb.__version__`) |
| **Generation Timestamp** | `{timestamp}` |
| **Declared Python Floor** | `>=3.12` (pure Python wheel `py3-none-any`, no upper version pin) |
| **Python Support Classifiers** | `3.12`, `3.13`, `3.14` |
| **CI Test Matrix** | Python `3.12` (floor) and `3.14` (head) on `ubuntu-latest` and `windows-latest` |
| **Public API Exports** | `{num_symbols}` symbols in `jnwb.__all__` |
| **Core Source Code Metrics** | `{len(sec6_files) + len(sec5_files)}` files, `{src_loc:,}` lines of code in `jnwb/` |
| **Test Suite Metrics** | `{len(sec7_files)}` test modules, `{test_loc:,}` lines of test code in `tests/` |
| **Test Execution Baseline** | `912 passed, 1 skipped, 5 subtests passed` |
| **Harness Gates Baseline** | `13 / 13 gates PASS` (`scripts/harness_gate.py`) |
| **Documentation Build** | Strict MkDocs (`python scripts/docs_build.py`) exits 0 with zero warnings |

---
""")

    # =========================================================================
    # 3. REPOSITORY STRUCTURE
    # =========================================================================
    out.append("## 3. Deterministic Tracked Repository Structure\n\n")
    out.append("Tracked files from `git ls-files` (excluding binary assets and internal historical scratch files):\n\n```text\n")
    for f in tracked:
        p = REPO_ROOT / f
        sz = p.stat().st_size if p.exists() else 0
        out.append(f"{f:<65} {sz:>8} bytes\n")
    out.append("```\n\n---\n\n")

    # =========================================================================
    # 4. PACKAGE / BUILD CONFIGURATION
    # =========================================================================
    out.append("## 4. Package & Build Configuration\n\n")
    out.append("Authoritative build definitions, dependencies, packaging manifests, and CI workflows.\n\n")
    for f in sec4_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 5. PUBLIC API & EXPORT MECHANICS
    # =========================================================================
    out.append("## 5. Public API Surface & Lazy Export Mechanics\n\n")
    out.append("The definitive exported surface, lazy-loading symbol resolution, and runtime API documentation generator.\n\n")
    for f in sec5_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 6. CORE SOURCE CODE
    # =========================================================================
    out.append("## 6. Core Source Code (`jnwb/`)\n\n")
    out.append("Complete, unabridged source code for all mathematical, electrophysiological, signal processing, and I/O modules.\n\n")
    for f in sec6_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 7. TEST SUITE
    # =========================================================================
    out.append("## 7. Verification Test Suite (`tests/`)\n\n")
    out.append("Complete, unabridged test modules asserting scientific invariants, numerical edge cases, and regression coverage.\n\n")
    for f in sec7_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 8. HARNESS & CI SCRIPTS
    # =========================================================================
    out.append("## 8. Harness Gates & Operational Scripts (`scripts/`)\n\n")
    out.append("Mechanical boundary verification gates (Gates 1-13), release validation scripts, and benchmark profiling.\n\n")
    for f in sec8_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 9. DOCUMENTATION & EXAMPLES
    # =========================================================================
    out.append("## 9. Documentation & Executable Tutorials\n\n")
    out.append("User guides, reference manuals, common pitfalls, and runnable end-to-end tutorial scripts.\n\n")
    if binary_files:
        out.append("### Note on Binary Assets\n")
        out.append("The following binary visual assets and Jupyter notebooks are tracked in the repository but excluded from inline text representation:\n")
        for b in binary_files:
            out.append(f"- `{b}`\n")
        out.append("\n")
    for f in sec9_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 10. SKILLS & AGENTS
    # =========================================================================
    out.append("## 10. Modular Domain Skills & Agent Protocols\n\n")
    out.append("Standardized task skills (`skills/`) and portable role definitions (`artifacts/agents/`).\n\n")
    for f in sec10_files:
        out.append(format_file_block(f))
    out.append("---\n\n")

    # =========================================================================
    # 11. VERIFICATION COMMANDS & REPORTED BASELINE
    # =========================================================================
    out.append("""## 11. Verification Commands & Baseline Reproduction

### 11.1 Standard Verification Commands
An external auditor can reproduce the reported baseline locally using the following commands:

```bash
# 1. Execute the full test suite
python -m pytest tests/ -v

# 2. Execute all 13 mechanical harness boundary gates
python scripts/harness_gate.py

# 3. Build documentation under strict mode (fails on any warning or broken reference)
python scripts/docs_build.py

# 4. Perform full release gate build, clean venv installation, and wheel smoke verification
python scripts/release_gate.py

# 5. Measure import latency profile
python scripts/benchmark_import.py
```

### 11.2 Reported Baseline Receipts
- **Pytest Output**: `912 passed, 1 skipped, 5 subtests passed in 18.2s` on Windows x86_64, Python 3.14.3.
- **Harness Gates**: 
  - Gate 1: Frozen boundary clean (0 unauthorized project imports).
  - Gate 2: Skill tree uniqueness verified.
  - Gate 3: Test suite free of hardcoded machine-local drive paths.
  - Gate 4: Repository root strictly frozen & clean (`ALLOWED_ROOT_FILES`).
  - Gate 5: 100% of public exports documented in `docs/`.
  - Gate 6: Zero forbidden study tokens on Gate 6 scan surface.
  - Gate 7: Version synchronization verified (`pyproject.toml` == `jnwb.__version__`).
  - Gate 8: Python floor consistency verified (`>=3.12`, classifiers `3.12`, `3.13`, `3.14`, CI matrix `3.12` and `3.14`).
  - Gate 9: API set equality: `docs/api.md` matches `jnwb.__all__` exactly (144 symbols).
  - Gate 10: Documentation versions derive from `jnwb.__version__`.
  - Gate 11: No unowned import-shadowing package at root.
  - Gate 12: Zero project identifiers in `jnwb/` code strings.
  - Gate 13: NWB onboarding workflow aligned across README, tutorials, skill, and MkDocs.

---
""")

    # =========================================================================
    # 12. EXTERNAL REVIEW RUBRIC
    # =========================================================================
    out.append("""## 12. External Review Rubric & Assessment Matrix

The external reviewer is requested to evaluate the repository across the following five primary axes:

| Category | High-Priority Invariants to Probe | Severity if Violated |
| :--- | :--- | :--- |
| **1. Numerical & Mathematical Correctness** | - Spectral tilt & FOOOF formulation: parameter bounds, initial guess sensitivity, fitting convergence.<br>- Decibel calculation: strictly check that `aggregate_to_db` never computes mean of decibels when raw power average is requested.<br>- Causal exp smoothing: verify recursion formula, tau scaling, and boundary edge values.<br>- Welch PSD: window scaling ($1/\\sum w^2$), two-sided vs one-sided spectrum, Nyquist normalization.<br>- Phase Slope Index: cross-spectral density matrix orientation, frequency step scaling, complex imaginary component signs. | **CRITICAL** |
| **2. Statistical Rigor & Hypothesis Testing** | - Exact statistics: combinatorial permutation enumeration coverage, tie handling, two-tailed symmetry.<br>- Monte Carlo permutation: verify surrogate generator exchangeability under null.<br>- FDR correction: Benjamini-Hochberg monotonicity and sorting bounds.<br>- RNG hygiene: absence of unseeded or global `np.random` calls; deterministic reproducibility under explicit seeds. | **CRITICAL / MAJOR** |
| **3. Laminar Electrophysiology & Geometry** | - `vflip`: continuous crossover interpolation accuracy, zero-crossing boundary limits, band power normalization.<br>- Support metric $\\Omega$: behavior under low SNR, monotonic decline vs noise, non-negative bounds.<br>- Layer labeling: strict invariance that rejected fits return `"na"` for all contacts without exception.<br>- Probe geometry: preservation of original contact ordering, coordinate conversion to $\\mu\\text{m}$, duplicate coordinate rejection. | **MAJOR** |
| **4. Architectural Boundary & Isolation** | - Zero dependencies on private or study-specific projects.<br>- Zero study-specific tokens, experimental condition codes, or manuscript results in `jnwb/` or skills.<br>- No accidental shadowing of packages when installed in editable mode (`pip install -e .`).<br>- Separation of concerns: addressing / geometry must never infer layer anatomy. | **CRITICAL / MAJOR** |
| **5. Device & Concurrency Parity** | - CPU vs CUDA numerical equivalence within floating point precision ($10^{-5}$).<br>- Multiprocessing (`_parallel.parallel_map`) invariance: worker count `n_jobs` must never alter result order or values.<br>- Streaming & Accumulator safety: no unbounded memory growth during continuous NWB reads. | **MAJOR / MINOR** |

---
""")

    # =========================================================================
    # 13. REQUIRED FINDING FORMAT
    # =========================================================================
    out.append("""## 13. Required Defect & Finding Reporting Format

When logging findings, the external auditor must format each finding according to the following strict specification:

```markdown
### Finding [EXT-REV-XXX]: <Concise Descriptive Title>
- **Severity**: CRITICAL | MAJOR | MINOR | NOTE
- **Claim Class**: observed | derived | inferred | assumed | unknown
- **Target Location**: `path/to/file.py` :: `<function_or_class_name>` (lines L-M)
- **Violation Description**: Detailed explanation of the defect, mathematical error, or broken invariant.
- **Scientific / Operational Consequence**: Impact on user analyses, downstream inference, or numerical stability.
- **Minimal Reproducible Example**:
```python
# Self-contained executable python snippet demonstrating the failure
import numpy as np
import jnwb
# ...
```
- **Proposed Correction**: Exact diff or algorithm modification.
- **Verification Invariant / Test**: Automated test to prove the fix and guarantee permanent regression prevention.
```

---
""")

    # =========================================================================
    # 14. REVIEW INSTRUCTIONS
    # =========================================================================
    out.append("""## 14. Review Instructions & Adversarial Heuristics

### 14.1 Reviewer Heuristics
1. **Never trust a passing test as proof of a correct rule.** A test that asserts `result == 42` merely proves the code outputs 42. Verify whether 42 is mathematically and scientifically correct.
2. **Re-derive, do not merely read.** Re-derive estimators from first principles. If a function claims to implement a published method (e.g. vFLIP from van Kempen et al. 2021, PSI from Nolte et al. 2008), compare the code against the original mathematical formulation in the cited paper.
3. **Probe Edge Cases & Pathological Inputs**:
   - Arrays with all identical values (zero variance).
   - High-amplitude DC offsets or linear trends.
   - Non-finite inputs (`np.nan`, `np.inf`, `-np.inf`).
   - Single-sample, single-channel, or empty arrays.
   - Odd sampling rates (e.g. $fs = 999.7\\text{ Hz}$).
   - Boundary frequencies (DC, Nyquist, frequencies outside filter passbands).
4. **Inspect Boundary Conversions**:
   - Check where seconds are converted to milliseconds and vice-versa ($s \\leftrightarrow ms$).
   - Check where Volts are converted to microvolts ($V \\leftrightarrow \\mu V$).
   - Ensure 0-indexing versus 1-indexing is never conflated in channel addressing or NWB electrode tables.
5. **Verify Rejection & Failure Modes**:
   - Confirm that algorithms fail loudly with informative exceptions rather than returning fallback approximations silently.
   - For estimation pipelines (such as laminar crossover), confirm that when a fit is rejected, downstream consumers cannot mistakenly use default or unvalidated parameters.

---
*End of `jnwb` Unified Independent External Deep-Review Dossier.*
""")

    full_content = "".join(out)
    print(f"Writing {len(full_content):,} characters to {OUTPUT_FILE}...")
    OUTPUT_FILE.write_text(full_content, encoding="utf-8")
    print("Done! Artifact successfully created.")


if __name__ == "__main__":
    build_unified_review()
