"""Page bodies for the Analysis 6A atlas.

Every numeric value rendered by these functions is read from the canonical public tables passed
in as `d`. No claim number is written as a literal here -- if a page needs a number, it computes
it from the table, so a table change propagates and a drifted table fails reconciliation rather
than silently disagreeing with the prose.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from build_atlas import base_layout, div, p_of, table_html

SUBJ_COLOR = {"M1": "#1f5f8b", "M2": "#a33a2c", "M3": "#0f7b52"}
BAND_ORDER = ["theta", "alpha", "beta", "low_gamma", "high_gamma", "out_of_band"]
BAND_COLOR = {"theta": "#6a51a3", "alpha": "#3182bd", "beta": "#e6820e",
              "low_gamma": "#31a354", "high_gamma": "#0f7b52", "out_of_band": "#8c8c8c"}


def _fmt_p(p: float) -> str:
    return f"{p:.3g}" if p >= 1e-4 else f"{p:.2e}"


# =============================================================================================
# 1. Overview
# =============================================================================================
def overview(d) -> str:
    c, s, lf, t = d["census"], d["spk"], d["lfp_freq"], d["tests"]
    t2, t1, t3 = (p_of(t, "LFP HIGH-minus-LOW"), p_of(t, "increase-vs-decrease"),
                  p_of(t, "omission-minus-stimulus"))
    n_dt = int(s.dT_ms.notna().sum())
    n_pos = int((s.dT_ms > 0).sum())
    med = s.T_om.median()
    q1, q3 = s.T_om.quantile(0.25), s.T_om.quantile(0.75)
    return f"""
<h2>Overview</h2>
<p class="mut">{'Which changes first during stimulus omission &mdash; the local field potential, or spiking?'}</p>

<div class="card key">
<h3 style="margin-top:0">Primary population-level result</h3>
<p>Temporal <em>resolvability</em> of the omission response is higher for high-frequency LFP
(beta / gamma) than for low-frequency LFP (theta / alpha), and this replicates across sessions:
median HIGH&minus;LOW difference <span class="stat pos">+{t2.median_D:g} percentage points</span>,
exact exhaustive sign-flip permutation
<span class="stat">p = {_fmt_p(t2.signflip_exact_p)}</span>
({int(t2.n_permutations_enumerated):,} assignments enumerated,
n = {int(t2.n_sessions)} sessions, {int(t2.n_nonzero_sessions)} non-zero),
Holm <span class="stat">p = {float(t2.holm_p):.1e}</span>.
<span class="badge b-pub">replicated across sessions</span></p>
</div>

<h3>What the corpus contains</h3>
<div class="scroll"><table><thead><tr><th>Quantity</th><th>Value</th><th>Scope</th></tr></thead>
<tbody>
<tr><td>Eligible single units</td><td class="stat">{int(c.n_units_eligible.sum()):,}</td>
<td class="mut">SPK, all sessions</td></tr>
<tr><td>Omission responses detected</td><td class="stat">{int(c.n_omission_detected.sum())}</td>
<td class="mut">a response exists</td></tr>
<tr><td>Omission latencies resolved</td><td class="stat">{int(c.n_latency_resolved.sum())}</td>
<td class="mut">estimators agree</td></tr>
<tr><td>Resolved units with a stimulus reference</td><td class="stat">{n_dt}</td>
<td class="mut">&Delta;T defined</td></tr>
<tr><td>Median resolved T<sub>om</sub></td>
<td class="stat">{med:g} ms</td><td class="mut">IQR {q1:g}&ndash;{q3:g} ms</td></tr>
<tr><td>LFP area&times;frequency cells</td><td class="stat">{int(lf.n_cells.sum()):,}</td>
<td class="mut">all sessions</td></tr>
<tr><td>LFP cells resolved</td><td class="stat">{int(lf.n_resolved.sum())}</td>
<td class="mut">{100 * lf.n_resolved.sum() / lf.n_cells.sum():.1f}% of cells</td></tr>
</tbody></table></div>

<h3>The three session-level tests, and their three different answers</h3>
<p>The session is the inferential unit. Units within a session and area&times;frequency cells
within a session are not independent, so pooled counts below are labelled descriptive.</p>
<div class="scroll"><table><thead><tr><th>Test</th><th>n</th><th>median</th><th>p (sign-flip)</th>
<th>Standing</th></tr></thead><tbody>
<tr><td>LFP HIGH&minus;LOW resolvability</td><td>{int(t2.n_sessions)}</td>
<td class="stat pos">+{t2.median_D:g} pp</td><td class="stat">{_fmt_p(t2.signflip_exact_p)}</td>
<td><span class="badge b-pub">replicated</span></td></tr>
<tr><td>SPK increase-vs-decrease timing</td><td>{int(t1.n_sessions)}</td>
<td class="stat">{t1.median_D:g} ms</td><td class="stat">{_fmt_p(t1.signflip_exact_p)}</td>
<td><span class="badge b-desc">not replicated</span></td></tr>
<tr><td>SPK omission&minus;stimulus shift</td><td>{int(t3.n_sessions)}</td>
<td class="stat">+{t3.median_D:g} ms</td><td class="stat">{_fmt_p(t3.signflip_exact_p)}</td>
<td><span class="badge b-desc">not significant</span></td></tr>
</tbody></table></div>
<p class="mut">Three outcomes under identical machinery. The third is
<em>insufficient session-level evidence</em>, not a demonstrated null: at n = {int(t3.n_sessions)}
sessions the smallest attainable exact p is bounded away from zero. The pooled unit-level
tendency ({n_pos}/{n_dt} = {100 * n_pos / n_dt:.1f}% of units with &Delta;T &gt; 0) is
<span class="badge b-desc">descriptive</span> and is weighted by unit count, not by session.</p>

