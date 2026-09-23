"""The order inventory states bounds with their references; the timed benchmark cites it by label.

The inventory is an upper-bound document and the benchmark is a measurement. They agree only if
every label the benchmark cites names the row it means, and the inventory carries no measured
exponent of its own -- an exponent there would have no fitting method, scale set or receipt behind
it.
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
    return defects


def test_the_inventory_states_bounds_with_their_references():
    assert inventory_defects(INVENTORY.read_text(encoding="utf-8")) == []


def test_every_label_the_benchmark_cites_names_its_row():
    bench = BENCHMARK.read_text(encoding="utf-8")
    assert re.search(r"^\| INV-\d{2} \|", bench, re.M), "the benchmark cites no label; the check is vacuous"
    assert citation_defects(bench, INVENTORY.read_text(encoding="utf-8")) == []


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
