"""Build the jnwb dashboard: ``data.json`` from committed records, and the page beside it.

Each section is read from the records named in ``sources``; no value is typed into this file.
The commit and its date come from git. A section whose source is absent is null, except the
sections the data schema does not allow to be null (``generated``, ``release``, ``releases``,
``figures``): a missing source there stops the build rather than writing a section it cannot say.

``order`` has one row per row of the measured-order tables in the computational-order record,
each with the module of the ``jnwb.x`` heading above its table. The record's other tables are
keyed by ``spec`` and ``parameter`` and are not read.

``validations`` has one card per receipt the build reads: its path, the commit that last changed
it, its SHA-256 and the fields it states. ``verify_validations`` checks a built site against the
repository.

``deferred`` has one row per roadmap row that is a validation, each read as not started. Each
replication in ``showcases`` carries a ``label``: the dashboard's name for the record's verdict.
Each also carries ``paper``, ``library`` and ``methods``: the relation to the paper, the frozen-register
coverage of the functions it lists, and the methods outcome, which follows the record's verdict
except where a rerun covered only part of the scope.

    python scripts/build_dashboard.py --out <dir>    # writes <dir>/data.json and the page
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = REPO_ROOT / "scripts" / "dashboard"
TEMPLATE_PATH = DASHBOARD / "index.html"
APP_PATH = DASHBOARD / "app.js"
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT_PATH = REPO_ROOT / "jnwb" / "__init__.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "workflow.yml"
FROZEN = REPO_ROOT / "artifacts" / "process" / "frozen_validated.json"
BENCHMARKS = REPO_ROOT / "artifacts" / "benchmarks"
BASELINE = BENCHMARKS / "performance" / "baseline_performance.json"
PEAK_MEMORY = BENCHMARKS / "performance" / "peak_memory.json"
IMPORT_BREAKDOWN = BENCHMARKS / "performance" / "import_breakdown.json"
REFERENCES = REPO_ROOT / "docs" / "references.md"
ASSETS = REPO_ROOT / "docs" / "assets"
FIGURES = ASSETS / "figures"
DOCS = REPO_ROOT / "docs"
ORDER_RECORD = REPO_ROOT / "artifacts" / "evidence" / "0.2.6" / "computational_order.md"
SHOWCASE_RECORD = REPO_ROOT / "artifacts" / "showcases" / "openscope_glo.json"
ROADMAP = REPO_ROOT / "artifacts" / "roadmap.md"
CALIBRATION = BENCHMARKS / "calibration"
#: The calibration receipts a card reads. Their raw records are not read, so they get no card.
CALIBRATION_RECEIPTS = (CALIBRATION / "xflip_calibration_0.2.5.md",
                        CALIBRATION / "vflip_calibration_0.2.4.md",
                        CALIBRATION / "curation_calibration_0.2.13.md",
                        CALIBRATION / "cuda_parity_0.2.4.md")
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
# The closure receipt is read by the release gate's own parser, which this module calls.
from scripts.release_gate import (RECEIPT_PATH as CLOSURE_RECEIPT_PATH,  # noqa: E402
                                  blocker_fixpoint_receipt)
CLOSURE_RECEIPT = REPO_ROOT / CLOSURE_RECEIPT_PATH
VALIDATION_HTML = ASSETS / "validations"
SECTIONS =("generated", "release", "releases", "ci", "api", "verified", "performance",
            "order", "references", "figures", "showcases", "validations", "deferred")

_VERSION_LINE = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\S+))?$")
_INIT_VERSION = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
_METHOD_COLUMNS = ["Reference", "Result implemented", "Functions"]
_RULE_CELL = re.compile(r":?-{3,}:?")
_ORDER_COLUMNS = ["spec", "parameter", "sizes", "median times (ms)", "exp", "r2", "t-span",
                  "achieved", "admissible", "cls", "gap"]
_MODULE_HEADING = re.compile(r"^### `(jnwb\.[^`]+)`")
_STUDY_COLUMNS = ["Reference", "Result reproduced", "Receipt"]
_TEST_ID = re.compile(r"test_\w+\.py::\w+(?:::\w+)*")
_STATED_COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
_STATED_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RESULT_HEADING = re.compile(r"^#+\s*(?:result|verdict|summary)\b", re.IGNORECASE)
#: The Read the Docs version the dashboard links: the newest build of the default branch.
DOCS_VERSION_PATH = "en/latest/"
#: The dashboard's name for each replication verdict in the record; the record keeps its own words.
VERDICT_LABELS = {"reproduces": "reproduced", "partial": "mixed", "does_not": "failed"}
#: The allowed paper verdicts for a replication. Every current replication targets no paper
#: claim, so each reads "not applicable"; a replication that does target one keeps the field
#: and takes one of the other values.
PAPER_VERDICTS = ("not applicable", "reproduces", "partial", "does_not")
#: The library verdicts the frozen-register coverage computes: every listed function covered,
#: some covered, none covered.
LIBRARY_VERDICTS = ("verified", "partial", "unverified")
#: Entries whose methods verdict is narrower than the record's verdict, by entry id. The
#: replication's own note already states the narrower scope and is kept as the reason.
METHODS_NARROWER = {"glo_s1_allunits": "partial"}
#: A roadmap row is a validation when its theme cell ends with this tag; the tag is left off the
#: theme the dashboard shows.
VALIDATION_TAG = "(validation)"


def _rel(path: Path) -> str:
    """The path relative to the repository; a path outside it is kept as given."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _present(*paths: Path) -> list[str]:
    return [_rel(path) for path in paths if path.is_file()]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _note(message: str) -> None:
    print(f"note: {message}", file=sys.stderr)


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def generated_section() -> dict:
    commit = _git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"HEAD is not a full commit id: {commit!r}")
    committed = datetime.fromisoformat(_git("show", "-s", "--format=%cI", commit))
    return {"commit": commit,
            "date": committed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def parse_changelog(path: Path) -> list[dict]:
    """``releases`` from a CHANGELOG, newest first, ``[Unreleased]`` left out.

    A top-level ``- `` bullet is an entry of the ``### Kind`` subsection it sits in. Lines
    indented under it, and unindented lines directly after it, belong to it; an unindented line
    after a blank line ends it.
    """
    releases: list[dict] = []
    release: dict | None = None
    kind: str | None = None
    bullet: list[str] | None = None
    after_blank = False

    def close_bullet() -> None:
        nonlocal bullet
        if bullet is None:
            return
        while bullet and not bullet[-1]:
            bullet.pop()
        release["entries"].append({"kind": kind, "text": "\n".join(bullet)})
        bullet = None

    for number, raw in enumerate(_read(path).splitlines(), 1):
        line = raw.rstrip()
        if line.startswith("## "):
            close_bullet()
            kind = None
            match = _VERSION_LINE.match(line)
            if match is None or match["version"] == "Unreleased":
                release = None
                continue
            if match["date"] is None:
                raise ValueError(f"{_rel(path)}:{number}: release {match['version']} has no date")
            release = {"version": match["version"], "date": match["date"], "counts": {},
                       "entries": []}
            releases.append(release)
        elif release is None:
            continue
        elif line.startswith("### "):
            close_bullet()
            kind = line[4:].strip()
        elif line.startswith("- "):
            close_bullet()
            if kind is None:
                raise ValueError(f"{_rel(path)}:{number}: a bullet sits outside any ### subsection")
            bullet = [line[2:]]
            after_blank = False
        elif bullet is None:
            continue
        elif not line:
            bullet.append("")
            after_blank = True
        elif after_blank and not line[0].isspace():
            close_bullet()
        else:
            bullet.append(line)
            after_blank = False
    close_bullet()
    for release in releases:
        release["counts"] = dict(Counter(entry["kind"] for entry in release["entries"]))
    return releases


def docs_base() -> str | None:
    """The Read the Docs address pages hang from. The bare host redirects only its root; every
    other page lives under a version path, so a link built on the host is a 404."""
    url = tomllib.loads(_read(PYPROJECT))["project"].get("urls", {}).get("Documentation")
    if url is None:
        return None
    url = url.rstrip("/") + "/"
    return url if "/en/" in url else url + DOCS_VERSION_PATH


def release_section(releases: list[dict]) -> dict:
    project = tomllib.loads(_read(PYPROJECT))
    attr = project["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    if attr != "jnwb.__version__":
        raise RuntimeError(f"pyproject reads its version from {attr}, not jnwb.__version__")
    match = _INIT_VERSION.search(_read(INIT_PATH))
    if match is None:
        raise RuntimeError(f"no __version__ literal in {_rel(INIT_PATH)}")
    version = match.group(1)
    dated = [r["date"] for r in releases if r["version"] == version]
    if not dated:
        raise RuntimeError(f"{_rel(CHANGELOG)} has no section for version {version}")
    name = project["project"]["name"]
    urls = project["project"].get("urls", {})
    links = {"pypi": f"https://pypi.org/project/{name}/{version}/"}
    if docs_base() is not None:
        links["docs"] = docs_base()
    if "Homepage" in urls:
        links["repo"] = urls["Homepage"]
        links["changelog"] = f"{urls['Homepage']}/blob/main/CHANGELOG.md"
    return {"version": version, "date": dated[0],
            "python": [c for c in project["project"]["classifiers"]
                       if c.startswith("Programming Language :: Python :: ")],
            "links": links}


def _as_leg(entry: dict) -> dict:
    """A workflow matrix entry, with its ``python-version`` key spelled as the schema spells it."""
    return {("python" if key == "python-version" else key): value
            for key, value in entry.items()}


def ci_section() -> dict | None:
    if not WORKFLOW.is_file():
        _note(f"{_rel(WORKFLOW)} is missing; ci is null")
        return None
    jobs = yaml.safe_load(_read(WORKFLOW))["jobs"]
    matrix = jobs["test"]["strategy"]["matrix"]
    legs = [{"os": os_name, "python": py}
            for os_name in matrix["os"] for py in matrix["python-version"]]
    excluded = [_as_leg(entry) for entry in matrix.get("exclude", [])]
    legs = [leg for leg in legs
            if not any(all(leg.get(k) == v for k, v in ex.items()) for ex in excluded)]
    for extra in matrix.get("include", []):
        entry = _as_leg(extra)
        base = {k: v for k, v in entry.items() if k in ("os", "python")}
        extras = [f"{k}: {v}" for k, v in entry.items() if k not in base]
        hits = [leg for leg in legs if all(leg.get(k) == v for k, v in base.items())]
        if not hits:
            legs.append({**base, "note": "; ".join(extras)} if extras else base)
        elif extras:
            for leg in hits:
                leg["note"] = "; ".join(filter(None, [leg.get("note"), *extras]))
    floors = jobs["test-floors"]
    legs.append({"os": floors["runs-on"], "python": floors["env"]["FLOOR_PYTHON"],
                 "note": "dependency floors"})
    return {"legs": legs}


def api_section() -> dict | None:
    # Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
    if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
    elif str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        import jnwb
    except ImportError as exc:
        _note(f"jnwb cannot be imported ({exc}); api is null")
        return None
    from jnwb._lazy_exports import EXPORT_MODULES, OPTIONAL_SUBMODULES

    # A symbol joins the group of the module EXPORT_MODULES names for it, written jnwb.<module>;
    # a symbol it does not name joins the package's own group. ``extra`` is the optional extra
    # OPTIONAL_SUBMODULES records for that module, else null.
    symbols = list(jnwb.__all__)
    groups: dict[str, dict] = {}
    for name in symbols:
        short = EXPORT_MODULES.get(name)
        module = f"jnwb.{short}" if short else "jnwb"
        group = groups.setdefault(module, {"module": module,
                                           "extra": OPTIONAL_SUBMODULES.get(short),
                                           "symbols": []})
        group["symbols"].append(name)
    return {"total": len(symbols), "groups": list(groups.values())}


def verified_section() -> dict | None:
    if not FROZEN.is_file():
        _note(f"{_rel(FROZEN)} is missing; verified is null")
        return None
    record = json.loads(_read(FROZEN))
    # killed_by names the tests that fail when a function's behaviour changes: the schema's tests.
    return {"functions": [{"file": f["file"], "qualname": f["qualname"],
                           "verified_at": f["verified_at"], "tests": list(f["killed_by"])}
                          for f in record["functions"]]}


def performance_section() -> dict | None:
    section: dict = {}
    if BASELINE.is_file():
        record = json.loads(_read(BASELINE))
        # The record's "_provenance" entry is metadata, not a benchmark.
        section["baseline"] = [{"name": name, "time_ms": row["time_ms"], "peak_mb": row["peak_mb"],
                                "scale": row["scale"]}
                               for name, row in record.items() if not name.startswith("_")]
    else:
        _note(f"{_rel(BASELINE)} is missing; baseline is left out")
    if PEAK_MEMORY.is_file():
        record = json.loads(_read(PEAK_MEMORY))
        record["operations"] = [{"name": name, **{k: row[k] for k in
                                                  ("peak_mib", "added_mib", "added_is")}}
                                for name, row in record["operations"].items()]
        section["peak_memory"] = record
    else:
        _note(f"{_rel(PEAK_MEMORY)} is missing; peak_memory is left out")
    if IMPORT_BREAKDOWN.is_file():
        section["import"] = json.loads(_read(IMPORT_BREAKDOWN))
    else:
        _note(f"{_rel(IMPORT_BREAKDOWN)} is missing; import is left out")
    return section or None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]


def _first_url(text: str) -> str | None:
    """The first Markdown link target in ``text`` that is an http(s) URL, parentheses balanced."""
    start = text.find("](")
    while start != -1:
        depth, end = 1, start + 2
        while end < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            end += 1
        if depth == 0:
            target = text[start + 2:end - 1]
            if target.startswith(("http://", "https://")):
                return target
        start = text.find("](", start + 2)
    return None


def references_section() -> list[dict] | None:
    """Rows of the method tables (header Reference | Result implemented | Functions).

    The pitfalls table and the bullet lists (books, NWB papers, software links) are not rows of
    those tables and are left out.
    """
    if not REFERENCES.is_file():
        _note(f"{_rel(REFERENCES)} is missing; references is null")
        return None
    rows: list[dict] = []
    in_method_table = False
    for raw in _read(REFERENCES).splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            in_method_table = False
            continue
        cells = _cells(line)
        if cells == _METHOD_COLUMNS:
            in_method_table = True
        elif in_method_table and not all(_RULE_CELL.fullmatch(c) for c in cells):
            rows.append({"text": cells[0], "url": _first_url(cells[0])})
    return rows


def order_section() -> list[dict] | None:
    """One row per data row of each measured-order table, in file order.

    ``export`` is the spec cell without backticks, ``order`` the achieved cell, and ``evidence``
    the parameter with its measured exponent and admissible order. ``module`` is the ``jnwb.x``
    heading above the table; a table under no such heading has none.
    """
    if not ORDER_RECORD.is_file():
        _note(f"{_rel(ORDER_RECORD)} is missing; order is null")
        return None
    rows: list[dict] = []
    module: str | None = None
    columns: list[str] | None = None
    separator_next = False
    for raw in _read(ORDER_RECORD).splitlines():
        line = raw.strip()
        if line.startswith("#"):
            heading = _MODULE_HEADING.match(line)
            module = heading.group(1) if heading else None
            columns = None
            continue
        if not line.startswith("|"):
            columns = None
            continue
        cells = _cells(line)
        if columns is None:
            if cells == _ORDER_COLUMNS:
                columns = cells
                separator_next = True
            continue
        if separator_next:
            separator_next = False
            continue
        if len(cells) != len(columns):
            raise ValueError(f"{_rel(ORDER_RECORD)}: a row has {len(cells)} cells, not "
                             f"{len(columns)}: {line[:60]!r}")
        row = dict(zip(columns, cells))
        entry = {"export": row["spec"].replace("`", ""), "order": row["achieved"],
                 "evidence": (f"{row['parameter']}: exponent {row['exp']}, "
                              f"admissible {row['admissible']}")}
        if module is not None:
            entry["module"] = module
        rows.append(entry)
    return rows


def _explaining_page(light_name: str) -> Path | None:
    """The first docs page, in name order, that embeds the figure. The landing page links several
    figures without explaining them, so it is not searched."""
    for page in sorted(DOCS.glob("*.md")):
        if page.name != "index.md" and light_name in _read(page):
            return page
    return None


def figures_section() -> list[dict]:
    if not FIGURES.is_dir():
        raise FileNotFoundError(f"{_rel(FIGURES)} is missing; figures cannot be null")
    pairs: list[dict] = []
    base = docs_base()
    for light in sorted(FIGURES.glob("*.png")):
        if light.name.endswith(".dark.png"):
            continue
        dark = FIGURES / f"{light.stem}.dark.png"
        if not dark.is_file():
            _note(f"{light.name} has no dark twin; left out")
            continue
        page = _explaining_page(light.name)
        pairs.append({"id": light.stem, "title": light.stem, "light": f"assets/{light.name}",
                      "dark": f"assets/{dark.name}",
                      "docs_page": f"{base}{page.stem}/" if page and base else None})
    return pairs


def _showcase_figures() -> Path:
    """The figures beside the record: artifacts/showcases/openscope_glo/figures/."""
    return SHOWCASE_RECORD.with_suffix("") / "figures"


def _copy_showcase_figures(showcases: dict, out: Path) -> None:
    """Copies each entry's light and dark figure to assets/showcases/ beside the page."""
    target = out / "assets" / "showcases"
    target.mkdir(parents=True, exist_ok=True)
    for entry in showcases["entries"]:
        for figure in entry["figures"]:
            for key in ("light", "dark"):
                name = Path(figure[key]).name
                shutil.copy2(_showcase_figures() / name, target / name)


def _frozen_function_names() -> set[str]:
    """Every name the frozen register covers: each qualname and each public name one serves."""
    if not FROZEN.is_file():
        raise ValueError(f"{_rel(FROZEN)} is missing; the library verdicts cannot be computed")
    names = set()
    for func in json.loads(_read(FROZEN))["functions"]:
        names.add(func["qualname"])
        names.add(func["qualname"].split(".")[-1])
        for served in func.get("serves", []):
            names.add(served)
            names.add(served.split(".")[-1])
    return names


def _library_verdict(functions: list, covered: set[str]) -> dict:
    """The library verdict for the functions a replication lists as used.

    ``verified`` when the register covers every one, ``partial`` when it covers some,
    ``unverified`` when it covers none. A name the register cannot resolve counts as not
    covered and is listed.
    """
    uncovered = [name for name in functions if name not in covered]
    if functions and not uncovered:
        verdict = "verified"
    elif len(functions) != len(uncovered):
        verdict = "partial"
    else:
        verdict = "unverified"
    assert verdict in LIBRARY_VERDICTS
    return {"verdict": verdict, "uncovered": uncovered}


def showcases_section() -> dict | None:
    """The showcase record, its figure paths relative to the built site; null while none exists.

    Refuses, naming the entry: a figure without its dark twin, a verified entry without a
    reproducing replication that carries a report digest, a replication without a verdict, a
    verdict without a dashboard label, an entry stating no relation to the paper, an entry
    listing no functions, an asset without its SHA-256. Each replication keeps its record
    verdict and label and gains ``paper`` (the entry's stated relation to the paper),
    ``library`` (the frozen-register coverage of the functions the entry lists) and ``methods``
    (the record's verdict, or the narrower one METHODS_NARROWER names). The data schema holds
    the rest of the shape.
    """
    if not SHOWCASE_RECORD.is_file():
        return None
    record = json.loads(_read(SHOWCASE_RECORD))
    covered = _frozen_function_names()
    where = SHOWCASE_RECORD.name
    figures_dir = _showcase_figures()
    for entry in record["entries"]:
        ident = entry["id"]
        for figure in entry["figures"]:
            light, dark = figure.get("light"), figure.get("dark")
            if not dark or not (figures_dir / dark).is_file():
                raise ValueError(f"{where}: entry {ident!r} has a figure without its dark twin "
                                 f"(light {light!r}, dark {dark!r})")
            if not light or not (figures_dir / light).is_file():
                raise ValueError(f"{where}: entry {ident!r} has no light figure {light!r}")
        reproduced = any(r.get("verdict") == "reproduces" and r.get("report_sha256")
                         for r in entry["replications"])
        if entry["status"] == "verified" and not reproduced:
            raise ValueError(f"{where}: entry {ident!r} is verified but has no reproducing "
                             "replication with a report_sha256")
        relation = entry.get("relation_to_published")
        if not relation:
            raise ValueError(f"{where}: entry {ident!r} states no relation to the paper")
        functions = entry.get("jnwb", {}).get("functions")
        if not functions:
            raise ValueError(f"{where}: entry {ident!r} lists no functions")
        for row in entry["replications"]:
            if "verdict" not in row:
                raise ValueError(f"{where}: entry {ident!r} has a replication without a verdict")
            if row["verdict"] not in VERDICT_LABELS:
                raise ValueError(f"{where}: entry {ident!r} has verdict {row['verdict']!r}, "
                                 "which has no dashboard label")
            row["label"] = VERDICT_LABELS[row["verdict"]]
            methods = METHODS_NARROWER.get(ident, row["verdict"])
            if methods not in VERDICT_LABELS:
                raise ValueError(f"{where}: entry {ident!r} has methods verdict {methods!r}, "
                                 "which has no dashboard label")
            row["methods"] = {"verdict": methods}
            if ident in METHODS_NARROWER:
                row["methods"]["reason"] = row["note"]
            paper = {"verdict": "not applicable", "reason": relation}
            if paper["verdict"] not in PAPER_VERDICTS:
                raise ValueError(f"{where}: entry {ident!r} has paper verdict "
                                 f"{paper['verdict']!r}, which the vocabulary does not allow")
            row["paper"] = paper
            row["library"] = _library_verdict(functions, covered)
        for asset in entry["dandi"]["assets"]:
            if not asset.get("sha256"):
                raise ValueError(f"{where}: entry {ident!r} asset {asset.get('asset_id')!r} "
                                 "has no sha256")
    for entry in record["entries"]:
        for figure in entry["figures"]:
            for key in ("light", "dark"):
                figure[key] = f"assets/showcases/{figure[key]}"
    return record


def deferred_section() -> list[dict] | None:
    """The roadmap rows that are validations, each read as not started. A row is one when its
    theme cell ends with the validation tag, and the tag is left off the theme returned; a deferred
    row without the tag is left out. Null while the roadmap is absent."""
    if not ROADMAP.is_file():
        _note(f"{_rel(ROADMAP)} is missing; deferred is null")
        return None
    rows: list[dict] = []
    for raw in _read(ROADMAP).splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != 5 or not cells[4].startswith("deferred-"):
            continue
        if not cells[1].endswith(VALIDATION_TAG):
            continue
        theme = cells[1][:-len(VALIDATION_TAG)].rstrip()
        rows.append({"id": cells[0], "theme": theme, "defect": cells[2], "waits": cells[3],
                     "release": cells[4], "label": "not started"})
    return rows


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked(rel: str) -> bool:
    proc = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=False)
    return proc.returncode == 0