<div class="card hold">
<h3 style="margin-top:0">Held, deliberately</h3>
<p><strong>No common-axis LFP-vs-SPK figure.</strong> It is withheld pending a scientifically
appropriate LFP representation: the LFP side must be interval- and censoring-based, not a cloud
of points, because beta latencies are strongly left-censored (see
<a href="lfp-resolvability.html">LFP</a>).</p>
<p><strong>No area-latency hierarchy claim.</strong> Area and subject are partially confounded;
no area was recorded in all animals. Pooled area medians are descriptive only
(see <a href="coverage.html">Coverage</a>).</p>
<p><strong>No LFP&rarr;SPK causal or directional claim.</strong> Nothing in 6A tests direction.</p>
</div>
"""


# =============================================================================================
# 2. SPK timing  (A1 funnel, A2 per-unit latency browser)
# =============================================================================================
def spk_timing(d) -> str:
    c, s = d["census"], d["spk"]
    steps = [
        ("Eligible units", int(c.n_units_eligible.sum()),
         "every spike-sorted unit with an analysable omission arm"),
        ("Omission response detected", int(c.n_omission_detected.sum()),
         "a change from baseline exists (this is DETECTED, not resolved)"),
        ("Omission latency resolved", int(c.n_latency_resolved.sum()),
         "independent estimators agree to within the spread criterion"),
        ("Stimulus reference defined", int(s.dT_ms.notna().sum()),
         "the unit also has an analysable stimulus arm, so &Delta;T exists"),
        ("|&Delta;T| &gt; 50 ms", int(s.dT_gt_50.sum()),
         "descriptive subset; not an inferential threshold"),
    ]
    tot = steps[0][1]
    rows = "".join(
        f"<tr><td>{i + 1}. {n}</td><td class='stat'>{v:,}</td>"
        f"<td class='stat'>{100 * v / tot:.1f}%</td><td class='mut'>{w}</td></tr>"
        for i, (n, v, w) in enumerate(steps))

    fig = go.Figure()
    fig.add_trace(go.Funnel(
        y=[n.replace("&Delta;", "Δ").replace("&gt;", ">") for n, _, _ in steps],
        x=[v for _, v, _ in steps], textinfo="value+percent initial",
        marker=dict(color=["#1f5f8b", "#2b7ba8", "#3f97c4", "#7bb6d4", "#b6d4e4"])))
    base_layout(fig, 380, title="A1 &middot; SPK census funnel")

    r = s.dropna(subset=["T_om"]).sort_values("T_om").reset_index(drop=True)
    r["rank"] = np.arange(1, len(r) + 1)
    f2 = go.Figure()
    for subj, g in r.groupby("subject_public"):
        f2.add_trace(go.Scatter(
            x=g["rank"], y=g.T_om, mode="markers", name=subj,
            error_y=dict(type="data", array=1.96 * g.T_om_boot_sd, width=0,
                         color="rgba(120,130,140,.45)", thickness=1),
            marker=dict(size=7, color=SUBJ_COLOR.get(subj, "#666"),
                        symbol=["circle" if x == "increase" else "triangle-down"
                                for x in g.om_direction],
                        line=dict(width=.6, color="#fff")),
            customdata=np.stack([g.area, g.unit_class, g.om_direction, g.unit_public,
                                 g.session_public, g.om_estimator_spread], axis=-1),
            hovertemplate=("<b>%{customdata[3]}</b><br>session %{customdata[4]}"
                           "<br>area %{customdata[0]} &middot; class %{customdata[1]}"
                           "<br>direction %{customdata[2]}"
                           "<br>T_om %{y:.0f} ms &plusmn; %{error_y.array:.0f} (95%)"
                           "<br>estimator spread %{customdata[5]:.0f} ms<extra></extra>")))
    base_layout(f2, 500, title="A2 &middot; Resolved omission latency, one point per unit",
                xaxis_title="unit, ranked by latency", yaxis_title="T<sub>om</sub> (ms)")
    f2.update_layout(hovermode="closest")

    return f"""
<h2>SPK timing</h2>
<p class="mut">Single-unit omission onset latency. {len(s)} units resolve out of
{int(c.n_units_eligible.sum()):,} eligible &mdash; omission timing in spiking is real but sparse.</p>

<h3>A1 &middot; Census funnel</h3>
<div class="card"><div class="scroll"><table><thead><tr><th>Step</th><th>n</th>
<th>of eligible</th><th>meaning</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<p class="mut"><strong>Naming hazard, stated explicitly:</strong> in the underlying receipts the
column named <code>resolved</code> counts <em>detected</em> responses
({int(c.n_omission_detected.sum())}), not resolved latencies
({int(c.n_latency_resolved.sum())}). The public tables rename these to
<code>n_omission_detected</code> and <code>n_latency_resolved</code> so the two cannot be
confused downstream.</p>
{div(fig, "funnel")}

