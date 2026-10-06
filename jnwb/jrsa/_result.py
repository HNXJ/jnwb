"""The result type and how a result is built, summarised, plotted and saved."""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class JRSAResult:
    """Container returned by jrsa().

    Attributes
    ----------
    value : np.ndarray
        Primary similarity tensor.
    statistic : np.ndarray | None
        Test statistic (r, rho, F, t, Z, GC …).
    effect : np.ndarray | None
        Effect size.
    p : np.ndarray | None
        Raw p-values, in the tail `alternative` names: the permutation p when a permutation
        null was formed, otherwise the metric's parametric p, or None for a metric that has
        none.
    q : np.ndarray | None
        Corrected p-values (after multiple-comparison correction).
    df : np.ndarray | None
        Degrees of freedom.
    ci : np.ndarray | None
        Percentile bootstrap interval, shape (…, 2), fixed at 95% (the 2.5th and 97.5th
        percentiles of the bootstrap distribution). `alpha` sets the significance
        threshold for the multiple-comparison correction and does not change this
        interval.
    metric : str
        Metric name.
    axes : tuple
        Compared dimensions.
    aligned_axes : tuple
        Dimensions that were aligned.
    labels : list | None
        Semantic axis labels.
    parameters : dict
        Full parameter snapshot.
    null_distribution : np.ndarray | None
        Permutation null distribution (if return_null=True).
    aligned_x1 : np.ndarray | None
        Internally aligned x1 (if return_input=True).
    aligned_x2 : np.ndarray | None
        Internally aligned x2 (if return_input=True).
    execution : dict
        Runtime metadata (backend, device, batch_size, runtime, memory, seed). What ran,
        not what was asked for; the request is in `parameters`.
    """

    value: np.ndarray
    statistic: Optional[np.ndarray] = None
    effect: Optional[np.ndarray] = None
    p: Optional[np.ndarray] = None
    q: Optional[np.ndarray] = None
    df: Optional[np.ndarray] = None
    ci: Optional[np.ndarray] = None
    metric: str = "rsa"
    axes: tuple = ()
    aligned_axes: tuple = ()
    labels: Optional[List[str]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    null_distribution: Optional[np.ndarray] = None
    aligned_x1: Optional[np.ndarray] = None
    aligned_x2: Optional[np.ndarray] = None
    execution: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # User-facing convenience methods
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Print and return a formatted summary table."""
        lines = _result_summary(self)
        print(lines)
        return lines

    def plot(self, **kwargs):
        """Automatic plot of the result matrix / time-course."""
        return _result_plot(self, **kwargs)

    def save(self, path: str, fmt: str = "npz"):
        """Save result to *path* (npz, json, or csv)."""
        return _result_save(self, path, fmt)

    def __repr__(self) -> str:  # pragma: no cover
        shape = getattr(self.value, "shape", None)
        p_repr = ""
        if self.p is not None and self.p.size > 0:
            try:
                p_repr = f", p={float(np.nanmin(self.p)):.4g}"
            except (TypeError, ValueError):
                pass
        return f"JRSAResult(metric='{self.metric}', value.shape={shape}{p_repr})"


# ===========================================================================
# PRIVATE – result helpers
# ===========================================================================

def _make_exec_meta(backend_ctx, device, t0, random_state):
    """`seed` is the `random_state` that was used, so it can be fed back.

    It used to be `rng.bit_generator.state['state']['state']` -- the 128-bit internal
    counter, e.g. 69277902251545625047243999639177715869 for `random_state=7`. That is a
    faithful record of the generator's position and a useless one for reproduction:
    passing it back as `random_state` seeds a different stream. `None` is recorded as
    None, which is the honest answer for a run seeded from OS entropy and, per the
    `random_state` docstring, one that will not reproduce.
    """
    seed_val = random_state
    return {
        "backend": backend_ctx.get("name", "numpy"),
        "device": device,
        # None means one pass over the whole array, which is always: jrsa does not chunk,
        # whatever `parameters['batch_size']` asked for.
        "batch_size": None,
        "runtime": time.perf_counter() - t0,
        "memory": None,
        "seed": seed_val,
    }


def _make_result(
    value, statistic, effect, p, q, df, ci,
    metric, axes, aligned_axes, labels, parameters,
    null_distribution, aligned_x1, aligned_x2, execution,
) -> JRSAResult:
    def _to_numpy(a):
        if a is None:
            return None
        if hasattr(a, "get"):
            a = a.get()
        return np.asarray(a)

    return JRSAResult(
        value=_to_numpy(value) if value is not None else np.float64(np.nan),
        statistic=_to_numpy(statistic),
        effect=_to_numpy(effect),
        p=_to_numpy(p),
        q=_to_numpy(q),
        df=_to_numpy(df),
        ci=_to_numpy(ci),
        metric=metric,
        axes=axes,
        aligned_axes=aligned_axes,
        labels=labels,
        parameters=parameters,
        null_distribution=_to_numpy(null_distribution),
        aligned_x1=_to_numpy(aligned_x1),
        aligned_x2=_to_numpy(aligned_x2),
        execution=execution,
    )


def _result_summary(result: JRSAResult) -> str:
    lines = [
        "JRSAResult Summary",
        "=" * 40,
        f"  metric     : {result.metric}",
        f"  value      : {result.value}",
        f"  statistic  : {result.statistic}",
        f"  effect     : {result.effect}",
        f"  p (raw)    : {result.p}",
        f"  q (corr.)  : {result.q}",
        f"  df         : {result.df}",
        f"  CI         : {result.ci}",
        f"  backend    : {result.execution.get('backend')}",
        f"  runtime    : {result.execution.get('runtime', 0):.4f}s",
    ]
    return "\n".join(lines)


def _signed_limits(val):
    """(-m, m) with m the largest finite magnitude when `val` has both signs, else (None, None).

    A diverging colormap reads its midpoint as zero; autoscaled limits put the midpoint at
    the mean of the extremes, so a matrix spanning -0.1 to 0.9 would show 0.4 as white.
    """
    finite = val[np.isfinite(val)]
    if finite.size and finite.min() < 0 < finite.max():
        m = float(np.abs(finite).max())
        return -m, m
    return None, None


def _result_plot(result: JRSAResult, **kwargs):
    """Auto-plot: matrix heatmap if 2-D, else line.

    A 2-D value with both signs is drawn with symmetric limits so the diverging colormap
    is centred on 0; `vmin` or `vmax` passed by the caller replaces both limits.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        warnings.warn("matplotlib not available for plotting.")
        return None
    val = np.asarray(result.value)
    fig, ax = plt.subplots(figsize=kwargs.get("figsize", (6, 5)))
    if val.ndim == 2:
        if "vmin" in kwargs or "vmax" in kwargs:
            vmin, vmax = kwargs.get("vmin"), kwargs.get("vmax")
        else:
            vmin, vmax = _signed_limits(val)
        im = ax.imshow(val, aspect="auto", cmap=kwargs.get("cmap", "RdBu_r"),
                       vmin=vmin, vmax=vmax)
        plt.colorbar(im, ax=ax)
    else:
        ax.plot(val)
    ax.set_title(f"jrsa – {result.metric}")
    plt.tight_layout()
    return fig


#: Fields holding an array or None. Every other field is a str, tuple, list, dict or None.
_ARRAY_FIELDS = ("value", "statistic", "effect", "p", "q", "df", "ci",
                 "null_distribution", "aligned_x1", "aligned_x2")
_TUPLE_FIELDS = ("axes", "aligned_axes")
#: The npz entry holding every field that is not an array, as one JSON string.
_NPZ_FIELDS_KEY = "fields_json"
#: The csv row naming the layout. Files without it were written before arrays were stored
#: and carry their non-array fields as Python text.
_CSV_FORMAT_KEY = "jnwb_csv_format"
_CSV_FORMAT = "2"


def _serial(obj):
    """JSON fallback: arrays as nested lists, NumPy scalars as Python numbers, else str."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return str(obj)


def _is_array(v):
    return isinstance(v, (np.ndarray, np.generic))


def _csv_rows(result: JRSAResult):
    """One `field, value` row per scalar field; arrays as rows of numbers.

    A 0-d array is `name, v`; a 1-D array is one row `name[:], v0, v1, ...`; an array of
    two or more dimensions is a row `name.shape, d0, d1, ...` followed by one row per index
    of its leading axes, `name[i]` or `name[i,j]`, holding the last axis. None is an empty
    cell. A str is written as is and any other field as JSON.
    """
    import dataclasses
    import json

    rows = [[_CSV_FORMAT_KEY, _CSV_FORMAT]]
    for f in dataclasses.fields(result):
        name, v = f.name, getattr(result, f.name)
        if v is None:
            rows.append([name, ""])
        elif _is_array(v):
            a = np.asarray(v)
            if a.ndim == 0:
                rows.append([name, repr(float(a))])
            elif a.ndim == 1:
                rows.append([f"{name}[:]"] + [repr(float(x)) for x in a])
            else:
                rows.append([f"{name}.shape"] + [str(d) for d in a.shape])
                for idx in np.ndindex(*a.shape[:-1]):
                    rows.append([f"{name}[{','.join(map(str, idx))}]"]
                                + [repr(float(x)) for x in a[idx]])
        elif isinstance(v, str):
            rows.append([name, v])
        else:
            rows.append([name, json.dumps(v, default=_serial)])
    return rows


def _result_save(result: JRSAResult, path: str, fmt: str):
    """Save every field to npz / json / csv.

    npz holds the arrays under their field names and the other fields as one JSON string
    under `fields_json`; json holds every field; csv holds every field as `_csv_rows`
    lays it out. A value JSON cannot hold (a Generator seed, say) is stored as its str.
    """
    import json

    if fmt == "npz":
        arrays = {k: np.asarray(v) for k, v in result.__dict__.items() if _is_array(v)}
        rest = {k: v for k, v in result.__dict__.items()
                if k not in _ARRAY_FIELDS}
        arrays[_NPZ_FIELDS_KEY] = np.array(json.dumps(rest, default=_serial))
        np.savez_compressed(path, **arrays)
    elif fmt == "json":
        with open(path, "w") as fh:
            json.dump(result.__dict__, fh, default=_serial, indent=2)
    elif fmt == "csv":
        import csv
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["field", "value"])
            writer.writerows(_csv_rows(result))
    else:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: npz, json, csv.")


def _restore_types(fields):
    for k in _TUPLE_FIELDS:
        if isinstance(fields.get(k), list):
            fields[k] = tuple(fields[k])
    return fields


def _read_csv(path):
    import csv
    import json

    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    current = bool(rows) and rows[0][0] == _CSV_FORMAT_KEY
    out, shapes, blocks = {}, {}, {}
    for row in rows[1:] if current else rows:
        key, cells = row[0], row[1:]
        cell = cells[0] if cells else ""
        if key.endswith(".shape"):
            shapes[key[:-6]] = tuple(int(c) for c in cells)
            blocks[key[:-6]] = []
        elif key.endswith("[:]"):
            out[key[:-3]] = np.array([float(c) for c in cells])
        elif key.endswith("]"):
            blocks[key[:key.index("[")]].extend(float(c) for c in cells)
        elif cell == "":
            out[key] = None
        elif key in _ARRAY_FIELDS:
            out[key] = np.asarray(float(cell))
        elif key == "metric" or not current:
            # Before format 2, tuples and dicts were written as Python text; returned as is.
            out[key] = cell
        else:
            out[key] = json.loads(cell)
    for name, shape in shapes.items():
        out[name] = np.array(blocks[name], dtype=float).reshape(shape)
    return out


def _result_load(path: str, fmt: str) -> Dict[str, Any]:
    """Read what `_result_save` wrote, as {field: value} for the fields the file holds.

    A current file holds every field, so `JRSAResult(**fields)` rebuilds the result. A file
    from 0.2.9 holds fewer: npz only its arrays, csv only its non-array fields (tuples and
    dicts as the Python text it wrote); nothing absent is filled in.
    """
    import json

    if fmt == "npz":
        with np.load(path, allow_pickle=False) as z:
            out = {k: z[k] for k in z.files if k != _NPZ_FIELDS_KEY}
            if _NPZ_FIELDS_KEY in z.files:
                out.update(json.loads(str(z[_NPZ_FIELDS_KEY])))
                out.update({k: None for k in _ARRAY_FIELDS if k not in out})
    elif fmt == "json":
        with open(path) as fh:
            out = json.load(fh)
        out.update({k: np.asarray(out[k]) for k in _ARRAY_FIELDS if out.get(k) is not None})
    elif fmt == "csv":
        out = _read_csv(path)
    else:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: npz, json, csv.")
    return _restore_types(out)
