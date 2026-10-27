### Recovery runs and receipts

- `scripts/vflip2_recovery.py` (usage: `python scripts/vflip2_recovery.py [--n N] [--oracle-only] [--write] [--oracle-file PATH] [--verify]`): recovers planted vFLIP2 crossovers. It plants probes with `jnwb.testing.synth_vflip2_crossover`, records the crossovers the estimator visits in each window, and measures them against an oracle PSD built from the estimator's own front end.
  - `--n` sets the probe count per run; 100 is the contract's value. Below 100 is a smoke run: 200 trials, printed only, never written.
  - `--write` writes `artifacts/evidence/0.2.13/vflip2_recovery.md` and `vflip2_recovery.json`; without it the same text is printed.
  - `--verify` rederives every frozen depth from its stored PSD.
  - If no oracle count passes its agreement check, the script stops before any measured run.
  - `tests/test_vflip2_recovery.py` checks the generator's definitions, the window definition, the frozen oracle and the script's caller path. The outcomes are in the evidence file, not in the tests.
- `artifacts/evidence/0.2.13/vflip2_generator_design.md`: the contract that the generator and the recovery run are held to.
- Calibration receipts. Each receipt records a hash of the code it describes, and its test fails when that code changes without a rerun of the script that wrote it:
  - `artifacts/benchmarks/calibration/vflip_calibration_0.2.4.md`: `tests/test_vflip_calibration_receipt.py`, rerun with `scripts/calibrate_vflip.py`.
  - `artifacts/benchmarks/calibration/xflip_calibration_0.2.5.md`: `tests/test_xflip_calibration_receipt.py`, rerun with `scripts/calibrate_xflip.py`.
  - `artifacts/benchmarks/calibration/curation_calibration_0.2.14.md`: `tests/test_curation_calibration_receipt.py`, rerun with `scripts/calibrate_curation.py`.