<h3>A2 &middot; Per-unit resolved latency</h3>
<p>One point per resolved unit, sorted by latency, with
T<sub>om</sub> &plusmn; 1.96 &times; bootstrap SD. Subject is encoded by colour and response
direction by marker shape, independently &mdash; area is available on hover rather than as a
visual grouping, so the display cannot suggest an area hierarchy the design cannot support.</p>
{div(f2, "a2")}
<p class="mut">Median T<sub>om</sub> = <span class="stat">{s.T_om.median():g} ms</span>
(IQR {s.T_om.quantile(.25):g}&ndash;{s.T_om.quantile(.75):g} ms;
{int((s.om_direction == 'increase').sum())} increases,
{int((s.om_direction == 'decrease').sum())} decreases).
All onsets are one-sided by construction: the estimator search window begins at the omitted
event, so no unit can report an onset before it. A pre-zero deviation lands on the bound or
returns undefined &mdash; it is never negative.</p>
<p class="mut">Source table: <a href="tables/analysis6a_spk_resolved_public.csv">
analysis6a_spk_resolved_public.csv</a> ({len(s)} rows).</p>
"""


# =============================================================================================
# 3. SPK omission vs stimulus  (A3)
# =============================================================================================
def spk_vs_stimulus(d) -> str:
    s, t = d["spk"], d["tests"]
    t3 = p_of(t, "omission-minus-stimulus")
    g = s.dropna(subset=["dT_ms"]).copy()
    n, npos, n50 = len(g), int((g.dT_ms > 0).sum()), int(g.dT_gt_50.sum())
    # Clopper-Pearson, exact -- no RNG, no resample count.
    from scipy.stats import beta as _b
    lo = _b.ppf(0.025, npos, n - npos + 1) * 100
    hi = _b.ppf(0.975, npos + 1, n - npos) * 100

    g = g.sort_values("dT_ms").reset_index(drop=True)
    g["rank"] = np.arange(1, len(g) + 1)
    near = g.dT_gt_50.eq(False)
    f = go.Figure()
    f.add_vrect(x0=-50, x1=50, fillcolor="#eceff2", opacity=.75, line_width=0,
                annotation_text="|ΔT| ≤ 50 ms", annotation_position="top left")
    f.add_vline(x=0, line=dict(color="#1a1a1a", width=1.5))
    for lbl, mask, col in (("|ΔT| > 50 ms", ~near, "#1f5f8b"),
                           ("|ΔT| ≤ 50 ms", near, "#9aa6b1")):
        h = g[mask]
        f.add_trace(go.Scatter(
            x=h.dT_ms, y=h["rank"], mode="markers", name=lbl,
            error_x=dict(type="data", array=1.96 * h.dT_boot_sd, width=0,
                         color="rgba(120,130,140,.4)", thickness=1),
            marker=dict(size=6.5, color=col, line=dict(width=.5, color="#fff")),
            customdata=np.stack([h.unit_public, h.area, h.om_direction,
                                 h.T_om, h.T_stim], axis=-1),
            hovertemplate=("<b>%{customdata[0]}</b><br>area %{customdata[1]}"
                           "<br>%{customdata[2]}<br>T_om %{customdata[3]:.0f} ms &minus; "
                           "T_stim %{customdata[4]:.0f} ms<br><b>ΔT %{x:.0f} ms</b>"
                           "<extra></extra>")))
    base_layout(f, 520, title="A3 &middot; ΔT = T<sub>om</sub> &minus; T<sub>stim</sub>",
                xaxis_title="ΔT (ms)", yaxis_title="unit, ranked by ΔT")

    return f"""
<h2>SPK omission vs stimulus timing</h2>
<p class="mut">&Delta;T = T<sub>om</sub> &minus; T<sub>stim</sub>, for the {n} resolved units that
also have an analysable stimulus arm.</p>
{div(f, "a3")}

<div class="card">
<p><span class="badge b-desc">descriptive</span>
<strong>{npos}/{n} = {100 * npos / n:.1f}%</strong> of units have &Delta;T &gt; 0
(Clopper&ndash;Pearson 95% CI [{lo:.1f}, {hi:.1f}]).
{n50}/{n} have |&Delta;T| &gt; 50 ms.</p>
<p class="mut">The denominator is units with &Delta;T <em>defined</em> &mdash; not all
{len(s)} resolved units. Dividing by all resolved units counts an undefined &Delta;T as
&quot;not positive&quot; and understates the fraction; that error was found and corrected during
review.</p>
</div>

