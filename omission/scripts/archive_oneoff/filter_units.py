import pathlib, sys, csv

# Add project root to sys.path
sys.path.insert(0, r'D:/workspace/omission')
import omission as oa
from omission.jnwb_ext.unit_classification import classify_session_units

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
    writer.writerow(['session', 'unit_id', 'classification', 'snr', 'firing_rate', 'area', 'layer'])
    for nwb_file in nwb_dir.glob('*.nwb'):
        try:
            sess = oa.read(str(nwb_file), context='omission_glo_passive')
            units = sess.get_units(quality='stable_plus')
            if units is None or units.empty:
                continue

            # SNR/FR gate first (cheap), matching the original filter
            gated = {}
            for uid, row in units.iterrows():
                snr = safe_float(row.get('snr'))
                fr = safe_float(row.get('firing_rate'))
                if snr is None or fr is None:
                    continue
                if snr <= 1.0 or fr <= 5.0:
                    continue
                gated[int(uid)] = {'snr': snr, 'firing_rate': fr,
                                    'area': row.get('area', ''), 'layer': row.get('layer', '')}

            if not gated:
                continue

            # Real shuffle-controlled O+/S+/S- classification (omission.jnwb_ext.unit_classification),
            # only on the units that already passed the SNR/FR gate (keeps this fast).
            class_df = classify_session_units(sess, unit_ids=list(gated.keys()))

            for uid, meta in gated.items():
                if uid in class_df.index:
                    cls = class_df.loc[uid, 'display_class']
                else:
                    cls = 'Other'
                writer.writerow([nwb_file.name, uid, cls, meta['snr'], meta['firing_rate'],
                                  meta['area'], meta['layer']])
        except Exception as e:
            print(f'Error processing {nwb_file.name}: {e}')
print('CSV written to', out_path)
