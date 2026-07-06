import pathlib, sys, csv

# Add project root to sys.path
sys.path.insert(0, r'D:/workspace/omission')
import jnwb as oa

nwb_dir = pathlib.Path(r'D:/analysis/nwb')
out_path = pathlib.Path('outputs/filtered_stable_plus_units.csv')
out_path.parent.mkdir(parents=True, exist_ok=True)

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return None

with out_path.open('w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['session','unit_id','classification','snr','firing_rate','area','layer'])
    for nwb_file in nwb_dir.glob('*.nwb'):
        try:
            sess = oa.read(str(nwb_file), context='omission_glo_passive')
            units = sess.get_units(quality='stable_plus')
            if units is None or units.empty:
                continue
            for uid, row in units.iterrows():
                snr = row.get('snr')
                fr = row.get('firing_rate')
                if snr is None or fr is None:
                    continue
                if snr <= 1.0 or fr <= 5.0:
                    continue
                # Classification flags (may be missing)
                o_plus = bool(row.get('sig_o_plus', False))
                s_plus = bool(row.get('sig_s_plus', False))
                s_minus = bool(row.get('sig_s_minus', False))
                if o_plus:
                    cls = 'O+'
                elif s_plus:
                    cls = 'S+'
                elif s_minus:
                    cls = 'S-'
                else:
                    cls = 'Null'
                area = row.get('area','')
                layer = row.get('layer','')
                writer.writerow([nwb_file.name, uid, cls, snr, fr, area, layer])
        except Exception as e:
            print(f'Error processing {nwb_file.name}: {e}')
print('CSV written to', out_path)