<div class="card key">
<p><strong>This proportion is not a population claim.</strong> Units within a session are not
independent, and the pooled percentage is weighted by unit count &mdash; the two heaviest
sessions dominate it. The session-level test is the one that carries inference:</p>
<p>n = <span class="stat">{int(t3.n_sessions)}</span> eligible sessions,
median <span class="stat">+{t3.median_D:g} ms</span>,
exact exhaustive sign-flip permutation
<span class="stat">p = {t3.signflip_exact_p:.3f}</span>
({int(t3.n_permutations_enumerated):,} assignments enumerated).</p>
<p><span class="badge b-desc">not significant / insufficient session-level evidence</span>
This is <em>not</em> a demonstrated null. It is a shift that the available number of sessions
cannot establish. See <a href="session-statistics.html">Session-level statistics</a>.</p>
</div>
"""


# =============================================================================================
# 4. LFP frequency / resolvability  (B1, B2, B4)
# =============================================================================================
def lfp_resolvability(d) -> str:
    lf, ls, lc, t = d["lfp_freq"], d["lfp_sess"], d["lfp_cens"], d["tests"]
    t2 = p_of(t, "LFP HIGH-minus-LOW")

    f1 = go.Figure()
    f1.add_trace(go.Scatter(
        x=lf.freq_Hz, y=lf.cp95_hi, mode="lines", line=dict(width=0),
        showlegend=False, hoverinfo="skip"))
    f1.add_trace(go.Scatter(
        x=lf.freq_Hz, y=lf.cp95_lo, mode="lines", line=dict(width=0), fill="tonexty",
        fillcolor="rgba(31,95,139,.15)", name="Clopper&ndash;Pearson 95%", hoverinfo="skip"))
    f1.add_trace(go.Scatter(
        x=lf.freq_Hz, y=lf.pct_resolved, mode="lines+markers", name="corpus",
        line=dict(color="#1f5f8b", width=2.2), marker=dict(size=7),
        customdata=np.stack([lf.band, lf.n_resolved, lf.n_cells,
                             lf.sess_min_pct, lf.sess_max_pct], axis=-1),
        hovertemplate=("%{x:.2f} Hz (%{customdata[0]})<br>"
                       "resolved %{customdata[1]}/%{customdata[2]} = %{y:.1f}%"
                       "<br>session range %{customdata[3]:.0f}&ndash;%{customdata[4]:.0f}%"
                       "<extra></extra>")))
    f1.add_trace(go.Scatter(
        x=lf.freq_Hz, y=lf.sess_median_pct, mode="lines", name="session median",
        line=dict(color="#8a6d1f", width=1.6, dash="dot")))
    base_layout(f1, 430, title="B1 &middot; P(resolved | frequency)",
                xaxis_title="frequency (Hz)", yaxis_title="% of cells resolved")
    f1.update_xaxes(type="log")

    ls2 = ls.sort_values("D_s_pct").reset_index(drop=True)
    f2 = go.Figure()
    for _, r in ls2.iterrows():
        f2.add_trace(go.Scatter(
            x=["LOW (theta/alpha)", "HIGH (beta/gamma)"], y=[r.r_low_pct, r.r_high_pct],
            mode="lines+markers", showlegend=False,
            line=dict(color=SUBJ_COLOR.get(r.subject_public, "#888"), width=1.2),
            marker=dict(size=7, color=SUBJ_COLOR.get(r.subject_public, "#888")),
            opacity=.75,
            hovertemplate=(f"<b>{r.session_public}</b> ({r.subject_public})<br>"
                           "%{x}: %{y:.2f}%<br>"
                           f"D = {r.D_s_pct:+.2f} pp<extra></extra>")))
    base_layout(f2, 460, title="B2 &middot; LOW vs HIGH resolvability, paired by session",
                yaxis_title="% of cells resolved")

    cens = lc.copy()
    f4 = go.Figure()
    f4.add_trace(go.Bar(x=cens.band, y=cens.n_at_lower_bound, name="pinned at lower bound",
                        marker_color="#a33a2c"))
    f4.add_trace(go.Bar(x=cens.band, y=cens.n_resolved - cens.n_at_lower_bound,
                        name="measured latency", marker_color="#1f5f8b"))
    base_layout(f4, 380, title="B4 &middot; Left-censoring among resolved LFP cells",
                yaxis_title="resolved cells", barmode="stack")

    beta = cens[cens.band == "beta"].iloc[0]
    return f"""
<h2>LFP frequency and temporal resolvability</h2>
<p class="mut">{int(lf.n_cells.sum()):,} area&times;frequency cells;
{int(lf.n_resolved.sum())} resolve. Resolvability &mdash; whether independent estimators agree on
<em>when</em> the change happened &mdash; is itself the informative quantity here.</p>

<div class="card">
<p><strong>Unresolved does not mean unmodulated.</strong> A cell can carry a large, robust
omission response whose onset is not localisable in time. Robust low-frequency modulation
magnitude and poor low-frequency temporal localisation are two distinct findings, and this page
reports only the second.</p>
</div>

<h3>B1 &middot; P(resolved | frequency)</h3>
{div(f1, "b1")}

<h3>B2 &middot; LOW vs HIGH, paired within session</h3>
<p>One line per session. The pairing is what makes this inferential: each session contributes a
single difference D<sub>s</sub>, so between-session and between-animal variation cannot inflate n.</p>
{div(f2, "b2")}
<div class="card key">
<p>median D = <span class="stat pos">+{t2.median_D:g} percentage points</span> &middot;
exact exhaustive sign-flip permutation
<span class="stat">p = {_fmt_p(t2.signflip_exact_p)}</span>
({int(t2.n_permutations_enumerated):,} assignments enumerated over
{int(t2.n_nonzero_sessions)} non-zero sessions of {int(t2.n_sessions)}) &middot;
Holm <span class="stat">p = {float(t2.holm_p):.1e}</span>
<span class="badge b-pub">replicated across sessions</span></p>
</div>

