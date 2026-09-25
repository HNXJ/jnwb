"""The order inventory states bounds with their references; the timed benchmark cites it by label.

The inventory is an upper-bound document and the benchmark is a measurement. They agree only if
every label the benchmark cites names the row it means and quotes the bound that row states, every
exponent the benchmark says a bound admits is the one that bound gives in the swept parameter, and
the inventory carries no measured exponent of its own -- an exponent there would have no fitting
method, scale set or receipt behind it.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "artifacts" / "benchmarks" / "complexity_inventory.md"
BENCHMARK = ROOT / "artifacts" / "evidence" / "0.2.6" / "computational_order.md"

_EXPONENT = re.compile(r"(?<![\w.])[+-]\d+\.\d{2}(?![\w.])")


def inventory_rows(text):
    """Map each ``INV-NN`` label to its cells, from the bounds table."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"INV-\d{2}", cells[0]):
            assert cells[0] not in rows, f"label {cells[0]} appears twice"
            rows[cells[0]] = cells
    return rows


def inventory_defects(text):
    rows = inventory_rows(text)
    defects = []
    if not rows:
        defects.append("no labelled rows")
    if re.search(r"\bverified\b", text, re.I):
        defects.append("claims verification")
    for label, cells in rows.items():
        if len(cells) != 7:
            defects.append(f"{label}: {len(cells)} cells, expected 7")
            continue
        if not cells[5] or not cells[6]:
            defects.append(f"{label}: names no algorithm or no reference")
        for cell in cells[3:5]:
            if _EXPONENT.search(cell):
                defects.append(f"{label}: states a measured exponent with no method")
    return defects


_LATEX = (
    (r"\$", ""),
    (r"\\mathcal\{O\}", "O"),
    (r"\\cdot", "."),
    (r"\\log", "log"),
    (r"\\text\{([^}]*)\}", r"\1"),
    (r"_\{([^}]*)\}", r"_\1"),
)


def plain_bound(latex):
    """The inventory's LaTeX bound in the benchmark's notation, e.g. ``O(C . F . T log T)``."""
    for pattern, replacement in _LATEX:
        latex = re.sub(pattern, replacement, latex)
    return " ".join(latex.split())


def quoted_bound(line, primitive):
    """The bound ``line`` quotes as ``primitive: O(...)``, parentheses balanced, or None."""
    match = re.search(rf"(?<!\w)`?{re.escape(primitive)}`?: O\(", line)
    if not match:
        return None
    depth = 0
    for i in range(match.end() - 1, len(line)):
        depth += {"(": 1, ")": -1}.get(line[i], 0)
        if depth == 0:
            return " ".join(line[match.end() - 2 : i + 1].split())
    return None


def citation_defects(benchmark_text, inventory_text):
    rows = inventory_rows(inventory_text)
    defects = []
    for line in benchmark_text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not re.fullmatch(r"INV-\d{2}", cells[0]):
            continue
        label = cells[0]
        if label not in rows:
            defects.append(f"{label} cited but absent from the inventory")
            continue
        primitive = rows[label][1].strip("`")
        if primitive not in line:
            defects.append(f"{label} cited for something other than `{primitive}`")
            continue
        stated = plain_bound(rows[label][3])
        quoted = quoted_bound(line, primitive)
        if quoted is None:
            defects.append(f"{label} quotes no bound for `{primitive}`")
        elif quoted.replace(" ", "") != stated.replace(" ", ""):
            defects.append(f"{label} quotes {quoted}; the inventory states {stated}")
    for label in sorted(set(re.findall(r"\bINV-\d{2}\b", benchmark_text)) - set(rows)):
        defects.append(f"{label} cited in the text but absent from the inventory")
    return defects


#: The inventory symbols that grow with each swept parameter. Welch segments grow with the
#: samples at a fixed segment length, so a sweep in samples grows both ``T`` and ``K_seg``.
_SWEPT = {
    "n_channels": ("C",),
    "n_freqs": ("F",),
    "n_samples": ("T", "K_seg"),
    "model_order": ("P",),
    "n_surrogates": ("S",),
    "n_conditions": ("N",),
    "n_features": ("D",),
    "n_folds": ("K",),
    "n_trials": ("R",),
    # One stream spec slices the tail of a growing file, the other a growing slice from the
    # start; both grow the offset of the last selected element.
    "n_elements_in_file": ("E",),
    "n_elements_sliced": ("E",),
}


def admitted_degree(bound, symbols):
    """Largest degree of ``symbols`` over the bound's terms, and whether that term logs one."""
    best = (0, False)
    for term in bound.strip()[2:-1].split("+"):
        tokens = term.replace(".", " ").split()
        degree, logged = 0, False
        for i, token in enumerate(tokens):
            base, _, power = token.partition("^")
            if i and tokens[i - 1] == "log":
                logged = logged or base in symbols
            elif base in symbols:
                degree += int(power or 1)
        best = max(best, (degree, logged))
    return best


