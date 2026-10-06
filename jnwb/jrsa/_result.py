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


def _result_plot(result: JRSAResult, **kwargs):
    """Auto-plot: matrix heatmap if 2-D, else line."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        warnings.warn("matplotlib not available for plotting.")
        return None
    val = np.asarray(result.value)
    fig, ax = plt.subplots(figsize=kwargs.get("figsize", (6, 5)))
    if val.ndim == 2:
        im = ax.imshow(val, aspect="auto", cmap=kwargs.get("cmap", "RdBu_r"))
        plt.colorbar(im, ax=ax)
    else:
        ax.plot(val)
    ax.set_title(f"jrsa – {result.metric}")
    plt.tight_layout()
    return fig


def _result_save(result: JRSAResult, path: str, fmt: str):
    """Save result fields to npz / json / csv."""
    if fmt == "npz":
        payload = {k: v for k, v in result.__dict__.items()
                   if isinstance(v, (np.ndarray, type(None)))}
        np.savez_compressed(path, **{k: v for k, v in payload.items() if v is not None})
    elif fmt == "json":
        import json
        def _serial(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)
        with open(path, "w") as fh:
            json.dump(result.__dict__, fh, default=_serial, indent=2)
    elif fmt == "csv":
        import csv
        rows = [(k, v) for k, v in result.__dict__.items() if not isinstance(v, np.ndarray)]
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["field", "value"])
            writer.writerows(rows)
    else:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: npz, json, csv.")