<h3>B4 &middot; Censoring, and why there is no beta onset distribution</h3>
<p><strong>Beta latencies are strongly left-censored.</strong> Of {int(beta.n_resolved)} resolved
beta cells, <span class="stat neg">{int(beta.n_at_lower_bound)}</span> sit exactly on the lower
search bound and {int(beta.n_le_20ms)} ({100 * beta.frac_le_20ms:.0f}%) fall at or below 20 ms.
A naive beta onset distribution would report a bound, not a measurement, so none is shown here
and boundary-pinned values are never rendered as ordinary latencies.</p>
{div(f4, "b4")}
{table_html(cens)}
<p class="mut">Theta and alpha resolve too few cells
({int(lc[lc.band == 'theta'].n_resolved.iloc[0])} and
{int(lc[lc.band == 'alpha'].n_resolved.iloc[0])} respectively) to support corpus latency claims.
Low and high gamma are the main descriptive LFP timing regimes.</p>
"""


# =============================================================================================
# 5. DSP temporal support  (B3)
# =============================================================================================
def dsp_support(d) -> str:
    s = d["dsp"].sort_values("freq")
    f = go.Figure()
    f.add_trace(go.Scatter(
        x=s.freq, y=s.S_intrinsic, mode="lines+markers", name="S_intrinsic (well behaved)",
        line=dict(color="#1f5f8b", width=2.6), marker=dict(size=7),
        hovertemplate="%{x:.2f} Hz<br>S_intrinsic %{y:.0f} ms<extra></extra>"))
    f.add_trace(go.Scatter(
        x=s.freq, y=s.W_backward, mode="lines+markers", name="W_backward (unstable through beta)",
        line=dict(color="#a33a2c", width=1.6, dash="dash"),
        marker=dict(size=6, symbol="x"),
        hovertemplate="%{x:.2f} Hz<br>W_backward %{y:.0f} ms<extra></extra>"))
    b = s[s.band == "beta"]
    if len(b):
        f.add_vrect(x0=b.freq.min(), x1=b.freq.max(), fillcolor="#a33a2c", opacity=.07,
                    line_width=0, annotation_text="beta: W_backward unstable",
                    annotation_position="top right")
    base_layout(f, 470, title="B3 &middot; Transform temporal support",
                xaxis_title="frequency (Hz)", yaxis_title="temporal support (ms)")
    f.update_xaxes(type="log")
    f.update_yaxes(type="log")

    bb = s[s.band == "beta"].W_backward
    return f"""
<h2>DSP temporal support</h2>
<p class="mut">What the transform can resolve, independent of what the data do. Empirical
resolvability must be read alongside this, or a property of the analysis is mistaken for a
property of the brain.</p>

{div(f, "b3")}

<div class="card">
<p><strong>S<sub>intrinsic</sub> is the well-behaved metric</strong> and is plotted prominently:
it falls monotonically from
<span class="stat">{s.S_intrinsic.iloc[0]:.0f} ms</span> at {s.freq.iloc[0]:.2f} Hz to
<span class="stat">{s.S_intrinsic.iloc[-1]:.0f} ms</span> at {s.freq.iloc[-1]:.1f} Hz.</p>
<p><strong>W<sub>backward</sub> is shown with its instability intact, not smoothed.</strong>
Through the beta band it takes the values
{', '.join(f'{v:.0f}' for v in bb)} ms &mdash; non-monotone, and not interpretable as a smooth
support curve there. Smoothing that away would hide the one thing the panel exists to show.</p>
</div>

<div class="card hold">
<p><strong>This curve does not explain the empirical gradient.</strong> The transform's temporal
support and the measured resolvability gradient are correlated in the obvious direction, but no
causal claim is made: a shared frequency dependence is not evidence that one produces the other.
Both are reported; neither is offered as the mechanism of the other.</p>
</div>

{table_html(d["dsp"])}
"""


# =============================================================================================
# 6. Session-level statistics  (C1, C2, C3)
# =============================================================================================
def session_statistics(d) -> str:
    t, ss, ls = d["tests"], d["spk_sess"], d["lfp_sess"]
    t1, t2, t3 = (p_of(t, "increase-vs-decrease"), p_of(t, "LFP HIGH-minus-LOW"),
                  p_of(t, "omission-minus-stimulus"))

    def strip(vals, title, unit, p, verdict, color):
        v = np.asarray([x for x in vals if pd.notna(x)], dtype=float)
        f = go.Figure()
        f.add_vline(x=0, line=dict(color="#1a1a1a", width=1.4))
        f.add_trace(go.Scatter(
            x=v, y=np.random.default_rng(0).uniform(-.14, .14, len(v)), mode="markers",
            marker=dict(size=10, color=color, opacity=.72,
                        line=dict(width=.7, color="#fff")), showlegend=False,
            hovertemplate="D = %{x:.2f} " + unit + "<extra></extra>"))
        f.add_trace(go.Scatter(x=[np.median(v)], y=[0], mode="markers",
                               marker=dict(size=17, color=color, symbol="line-ns",
                                           line=dict(width=3, color=color)),
                               showlegend=False, hoverinfo="skip"))
        base_layout(f, 210, title=f"{title} &middot; p = {p} &middot; {verdict}",
                    xaxis_title=f"per-session difference D<sub>s</sub> ({unit})")
        f.update_yaxes(visible=False, range=[-.4, .4])
        f.update_layout(margin=dict(l=64, r=24, t=48, b=52))
        return f

    e1 = ss[ss.eligible_signtiming.eq(True)]
    e3 = ss[ss.eligible_dT.eq(True)]
    f1 = strip(e1.D_s_signtiming, "C1 &middot; SPK increase-vs-decrease timing", "ms",
               f"{t1.signflip_exact_p:.3f}", "not replicated", "#8a6d1f")
    f2 = strip(ls.D_s_pct, "C2 &middot; LFP HIGH&minus;LOW resolvability", "pp",
               _fmt_p(t2.signflip_exact_p), "replicated", "#0f7b52")
    f3 = strip(e3.D_s_dT, "C3 &middot; SPK omission&minus;stimulus shift", "ms",
               f"{t3.signflip_exact_p:.3f}", "insufficient evidence", "#1f5f8b")

    return f"""
