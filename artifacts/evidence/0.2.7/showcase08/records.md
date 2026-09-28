# Docs-08 showcase: recorded outputs

Run at `2fae557f` (jnwb 0.2.6.1, imported from the checkout) on 2026-09-28. `showcase.py` runs the
page and eight ground-truth scenarios; `calib.py` measures false-positive rates under two true
nulls; `probe_psi.py` measures PSI power against segment count. The figure is `figure.py` over
`showcase.py`'s JSON record, which is not committed.

## calib.py

```text
independent
  granger X->Y             0.044   (nominal 0.050, 2 SE = 0.019)
  granger Y->X             0.038   (nominal 0.050, 2 SE = 0.019)
  TE X->Y                  0.046   (nominal 0.050, 2 SE = 0.019)
  TE Y->X                  0.040   (nominal 0.050, 2 SE = 0.019)
  TE(no bias corr) X->Y    0.046   (nominal 0.050, 2 SE = 0.019)
  TE(no bias corr) Y->X    0.040   (nominal 0.050, 2 SE = 0.019)
  PSI (nperseg 100)        0.046   (nominal 0.050, 2 SE = 0.019)
zero-lag mixing
  granger X->Y             0.040   (nominal 0.050, 2 SE = 0.019)
  granger Y->X             0.028   (nominal 0.050, 2 SE = 0.019)
  TE X->Y                  0.102   (nominal 0.050, 2 SE = 0.019)
  TE Y->X                  0.086   (nominal 0.050, 2 SE = 0.019)
  TE(no bias corr) X->Y    0.044   (nominal 0.050, 2 SE = 0.019)
  TE(no bias corr) Y->X    0.048   (nominal 0.050, 2 SE = 0.019)
  PSI (nperseg 100)        0.158   (nominal 0.050, 2 SE = 0.019)
rc=0
```

## probe_psi.py

```text
PSI: rate p_net<0.05 and median net, by nperseg
  X->Y                     nperseg= 100 band=(5.0, 100.0)   rate=0.75  median net=+0.138  sign+ 1.00
  X->Y                     nperseg= 200 band=(5.0, 100.0)   rate=0.00  median net=+0.145  sign+ 0.90
  X->Y                     nperseg= 500 band=(5.0, 100.0)   rate=0.00  median net=+0.219  sign+ 0.70
  Y->X                     nperseg= 100 band=(5.0, 100.0)   rate=0.75  median net=-0.138  sign+ 0.00
  Y->X                     nperseg= 200 band=(5.0, 100.0)   rate=0.00  median net=-0.145  sign+ 0.10
  Y->X                     nperseg= 500 band=(5.0, 100.0)   rate=0.00  median net=-0.219  sign+ 0.30
  beta X leads Y by 5 ms   nperseg= 100 band=(14.0, 30.0)   rate=0.05  median net=+0.012  sign+ 0.80
  beta X leads Y by 5 ms   nperseg= 200 band=(14.0, 30.0)   rate=0.00  median net=+0.023  sign+ 0.60
  beta X leads Y by 5 ms   nperseg= 500 band=(14.0, 30.0)   rate=0.00  median net=+0.037  sign+ 0.55
  independent              nperseg= 100 band=(5.0, 100.0)   rate=0.05  median net=+0.010  sign+ 0.55
  independent              nperseg= 200 band=(5.0, 100.0)   rate=0.00  median net=-0.019  sign+ 0.40
  independent              nperseg= 500 band=(5.0, 100.0)   rate=0.05  median net=+0.057  sign+ 0.65
  weak X->Y                nperseg= 100 band=(5.0, 100.0)   rate=0.00  median net=+0.015  sign+ 0.60
  weak X->Y                nperseg= 200 band=(5.0, 100.0)   rate=0.00  median net=-0.039  sign+ 0.45
  weak X->Y                nperseg= 500 band=(5.0, 100.0)   rate=0.00  median net=+0.077  sign+ 0.65
  zero-lag mixing          nperseg= 100 band=(5.0, 100.0)   rate=0.10  median net=-0.001  sign+ 0.50
  zero-lag mixing          nperseg= 200 band=(5.0, 100.0)   rate=0.00  median net=-0.023  sign+ 0.40
  zero-lag mixing          nperseg= 500 band=(5.0, 100.0)   rate=0.00  median net=-0.027  sign+ 0.45
TE, 200 fresh seeds each: rate p<0.05 (X->Y, Y->X)
  zero-lag mixing  0.075 0.100  either 0.170
  independent      0.015 0.055  either 0.065
```

