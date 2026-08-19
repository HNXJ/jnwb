import argparse
import pathlib
import matplotlib.pyplot as plt
import sys
# Ensure project root is on sys.path
sys.path.insert(0, r'D:/workspace/omission')
import omission as oa
from omission.jnwb_ext.viz import raster_suite_omission


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a raster suite figure for one unit.")
    parser.add_argument("--nwb", default=r"D:/analysis/nwb/sub-V182o_ses-260629.nwb",
                         help="Path to .nwb file.")
    parser.add_argument("--unit-id", type=int, default=None,
                         help="Unit ID to plot. If omitted, uses the first stable_plus unit.")
    parser.add_argument("--out-dir", default="outputs/figures",
                         help="Output directory for PNG/PDF.")
    return parser.parse_args()


def main():
    args = parse_args()
    nwb_path = pathlib.Path(args.nwb)
    if not nwb_path.is_file():
        raise FileNotFoundError(f'NWB file not found: {nwb_path}')

    session = oa.read(str(nwb_path), context='omission_glo_passive')

    if args.unit_id is not None:
        unit_id = args.unit_id
    else:
        units_df = session.get_units(quality='stable_plus')
        if units_df.empty:
            raise ValueError('No stable_plus units found in session')
        if hasattr(units_df, 'index') and not units_df.index.empty:
            unit_id = units_df.index[0]
        else:
            unit_id = units_df.iloc[0]['unit_id']

    fig = raster_suite_omission(session, unit_id=unit_id)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = f'raster_suite_unit_{unit_id}'
    png_path = out_dir / f'{base_name}.png'
    pdf_path = out_dir / f'{base_name}.pdf'
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved raster suite to {png_path} and {pdf_path}')


if __name__ == '__main__':
    main()