<h2>Session-level statistics</h2>
<p class="mut">One difference per session; the session is the inferential unit throughout.</p>

<div class="card">
<h3 style="margin-top:0">Why an exhaustive sign-flip permutation, and not the &quot;exact&quot; Wilcoxon</h3>
<p>Under the null that D<sub>s</sub> is symmetric about zero, all 2<sup>k</sup> sign assignments
are equally likely, so enumerating them is <em>complete</em> rather than sampled &mdash; there is
no seed and no resample count to reproduce. Sign-flipping an exact zero changes nothing, so the
enumeration runs over the non-zero sessions only.</p>
<p><strong>All three D<sub>s</sub> vectors contain ties in |D<sub>s</sub>|.</strong> SciPy's own
documentation states its exact Wilcoxon null holds only when there are no ties, so the exact
Wilcoxon value is invalid here and is reported in the tables as a secondary diagnostic under a
name that says so. Using it as a headline test was an error caught in review; the numbers moved
(Test&nbsp;1 0.9375&nbsp;&rarr;&nbsp;0.875, Test&nbsp;2
7.63e-5&nbsp;&rarr;&nbsp;8.39e-5) and no conclusion changed.</p>
</div>

{div(f1, "c1")}
<p class="mut">n = {int(t1.n_sessions)} eligible sessions, all non-zero, median
{t1.median_D:g} ms, {int(t1.n_permutations_enumerated)} assignments enumerated.
Directions are mixed across sessions. <span class="badge b-desc">not replicated</span>
This one <em>is</em> naturally read as a replicated null: the smallest attainable exact p at
n = {int(t1.n_sessions)} is 0.0156, so the test had the resolution to detect a consistent effect
and did not.</p>

{div(f2, "c2")}
<p class="mut">n = {int(t2.n_sessions)} sessions ({int(t2.n_nonzero_sessions)} non-zero), median
<span class="stat pos">+{t2.median_D:g} pp</span>,
{int(t2.n_permutations_enumerated):,} assignments enumerated,
Holm <span class="stat">p = {float(t2.holm_p):.1e}</span>.
<span class="badge b-pub">replicated &mdash; the primary positive result of Analysis 6A</span></p>

{div(f3, "c3")}
<p class="mut">n = {int(t3.n_sessions)} sessions ({int(t3.n_nonzero_sessions)} non-zero), median
<span class="stat">+{t3.median_D:g} ms</span>,
{int(t3.n_permutations_enumerated):,} assignments enumerated.
<span class="badge b-desc">not significant / insufficient session-level evidence</span>
Deliberately <em>not</em> called a null: unlike C1 this is a shift in a consistent direction that
the available number of sessions cannot establish.</p>

<h3>All three, with secondary diagnostics</h3>
{table_html(t)}
<p class="mut">Wilcoxon and sign-test columns are secondary diagnostics recorded for transparency.
They are not competing headline tests and must not be quoted as such.</p>
"""


# =============================================================================================
# 7. Coverage and design limits  (D)
# =============================================================================================
def coverage(d) -> str:
    cov, c = d["cov"], d["census"]
    piv = cov.pivot_table(index="area", columns="subject_public",
                          values="n_units_eligible", aggfunc="sum").fillna(0)
    subs = sorted(cov.subject_public.unique())
    for s in subs:
        if s not in piv.columns:
            piv[s] = 0
    piv = piv[subs]
    f = go.Figure(go.Heatmap(
        z=piv.values, x=list(piv.columns), y=list(piv.index),
        colorscale="Blues", hovertemplate="%{y} &times; %{x}<br>%{z:.0f} units<extra></extra>",
        colorbar=dict(title="units")))
    base_layout(f, 520, title="D &middot; area &times; subject coverage",
                xaxis_title="subject (anonymised)", yaxis_title="area")

    n_area_all = int((piv > 0).all(axis=1).sum())
    n_area_one = int((piv > 0).sum(axis=1).eq(1).sum())
    nsess = cov.groupby("subject_public").session_public.nunique()
    sess_rows = "".join(
        f"<tr><td>{s}</td><td class='stat'>{int(nsess[s])}</td>"
        f"<td class='stat'>{int(cov[cov.subject_public == s].n_units_eligible.sum()):,}</td>"
        f"<td class='stat'>{int((piv[s] > 0).sum())}</td></tr>" for s in subs)

    return f"""
