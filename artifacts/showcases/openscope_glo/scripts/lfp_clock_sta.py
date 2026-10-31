"""LFP clock offset against the spike clock, by spike-triggered LFP (DECISIONS.md ruling 4).

Usage: python scripts/lfp_clock_sta.py SESSION_ID PROBE_K OUT_JSON

For one probe of one session, in each LFP file version (0.240503.0152 and 0.240923.1441; one file
when the asset id is the same), reads two 70-s windows by HTTP range reads (or the local file when
present): one starting 300 s after the first LFP sample, one ending 300 s before the last. The LFP
of each selected unit's peak channel (or the nearest stored channel) is band-passed 100-500 Hz
(`jnwb.bandpass_filter`, zero phase) and averaged around the unit's spikes (spike clock = the
ogen units table, the session clock of the stimulus table) over lags of +-5 s. The STA trough is
the spike's own LFP-band signature; its lag, refined by a parabola through the three samples
around the minimum, is the offset: stored LFP time minus spike time. No band power is computed.
"""
import json
import sys
import time
from pathlib import Path

import fsspec
import h5py
import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).parent))
from glo_common import DATA, assets, receipt  # noqa: E402
import jnwb  # noqa: E402

API = "https://api.dandiarchive.org/api"
VERSIONS = ("0.240503.0152", "0.240923.1441")
WIN_S, EDGE_S, MAXLAG_S = 70.0, 300.0, 5.0
N_UNITS = 12


def probe_assets(ses, k):
    d = json.load(open(Path(__file__).parents[1] / "receipts" / "probe_assets_000253.json"))
    out = {}
    for v in VERSIONS:
        hit = [a for a in d[v] if f"ses-{ses}_probe-{k}_" in a["path"]]
        assert len(hit) == 1, (v, ses, k, hit)
        out[v] = hit[0]
    return out


def units_on_probe(ogen, letter):
    with h5py.File(ogen, "r") as f:
        u, e = f["units"], f["general/extracellular_ephys/electrodes"]
        eid, grp, loc = e["id"][()], e["group_name"][()].astype(str), e["local_index"][()]
        row = {int(i): j for j, i in enumerate(eid)}
        pk = u["peak_channel_id"][()]
        qual = u["quality"][()].astype(str)
        fr, snr = u["firing_rate"][()], u["snr"][()]
        st, idx = u["spike_times"], u["spike_times_index"][()]
        sel = []
        for i in range(len(pk)):
            j = row[int(pk[i])]
            if grp[j] == letter and qual[i] == "good" and fr[i] > 2:
                sel.append((snr[i], i, int(loc[j])))
        sel.sort(reverse=True)
        out = []
        for s, i, li in sel[:N_UNITS]:
            lo = idx[i - 1] if i else 0
            out.append({"unit_row": int(i), "snr": float(s), "local_index": li, "spikes": st[lo:idx[i]]})
    return out


def open_file(asset, version):
    # The one local probe file is the paper version (asset 56e98383); a replaced file shares its name.
    local = DATA / Path(asset["path"]).name
    if version == VERSIONS[0] and local.exists():
        assert local.stat().st_size == asset["size"], (local, asset)
        return h5py.File(local, "r"), "local"
    url = requests.get(f"{API}/assets/{asset['asset_id']}/download/", allow_redirects=False, timeout=120).headers["Location"]
    fh = fsspec.filesystem("http").open(url, "rb", block_size=4 * 1024 * 1024, cache_type="blockcache")
    return h5py.File(fh, "r"), "remote"


def sta_offset(x, ts, spikes, fs):
    """x: filtered window (n,), ts: stored times of the window. Returns offset (s) and trough depth/SD."""
    dt = 1.0 / fs
    n, L = len(x), int(round(MAXLAG_S * fs))
    sp = spikes[(spikes > ts[0] + MAXLAG_S + 0.01) & (spikes < ts[-1] - MAXLAG_S - 0.01)]
    j0 = np.searchsorted(ts, sp)  # sample whose stored time is at the spike time (offset 0)
    train = np.bincount(j0, minlength=n).astype(float)
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    cc = np.fft.irfft(np.fft.rfft(x, nfft) * np.conj(np.fft.rfft(train, nfft)), nfft)
    lags = np.arange(-L, L + 1)
    sta = cc[lags % nfft] / len(sp)
    m = int(np.argmin(sta))
    if 0 < m < len(sta) - 1:
        a, b, c = sta[m - 1], sta[m], sta[m + 1]
        frac = 0.5 * (a - c) / (a - 2 * b + c)
    else:
        frac = 0.0
    far = np.abs(lags - lags[m]) > int(0.05 * fs)
    return {"n_spikes": int(len(sp)), "lag_samples": int(lags[m]), "lag_frac": float(frac),
            "offset_s": float((lags[m] + frac) * dt), "trough_z": float((sta[m] - sta[far].mean()) / sta[far].std())}