def table_rows(text, required):
    """Each body row, as {column: cell}, of every table whose header has ``required`` columns."""
    header = None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells if set(required) <= set(cells) else []
        elif header and not all(re.fullmatch(r":?-+:?", c) for c in cells):
            if len(cells) == len(header):
                yield dict(zip(header, cells))


def bound_defects(benchmark_text, inventory_text):
    """Every exponent a bound is said to admit, and every verdict drawn from it, re-derived."""
    rows = inventory_rows(inventory_text)
    parameter = {r["spec"].strip("`"): r["parameter"]
                 for r in table_rows(benchmark_text, ("spec", "parameter", "exp"))}
    defects, checked, label = [], 0, None
    for row in table_rows(benchmark_text, ("Claim", "Spec", "Bound admits", "Measured", "Verdict")):
        label = row["Claim"] or label
        if label not in rows or not _EXPONENT.fullmatch(row["Bound admits"]):
            continue
        spec = row["Spec"].strip("`")
        swept = _SWEPT.get(parameter.get(spec))
        if swept is None:
            defects.append(f"{label} {spec}: no inventory symbol for its swept parameter")
            continue
        degree, logged = admitted_degree(plain_bound(rows[label][3]), swept)
        admits = float(row["Bound admits"])
        if not degree <= admits <= degree + (0.2 if logged else 0.0):
            defects.append(f"{label} {spec}: says the bound admits {admits:+.2f}, it gives {degree}"
                           + (" plus a log" if logged else ""))
        measured = float(_EXPONENT.search(row["Measured"]).group())
        # Two exponents agree within 0.25, the resolution section 2.5 of the benchmark sets.
        within = measured <= admits + 0.25
        if row["Verdict"].startswith("within") != within:
            defects.append(f"{label} {spec}: verdict '{row['Verdict']}' for {measured:+.2f} "
                           f"against {admits:+.2f}")
        checked += 1
    return defects, checked


def test_the_inventory_states_bounds_with_their_references():
    assert inventory_defects(INVENTORY.read_text(encoding="utf-8")) == []


def test_every_label_the_benchmark_cites_names_its_row():
    bench = BENCHMARK.read_text(encoding="utf-8")
    assert re.search(r"^\| INV-\d{2} \|", bench, re.M), "the benchmark cites no label; the check is vacuous"
    assert citation_defects(bench, INVENTORY.read_text(encoding="utf-8")) == []


def test_every_exponent_a_bound_admits_is_the_one_it_gives():
    defects, checked = bound_defects(
        BENCHMARK.read_text(encoding="utf-8"), INVENTORY.read_text(encoding="utf-8")
    )
    assert checked >= 20, f"only {checked} rows checked; the table was not found"
    assert defects == []


def test_the_bound_checks_see_what_they_are_for():
    header = "| ID | Primitive | Module | Time | Memory | Algorithm | Reference |\n|---|---|---|---|---|---|---|\n"
    inv = header + "| INV-01 | `g` | `m` | $\\mathcal{O}(T \\cdot P^2 + P^3)$ | x | a | r |\n"
    inv += "| INV-02 | `s` | `m` | $\\mathcal{O}(N^2 \\log N)$ | x | a | r |\n"
    sweeps = (
        "| spec | parameter | exp |\n|---|---|---|\n"
        "| `g[model_order]` | model_order | +1.00 |\n| `s[n_conditions]` | n_conditions | +2.10 |\n\n"
    )
    table = "| Claim | What it says | Spec | Bound admits | Measured | Verdict |\n|---|---|---|---|---|---|\n"

    def bench(g_row, s_row="| INV-02 | s: O(N^2 log N) | `s[n_conditions]` | +2.16 | +2.11 | within bound |"):
        return sweeps + table + g_row + "\n" + s_row + "\n"

    good = "| INV-01 | g: O(T . P^2 + P^3) | `g[model_order]` | +3.00 | +1.07 | within bound |"
    assert citation_defects(bench(good), inv) == []
    assert bound_defects(bench(good), inv) == ([], 2)
    assert citation_defects(bench(good.replace(" + P^3", "")), inv) != []
    assert citation_defects(bench(good.replace("g: O(T . P^2 + P^3)", "g")), inv) != []
    assert citation_defects(bench(good) + "INV-07 is cited in prose.\n", inv) != []
    assert bound_defects(bench(good.replace("+3.00", "+2.00")), inv)[0] != []
    assert bound_defects(bench(good.replace("within bound", "exceeds bound")), inv)[0] != []
    assert bound_defects(bench(good.replace("+1.07", "+3.40")), inv)[0] != []
    logged = "| INV-02 | s: O(N^2 log N) | `s[n_conditions]` | {} | +2.11 | within bound |"
    assert bound_defects(bench(good, logged.format("+2.40")), inv)[0] != []
    assert bound_defects(bench(good, logged.format("+1.90")), inv)[0] != []