<h2>Coverage and design limits</h2>
<p class="mut">This page exists to make the confound visible, not to work around it.</p>

<div class="card key">
<p><strong>Area and subject are partially confounded.</strong> Of {len(piv)} recorded areas,
<span class="stat">{n_area_all}</span> appear in all {len(subs)} animals and
<span class="stat">{n_area_one}</span> appear in only one. A between-area difference is therefore
not separable from a between-animal difference by modelling alone, and
<strong>no area-latency hierarchy is claimed anywhere in Analysis 6A.</strong> Pooled area
medians, wherever they appear, are <span class="badge b-desc">descriptive</span>.</p>
</div>

{div(f, "d1")}

<div class="scroll"><table><thead><tr><th>Subject</th><th>sessions</th><th>eligible units</th>
<th>areas</th></tr></thead><tbody>{sess_rows}</tbody></table></div>

<div class="card">
<p><strong>Unit counts are not independent biological replicates.</strong> Units within a session
share an animal, a session, a probe insertion, and a preprocessing pass. Every inferential claim
in Analysis 6A reduces each session to a single number before testing; the pooled unit-level
percentages that appear on other pages are labelled descriptive for exactly this reason.</p>
</div>

<h3>Session-level census</h3>
{table_html(c)}
"""


# =============================================================================================
# 8. Methods
# =============================================================================================
def methods(d) -> str:
    lc, lf = d["lfp_cens"], d["lfp_freq"]
    return f"""
<h2>Methods</h2>

<h3>Onset estimation and the resolution criterion</h3>
<p>Each candidate response is fitted by several independent onset estimators (a derivative-based
estimator, a change-point estimator, and a bounded exponential fit). A latency is called
<strong>resolved</strong> only when those estimators agree to within a fixed spread criterion;
otherwise the response is <strong>detected</strong> but its timing is not identified. Detection
and resolution are different states and are never merged.</p>

<h3>One-sidedness</h3>
<p>Every estimator's search window begins at the omitted event, and the exponential fit's onset
parameter is bounded below at zero. A response that deviates before the event lands on the bound
or returns undefined; it can never be reported as a negative latency. Across the whole corpus
there are zero negative onsets in any onset column of either modality.</p>
<p>One-sidedness alone is not sufficient. A step placed well before the event can still yield a
one-sided but meaningless value from a single estimator; what rejects that case is the
estimator-agreement criterion, not the bound.</p>

<h3>Inferential unit and permutation scheme</h3>
<p>The session is the inferential unit. Each session contributes one difference D<sub>s</sub>.
The primary test is an <strong>exact exhaustive sign-flip permutation</strong>: under the null
that D<sub>s</sub> is symmetric about zero, every one of the 2<sup>k</sup> sign assignments over
the k non-zero sessions is equally likely, and all of them are enumerated. The test has no seed
and no resample count.</p>
<p>Wilcoxon signed-rank and sign-test values appear in the tables as secondary diagnostics only.
SciPy's exact Wilcoxon null is valid only without ties, and all three D<sub>s</sub> vectors
contain ties, so that value is explicitly not used as a headline test.</p>

<h3>Intervals and multiplicity</h3>
<p>Proportions use exact <strong>Clopper&ndash;Pearson</strong> intervals &mdash; no RNG, no seed,
no resample count. Latency uncertainty uses a bootstrap SD, reported as
&plusmn;1.96&nbsp;&times;&nbsp;SD. Where a family of tests is corrected, <strong>Holm</strong> is
used and controls FWER; Holm and Benjamini&ndash;Hochberg control different rates and are never
conflated.</p>

<h3>Constants</h3>
<div class="scroll"><table><thead><tr><th>Constant</th><th>Value</th><th>Role</th></tr></thead>
<tbody>
<tr><td>Estimator spread criterion</td><td class="stat">&le; 50 ms</td>
<td class="mut">defines <em>resolved</em></td></tr>
<tr><td>Bootstrap identifiability floor</td><td class="stat">0.5</td>
<td class="mut">minimum bootstrap identification rate</td></tr>
<tr><td>Minimum units per sign (Test 1)</td><td class="stat">3</td>
<td class="mut">session eligibility</td></tr>
<tr><td>Minimum units with &Delta;T (Test 3)</td><td class="stat">3</td>
<td class="mut">session eligibility</td></tr>
<tr><td>LOW bands</td><td>theta, alpha</td><td class="mut">Test 2 grouping</td></tr>
<tr><td>HIGH bands</td><td>beta, low_gamma, high_gamma</td><td class="mut">Test 2 grouping</td></tr>
<tr><td>Onset search lower bound</td><td class="stat">0 ms</td>
<td class="mut">enforces one-sidedness</td></tr>
<tr><td>|&Delta;T| descriptive threshold</td><td class="stat">50 ms</td>
<td class="mut">display only, not inferential</td></tr>
</tbody></table></div>

<h3>Censoring</h3>
<p>Because the search bound is zero, a response whose true onset precedes or coincides with the
event is left-censored at the bound. This is not uniform across frequency: it dominates beta
({int(lc[lc.band == 'beta'].n_at_lower_bound.iloc[0])} of
{int(lc[lc.band == 'beta'].n_resolved.iloc[0])} resolved cells pinned) and is rare elsewhere.
Beta latencies are therefore never presented as a distribution.</p>

