"""The dashboard data builder: its output validates against the data contract, its counts agree
with the entries they count, its API total is the imported package's and its groups cover it
exactly once, its order rows are the measured tables' rows, its peak-memory rows are the
record's, a CHANGELOG parses to the counts it holds, and an output directory inside the
repository is refused before anything is written."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import jnwb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

SCHEMA_PATH = REPO_ROOT / "scripts" / "dashboard" / "data.schema.json"
PEAK_MEMORY_PATH = REPO_ROOT / "artifacts" / "benchmarks" / "performance" / "peak_memory.json"
ORDER_RECORD_PATH = REPO_ROOT / "artifacts" / "evidence" / "0.2.6" / "computational_order.md"
SHOWCASE_RECORD_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "showcase_record.json"
DASHBOARD_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "dashboard_data.json"
PNG_BYTES = b"\x89PNG\r\n\x1a\n"  # the build copies figures; it never decodes them
ORDER_HEADER = ("| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved "
                "| admissible | cls | gap |")

# Two released sections and an [Unreleased] one that must be left out. The first release repeats
# a subsection heading, so its counts add both blocks. The paragraph ends a list and is no entry.
CHANGELOG_FIXTURE = """# Changelog

## [Unreleased]

### Added

- Not released yet.

## [0.3.0] - 2026-02-02

### Added

- First entry with a
  continuation line.
  - nested detail
- Second entry.

### Fixed

- A fix.

### Fixed

- A second fix under the same heading.

## [0.2.0] - 2026-01-01

### Changed

- Old change.

A paragraph after the list, not part of any bullet.