def _uncommitted(rel: str) -> bool:
    """True when the file differs from HEAD, so its bytes are not the committed ones."""
    proc = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=False)
    return proc.returncode != 0


def _receipt(path: Path, card: str) -> str:
    """The repository-relative path of a file a card reads. Refused before anything is read: a
    path outside the repository, a missing file, a file git does not track, and a tracked file
    with uncommitted changes."""
    resolved = path.resolve()
    if REPO_ROOT not in resolved.parents:
        raise ValueError(f"validations: {path} is outside REPO_ROOT")
    rel = resolved.relative_to(REPO_ROOT).as_posix()
    if not resolved.is_file():
        raise FileNotFoundError(f"validations: {rel} is missing; {card} cannot be built")
    if not _tracked(rel):
        raise RuntimeError(f"validations: {rel} is not tracked by git")
    if _uncommitted(rel):
        raise RuntimeError(f"validations: {rel} has uncommitted changes")
    return rel


def _record(path: Path, card: str) -> dict:
    """A JSON receipt, read once :func:`_receipt` has accepted its path."""
    _receipt(path, card)
    return json.loads(_read(path))


def _card(card: str, section: str, path: Path, title: str, fields: dict,
          recorded_commit: str | None = None) -> dict:
    """One card: the receipt's path, the commit that last changed it, its SHA-256 and the fields
    read from it. ``recorded_commit`` is the commit the receipt itself states, when it states one."""
    rel = _receipt(path, card)
    commit = _git("log", "-1", "--format=%H", "--", rel)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"validations: {rel} has no commit in git history: {commit!r}")
    entry = {"id": card, "section": section, "title": title, "path": rel, "commit": commit,
             "sha256": _digest(path), "fields": fields, "html": None}
    if recorded_commit is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", recorded_commit):
            raise ValueError(f"validations: {rel} states no 40-digit commit: {recorded_commit!r}")
        entry["recorded_commit"] = recorded_commit
    return entry