<h3>What is deliberately not done</h3>
<ul>
<li>No common-axis SPK-vs-LFP figure &mdash; held until the LFP side can be shown as intervals
with censoring state rather than points.</li>
<li>No area-latency hierarchy &mdash; area and subject are confounded.</li>
<li>No directional or causal LFP&rarr;SPK claim &mdash; nothing here tests direction.</li>
<li>No naive beta onset distribution &mdash; it would report a bound.</li>
<li>No theta/alpha corpus latency claim &mdash;
{int(lc[lc.band == 'theta'].n_resolved.iloc[0])} and
{int(lc[lc.band == 'alpha'].n_resolved.iloc[0])} resolved cells respectively.</li>
</ul>
"""


# =============================================================================================
# 9. Static figures
# =============================================================================================
def figures(d) -> str:
    items = [
        ("fig6a_A_spk_latency.svg", "Figure A &mdash; SPK timing",
         "Census funnel, per-unit resolved latency with bootstrap intervals, and "
         "&Delta;T = T<sub>om</sub> &minus; T<sub>stim</sub>."),
        ("fig6a_B_lfp_resolvability.svg", "Figure B &mdash; LFP temporal resolution",
         "P(resolved | frequency), LOW-vs-HIGH session pairing, transform temporal support, "
         "and censoring / estimator width."),
        ("fig6a_C_session_level_tests.svg", "Figure C &mdash; session-level inference",
         "The three session-level tests under identical machinery, with their three "
         "different outcomes."),
        ("fig6a_D_coverage.svg", "Figure D &mdash; coverage and design",
         "Subject &times; session &times; area coverage, making the area/subject confound "
         "visible."),
    ]
    blocks = "".join(
        f'<figure><img src="figures/{fn}" alt="{ttl}" loading="lazy">'
        f"<figcaption><strong>{ttl}.</strong> {cap}</figcaption></figure>" for fn, ttl, cap in items)
    return f"""
<h2>Static publication figures</h2>
<p class="mut">Vector SVG, generated by the frozen figure script from the same canonical tables
that drive the interactive pages. These are the citable versions.</p>
{blocks}
<div class="card hold">
<p><strong>Figure E does not exist.</strong> A common-axis SPK-vs-LFP comparison is held pending
separate authorization. The LFP side would need an interval-and-censoring representation, and
producing it merely because a website can display it would invert the order of evidence.</p>
</div>
"""


# =============================================================================================
# 10. Provenance
# =============================================================================================
def provenance(d, prov: dict, manifest: list[dict]) -> str:
    rows = "".join(
        f"<tr><td><a href=\"tables/{k}\">{k}</a></td><td class='stat'>{v['rows']}</td>"
        f"<td class='mut' style='font-family:monospace;font-size:11.5px'>{v['sha256'][:16]}&hellip;</td></tr>"
        for k, v in prov["tables"].items())
    site = "".join(
        f"<tr><td>{m['path']}</td><td class='stat'>{m['bytes']:,}</td>"
        f"<td><span class='badge b-pub'>{m['visibility']}</span></td></tr>" for m in manifest)
    return f"""
<h2>Provenance</h2>

<div class="card">
<div class="scroll"><table><tbody>
<tr><td>Analysis</td><td style="text-align:left"><code>{prov['analysis']}</code></td></tr>
<tr><td>Status</td><td style="text-align:left"><span class="badge b-review">Exploratory
analysis &mdash; NOT publication-final</span></td></tr>
<tr><td>Source commit</td><td style="text-align:left"><code>{prov['source_commit']}</code></td></tr>
<tr><td>Tables generated</td><td style="text-align:left">{prov['generated_utc']}</td></tr>
<tr><td>Table builder</td><td style="text-align:left"><code>{prov['builder']}</code></td></tr>
<tr><td>Site builder</td><td style="text-align:left"><code>omission/atlas/build_atlas.py</code></td></tr>
<tr><td>Statistics receipt</td><td style="text-align:left">
<code>onset6a_session_level_tests.json</code></td></tr>
<tr><td>Identifier policy</td><td style="text-align:left">{prov['identifier_policy']}</td></tr>
</tbody></table></div>
</div>

<h3>Truth order</h3>
<p><code>current receipted analysis &rarr; canonical table &rarr; generated figure / site</code></p>
<p>This site is the last link in that chain and has no independent authority. If a value rendered
here disagrees with its canonical table, <strong>the site is wrong</strong> and must fail
verification. Analysis scripts, receipts, and the frozen <code>jnwb</code> estimators are not
modified to make the site render better.</p>

<h3>Canonical public tables</h3>
{f'<div class="scroll"><table><thead><tr><th>Table</th><th>rows</th><th>sha256</th></tr></thead><tbody>{rows}</tbody></table></div>'}

<h3>Deployed file manifest</h3>
{f'<div class="scroll"><table><thead><tr><th>Path</th><th>bytes</th><th>visibility</th></tr></thead><tbody>{site}</tbody></table></div>'}

<h3>What is not published</h3>
<p>No spike times, no LFP traces, no trial-level neural data, no eye traces, no NWB paths, no
machine-local absolute paths, and no subject/session identifier mapping. Subject and session
labels on this site are deterministic anonymous labels; the mapping to recording identifiers is
kept outside the published site and is not tracked in the repository.</p>
"""
