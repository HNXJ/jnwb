"""
Master Review Package Builder for 8-Figure Alignment
======================================================
Bundles master Word docx, PDF, figures 1 to 8, author response,
onboarding manifest, and reproducibility notebook into zip.
Places output zip inside context/ folder.
"""

import zipfile
import pathlib

REPO = pathlib.Path(r'D:\workspace\omission')
CONTEXT = REPO / 'context'
ZIP_OUT = CONTEXT / 'omission_2026_manuscript_package.zip'
DRAFT_ASSETS = CONTEXT / 'draft-assets'

files_to_pack = [
    CONTEXT / 'omission-2026-manuscript-master.pdf',
    CONTEXT / 'omission-2026-manuscript-master.docx',
    DRAFT_ASSETS / 'HANDOVER_NEXT_AGENT_2026-07-27.md',
    DRAFT_ASSETS / 'figure_01_madelane_setup.png',
    DRAFT_ASSETS / 'figure_02_sequential_omission_paradigm.png',
    DRAFT_ASSETS / 'figure_03_spiking_exemplars.png',
    DRAFT_ASSETS / 'figure_04_spiking_population_census.png',
    DRAFT_ASSETS / 'figure_05_spiking_glmm_forest.png',
    DRAFT_ASSETS / 'figure_06_lfp_tfr_spectrograms.png',
    DRAFT_ASSETS / 'figure_07_lfp_band_power_population.png',
    DRAFT_ASSETS / 'figure_08_lfp_lmm_dissociation_synthesis.png',
]

with zipfile.ZipFile(ZIP_OUT, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for f in files_to_pack:
        if f.exists():
            z.write(f, arcname=f.name)
            print(f'Packed: {f.name} ({f.stat().st_size} bytes)')

print(f'Successfully built master review zip package inside context/: {ZIP_OUT} ({ZIP_OUT.stat().st_size} bytes)')