def _title_line(text: str) -> str | None:
    """The text of the first ``# `` heading, or None."""
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), None)


def _result_summary(text: str) -> str | None:
    """The first bullet under a heading that begins Result, Verdict or Summary, or None."""
    under = False
    for line in text.splitlines():
        if line.startswith("#"):
            under = _RESULT_HEADING.match(line) is not None
        elif under and line.startswith("- "):
            return line[2:].strip()
    return None


def _calibration_fields(text: str) -> dict:
    """What a calibration receipt states: a commit or a date written out in it, and the first
    bullet under its Result heading. A field the receipt does not state is left out."""
    fields: dict = {}
    commit = _STATED_COMMIT.search(text)
    if commit:
        fields["stated_commit"] = commit.group(0)
    date = _STATED_DATE.search(text)
    if date:
        fields["stated_date"] = date.group(0)
    summary = _result_summary(text)
    if summary is not None:
        fields["summary"] = summary
    return fields


def _calibration_card(path: Path) -> dict:
    rel = _receipt(path, path.stem)
    text = _read(path)
    title = _title_line(text)
    if title is None:
        raise ValueError(f"validations: {rel} has no title line")
    return _card(path.stem, "calibration", path, title, _calibration_fields(text))


def _performance_cards() -> list[dict]:
    baseline = _record(BASELINE, "baseline_performance")
    peak = _record(PEAK_MEMORY, "peak_memory")
    imports = _record(IMPORT_BREAKDOWN, "import_breakdown")
    return [
        _card("baseline_performance", "performance", BASELINE, "Baseline timings",
              {"rows": sum(not name.startswith("_") for name in baseline)}),
        _card("peak_memory", "performance", PEAK_MEMORY, "Peak memory",
              {"operations": len(peak["operations"])}, recorded_commit=peak.get("commit")),
        _card("import_breakdown", "performance", IMPORT_BREAKDOWN, "Import cost",
              {"version": imports["version"], "python": imports["python"],
               "warm_median_ms": round(imports["warm_median_ms"]), "runs": imports["runs"]}),
    ]


