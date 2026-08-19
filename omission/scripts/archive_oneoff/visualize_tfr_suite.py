import argparse
import pathlib
import sys
import matplotlib.pyplot as plt

# Ensure project root on path
sys.path.insert(0, r'D:/workspace/omission')
import omission as oa
from omission.jnwb_ext.viz import lfp_tfr_trace_suite_omission


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a TFR trace suite figure for one area/layer.")
    parser.add_argument("--nwb", default=r"D:/analysis/nwb/sub-V182o_ses-260629.nwb",
                         help="Path to .nwb file.")
    parser.add_argument("--area", default="FEF", help="Brain area.")
    parser.add_argument("--layer", default="superficial", choices=["superficial", "deep"],
                         help="Cortical layer.")
    parser.add_argument("--out-dir", default="outputs/figures",
                         help="Output directory for PNG/PDF.")
    return parser.parse_args()


def main():
    args = parse_args()
    nwb_path = pathlib.Path(args.nwb)
    if not nwb_path.is_file():
        raise FileNotFoundError(f'NWB file not found: {nwb_path}')

    session = oa.read(str(nwb_path), context='omission_glo_passive')
    fig = lfp_tfr_trace_suite_omission(session, area=args.area, layer=args.layer)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = f'tfr_suite_{args.area}_{args.layer}'
    png_path = out_dir / f'{base_name}.png'
    pdf_path = out_dir / f'{base_name}.pdf'
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved TFR suite to {png_path} and {pdf_path}')


if __name__ == '__main__':
    main()
