import argparse
import pathlib
import sys
import csv

# Add project root to sys.path
sys.path.insert(0, r'D:/workspace/omission')
import omission as oa


def parse_args():
    parser = argparse.ArgumentParser(
        description="List stable_plus units for one session (or all sessions if --session is omitted)."
    )
    parser.add_argument("--session", default=None,
                         help="Session filename or stem substring (e.g. 'sub-V182o_ses-260629'). "
                              "If omitted, processes every .nwb file under --nwb-dir.")
    parser.add_argument("--nwb-dir", default=r"D:/analysis/nwb",
                         help="Directory containing .nwb files.")
    parser.add_argument("--out", default="outputs/stable_plus_units.csv",
                         help="Output CSV path.")
    return parser.parse_args()


def main():
    args = parse_args()
    nwb_dir = pathlib.Path(args.nwb_dir)
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nwb_files = sorted(nwb_dir.glob('*.nwb'))
    if args.session:
        nwb_files = [f for f in nwb_files if args.session in f.stem]
        if not nwb_files:
            print(f"No .nwb files matching --session={args.session!r} under {nwb_dir}")
            sys.exit(2)

    with out_path.open('w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['session', 'unit_id', 'area', 'layer', 'firing_rate', 'snr'])
        for nwb_file in nwb_files:
            try:
                sess = oa.read(str(nwb_file), context='omission_glo_passive')
                units = sess.get_units(quality='stable_plus')
                if units is None or units.empty:
                    continue
                for uid, row in units.iterrows():
                    area = row.get('area', '')
                    layer = row.get('layer', '')
                    fr = row.get('firing_rate', '')
                    snr = row.get('snr', '')
                    writer.writerow([nwb_file.name, uid, area, layer, fr, snr])
            except Exception as e:
                print(f'Error processing {nwb_file.name}: {e}')
    print('CSV written to', out_path)


if __name__ == "__main__":
    main()