def _frozen_card() -> dict:
    record = _record(FROZEN, "frozen_validated")
    return _card("frozen_validated", "frozen", FROZEN, "Independently verified functions",
                 {"functions": len(record["functions"])})


def _study_cards() -> list[dict]:
    """One card per studies row. Each card's digest is that of the whole references page, which
    holds the row."""
    _receipt(REFERENCES, "studies")
    rows, in_table = [], False
    for raw in _read(REFERENCES).splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            in_table = False
            continue
        cells = _cells(line)
        if cells == _STUDY_COLUMNS:
            in_table = True
        elif in_table and not all(_RULE_CELL.fullmatch(c) for c in cells):
            if len(cells) != len(_STUDY_COLUMNS):
                raise ValueError(f"{_rel(REFERENCES)}: a studies row has {len(cells)} cells, not "
                                 f"{len(_STUDY_COLUMNS)}: {line[:60]!r}")
            rows.append(cells)
    if not rows:
        raise ValueError(f"{_rel(REFERENCES)} has no studies table rows")
    return [_card(f"studies-{number}", "studies", REFERENCES, cells[0],
                  {"result": cells[1], "tests": _TEST_ID.findall(cells[2])})
            for number, cells in enumerate(rows, 1)]


def _closure_card() -> dict:
    _receipt(CLOSURE_RECEIPT, "blocker_fixpoint_receipt")
    commit, blockers = blocker_fixpoint_receipt(REPO_ROOT)
    if commit is None or blockers is None:
        raise ValueError(f"validations: {_rel(CLOSURE_RECEIPT)} states no commit or no blocker "
                         "count")
    title = _title_line(_read(CLOSURE_RECEIPT))
    if title is None:
        raise ValueError(f"validations: {_rel(CLOSURE_RECEIPT)} has no title line")
    return _card("blocker_fixpoint_receipt", "closure", CLOSURE_RECEIPT, title,
                 {"new_blockers": blockers}, recorded_commit=commit)


