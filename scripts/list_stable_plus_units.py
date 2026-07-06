import pathlib, sys, csv

# Add project root to sys.path
sys.path.insert(0, r'D:/workspace/omission')
import jnwb as oa

# Directory containing NWB files
nwb_dir = pathlib.Path(r'D:/analysis/nwb')

# Output CSV path
out_path = pathlib.Path('outputs/stable_plus_units.csv')
out_path.parent.mkdir(parents=True, exist_ok=True)

with out_path.open('w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['session','unit_id','area','layer','firing_rate','snr'])
    for nwb_file in nwb_dir.glob('*.nwb'):
        try:
            sess = oa.read(str(nwb_file), context='omission_glo_passive')
            units = sess.get_units(quality='stable_plus')
            if units is None or units.empty:
                continue
            for uid, row in units.iterrows():
                area = row.get('area','')
                layer = row.get('layer','')
                fr = row.get('firing_rate','')
                snr = row.get('snr','')
                writer.writerow([nwb_file.name, uid, area, layer, fr, snr])
        except Exception as e:
            print(f'Error processing {nwb_file.name}: {e}')
print('CSV written to', out_path)