def test_the_checks_see_what_they_are_for():
    header = "| ID | Primitive | Module | Time | Memory | Algorithm | Reference |\n|---|---|---|---|---|---|---|\n"
    good = header + "| INV-01 | `f` | `m` | $O(T)$ | $O(1)$ | one pass | Author 2000 |\n"
    assert inventory_defects(good) == []
    assert inventory_defects(good.replace("$O(T)$", "+1.00")) != []
    assert inventory_defects(good.replace("Author 2000", "")) != []
    assert inventory_defects(good + "Bounds verified on the heap.\n") != []
    bench_ok = "| INV-01 | inv | f: O(T) | spec |\n"
    assert citation_defects(bench_ok, good) == []
    assert citation_defects("| INV-02 | inv | f: O(T) |\n", good) != []
    assert citation_defects("| INV-01 | inv | g: O(T) |\n", good) != []
    assert citation_defects("| INV-01 | inv | f: O(1) |\n", good) != []


def test_the_harness_behind_the_benchmark_measures_what_it_says(tmp_path):
    import os
    import subprocess
    import sys

    import pytest
    import threadpoolctl

    # Appended, never prepended: this suite also qualifies an installed jnwb.
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from scripts import measure_order

    sizes = [100, 1_000, 10_000]
    assert abs(measure_order.fit(sizes, [1e-9 * s**2 for s in sizes])["exp"] - 2.0) < 1e-9
    short = measure_order.Spec("n", (100, 900), "", lambda n, tmp: (lambda: None))
    with pytest.raises(SystemExit, match="less than a decade"):
        measure_order.sweep("short", short, 1, None, tmp_path)

    limiter = measure_order.pin_threads()
    try:
        assert {p["num_threads"] for p in threadpoolctl.threadpool_info()} <= {1}
    finally:
        limiter.restore_original_limits()

    bench = BENCHMARK.read_text(encoding="utf-8")
    remeasured = set(re.findall(r"`(\w+\[\w+\])`", bench[bench.index("### 6.2"):bench.index("## 7.")]))
    assert remeasured and remeasured <= set(measure_order.SPECS)

    script = [sys.executable, str(ROOT / "scripts" / "measure_order.py"), "--list"]
    listed = subprocess.run(script, capture_output=True, text=True, check=True).stdout
    assert all(name in listed for name in measure_order.SPECS)
    # A jnwb that shadows the checkout's is refused rather than timed.
    (tmp_path / "jnwb").mkdir()
    (tmp_path / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), str(ROOT)]))
    shadowed = subprocess.run(script, capture_output=True, text=True, env=env)
    assert shadowed.returncode != 0 and "refusing to time it" in shadowed.stderr


# An order reduction must compute what the slower path computed. The benchmark records the
# reduced orders; these hold each reduced path to the definition it replaced.


def test_the_linear_jackknife_equals_leaving_each_segment_out():
    import numpy as np

    from jnwb.connectivity import _psi_from_spectra, _psi_leave_one_out

    rng = np.random.default_rng(5)
    n_seg, n_freq = 40, 33
    fx = rng.normal(size=(n_seg, n_freq)) + 1j * rng.normal(size=(n_seg, n_freq))
    fy = 0.6 * fx * np.exp(0.3j * np.arange(n_freq)) + rng.normal(size=(n_seg, n_freq))
    # One segment carrying almost all of the power: subtracting it from the total would cancel.
    fx[17] *= 1e8
    # A bin only one segment carries: leaving that segment out leaves no power there at all.
    fx[:, 20] = 0.0
    fx[3, 20] = 1.0 + 1.0j
    idx = np.arange(4, 29)

    direct = np.array(
        [_psi_from_spectra(np.delete(fx, i, 0), np.delete(fy, i, 0), idx) for i in range(n_seg)]
    )
    fast = _psi_leave_one_out(fx, fy, idx)
    assert fast.shape == (n_seg,)
    assert np.ptp(direct) > 0.1, "the replicates must differ, or any constant passes"
    np.testing.assert_allclose(fast, direct, rtol=1e-9, atol=1e-12)