def _validation_html() -> list[Path]:
    """The HTML outputs in docs/assets/validations/; an empty or missing directory gives none."""
    if not VALIDATION_HTML.is_dir():
        return []
    return sorted(VALIDATION_HTML.glob("*.html"))


def validations_section() -> list[dict]:
    """The validation cards, in section order. An HTML output named for a card's id is linked
    from that card."""
    cards = [*(_calibration_card(path) for path in CALIBRATION_RECEIPTS),
             *_performance_cards(), _frozen_card(), *_study_cards(), _closure_card()]
    for card in cards:
        name = f"{card['id']}.html"
        if (VALIDATION_HTML / name).is_file():
            card["html"] = f"assets/validations/{name}"
    return cards


def _copy_validation_figures(out: Path) -> None:
    """Copies each HTML output to assets/validations/ beside the page."""
    files = _validation_html()
    if not files:
        return
    target = out / "assets" / "validations"
    target.mkdir(parents=True, exist_ok=True)
    for source in files:
        shutil.copy2(source, target / source.name)


def verify_validations(out_dir: Path) -> list[str]:
    """One message per card in a built site's data.json whose receipt is missing, untracked, has
    uncommitted changes or lies outside the repository, or whose bytes no longer match the
    recorded digest. [] when every card holds."""
    cards = json.loads(_read(out_dir / "data.json"))["validations"]
    messages = []
    for card in cards:
        rel = card["path"]
        path = (REPO_ROOT / rel).resolve()
        if REPO_ROOT not in path.parents:
            messages.append(f"validations: {rel} is outside REPO_ROOT")
        elif not path.is_file():
            messages.append(f"validations: {rel} is missing")
        elif not _tracked(rel):
            messages.append(f"validations: {rel} is not tracked by git")
        elif _uncommitted(rel):
            messages.append(f"validations: {rel} has uncommitted changes")
        else:
            actual = _digest(path)
            if actual != card["sha256"]:
                messages.append(f"validations: {rel} digest {actual} != recorded "
                                f"{card['sha256']}")
    return messages