## showcase.py, summarised by summarize.py

```text
A: page blocks
  0 ok 0.94 s []
  1 ok 3.15 s []
  2 ok 0.07 s []
  3 ok 0.49 s []
  4 ok 0.0 s []
  5 ok 0.25 s []
  6 ok 0.0 s []

B: rate p<0.05  (X->Y / Y->X), expected, median net
  X->Y  expected X->Y=True Y->X=False
    granger            1.00 / 0.05  net +0.2259  nan 0  OK
    granger_spectral   1.00 / 0.00  net +0.2259  nan 0  OK
    phase_slope_index  0.75 / 0.00  net +0.1376  nan 0  MISS
    transfer_entropy   1.00 / 0.05  net +0.1105  nan 0  OK
  Y->X  expected X->Y=False Y->X=True
    granger            0.05 / 1.00  net -0.2259  nan 0  OK
    granger_spectral   0.00 / 1.00  net -0.2259  nan 0  OK
    phase_slope_index  0.00 / 0.75  net -0.1376  nan 0  MISS
    transfer_entropy   0.15 / 1.00  net -0.1105  nan 0  OK
  independent  expected X->Y=False Y->X=False
    granger            0.10 / 0.05  net -0.0001  nan 0  OK
    granger_spectral   0.10 / 0.05  net -0.0001  nan 0  OK
    phase_slope_index  0.05 / 0.00  net +0.0096  nan 0  OK
    transfer_entropy   0.00 / 0.00  net -0.0005  nan 0  OK
  bidirectional  expected X->Y=True Y->X=True
    granger            1.00 / 1.00  net +0.0034  nan 0  OK
    granger_spectral   1.00 / 1.00  net +0.0030  nan 0  OK
    phase_slope_index  0.10 / 0.05  net -0.0006  nan 0  MISS
    transfer_entropy   1.00 / 1.00  net +0.0003  nan 0  OK
  zero-lag mixing  expected X->Y=False Y->X=False
    granger            0.10 / 0.00  net -0.0000  nan 0  OK
    granger_spectral   0.10 / 0.00  net -0.0000  nan 0  OK
    phase_slope_index  0.05 / 0.05  net -0.0007  nan 0  OK
    transfer_entropy   0.05 / 0.25  net -0.0010  nan 0  MISS
  weak X->Y  expected X->Y=True Y->X=False
    granger            0.95 / 0.10  net +0.0120  nan 0  OK
    granger_spectral   0.95 / 0.10  net +0.0120  nan 0  OK
    phase_slope_index  0.00 / 0.00  net +0.0145  nan 0  MISS
    transfer_entropy   0.50 / 0.05  net +0.0042  nan 0  MISS
  beta X leads Y by 5 ms  expected X->Y=True Y->X=False
    granger            1.00 / 0.70  net +0.2261  nan 0  MISS
    granger_spectral   1.00 / 0.30  net +0.1078  nan 0  MISS
    phase_slope_index  0.50 / 0.00  net +0.2415  nan 0  MISS
    transfer_entropy   0.25 / 0.00  net +0.0464  nan 0  MISS
  common driver Z  expected X->Y=False Y->X=False
    granger            1.00 / 0.00  net +0.0767  nan 0  MISS
    granger_spectral   1.00 / 0.00  net +0.0757  nan 0  MISS
    phase_slope_index  0.20 / 0.00  net +0.0834  nan 0  MISS
    transfer_entropy   0.10 / 0.00  net -0.0002  nan 0  OK
    granger | Z        0.05 / 0.05  net +0.0014  nan 0  OK

```
