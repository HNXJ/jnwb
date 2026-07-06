import os
import pathlib
import sys
import matplotlib.pyplot as plt

# Ensure project root on path
sys.path.insert(0, r'D:/workspace/omission')
import jnwb as oa
from jnwb.viz import lfp_tfr_trace_suite_omission

def main():
    # Path to NWB file (use the same V182 example)
    nwb_path = pathlib.Path(r'D:/analysis/nwb/sub-V182o_ses-260629.nwb')
    if not nwb_path.is_file():
        raise FileNotFoundError(f'NWB file not found: {nwb_path}')
    # Load session
    session = oa.read(str(nwb_path), context='omission_glo_passive')
    # Generate TFR trace suite for FEF superficial layer
    fig = lfp_tfr_trace_suite_omission(session, area='FEF', layer='superficial')
    # Save output
    out_dir = pathlib.Path('outputs/figures')
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = f'tfr_suite_FEF_superficial'
    png_path = out_dir / f'{base_name}.png'
    pdf_path = out_dir / f'{base_name}.pdf'
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved TFR suite to {png_path} and {pdf_path}')

if __name__ == '__main__':
    main()
