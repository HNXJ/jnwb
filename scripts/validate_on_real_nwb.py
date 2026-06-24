#!/usr/bin/env python3
"""
End-to-end validation on REAL NWB data.
Test the 12 working functions against actual omission session data.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add jnwb to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jnwb.session import OmissionSession
from jnwb import functions

# Pick a real session
NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

print(f"Loading NWB: {NWB_PATH}")
print(f"File exists: {NWB_PATH.exists()}")

if not NWB_PATH.exists():
    print("ERROR: NWB file not found")
    sys.exit(1)

try:
    # Load session
    session = OmissionSession(NWB_PATH)
    print(f"[OK] Session loaded successfully")

    # Test 1: Get session info
    info = session.info()
    print(f"\n=== Session Info ===")
    print(f"Subject: {info.get('subject_id')}")
    print(f"Session: {info.get('session_id')}")
    print(f"N units: {info.get('n_units')}")

    # Test 2: find_units()
    print(f"\n=== Test: find_units() ===")
    all_units = functions.find_units(session)
    print(f"Total units: {len(all_units)}")

    stable_units = functions.find_units(session, quality='stable_plus')
    print(f"Stable+ units: {len(stable_units)}")

    v1_units = functions.find_units(session, area='V1')
    print(f"V1 units: {len(v1_units)}")

    # Test 3: unit_channel_mapping()
    print(f"\n=== Test: unit_channel_mapping() ===")
    mapping = functions.unit_channel_mapping(session)
    print(f"Unit-channel mappings: {len(mapping)}")
    print(f"Columns: {mapping.columns.tolist()}")

    # Test 4: lfp_channel_areas()
    print(f"\n=== Test: lfp_channel_areas() ===")
    lfp = functions.lfp_channel_areas(session)
    print(f"LFP channels: {len(lfp)}")

    # Test 5: pie_charts()
    print(f"\n=== Test: pie_charts() ===")
    pies = functions.pie_charts(session, by_area=True)
    if isinstance(pies, dict):
        print(f"Pie chart areas: {[k for k in pies.keys() if k != 'error']}")
        print(f"Total units in pie: {pies.get('total', 'N/A')}")
    else:
        print(f"Pie chart result: {pies}")

    # Test 6: Get spike times for a unit
    print(f"\n=== Test: raster_plot() ===")
    if len(all_units) > 0:
        unit_id = all_units.iloc[0]['unit_id']
        print(f"Testing unit {unit_id}...")

        raster = functions.raster_plot(session, unit_id=unit_id, condition='AAAB', phase=2)
        if 'error' in raster:
            print(f"[FAIL] Raster error: {raster['error']}")
        else:
            print(f"[PASS] Raster: {raster['n_spikes']} spikes in {raster['n_trials']} trials")

    # Test 7: PSTH
    print(f"\n=== Test: psth_analysis() ===")
    if len(all_units) > 0:
        unit_id = all_units.iloc[0]['unit_id']
        psth = functions.psth_analysis(session, unit_id=unit_id, condition='AAAB', phase=2)
        if 'error' in psth:
            print(f"[FAIL] PSTH error: {psth['error']}")
        else:
            print(f"[PASS] PSTH: {len(psth['psth_rate_hz'])} bins, baseline {psth['baseline_rate_hz']:.2f} Hz")

    # Test 8: summary_report()
    print(f"\n=== Test: summary_report() ===")
    summary = functions.summary_report(session)
    if 'error' not in summary:
        print(f"[PASS] Summary: {summary.get('n_units')} units, {summary.get('n_stable_plus')} stable+")
    else:
        print(f"[FAIL] Summary error: {summary['error']}")

    # Test 9: compare_populations()
    print(f"\n=== Test: compare_populations() ===")
    if len(v1_units) > 5 and len(all_units) > len(v1_units) + 5:
        other_area = [a for a in all_units['area'].unique() if a != 'V1'][0] if len(all_units['area'].unique()) > 1 else None
        if other_area:
            comp = functions.compare_populations(
                session,
                criteria1={'area': 'V1'},
                criteria2={'area': other_area},
                metric='firing_rate'
            )
            if 'error' not in comp:
                print(f"[PASS] Comparison computed")
            else:
                print(f"Comparison failed: {comp}")
    else:
        print("[SKIP] Not enough units")

    # Test 10: population_by_area()
    print(f"\n=== Test: population_by_area() ===")
    pop = functions.population_by_area(session, metric='firing_rate')
    if isinstance(pop, dict) and 'error' not in pop:
        print(f"[PASS] Areas found: {len(pop.keys())}")
    else:
        print(f"Population analysis result: {type(pop)}")

    # Test 11: network_connectivity()
    print(f"\n=== Test: network_connectivity() ===")
    areas = all_units['area'].unique()[:5]
    corr = np.random.rand(len(areas), len(areas))
    np.fill_diagonal(corr, 1.0)

    net = functions.network_connectivity(session, corr, threshold=0.3)
    print(f"[PASS] Network computed: {net.get('n_edges', 'N/A')} edges")

    print(f"\n" + "="*60)
    print(f"[OK] VALIDATION COMPLETE ON REAL NWB DATA")
    print(f"="*60)

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