def build_data() -> dict:
    """The data.json object. A section whose source is absent is null, as its docstring says."""
    releases = parse_changelog(CHANGELOG)
    ci = ci_section()
    api = api_section()
    verified = verified_section()
    performance = performance_section()
    references = references_section()
    order = order_section()
    figures = figures_section()
    showcases = showcases_section()
    validations = validations_section()
    deferred = deferred_section()
    pages = sorted({_rel(page) for figure in figures
                    if (page := _explaining_page(Path(figure["light"]).name))})
    sources = {
        "generated": [".git"],
        "release": _present(PYPROJECT, INIT_PATH, CHANGELOG),
        "releases": _present(CHANGELOG),
        "ci": _present(WORKFLOW) if ci else [],
        "api": _present(INIT_PATH) if api else [],
        "verified": _present(FROZEN) if verified else [],
        "performance": _present(BASELINE, PEAK_MEMORY, IMPORT_BREAKDOWN) if performance else [],
        "order": _present(ORDER_RECORD) if order is not None else [],
        "references": _present(REFERENCES) if references is not None else [],
        "figures": [_rel(FIGURES), *pages],
        "showcases": _present(SHOWCASE_RECORD) if showcases else [],
        "validations": list(dict.fromkeys(card["path"] for card in validations)),
        "deferred": _present(ROADMAP) if deferred is not None else [],
    }
    return {
        "generated": generated_section(),
        "sources": sources,
        "release": release_section(releases),
        "releases": releases,
        "ci": ci,
        "api": api,
        "verified": verified,
        "performance": performance,
        "order": order,
        "references": references,
        "figures": figures,
        "showcases": showcases,
        "validations": validations,
        "deferred": deferred,
    }


