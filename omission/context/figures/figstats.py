r"""
The statistical harness every omission-a figure reports through.

WHY THIS EXISTS
    A figure is an analysis. Every panel that makes a claim owes a test, the test owes its
    statistic, its degrees of freedom, its n, its effect size, and its place in a declared
    correction family. Scattering that across five scripts guarantees drift, so it lives here
    and each figure writes figNN_stats.{md,csv} beside itself.

    This module owns no data and draws nothing.

CORRECTING FOR N -- WHICH ERROR RATE
    Two corrections are reported for every test, and they do NOT control the same thing:

      p_holm   Holm-Bonferroni. Controls the FAMILY-WISE error rate: the probability of ONE
               OR MORE false positives anywhere in the family. This is the correction that
               minimises false positives, and it is the one the headline claims use. Holm is
               uniformly more powerful than plain Bonferroni and needs no extra assumption.

      q_bh     Benjamini-Hochberg. Controls the FALSE DISCOVERY RATE: the expected PROPORTION
               of the rejections that are false. It rejects more, and it is the right tool for
               a screen -- 6,655 units under Holm would leave almost nothing standing, and
               that is a statement about Holm, not about the units.

    Writing that one procedure controls the other's rate is a factual error, not a wording
    choice. Every row carries `family` and both columns, so a reader can see which threshold
    a claim survived.

FAMILY IS A PROPERTY OF THE QUESTION, NOT OF THE NUMBER
    The family is declared per test when it is registered, and every test sharing a `family`
    string is corrected together. Correcting a single pre-specified coefficient is meaningless
    and implies an undisclosed set; several tests reported together with no correction is the
    commonest route to a false positive. Declaring the family is what makes either visible.

PARAMETRIC OR NOT
    `paired_location` and `group_location` choose by testing the assumption rather than by
    habit: Shapiro-Wilk on the differences (or on each group), and the parametric test only
    when it passes at 0.05 and n is large enough for Shapiro to mean anything. The choice, the
    Shapiro statistic and its p are recorded on the row, so the decision is auditable and not
    a researcher degree of freedom exercised silently.

UNIT OF INFERENCE
    Every test must name it. Nested observations -- trials within units within sessions within
    animals -- do not contribute independent degrees of freedom. A per-channel or per-unit n
    on a population claim is pseudo-replication; those tests are registered with
    `unit="unit"` or `unit="channel"` and flagged as descriptive in the written table.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from scipy import stats as sst

# figNN_*.py scripts are run directly (python figNN_foo.py), which only puts
# context/figures/ on sys.path -- the repo root must be added here so `import jnwb`
# works regardless of whether the calling script already added it.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from jnwb.statistics import StatisticalAnalysis as _StatisticalAnalysis

# Units of inference that support a population claim on this corpus. Anything else is
# descriptive, however small its p-value.
INFERENTIAL_UNITS = {"session", "animal"}

# n below which Shapiro-Wilk cannot distinguish anything; default to the rank test.
SHAPIRO_MIN_N = 8


@dataclass
class Result:
    figure: str
    panel: str
    question: str
    test: str
    statistic_name: str
    statistic: float
    df: str                  # string: "n-2", "k-1 = 9", or "" for rank tests without one
    n: int
    unit: str                # session, animal, unit, channel, trial
    effect_name: str = ""
    effect: float = np.nan
    p: float = np.nan
    family: str = "default"
    tail: str = "two-sided"
    note: str = ""
    p_holm: float = np.nan
    q_bh: float = np.nan
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------- corrections ----
def holm(p):
    """Holm-Bonferroni step-down adjusted p-values. Controls FWER."""
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    out = np.full(p.shape, np.nan)
    v = p[ok]
    m = v.size
    if m == 0:
        return out
    o = np.argsort(v)
    adj = np.maximum.accumulate(v[o] * (m - np.arange(m)))
    r = np.empty(m)
    r[o] = np.clip(adj, 0, 1)
    out[ok] = r
    return out


def bh(p):
    """Benjamini-Hochberg adjusted p-values (q). Controls FDR.

    Delegates the correction itself to jnwb.statistics.StatisticalAnalysis.fdr_correct (the
    project's single canonical BH implementation) on the finite subset; this wrapper only
    handles NaN masking so every existing figNN_*.py caller keeps its original NaN-in/NaN-out
    contract.
    """
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    out = np.full(p.shape, np.nan)
    v = p[ok]
    if v.size == 0:
        return out
    out[ok] = np.clip(_StatisticalAnalysis.fdr_correct(v), 0, 1)
    return out


def correct(results):
    """Apply both corrections WITHIN each declared family. Returns the same list."""
    by = {}
    for i, r in enumerate(results):
        by.setdefault(r.family, []).append(i)
    for fam, idx in by.items():
        p = [results[i].p for i in idx]
        ph, qb = holm(p), bh(p)
        for j, i in enumerate(idx):
            results[i].p_holm = float(ph[j])
            results[i].q_bh = float(qb[j])
    return results


# ------------------------------------------------------------------------- tests ----
def _shapiro(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < SHAPIRO_MIN_N or np.allclose(x, x[0]):
        return np.nan, np.nan
    w, p = sst.shapiro(x)
    return float(w), float(p)


def paired_location(a, b, figure, panel, question, unit, family, tail="two-sided",
                    force=None, note=""):
    """Is the paired difference a - b located away from zero?

    Wilcoxon signed-rank unless the differences pass Shapiro-Wilk, in which case the paired
    t-test is reported instead. Both carry an effect size: Cohen's dz for t, and the
    rank-biserial correlation r = |Z| / sqrt(n) for Wilcoxon.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    d = a[m] - b[m]
    n = d.size
    if n < 3 or np.allclose(d, 0):
        return Result(figure, panel, question, "none", "", np.nan, "", n, unit,
                      family=family, note="too few finite pairs" if n < 3 else "all zero")
    w, wp = _shapiro(d)
    parametric = force == "t" or (force is None and np.isfinite(wp) and wp > 0.05)

    if parametric:
        t, p = sst.ttest_rel(a[m], b[m], alternative=tail)
        return Result(figure, panel, question, "paired t-test", "t", float(t), f"{n - 1}",
                      n, unit, "Cohen's dz", float(d.mean() / d.std(ddof=1)), float(p),
                      family, tail, note,
                      extra={"shapiro_W": w, "shapiro_p": wp, "mean_diff": float(d.mean())})

    res = sst.wilcoxon(d, alternative=tail, method="approx")
    z = float(res.zstatistic)
    return Result(figure, panel, question, "Wilcoxon signed-rank", "W", float(res.statistic),
                  "", n, unit, "r = |Z|/sqrt(n)", abs(z) / np.sqrt(n), float(res.pvalue),
                  family, tail, note,
                  extra={"Z": z, "shapiro_W": w, "shapiro_p": wp,
                         "median_diff": float(np.median(d))})


def group_location(groups, labels, figure, panel, question, unit, family, note=""):
    """Do k independent groups differ in location?

    Kruskal-Wallis unless every group passes Shapiro-Wilk AND Levene finds equal variance, in
    which case one-way ANOVA is reported. Two groups reduce to Mann-Whitney U or Welch's t.
    """
    gs = [np.asarray(g, float)[np.isfinite(g)] for g in groups]
    keep = [i for i, g in enumerate(gs) if g.size >= 2]
    gs = [gs[i] for i in keep]
    labels = [labels[i] for i in keep]
    k, n = len(gs), int(sum(g.size for g in gs))
    if k < 2:
        return Result(figure, panel, question, "none", "", np.nan, "", n, unit,
                      family=family, note="fewer than two usable groups")

    sh = [_shapiro(g) for g in gs]
    normal = all(np.isfinite(p) and p > 0.05 for _, p in sh)
    equal_var = False
    if normal:
        try:
            equal_var = sst.levene(*gs, center="median").pvalue > 0.05
        except Exception:
            equal_var = False

    sizes = {lab: int(g.size) for lab, g in zip(labels, gs)}
    if k == 2:
        if normal:
            t, p = sst.ttest_ind(gs[0], gs[1], equal_var=equal_var)
            pooled = np.sqrt((gs[0].var(ddof=1) + gs[1].var(ddof=1)) / 2)
            return Result(figure, panel, question,
                          "Student's t" if equal_var else "Welch's t", "t", float(t),
                          f"{n - 2}" if equal_var else "Welch", n, unit, "Cohen's d",
                          float((gs[0].mean() - gs[1].mean()) / pooled) if pooled else np.nan,
                          float(p), family, note=note, extra={"group_n": sizes})
        u = sst.mannwhitneyu(gs[0], gs[1], alternative="two-sided", method="asymptotic")
        n1, n2 = gs[0].size, gs[1].size
        return Result(figure, panel, question, "Mann-Whitney U", "U", float(u.statistic),
                      "", n, unit, "rank-biserial r",
                      float(2 * u.statistic / (n1 * n2) - 1), float(u.pvalue), family,
                      note=note, extra={"group_n": sizes})

    if normal and equal_var:
        f, p = sst.f_oneway(*gs)
        ss_b = sum(g.size * (g.mean() - np.concatenate(gs).mean()) ** 2 for g in gs)
        ss_t = ((np.concatenate(gs) - np.concatenate(gs).mean()) ** 2).sum()
        return Result(figure, panel, question, "one-way ANOVA", "F", float(f),
                      f"{k - 1}, {n - k}", n, unit, "eta squared",
                      float(ss_b / ss_t) if ss_t else np.nan, float(p), family, note=note,
                      extra={"group_n": sizes})

    h, p = sst.kruskal(*gs)
    return Result(figure, panel, question, "Kruskal-Wallis", "H", float(h), f"{k - 1}", n,
                  unit, "epsilon squared",
                  float((h - k + 1) / (n - k)) if n > k else np.nan, float(p), family,
                  note=note, extra={"group_n": sizes})


def correlation(x, y, figure, panel, question, unit, family, method="spearman", note=""):
    """Monotone association, with r squared and the degrees of freedom that go with it.

    Spearman by default. On few, non-independent aggregate units -- ten areas, three animals --
    this is a descriptive effect size, and the written table says so rather than letting a
    p-value on n = 10 read as inference.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    n = int(m.sum())
    if n < 4:
        return Result(figure, panel, question, "none", "", np.nan, "", n, unit,
                      family=family, note="fewer than four usable pairs")
    if method == "pearson":
        r, p = sst.pearsonr(x[m], y[m])
        name = "Pearson r"
    else:
        r, p = sst.spearmanr(x[m], y[m])
        name = "Spearman rho"
    return Result(figure, panel, question, name, "r", float(r), f"{n - 2}", n, unit,
                  "r squared", float(r) ** 2, float(p), family, note=note,
                  extra={"t": float(r * np.sqrt((n - 2) / max(1 - r ** 2, 1e-12)))})


def shuffle_null_distribution(x, y, method="spearman", n_shuffle=2000, seed=0):
    """The observed r and its label-shuffle null draws. Shared by the test and by any panel
    that wants to plot the null histogram, so the two never compute it two different ways."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    xn, yn = x[m], y[m]
    n = xn.size
    if method == "pearson":
        r = float(sst.pearsonr(xn, yn)[0])
        vx, vy = xn, yn
    else:
        r = float(sst.spearmanr(xn, yn)[0])
        vx, vy = sst.rankdata(xn), sst.rankdata(yn)
    rng = np.random.default_rng(seed)
    cx = vx - vx.mean()
    cx = cx / np.sqrt((cx ** 2).sum())
    idx = np.argsort(rng.random((n_shuffle, n)), axis=1)
    ys = vy[idx]
    cys = ys - ys.mean(axis=1, keepdims=True)
    cys = cys / np.sqrt((cys ** 2).sum(axis=1, keepdims=True))
    null = cys @ cx
    return r, null, n


def correlation_with_shuffle_null(x, y, figure, panel, question, unit, family,
                                  method="spearman", n_shuffle=2000, seed=0, note=""):
    """Association between x and y, cross-checked against a label-shuffle null.

    The analytic p from spearmanr/pearsonr assumes a well-behaved null distribution of the
    test statistic. The shuffle null instead breaks the x-y pairing directly n_shuffle times
    and recomputes r on each permutation, which needs no distributional assumption. Reported
    ALONGSIDE, not instead of, the analytic test -- agreement between the two is itself
    informative, and disagreement is a flag that the analytic assumption failed.

    Vectorised: for Spearman, ranks are fixed once and every shuffle is one dot product
    against a batch of permuted rank vectors, not a python-level loop calling spearmanr
    n_shuffle times.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    xn, yn = x[m], y[m]
    n = xn.size
    if n < 4:
        return Result(figure, panel, question, "none", "", np.nan, "", n, unit,
                      family=family, note="fewer than four usable pairs")

    name = "Pearson r" if method == "pearson" else "Spearman rho"
    p = float(sst.pearsonr(xn, yn)[1]) if method == "pearson" else float(sst.spearmanr(xn, yn)[1])
    r, null, _ = shuffle_null_distribution(xn, yn, method, n_shuffle, seed)
    p_shuffle = float((1 + np.sum(np.abs(null) >= abs(r))) / (n_shuffle + 1))

    # The raw null draws are NOT stored on the Result: 2000 floats per test would bloat the
    # written CSV for no benefit. A caller that wants to plot the null histogram regenerates
    # it from the same (seed, method) recorded here -- deterministic, so it reproduces exactly.
    return Result(figure, panel, question, name, "r", float(r), f"{n - 2}", n, unit,
                  "r squared", float(r) ** 2, float(p), family, note=note,
                  extra={"p_shuffle": p_shuffle, "n_shuffle": n_shuffle, "seed": seed,
                         "shuffle_null_mean": float(null.mean()),
                         "shuffle_null_sd": float(null.std(ddof=1))})


def proportion_vs_reference(k, n, p0, figure, panel, question, unit, family, note=""):
    """Exact binomial test of k/n against a reference rate, with a Clopper-Pearson interval.

    Exact, not normal-approximate: the counts here are small enough that the approximation
    misstates the tail, and an exact interval needs no RNG, no seed and no resample count.
    """
    k, n = int(k), int(n)
    if n == 0:
        return Result(figure, panel, question, "none", "", np.nan, "", 0, unit, family=family,
                      note="empty denominator")
    res = sst.binomtest(k, n, p0, alternative="two-sided")
    ci = res.proportion_ci(confidence_level=0.95, method="exact")
    return Result(figure, panel, question, "exact binomial", "k", float(k), "", n, unit,
                  "proportion", k / n, float(res.pvalue), family, note=note,
                  extra={"reference_p": float(p0), "ci95_low": float(ci.low),
                         "ci95_high": float(ci.high),
                         "interval": "Clopper-Pearson exact"})


def contingency(table, figure, panel, question, unit, family, rows=None, cols=None, note=""):
    """Independence in an r x c table. Fisher exact for 2 x 2, chi-square otherwise.

    Chi-square carries Cramer's V; the expected-count minimum is recorded, because the
    approximation is not trustworthy below about five and the row says so when it is.
    """
    t = np.asarray(table, float)
    n = int(round(t.sum()))          # counts summed as float can land at x.9999...; round, not truncate
    if t.shape == (2, 2):
        odds, p = sst.fisher_exact(t)
        return Result(figure, panel, question, "Fisher exact", "odds ratio", float(odds), "",
                      n, unit, "odds ratio", float(odds), float(p), family, note=note,
                      extra={"table": t.tolist(), "rows": rows, "cols": cols})
    # Drop all-zero rows and columns to prevent scipy zero-expected frequency error
    valid_r = t.sum(axis=1) > 0
    valid_c = t.sum(axis=0) > 0
    t_clean = t[valid_r][:, valid_c]
    if t_clean.shape[0] < 2 or t_clean.shape[1] < 2:
        return Result(figure, panel, question, "chi-square of independence", "chi2", float(0.0),
                      "0", n, unit, "Cramer's V", float(0.0), float(1.0), family, note=note,
                      extra={"min_expected": float(0.0), "table": t.tolist(), "rows": rows, "cols": cols})
    chi2, p, dof, exp = sst.chi2_contingency(t_clean)
    mn = min(t_clean.shape)
    return Result(figure, panel, question, "chi-square of independence", "chi2", float(chi2),
                  f"{dof}", n, unit, "Cramer's V",
                  float(np.sqrt(chi2 / (n * (mn - 1)))) if n and mn > 1 else np.nan,
                  float(p), family, note=note,
                  extra={"min_expected": float(exp.min()),
                         "approximation_note": ("min expected count below 5; chi-square "
                                                "approximation unreliable"
                                                if exp.min() < 5 else ""),
                         "rows": rows, "cols": cols})


def trend_in_proportions(k, n, scores, figure, panel, question, unit, family, note=""):
    """Cochran-Armitage test for a monotone trend in proportions across ordered groups.

    Preferred over correlating the proportions: it keeps the denominators, so an area with 46
    units does not weigh the same as one with 1,342, and it does not dichotomise anything.
    """
    k = np.asarray(k, float)
    n = np.asarray(n, float)
    s = np.asarray(scores, float)
    N, K = n.sum(), k.sum()
    if N == 0 or K == 0 or K == N:
        return Result(figure, panel, question, "none", "", np.nan, "", int(N), unit,
                      family=family, note="degenerate counts")
    pbar = K / N
    num = float(np.sum(s * (k - n * pbar)))
    var = float(pbar * (1 - pbar) * (np.sum(n * s ** 2) - np.sum(n * s) ** 2 / N))
    if var <= 0:
        return Result(figure, panel, question, "none", "", np.nan, "", int(N), unit,
                      family=family, note="zero variance in scores")
    z = num / np.sqrt(var)
    p = 2 * sst.norm.sf(abs(z))
    return Result(figure, panel, question, "Cochran-Armitage trend", "Z", float(z), "1",
                  int(N), unit, "z per score unit", float(z), float(p), family, note=note,
                  extra={"scores": s.tolist(), "overall_p": float(pbar)})


# ------------------------------------------------------------------------ output ----
def _fmt(v, nd=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "--"
    if isinstance(v, float):
        if v != 0 and (abs(v) < 1e-3 or abs(v) >= 1e4):
            return f"{v:.2e}"
        return f"{v:.{nd}f}"
    return str(v)


def _p(v):
    if v is None or not np.isfinite(v):
        return "--"
    return "< 1e-4" if v < 1e-4 else f"{v:.4f}"


def write(results, out_dir, stem, title, preamble=""):
    """Correct within families, then write stem_stats.csv and stem_stats.md."""
    results = correct(list(results))
    rows = []
    for r in results:
        d = asdict(r)
        ex = d.pop("extra")
        for k, v in ex.items():
            d[f"extra_{k}"] = v
        rows.append(d)
    df = pd.DataFrame(rows)
    os.makedirs(out_dir, exist_ok=True)
    csv = os.path.join(out_dir, f"{stem}_stats.csv")
    df.to_csv(csv, index=False)

    fams = {}
    for r in results:
        fams.setdefault(r.family, []).append(r)

    L = [f"# {title}", "",
         "Generated by the figure's own script; every row traces to that script's receipt.", ""]
    if preamble:
        L += [preamble, ""]
    L += ["**Corrections.** `p_holm` is Holm-Bonferroni and controls the family-wise error "
          "rate, the probability of one or more false positives anywhere in the family; it is "
          "the correction the headline claims use. `q_BH` is Benjamini-Hochberg and controls "
          "the false discovery rate, the expected proportion of rejections that are false. "
          "They are different guarantees and are reported side by side, never interchanged.",
          "",
          "**Unit of inference.** Rows whose unit is not `session` or `animal` are "
          "descriptive: nested observations do not contribute independent degrees of freedom, "
          "so a per-unit or per-channel n cannot carry a population claim however small its "
          "p-value. Those rows are marked.",
          "",
          "**Parametric or not.** Chosen per test by Shapiro-Wilk on the differences or the "
          "groups, with Levene for equal variance; the statistic and p of that check are in "
          "the CSV. The rank test is the default when the check fails or n is under "
          f"{SHAPIRO_MIN_N}.", ""]

    for fam, rs in fams.items():
        L += [f"## Family: {fam}", "",
              f"{len(rs)} test{'s' if len(rs) != 1 else ''} corrected together.", "",
              "| Panel | Question | Test | Statistic | df | n | Unit | Effect | p | p_holm | q_BH |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(rs, key=lambda x: (np.inf if not np.isfinite(x.p) else x.p)):
            mark = "" if r.unit in INFERENTIAL_UNITS else " *"
            eff = f"{r.effect_name} = {_fmt(r.effect)}" if r.effect_name else "--"
            L.append(f"| {r.panel} | {r.question} | {r.test} | "
                     f"{r.statistic_name} = {_fmt(r.statistic)} | {r.df or '--'} | {r.n} | "
                     f"{r.unit}{mark} | {eff} | {_p(r.p)} | {_p(r.p_holm)} | {_p(r.q_bh)} |")
        L.append("")
        if any(r.unit not in INFERENTIAL_UNITS for r in rs):
            L += ["\\* descriptive: the unit of inference does not support a population claim.",
                  ""]
        seen, notes = set(), []
        for r in rs:
            if r.note and (r.panel, r.note) not in seen:
                seen.add((r.panel, r.note))
                notes.append(f"- **{r.panel}** -- {r.note}")
        if notes:
            L += ["Notes:", ""] + notes + [""]

    md = os.path.join(out_dir, f"{stem}_stats.md")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return csv, md