- Bullet after paragraph.
"""


def _builder():
    return importlib.import_module("scripts.build_dashboard")


def _measured_order_rows_on_disk() -> int:
    """Data rows under every measured-order table header, counted from the record alone."""
    rows = 0
    under_header = False
    separator_next = False
    for raw in ORDER_RECORD_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == ORDER_HEADER:
            under_header = separator_next = True
        elif not under_header:
            continue
        elif separator_next:
            separator_next = False
        elif line.startswith("|"):
            rows += 1
        else:
            under_header = False
    return rows


@pytest.fixture(scope="module")
def data():
    return _builder().build_data()


def test_output_validates_against_the_schema(data):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        missing = [key for key in schema["required"] if key not in data]
        assert not missing, f"required keys absent: {missing}"
    else:
        jsonschema.validate(data, schema)


def test_release_counts_equal_entries_per_kind(data):
    assert data["releases"], "fixture must have releases"
    for release in data["releases"]:
        per_kind = dict(Counter(entry["kind"] for entry in release["entries"]))
        assert release["counts"] == per_kind, release["version"]


def test_docs_links_carry_the_read_the_docs_version_path(data):
    """The bare Read the Docs host serves only its root; a page link built on it, or relative to
    the dashboard, is a 404."""
    docs = data["release"]["links"]["docs"]
    assert docs.startswith("https://") and "/en/" in docs, docs
    pages = [f["docs_page"] for f in data["figures"] if f["docs_page"]]
    assert pages, "fixture must link at least one figure to its page"
    assert all(page.startswith(docs) and page.endswith("/") for page in pages), pages


def test_every_source_is_a_path_in_the_repository(data):
    sources = [path for paths in data["sources"].values() for path in paths]
    assert any(path.startswith("docs/") and path.endswith(".md") for path in sources), \
        "fixture must name a docs page among its sources"
    missing = [path for path in sources if not (REPO_ROOT / path).exists()]
    assert not missing, missing


def test_api_total_is_len_of_all(data):
    assert data["api"]["total"] > 0, "fixture must export symbols"
    assert data["api"]["total"] == len(jnwb.__all__)


def test_peak_memory_operations_equal_the_record(data):
    record = json.loads(PEAK_MEMORY_PATH.read_text(encoding="utf-8"))
    expected = [
        (name, row["peak_mib"], row["added_mib"], row["added_is"])
        for name, row in record["operations"].items()
    ]
    assert expected, "the record must hold operations"
    actual = [
        (op["name"], op["peak_mib"], op["added_mib"], op["added_is"])
        for op in data["performance"]["peak_memory"]["operations"]
    ]
    assert actual == expected


def test_changelog_fixture_parses_to_known_counts(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG_FIXTURE, encoding="utf-8", newline="\n")
    releases = _builder().parse_changelog(path)
    assert [r["version"] for r in releases] == ["0.3.0", "0.2.0"]
    assert releases[0]["counts"] == {"Added": 2, "Fixed": 2}
    assert releases[1]["counts"] == {"Changed": 2}
    assert [e["text"] for e in releases[0]["entries"]] == [
        "First entry with a\n  continuation line.\n  - nested detail",
        "Second entry.",
        "A fix.",
        "A second fix under the same heading.",
    ]
    assert [e["text"] for e in releases[1]["entries"]] == [
        "Old change.",
        "Bullet after paragraph.",
    ]


def test_order_has_one_row_per_measured_table_row(data):
    counted = _measured_order_rows_on_disk()
    assert counted > 0, "fixture must have measured-order tables"
    assert data["order"] is not None, "order must not be null while its record exists"
    assert len(data["order"]) == counted


def test_api_groups_cover_all_exactly_once(data):
    from jnwb._lazy_exports import EXPORT_MODULES

    groups = data["api"]["groups"]
    union = [name for group in groups for name in group["symbols"]]
    assert sorted(union) == sorted(jnwb.__all__)
    home = {name: group["module"] for group in groups for name in group["symbols"]}
    mapped = {name: module for name, module in EXPORT_MODULES.items() if name in home}
    assert mapped, "fixture must map some exports"
    assert len({home[name] for name in mapped}) > 1, "grouping must split the exports"
    for name, module in mapped.items():
        assert home[name] == f"jnwb.{module}", name


def test_out_inside_the_repository_is_refused():
    inside = REPO_ROOT / "_refused_dashboard_out"
    with pytest.raises(ValueError) as info:
        _builder().main(["--out", str(inside)])
    assert "_refused_dashboard_out" in str(info.value)
    assert not inside.exists()


# ---- showcase record ----------------------------------------------------------------------

def _record():
    return json.loads(SHOWCASE_RECORD_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def point_at(tmp_path, monkeypatch):
    """Points the builder at a record written to a temporary directory, its figures beside it."""
    builder = _builder()
    figures = tmp_path / "openscope_glo" / "figures"
    figures.mkdir(parents=True)
    for name in ("fixture_light.png", "fixture_dark.png"):
        (figures / name).write_bytes(PNG_BYTES)

    def point(record):
        path = tmp_path / "openscope_glo.json"
        path.write_text(json.dumps(record), encoding="utf-8", newline="\n")
        monkeypatch.setattr(builder, "SHOWCASE_RECORD", path, raising=False)
        return path

    return point


@pytest.mark.parametrize("dark", [None, "absent_dark.png"], ids=["null", "no-file"])
def test_a_figure_without_its_dark_twin_is_refused(point_at, dark):
    record = _record()
    record["entries"][0]["figures"][0]["dark"] = dark
    point_at(record)
    with pytest.raises(ValueError) as info:
        _builder().build_data()
    assert "fixture_entry" in str(info.value)
    assert "dark" in str(info.value)


@pytest.mark.parametrize("case", ["no-replication", "no-reproduces", "null-digest"])
def test_a_verified_entry_without_a_reproducing_replication_is_refused(point_at, case):
    record = _record()
    entry = record["entries"][0]
    assert entry["status"] == "verified", "the fixture entry must be verified"
    reproducing = [r for r in entry["replications"] if r["verdict"] == "reproduces"]
    assert reproducing, "the fixture must hold a reproducing replication"
    if case == "no-replication":
        entry["replications"] = []
    elif case == "no-reproduces":
        entry["replications"] = [r for r in entry["replications"] if r["verdict"] != "reproduces"]
    else:
        reproducing[0]["report_sha256"] = None
    point_at(record)
    with pytest.raises(ValueError) as info:
        _builder().build_data()
    assert "fixture_entry" in str(info.value)
    assert "reproducing replication" in str(info.value)


def test_an_asset_without_a_sha256_is_refused(point_at):
    record = _record()
    asset = record["entries"][0]["dandi"]["assets"][0]
    assert "sha256" in asset, "the fixture asset must carry a digest before it is removed"
    del asset["sha256"]
    point_at(record)
    with pytest.raises(ValueError) as info:
        _builder().build_data()
    assert "fixture_entry" in str(info.value)
    assert asset["asset_id"] in str(info.value)


def test_showcases_is_null_while_no_record_exists(tmp_path, monkeypatch):
    builder = _builder()
    monkeypatch.setattr(builder, "SHOWCASE_RECORD", tmp_path / "no_record.json", raising=False)
    assert builder.build_data()["showcases"] is None


def test_a_records_figures_are_copied_beside_the_page(point_at, tmp_path):
    point_at(_record())
    builder = _builder()
    showcases = builder.showcases_section()
    figure = showcases["entries"][0]["figures"][0]
    assert figure["light"] == "assets/showcases/fixture_light.png"
    assert figure["dark"] == "assets/showcases/fixture_dark.png"
    builder._copy_showcase_figures(showcases, tmp_path / "site")
    for name in ("fixture_light.png", "fixture_dark.png"):
        assert (tmp_path / "site" / "assets" / "showcases" / name).read_bytes() == PNG_BYTES


def test_a_built_record_validates_against_the_schema(point_at):
    point_at(_record())
    data = _builder().build_data()
    assert data["showcases"] is not None, "the build must hold the record"
    errors = list(_validator().iter_errors(data))
    assert not errors, [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]


def test_the_schema_requires_showcases_and_the_fixtures_validate():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "showcases" in schema["required"], "showcases must be a required key"
    dashboard = json.loads(DASHBOARD_FIXTURE.read_text(encoding="utf-8"))
    record = _as_site_paths(json.loads(SHOWCASE_RECORD_FIXTURE.read_text(encoding="utf-8")))
    assert record["entries"], "the record fixture must hold an entry"
    assert dashboard["showcases"] == record, "the page fixture holds the record fixture's entry"
    errors = list(_validator().iter_errors(dashboard))
    assert not errors, [error.message for error in errors]


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _as_site_paths(record):
    """The record as data.json holds it: each figure file named under assets/showcases/."""
    for entry in record["entries"]:
        for figure in entry["figures"]:
            for key in ("light", "dark"):
                figure[key] = f"assets/showcases/{figure[key]}"
    return record


def _schema_errors(mutate):
    record = _as_site_paths(_record())
    mutate(record["entries"][0])
    dashboard = json.loads(DASHBOARD_FIXTURE.read_text(encoding="utf-8"))
    dashboard["showcases"] = record
    return list(_validator().iter_errors(dashboard))


def _add_unknown_field(entry):
    entry["extra"] = 1


def _species_human(entry):
    entry["species"] = "human"


def _figure_without_dark(entry):
    del entry["figures"][0]["dark"]


def _origin_missing(entry):
    del entry["origin"]


def _verdict_maybe(entry):
    entry["replications"][0]["verdict"] = "maybe"


def _no_replications(entry):
    entry["replications"] = []


def _partial_only(entry):
    entry["replications"] = [r for r in entry["replications"] if r["verdict"] != "reproduces"]


@pytest.mark.parametrize(
    "mutate, names",
    [(_add_unknown_field, "extra"), (_species_human, "species"), (_figure_without_dark, "dark"),
     (_origin_missing, "origin"), (_verdict_maybe, "verdict")],
    ids=["unknown-field", "species-human", "figure-no-dark", "origin-missing", "verdict-maybe"],
)
def test_the_schema_refuses_a_malformed_entry(mutate, names):
    errors = _schema_errors(mutate)
    assert any(names in e.message or names in [str(p) for p in e.absolute_path] for e in errors), (
        f"no schema error names {names!r}: {[e.message for e in errors]}")


@pytest.mark.parametrize("mutate", [_no_replications, _partial_only],
                         ids=["no-replication", "partial-only"])
def test_the_schema_rejects_a_verified_entry_without_a_reproducing_replication(mutate):
    errors = _schema_errors(mutate)
    assert any(e.validator == "contains" for e in errors), (
        f"no contains-rule error for the reproduction rule: {[e.message for e in errors]}")


@pytest.mark.parametrize("status", ["published", "exploratory"])
def test_the_schema_accepts_an_entry_with_no_replications_below_verified(status):
    def mutate(entry):
        entry["status"] = status
        entry["replications"] = []

    assert not _schema_errors(mutate), f"the schema rejected a {status} entry with no replications"


def test_the_fixture_entry_holds_one_reproducing_and_one_partial_replication():
    entry = _record()["entries"][0]
    assert sorted(r["verdict"] for r in entry["replications"]) == ["partial", "reproduces"]


def test_the_schema_accepts_the_unmutated_entry():
    """The control: without it, every refusal above could come from the shared setup."""
    assert not _schema_errors(lambda entry: None), "the control entry must validate"


# ---- validation cards ---------------------------------------------------------------------

CALIBRATION_DIR = REPO_ROOT / "artifacts" / "benchmarks" / "calibration"
CALIBRATION_NAMES = ("xflip_calibration_0.2.5.md", "vflip_calibration_0.2.4.md",
                     "curation_calibration_0.2.13.md", "cuda_parity_0.2.4.md")
REFERENCES_PATH = REPO_ROOT / "docs" / "references.md"
CLOSURE_PATH = REPO_ROOT / "artifacts" / "process" / "blocker_fixpoint_receipt.md"


def _cards(data):
    cards = data["validations"]
    assert cards, "the build must hold validation cards"
    return cards


def _card_for(data, path):
    rel = path.relative_to(REPO_ROOT).as_posix()
    return next(card for card in _cards(data) if card["path"] == rel)


def _dump(record, path):
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def test_validations_cards_name_tracked_receipts(data):
    for card in _cards(data):
        assert (REPO_ROOT / card["path"]).is_file(), f"{card['path']} is not a file"
        listed = subprocess.run(["git", "ls-files", "--error-unmatch", "--", card["path"]],
                                cwd=REPO_ROOT, capture_output=True, check=False)
        assert listed.returncode == 0, f"{card['path']} is not tracked by git"


def test_validations_card_holds_commit_and_digest(data):
    for card in _cards(data):
        log = subprocess.run(["git", "log", "-1", "--format=%H", "--", card["path"]],
                             cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        assert card["commit"] == log.stdout.strip(), card["id"]
        digest = hashlib.sha256((REPO_ROOT / card["path"]).read_bytes()).hexdigest()
        assert card["sha256"] == digest, card["id"]


def test_missing_receipt_refuses_the_build(monkeypatch):
    builder = _builder()
    absent = CALIBRATION_DIR / "absent_calibration_receipt.md"
    monkeypatch.setattr(builder, "CALIBRATION_RECEIPTS", (absent,))
    with pytest.raises(FileNotFoundError) as info:
        builder.build_data()
    assert "absent_calibration_receipt" in str(info.value)
    assert "is missing" in str(info.value)


def test_path_outside_the_repo_is_refused(monkeypatch, tmp_path):
    builder = _builder()
    outside = tmp_path / "outside_receipt.md"
    outside.write_text("# Outside receipt\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(builder, "CALIBRATION_RECEIPTS", (outside,))
    with pytest.raises(ValueError) as info:
        builder.build_data()
    assert "outside REPO_ROOT" in str(info.value)


def test_untracked_receipt_is_refused(monkeypatch):
    builder = _builder()
    untracked = REPO_ROOT / "_temp_untracked_receipt_1616.md"
    untracked.write_text("# Untracked receipt\n", encoding="utf-8", newline="\n")
    try:
        monkeypatch.setattr(builder, "CALIBRATION_RECEIPTS", (untracked,))
        with pytest.raises(RuntimeError) as info:
            builder.build_data()
        assert "is not tracked by git" in str(info.value)
    finally:
        untracked.unlink()


def test_a_recorded_digest_that_differs_from_the_bytes_is_reported(tmp_path):
    builder = _builder()
    site = tmp_path / "site"
    builder.write_dashboard(site)
    assert builder.verify_validations(site) == [], "a fresh build must verify"
    record = json.loads((site / "data.json").read_text(encoding="utf-8"))
    card = record["validations"][0]
    digest = card["sha256"]
    card["sha256"] = ("1" if digest[0] == "0" else "0") + digest[1:]
    _dump(record, site / "data.json")
    messages = builder.verify_validations(site)
    assert len(messages) == 1, messages
    assert card["path"] in messages[0] and "digest" in messages[0], messages[0]


def test_verify_names_a_card_whose_receipt_is_missing_untracked_or_outside(tmp_path):
    builder = _builder()
    site = tmp_path / "site"
    builder.write_dashboard(site)
    record = json.loads((site / "data.json").read_text(encoding="utf-8"))
    untracked = REPO_ROOT / "_temp_untracked_verify_1616.md"
    untracked.write_text("# Untracked receipt\n", encoding="utf-8", newline="\n")
    cases = {
        "is missing": "artifacts/absent_receipt_1616.md",
        "is not tracked by git": untracked.name,
        "is outside REPO_ROOT": str(tmp_path / "outside_receipt.md"),
    }
    try:
        for reason, path in cases.items():
            record["validations"][0]["path"] = path
            _dump(record, site / "data.json")
            messages = builder.verify_validations(site)
            assert len(messages) == 1 and reason in messages[0], (reason, messages)
    finally:
        untracked.unlink()


def test_validation_html_outputs_are_copied_beside_the_page(monkeypatch, tmp_path):
    builder = _builder()
    source = tmp_path / "validations"
    source.mkdir()
    (source / "studies-1.html").write_bytes(b"<!doctype html>\n<p>fixture</p>\n")
    monkeypatch.setattr(builder, "VALIDATION_HTML", source)
    site = tmp_path / "site"
    builder.write_dashboard(site)
    copied = site / "assets" / "validations" / "studies-1.html"
    assert copied.read_bytes() == (source / "studies-1.html").read_bytes()
    record = json.loads((site / "data.json").read_text(encoding="utf-8"))
    card = next(c for c in record["validations"] if c["id"] == "studies-1")
    assert card["html"] == "assets/validations/studies-1.html"


def test_an_absent_html_directory_gives_no_outputs(monkeypatch, tmp_path):
    builder = _builder()
    monkeypatch.setattr(builder, "VALIDATION_HTML", tmp_path / "absent")
    assert builder._validation_html() == []


@pytest.mark.parametrize("name", CALIBRATION_NAMES)
def test_a_calibration_card_holds_fields_only_from_its_receipt(data, name):
    path = CALIBRATION_DIR / name
    card = _card_for(data, path)
    text = path.read_text(encoding="utf-8")
    title = next(line for line in text.splitlines() if line.startswith("# "))
    assert card["title"] == title[2:].strip(), name
    for key, value in card["fields"].items():
        for item in (value if isinstance(value, list) else [value]):
            assert str(item) in text, f"{name}: field {key!r} does not come from the file"


def test_the_curation_card_reads_its_result_bullet(data):
    path = CALIBRATION_DIR / "curation_calibration_0.2.13.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    result = lines.index("## Result")
    bullet = next(line for line in lines[result + 1:] if line.startswith("- "))
    assert _card_for(data, path)["fields"]["summary"] == bullet[2:].strip()


def test_the_calibration_parser_reads_only_what_the_text_states():
    builder = _builder()
    stated = ("# Stated receipt\n\nWritten at " + "a" * 40 + " on 2026-10-21.\n\n## Result\n\n"
              "- Trials: 4; refused 0.\n- Second bullet.\n")
    assert builder._title_line(stated) == "Stated receipt"
    assert builder._calibration_fields(stated) == {
        "stated_commit": "a" * 40, "stated_date": "2026-10-21",
        "summary": "Trials: 4; refused 0."}
    bare = "# Bare receipt\n\nEstimator 88dc86fcef7ca90d over 3 trials.\n"
    assert builder._title_line(bare) == "Bare receipt"
    assert builder._calibration_fields(bare) == {}


def test_each_studies_row_is_a_card_naming_its_tests(data):
    lines = REFERENCES_PATH.read_text(encoding="utf-8").splitlines()
    header = lines.index("| Reference | Result reproduced | Receipt |")
    rows = []
    for line in lines[header + 2:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    cards = [card for card in _cards(data) if card["section"] == "studies"]
    assert rows and len(cards) == len(rows), (len(cards), len(rows))
    for card, row in zip(cards, rows):
        assert card["title"] == row.split("|")[1].strip()
        assert card["path"] == "docs/references.md"
        assert len(card["fields"]["tests"]) == len(re.findall(r"test_\w+\.py::\w+", row))


def test_the_closure_card_records_the_commit_and_count_its_receipt_states(data):
    card = next(c for c in _cards(data) if c["id"] == "blocker_fixpoint_receipt")
    text = CLOSURE_PATH.read_text(encoding="utf-8")
    commit = re.search(r"^\|\s*commit\s*\|\s*`([0-9a-f]{40})`", text, re.M).group(1)
    count = re.search(r"^\|\s*new release-blocking problems found\s*\|\s*(\d+)", text, re.M)
    assert card["section"] == "closure"
    assert card["recorded_commit"] == commit
    assert card["fields"]["new_blockers"] == int(count.group(1))


def test_the_peak_memory_card_records_the_commit_its_record_states(data):
    card = next(c for c in _cards(data) if c["id"] == "peak_memory")
    record = json.loads(PEAK_MEMORY_PATH.read_text(encoding="utf-8"))
    assert card["recorded_commit"] == record["commit"]


def test_performance_files_no_parser_reads_get_no_card(data):
    paths = {card["path"] for card in _cards(data)}
    unread = ["import_profile.txt", "gpu_launch_overhead_0.2.5.md", "complexity_inventory.md"]
    for name in unread:
        assert f"artifacts/benchmarks/performance/{name}" not in paths, name


def _committed_repo(root):
    """A temporary git repository whose only file, receipt.md, is committed. Returns the git runner."""
    def git(*args):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "user.name=test",
                               "-c", "user.email=test@example.invalid", *args], cwd=root,
                              check=True, capture_output=True, text=True)

    root.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    (root / "receipt.md").write_text("# Receipt\n", encoding="utf-8", newline="\n")
    git("add", "receipt.md")
    git("commit", "-q", "-m", "receipt")
    return git


def test_a_tracked_receipt_with_uncommitted_changes_is_refused(monkeypatch, tmp_path):
    builder = _builder()
    root = tmp_path / "repo"
    git = _committed_repo(root)
    monkeypatch.setattr(builder, "REPO_ROOT", root.resolve())
    receipt = root / "receipt.md"
    assert builder._receipt(receipt, "receipt") == "receipt.md", "a committed receipt is accepted"
    receipt.write_text("# Receipt, edited\n", encoding="utf-8", newline="\n")
    with pytest.raises(RuntimeError) as info:
        builder._receipt(receipt, "receipt")
    assert "has uncommitted changes" in str(info.value)
    git("add", "receipt.md")
    git("commit", "-q", "-m", "edit")
    assert builder._receipt(receipt, "receipt") == "receipt.md", "once committed, it is accepted"


def test_verify_refuses_a_receipt_with_uncommitted_changes_even_when_its_digest_matches(
        monkeypatch, tmp_path):
    builder = _builder()
    root = tmp_path / "repo"
    git = _committed_repo(root)
    monkeypatch.setattr(builder, "REPO_ROOT", root.resolve())
    receipt = root / "receipt.md"
    receipt.write_text("# Receipt, edited\n", encoding="utf-8", newline="\n")
    site = tmp_path / "site"
    site.mkdir()
    digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    _dump({"validations": [{"path": "receipt.md", "sha256": digest}]}, site / "data.json")
    assert builder.verify_validations(site) == [
        "validations: receipt.md has uncommitted changes"], "the digest matches, so only git refuses"
    git("add", "receipt.md")
    git("commit", "-q", "-m", "edit")
    assert builder.verify_validations(site) == [], "once committed, the card holds"


# ---- verdict labels and deferred validations ----------------------------------------------

LABEL_OF_VERDICT = {"reproduces": "reproduced", "partial": "mixed", "does_not": "failed"}
VALIDATION_TAG = "(validation)"
ROADMAP_PATH = REPO_ROOT / "artifacts" / "roadmap.md"


@pytest.mark.parametrize("verdict", sorted(LABEL_OF_VERDICT))
def test_each_replication_verdict_carries_its_dashboard_label(point_at, verdict):
    record = _record()
    entry = record["entries"][0]
    entry["status"] = "exploratory"  # a verified entry needs a reproducing replication
    entry["replications"] = [dict(entry["replications"][0], verdict=verdict)]
    point_at(record)
    rows = _builder().build_data()["showcases"]["entries"][0]["replications"]
    assert [row["label"] for row in rows] == [LABEL_OF_VERDICT[verdict]]


def test_a_replication_verdict_outside_the_record_vocabulary_is_refused(point_at):
    record = _record()
    entry = record["entries"][0]
    entry["status"] = "exploratory"
    entry["replications"][0]["verdict"] = "maybe"
    point_at(record)
    with pytest.raises(ValueError) as info:
        _builder().build_data()
    assert "fixture_entry" in str(info.value)
    assert "maybe" in str(info.value)


def test_the_deferred_section_is_the_tagged_roadmap_rows_and_reads_not_started(data):
    rows = [line for line in ROADMAP_PATH.read_text(encoding="utf-8").splitlines()
            if line.startswith("| ") and "| deferred-" in line]
    validating = [line for line in rows if line.split("|")[2].strip().endswith(VALIDATION_TAG)]
    assert validating, "the roadmap must hold a tagged deferred validation row"
    deferred = data["deferred"]
    assert len(deferred) == len(validating), (len(deferred), len(validating))
    for item in deferred:
        assert item["label"] == "not started", item["id"]
        assert item["release"].startswith("deferred-"), item["id"]
        assert any(line.startswith(f"| {item['id']} |") for line in validating), item["id"]


def test_a_deferred_row_is_a_validation_only_when_its_theme_carries_the_tag(tmp_path, monkeypatch):
    """Text is not the test: an untagged row that says it recovers something is left out, and a
    tagged row is listed with the tag left off its theme."""
    builder = _builder()
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        "| ID | Theme | Defect | Waits | Release |\n"
        "|---|---|---|---|---|\n"
        "| row-a | A model recovers a planted signal | Recovery is measured | Waits | deferred-0.2.15 |\n"
        "| row-b | A model recovers a planted signal (validation) | Recovery is measured | Waits "
        "| deferred-0.2.15 |\n",
        encoding="utf-8", newline="\n")
    monkeypatch.setattr(builder, "ROADMAP", roadmap)
    rows = builder.deferred_section()
    assert [row["id"] for row in rows] == ["row-b"], rows
    assert rows[0]["theme"] == "A model recovers a planted signal", rows[0]["theme"]
    assert rows[0]["label"] == "not started"


def test_the_schema_declares_the_deferred_section_and_the_replication_label():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "deferred" in schema["properties"], "the schema must name the deferred section"
    replication = schema["$defs"]["showcase"]["properties"]["replications"]["items"]
    assert set(replication["properties"]["label"]["enum"]) == set(LABEL_OF_VERDICT.values())