def test_a_stored_entry_seeks_and_a_compressed_one_reads(tmp_path, monkeypatch):
    import numpy as np

    import jnwb.io

    arr = np.arange(50_000, dtype=np.float64)
    stored, deflated = tmp_path / "s.npz", tmp_path / "d.npz"
    np.savez(stored, a=arr)
    np.savez_compressed(deflated, a=arr)
    real_read_skip = jnwb.io._read_skip
    read = []

    def counting_read_skip(f, n_bytes, *args, **kwargs):
        read.append(n_bytes)
        return real_read_skip(f, n_bytes, *args, **kwargs)

    monkeypatch.setattr(jnwb.io, "_read_skip", counting_read_skip)
    tail = (slice(49_000, None),)
    np.testing.assert_array_equal(jnwb.io.stream_npz_array(stored, "a", tail), arr[tail])
    if jnwb.io._stored_seek_is_reliable():
        assert read == [], "a stored entry was read through to skip its leading elements"
    else:
        assert read == [49_000 * 8], "a stored entry was seeked where zipfile seeks it wrongly"
    read.clear()
    np.testing.assert_array_equal(jnwb.io.stream_npz_array(deflated, "a", tail), arr[tail])
    # A compressed entry cannot seek; zipfile would emulate it with reads of up to 16 MiB.
    assert read == [49_000 * 8]


def test_a_stored_entry_reads_forward_where_zipfile_seeks_wrongly(tmp_path, monkeypatch):
    """A seek that lands and then ends the entry early must not make a valid archive corrupt."""
    import os
    import sys
    import zipfile

    import numpy as np

    import jnwb.io

    arr = np.arange(24 * 7, dtype=np.float64).reshape(24, 7)
    path = tmp_path / "s.npz"
    np.savez(path, a=arr)
    real_seek = zipfile.ZipExtFile.seek

    def seek_then_end_early(self, offset, whence=os.SEEK_SET):
        # The observable failure of CPython 3.12.0: the position is right, the reads are short.
        landed = real_seek(self, offset, whence)
        self.read = lambda n=-1: b""
        self.readinto = lambda b: 0
        return landed

    reliable = jnwb.io._stored_seek_is_reliable
    reliable.cache_clear()
    monkeypatch.setattr(zipfile.ZipExtFile, "seek", seek_then_end_early)
    try:
        for index in ((3,), (slice(2, 9), 4), (-1,), (slice(None, None, -1), 2)):
            np.testing.assert_array_equal(jnwb.io.stream_npz_array(path, "a", index), arr[index])
        assert reliable() is False
    finally:
        monkeypatch.undo()
        reliable.cache_clear()
    # CPython 3.12.0 is the one declared interpreter whose zipfile fails the probe; a probe that
    # failed everywhere would pass everything above and drop the seek on every interpreter.
    assert reliable() is (sys.version_info[:3] != (3, 12, 0))


def test_a_stored_entry_shorter_than_its_header_still_fails(tmp_path):
    import io
    import zipfile

    import numpy as np
    import pytest

    import jnwb.io

    buf = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        buf, {"descr": "<f8", "fortran_order": False, "shape": (1000,)}
    )
    buf.write(np.ones(100).tobytes())
    path = tmp_path / "short.npz"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("a.npy", buf.getvalue())
    # Seeking clamps at the end of the entry; without a check this returns uninitialised memory.
    with pytest.raises(ValueError, match="corrupt"):
        jnwb.io.stream_npz_array(path, "a", (slice(900, 1000),))
    # A read that runs off the end fails too, rather than leaving the rest of the output unset.
    with pytest.raises(ValueError, match="corrupt"):
        jnwb.io.stream_npz_array(path, "a", (slice(50, 1000),))


def test_the_streaming_reader_walks_edge_slices_in_file_order(tmp_path):
    """The reader moves forward only, so every slice has to be put into file order first."""
    import numpy as np
    import pytest

    import jnwb.io

    arr = np.arange(7 * 40 * 33, dtype=np.int32).reshape(7, 40, 33)
    for save in (np.savez, np.savez_compressed):
        path = tmp_path / f"{save.__name__}.npz"
        save(path, a=arr)
        for edge in ((-1,), (-7,)):
            np.testing.assert_array_equal(
                jnwb.io.stream_npz_array(path, "a", edge), arr[edge], strict=True
            )
        # An out-of-range integer is an error, as in numpy, not an empty result.
        for bad in ((7,), (-8,), (0, 40)):
            with pytest.raises(IndexError, match="out of bounds"):
                jnwb.io.stream_npz_array(path, "a", bad)
        reversed_outer = (slice(None, None, -1), slice(None, None, -3))
        np.testing.assert_array_equal(
            jnwb.io.stream_npz_array(path, "a", reversed_outer), arr[reversed_outer]
        )
