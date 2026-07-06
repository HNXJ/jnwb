import os
import pathlib
import matplotlib.pyplot as plt
import sys
# Ensure project root is on sys.path
sys.path.insert(0, r'D:/workspace/omission')
import jnwb as oa
from jnwb.viz import raster_suite_omission

def main():
    # Path to NWB file (choose V182 example)
    nwb_path = pathlib.Path(r'D:/analysis/nwb/sub-V182o_ses-260629.nwb')
    if not nwb_path.is_file():
        raise FileNotFoundError(f'NWB file not found: {nwb_path}')
    # Load session
    session = oa.read(str(nwb_path), context='omission_glo_passive')
    # Get first stable_plus unit
    units_df = session.get_units(quality='stable_plus')
    if units_df.empty:
        raise ValueError('No stable_plus units found in session')
    # Determine unit ID (index may be the unit id)
    if hasattr(units_df, 'index') and not units_df.index.empty:
        unit_id = units_df.index[0]
    else:
        unit_id = units_df.iloc[0]['unit_id']
    # Generate raster suite figure
    fig = raster_suite_omission(session, unit_id=unit_id)
    # Output directory
    out_dir = pathlib.Path('outputs/figures')
    out_dir.mkdir(parents=True, exist_ok=True)
    # Save PNG and PDF
    base_name = f'raster_suite_unit_{unit_id}'
    png_path = out_dir / f'{base_name}.png'
    pdf_path = out_dir / f'{base_name}.pdf'
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved raster suite to {png_path} and {pdf_path}')

if __name__ == '__main__':
    main()
