"""bias_corrected_* under zero-lag mixing (common white source) and under independence."""
import sys
sys.path.insert(0, r"C:\workspace\jnwb-lanes\g-10-06")
import numpy as np
import jnwb

n = 2000
for label, mix in (("mixing", 1.0), ("independent", 0.0)):
    te, gc = [], []
    for seed in range(40):
        r = np.random.default_rng(seed)
        s = r.normal(size=n)
        x = mix * s + 0.5 * r.normal(size=n)
        y = mix * s + 0.5 * r.normal(size=n)
        t = jnwb.transfer_entropy(x, y, n_surrogates=49, rng=seed)
        te.append(t.diagnostics["surrogates"]["bias_corrected_x_to_y"])
        g = jnwb.granger(x, y, order=2, n_surrogates=49, rng=seed)
        gc.append(g.diagnostics["surrogates"]["bias_corrected_x_to_y"])
    te, gc = np.array(te), np.array(gc)
    print(label, "TE bc mean %.4g sd %.3g frac>0 %.2f" % (te.mean(), te.std(), (te > 0).mean()),
          "| GC bc mean %.4g sd %.3g frac>0 %.2f" % (gc.mean(), gc.std(), (gc > 0).mean()))