def main():
    ses, k, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    letter = "probe" + "ABCDEF"[k]
    ogen = Path(assets()[ses]["dest"])
    units = units_on_probe(ogen, letter)
    pa = probe_assets(ses, k)
    rec = {"session": ses, "probe": k, "probe_letter": letter, "assets": pa, "versions": {},
           "units": [{kk: v for kk, v in u.items() if kk != "spikes"} for u in units]}
    seen = {}
    for v in VERSIONS:
        a = pa[v]
        if a["asset_id"] in seen:
            rec["versions"][v] = {"same_asset_as": seen[a["asset_id"]]}
            continue
        seen[a["asset_id"]] = v
        t0 = time.time()
        f, how = open_file(a, v)
        name = [n for n in f["acquisition"] if n.endswith("_lfp")][0]
        series = f[f"acquisition/{name}"]
        sub = [n for n in series if isinstance(series[n], h5py.Group)]
        d = series[sub[0]] if sub else series
        D, T = d["data"], d["timestamps"]
        e = f["general/extracellular_ephys/electrodes"]
        floc, fgrp = e["local_index"][()], e["group_name"][()].astype(str)
        assert set(fgrp) == {letter}, set(fgrp)
        n = T.shape[0]
        head, tail = T[:2], T[n - 2:]
        vr = {"access": how, "series": d.name, "shape": list(D.shape), "chunks": D.chunks, "dtype": str(D.dtype),
              "ts_first": float(head[0]), "ts_last": float(tail[-1]), "ts_step_first": float(head[1] - head[0]),
              "ts_unit": T.attrs.get("unit", b"").decode() if isinstance(T.attrs.get("unit", ""), bytes) else T.attrs.get("unit", ""),
              "windows": {}}
        step = (tail[-1] - head[0]) / (n - 1)
        ticks = step > 1.0  # stored as 30-kHz ticks (paper version)
        scale = 1 / 30000.0 if ticks else 1.0
        vr["time_axis"] = "ticks/30000" if ticks else "stored seconds"
        fs = 1.0 / (step * scale)
        vr["fs_from_timestamps"] = float(fs)
        cols = sorted({int(np.argmin(np.abs(floc - u["local_index"]))) for u in units})
        ucol = [int(np.argmin(np.abs(floc - u["local_index"]))) for u in units]
        nw = int(WIN_S * fs)
        for wname, i0 in (("early", int(EDGE_S * fs)), ("late", n - int(EDGE_S * fs) - nw)):
            ts = T[i0:i0 + nw] * scale
            X = D[i0:i0 + nw, cols].astype(float)
            Xf = jnwb.bandpass_filter(X, fs, 100.0, 500.0, zero_phase=True, axis=0)
            res = []
            for u, c in zip(units, ucol):
                r = sta_offset(Xf[:, cols.index(c)], ts, u["spikes"], fs)
                r.update(unit_row=u["unit_row"], channel_local_index=int(floc[c]), peak_local_index=u["local_index"])
                res.append(r)
            good = [r for r in res if r["trough_z"] < -8]
            off = np.array([r["offset_s"] for r in good])
            vr["windows"][wname] = {"stored_time_span_s": [float(ts[0]), float(ts[-1])], "units": res,
                                    "n_units_trough_z_below_-8": len(good),
                                    "median_offset_ms": float(np.median(off) * 1e3) if len(off) else None,
                                    "range_offset_ms": [float(off.min() * 1e3), float(off.max() * 1e3)] if len(off) else None,
                                    "lag_samples_values": sorted({r["lag_samples"] for r in good})}
            print(ses, v, wname, vr["windows"][wname]["median_offset_ms"], vr["windows"][wname]["range_offset_ms"],
                  len(good), "of", len(res), flush=True)
        vr["seconds"] = round(time.time() - t0, 1)
        rec["versions"][v] = vr
        f.close()
    json.dump(receipt(rec), open(out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