def write_dashboard(out: Path) -> dict:
    resolved = out.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError(f"--out {out} is inside the repository {REPO_ROOT}; write the dashboard "
                         "outside it")
    data = build_data()
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "data.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (out / "assets").mkdir(exist_ok=True)
    for name in ("favicon.png", "jnwb-logo.png"):
        shutil.copy2(ASSETS / name, out / "assets" / name)
    for figure in data["figures"]:
        for key in ("light", "dark"):
            name = Path(figure[key]).name
            shutil.copy2(FIGURES / name, out / "assets" / name)
    if data["showcases"]:
        _copy_showcase_figures(data["showcases"], out)
    _copy_validation_figures(out)
    shutil.copy2(TEMPLATE_PATH, out / "index.html")
    if APP_PATH.is_file():
        shutil.copy2(APP_PATH, out / "app.js")
    return data


def _size(name: str, value) -> str:
    if value is None:
        return "null"
    if name == "releases":
        return (f"{len(value)} releases, "
                f"{sum(len(r['entries']) for r in value)} entries")
    if name == "ci":
        return f"{len(value['legs'])} legs"
    if name == "api":
        return f"{value['total']} symbols in {len(value['groups'])} group"
    if name == "verified":
        return f"{len(value['functions'])} functions"
    if name == "performance":
        peak = value.get("peak_memory", {}).get("operations", [])
        return (f"{len(value.get('baseline', []))} baseline rows, {len(peak)} peak-memory "
                f"operations, import {'present' if 'import' in value else 'absent'}")
    if name == "references":
        return f"{len(value)} rows"
    if name == "figures":
        return f"{len(value)} pairs"
    if name == "order":
        return f"{len(value)} rows"
    if name == "showcases":
        return f"{len(value['entries'])} entries"
    if name == "validations":
        return f"{len(value)} cards"
    if name == "deferred":
        return f"{len(value)} rows"
    return "present"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path,
                        help="directory to write data.json and the page into")
    args = parser.parse_args(argv)
    data = write_dashboard(args.out)
    print(f"wrote {args.out / 'data.json'} ({(args.out / 'data.json').stat().st_size} bytes)")
    for name in SECTIONS:
        print(f"  {name:<12} {_size(name, data[name])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
