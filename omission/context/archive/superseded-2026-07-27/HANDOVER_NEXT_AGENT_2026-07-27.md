# HANDOVER DOCUMENT: Omission 2026 Manuscript & Project State
**Date:** 2026-07-27  
**User:** Hamm  
**Package:** `jnwb`  
**Current Handover File:** `context/HANDOVER_NEXT_AGENT_2026-07-27.md`

---

## Executive Summary & Current Manuscript Status

The manuscript and analysis suite are in an **advanced production state** (Score: ~91–93/100). All 8 main figures + supplementary figures are fully generated, verified against empirical NWB session data, typeset inside the master Word document, and compiled into the master PDF and review ZIP package.

### Key Deliverables & Paths

| Deliverable | Path | Description |
| :--- | :--- | :--- |
| **Master PDF** | [omission-2026-manuscript-master.pdf](file:///D:/workspace/omission/context/omission-2026-manuscript-master.pdf) | Fully typeset PDF compiled via Word COM |
| **Master DOCX** | [omission-2026-manuscript-master.docx](file:///D:/workspace/omission/context/omission-2026-manuscript-master.docx) | Source Word manuscript with embedded PNG figures |
| **Master Review ZIP** | [omission_2026_manuscript_package.zip](file:///D:/workspace/omission/context/omission_2026_manuscript_package.zip) | Complete submission package containing DOCX, PDF, and high-res figure PNGs |
| **Draft Assets** | `D:/workspace/omission/context/draft-assets/` | High-res figure PNGs and SVGs (`figure_01` through `figure_08` + supplements) |
| **Labyrinth State** | `D:/workspace/omission/artifacts/.lab/` | Ontological graph nodes and SQLite ledger (`labyrinth.db`) |

---

## Hard Rules & Directives (MUST BE FOLLOWED BY NEXT AGENT)

1. **NO COLOR CODE CHANGES**: Never change color palettes on any existing figures without explicit instruction.
   - **Epoch Shading Patches** (`p1`→`p2`→`p3`→`p4`): `Yellow` (`#FCF9E3`) → `Purple` (`#F3E8F4`) → `Green` (`#E8F5E9`) → `Blue` (`#E1F5FE`).
   - **Condition Colors**: Standard=Gray (`#555555`), Omission=Red (`#D9534F`), Random Control=Teal (`#008080`).
   - Defined in: [.cursor/rules/omission-palette.mdc](file:///D:/workspace/omission/.cursor/rules/omission-palette.mdc) and [.agents/skills/jnwb-visualization/SKILL.md](file:///D:/workspace/omission/.agents/skills/jnwb-visualization/SKILL.md).

2. **FIGURE INSERTION ORDER IN DOCX**:
   - Always maintain strict ascending narrative figure order in `omission-2026-manuscript-master.docx`:
     `Figure 1 → Figure 2 → Figure 3 → Figure 4 → Figure 5 → Figure 6 → Figure 7 → Figure 8`
   - *Never* append figures in code-execution order (e.g. putting Fig 6 & 7 after Fig 8).

3. **EMPIRICAL DATA INTEGRITY**:
   - Figure 6 (TFR Spectrograms) is generated from **100% empirical precomputed TFR arrays** in `D:/workspace/data/tfr_arrays/`. *Do not replace with synthetic/Gaussian mock data.*
   - Figure 8 contains 5 multi-band subpanels (`a`–`e`: Alpha, Theta, Beta, Gamma, and cross-modal correlation).

4. **DECLARATIVE HEADINGS & CAPTION DISCIPLINE**:
   - All Results headings are **declarative scientific statements** (e.g., *"Omission-linked spiking is sparse and biased toward higher-order cortex."*). Do NOT revert to question-style headings.
   - Captions are **descriptive** (sample size, statistics, error bars) and do not contain pre-baked conclusion claims ("Together, these demonstrate...").

5. **DATA RETRIEVAL FOOTGUNS**:
   - `session.get_spike_times(unit_id)` takes the DataFrame **row index** (`units_df.index`), NOT the kilosort `unit_id` column.
   - Multi-area probe channel resolving must use `jnwb.addressing.map_peak_channel_to_area()`, NOT simple string splitting.

---

## Summary of Recent Modifications

1. **Editorial Polish Pass**:
   - Removed editing artifact `"Beco-occur"` from Introduction paragraph 11.
   - Converted 7 Results headings from question format to declarative headings.
   - Removed repetitive interpretive closing sentences from figure captions.
   - Condensed Discussion section paragraph 168 to reduce redundancy.
   - Moved the Software & Analysis Environment paragraph to the end of the Methods section.
   - Added missing DOIs to 10 key references.
   - Inserted explicit page break before Figure 7 to prevent crowding with Figure 6.

2. **Figure 8 Multi-Band Subpanel Expansion**:
   - Expanded Figure 8 to display multi-band LFP channel modulation across Alpha (8–12 Hz), Theta (3–8 Hz), Beta (14–30 Hz), and Gamma (30–80 Hz), along with the multi-band cross-modal rank correlation.

3. **Empirical Figure 6 Replacement**:
   - Re-computed Figure 6 using actual multi-session precomputed TFR `.npy` arrays.

4. **Figure Reordering in DOCX**:
   - Fixed element order in `omission-2026-manuscript-master.docx` so Figure 6 and Figure 7 appear before Figure 8.

---

## Remaining Backlog / Open Items for Next Agent

If the user asks for further refinements, prioritize these known items:

1. **Figure Aesthetic Unification (If explicitly requested by Hamm)**:
   - While figure content and data are verified, individual figure rendering software signatures vary slightly (Fig 1: Vector/Illustrator style; Fig 3: Ephys raster suite style; Fig 5: Forest plot; Fig 8: Composite multi-panel). Any aesthetic cleanup must preserve all current colors and layout rules.
2. **Supplemental Materials Audit**:
   - Ensure supplementary tables S1–S2 and supplementary figures S1–S4 remain in sync with the primary text if any sample sizes or census metrics are updated.
3. **Labyrinth Protocol Sync**:
   - Always run graph verification and append turn deltas to `artifacts/.lab/` after major edits.

---

## Verification Commands for Incoming Agent

To verify the state of the manuscript at any point, run:

```powershell
# 1. Audit Figure Order & Paragraph Headings in DOCX
python -c "
import docx
doc = docx.Document(r'D:\workspace\omission\context\omission-2026-manuscript-master.docx')
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if t.startswith('Figure'):
        print(f'[{i}] {t[:90]}')
"

# 2. Re-export Master PDF via Word COM (Windows Word required)
python -c "
import win32com.client, pathlib
docx_path = str(pathlib.Path(r'D:\workspace\omission\context\omission-2026-manuscript-master.docx').resolve())
pdf_path  = str(pathlib.Path(r'D:\workspace\omission\context\omission-2026-manuscript-master.pdf').resolve())
word = win32com.client.Dispatch('Word.Application')
word.Visible = False
doc = word.Documents.Open(docx_path)
doc.SaveAs(pdf_path, FileFormat=17)
doc.Close()
word.Quit()
print('PDF Exported Successfully')
"

# 3. Rebuild Review Zip Package
python scripts/build_master_review_package.py
```
