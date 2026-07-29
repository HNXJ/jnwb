"""
Physical Image Replacement Script for omission-2026-manuscript-master.docx
=============================================================================
Directly replaces the binary image blobs in the docx media archive with the new 100% white background PNGs:
- media/image6.png (Figure 7) -> figure7_coherence_matrix_clean.png (10x10 white background matrix)
- media/image8.png (Figure 9) -> figure9_plv_distributions_clean.png (100% white PLV plot)
- media/image9.png (Figure 10) -> figure10_granger_matrix_clean.png (100% white Granger matrix)
- media/image3.png (Figure 4) -> figure1_main_killer_summary.png (Clean Population TFR heatmap)
"""

import docx
import pathlib

REPO = pathlib.Path(r'D:\workspace\omission')
DOCX_PATH = REPO / 'context' / 'omission-2026-manuscript-master.docx'
FIGS_DIR = REPO / 'context' / 'figures'

doc = docx.Document(str(DOCX_PATH))

# Map media paths to new generated figure paths
replacements = {
    'media/image6.png': FIGS_DIR / 'figure7_coherence_matrix_clean.png',
    'media/image8.png': FIGS_DIR / 'figure9_plv_distributions_clean.png',
    'media/image9.png': FIGS_DIR / 'figure10_granger_matrix_clean.png',
    'media/image3.png': FIGS_DIR / 'figure5_stim_vs_omission_contrast.png'
}

print("=== PHYSICALLY REPLACING BINARY IMAGE BLOBS IN MASTER DOCX ===")

replaced_count = 0
for rel_id, rel in doc.part.rels.items():
    if 'image' in rel.target_ref:
        target_ref = rel.target_ref
        if target_ref in replacements and replacements[target_ref].exists():
            new_blob = replacements[target_ref].read_bytes()
            # Replace blob directly in docx part
            rel.target_part._blob = new_blob
            replaced_count += 1
            print(f"Successfully replaced {target_ref} ({len(new_blob):,} bytes) with {replacements[target_ref].name}")

doc.save(str(DOCX_PATH))
print(f"\nPhysical replacement completed! Total images replaced: {replaced_count}")
