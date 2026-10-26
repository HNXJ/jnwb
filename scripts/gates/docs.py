"""Documentation gates: public symbols, dataset leakage, API reference, docs versions, NWB onboarding."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


GENERATED_REFERENCE = "api.md"


def check_public_symbols_documented(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 5 (API Completeness): every public export is written about by a person.

    This searched every ``docs/*.md``, and ``docs/api.md`` is generated from
    ``jnwb.__all__``. The gate therefore asserted that every export appears in a file
    guaranteed to contain every export. It passed while twelve symbols -- seven error
    classes, the two NWB resolvers, ``EventTable`` and ``DETECTION_TAILS`` -- appeared on
    no page a reader would find. The generated reference is excluded, so the gate now
    means what its name says. A whole-word match, so ``events`` is not credited to a page
    that only mentions ``event_onsets``.
    """
    root = repo_root or REPO_ROOT
    import jnwb
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return ["MISSING_DOCS_DIR: docs/ not found"]
    
    all_docs_text = ""
    # rglob: docs/tutorials/ holds nine live pages that glob("*.md") never read, so a
    # symbol documented only there counted as undocumented.
    for doc_path in sorted(docs_dir.rglob("*.md")):
        if doc_path.name == GENERATED_REFERENCE:
            continue
        all_docs_text += "\n" + doc_path.read_text(encoding="utf-8")
        
    violations = []
    for symbol in jnwb.__all__:
        if not re.search(rf"\b{re.escape(symbol)}\b", all_docs_text):
            violations.append(
                f"UNDOCUMENTED_PUBLIC_SYMBOL: Public export 'jnwb.{symbol}' appears in "
                f"no hand-written docs/*.md page (docs/{GENERATED_REFERENCE} is "
                f"generated from __all__ and does not count)")
    return violations


def check_documented_api_matches_all(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 9 (API Set Equality): assert documented API == set(jnwb.__all__), both directions.

    Gate 5 checks that every export is *mentioned* somewhere in docs/. That is necessary but
    weak: it cannot see a reference row left behind for a symbol that no longer exists, and it
    is satisfied by an incidental mention anywhere in any file. This gate pins the reference
    surface itself as a set.

    It exists because prose cannot hold a count true. ``docs/memory.md`` carried "exactly 105
    public symbols" while the package exported 111 -- stale within one release cycle, in the
    document agents are pointed at, and nothing failed. The repair is to state the invariant and
    check it here rather than to write a fresher number that will go stale in turn.
    """
    root = repo_root or REPO_ROOT
    import jnwb

    api_path = root / "docs" / "api.md"
    if not api_path.exists():
        return ["MISSING_API_DOC: docs/api.md not found"]

    # Reference rows look like: | jnwb.NAME | function | ... |
    documented = set(re.findall(r"^\|\s*jnwb\.([A-Za-z_][A-Za-z0-9_]*)\s*\|",
                                api_path.read_text(encoding="utf-8"), flags=re.MULTILINE))
    exported = set(jnwb.__all__)

    violations = []
    for symbol in sorted(exported - documented):
        violations.append(
            f"UNDOCUMENTED_EXPORT: 'jnwb.{symbol}' is in __all__ but has no docs/api.md row")
    for symbol in sorted(documented - exported):
        violations.append(
            f"PHANTOM_API_ROW: docs/api.md documents 'jnwb.{symbol}', which is not in __all__")
    return violations


def check_docs_version_matches_package(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 10 (Version Provenance): assert every version the docs state equals the package's.

    A rendered version is provenance: it tells a reader which release they are looking at. A
    *duplicated* version is a liability -- it is correct only until the next release, and
    nothing notices when it stops being. So the rule is not "the docs must state a version"
    but "any version the docs state must be derived from, or equal to, jnwb.__version__".

    Checked locations, each a place a literal can drift:
      * mkdocs.yml ``extra.jnwb_version`` (consumed by the version hook)
      * ``jnwb==X.Y.Z`` install pins in README.md and docs/*.md
    """
    root = repo_root or REPO_ROOT
    import jnwb

    expected = jnwb.__version__
    violations = []

    mkdocs_yml = root / "mkdocs.yml"
    if mkdocs_yml.exists():
        text = mkdocs_yml.read_text(encoding="utf-8")
        for found in re.findall(r"^\s*jnwb_version:\s*[\"']?([0-9][^\"'\s]*)", text,
                                flags=re.MULTILINE):
            if found != expected:
                violations.append(
                    f"DOCS_VERSION_MISMATCH: mkdocs.yml extra.jnwb_version is {found!r}, "
                    f"but jnwb.__version__ is {expected!r}")

    # rglob for the same reason as Gate 5, and here it is a hole rather than a
    # strictness bug: a `jnwb==0.0.9` pin planted in docs/tutorials/01_nwb_basics.md
    # passed this gate.
    for md in [root / "README.md", *sorted((root / "docs").rglob("*.md"))]:
        if not md.exists():
            continue
        for found in re.findall(r"jnwb==([0-9][0-9A-Za-z.\-]*)", md.read_text(encoding="utf-8")):
            if found != expected:
                violations.append(
                    f"DOCS_VERSION_MISMATCH: {md.relative_to(root).as_posix()} pins "
                    f"jnwb=={found}, but jnwb.__version__ is {expected}")

    return violations


#: Root-level user-facing documents included in the Gate 6 scan. These ship to or are read by
#: downstream users, so they carry the same dataset-independence obligation as docs/.
DATASET_SCAN_ROOT_DOCS = ("README.md", ".github/CONTRIBUTING.md", "AGENTS.md")

#: Files exempt from the Gate 6 scan, each with the reason it legitimately carries a token.
#: An exemption is a deliberate, named decision -- never a silent skip.
DATASET_SCAN_EXEMPT = {
    "CHANGELOG.md": "historical release record; not rewritten to satisfy a textual scan",
}

#: Files under tests/ that carry a forbidden token on purpose, each with the reason. Gate 6 scans
#: every other file under tests/.
TESTS_PLANTED_TOKENS = (
    ("tests/test_harness_adversarial_gates.py",
     "plants the tokens in temporary fixtures to show the gate refuses them, and names one as a constant"),
    ("tests/test_nwb_synthetic_fixtures.py",
     "lists the forbidden tokens its synthetic fixtures must not carry"),
)


def check_dataset_leakage(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 6 (Dataset Independence): scan a fixed forbidden-token list.

    Scanned, recursively: ``jnwb/**/*.py``, ``skills/**/*.md``, ``docs/**/*.md``,
    ``examples/**/*.py``, ``examples/**/*.ipynb``, ``tests/**`` (every file, except the reviewed
    plants in ``TESTS_PLANTED_TOKENS``), and the root user-facing documents listed in
    ``DATASET_SCAN_ROOT_DOCS``. These are the durable surfaces a reader or downstream user sees,
    and all of them are meant to be dataset-independent.

    Deliberately NOT scanned, each for a stated reason:
      * ``scripts/`` -- harness code legitimately names the tokens it forbids.
      * the files in ``TESTS_PLANTED_TOKENS`` -- test code that names a token on purpose.
      * ``CHANGELOG.md`` -- a historical record; rewriting history to satisfy a scan would be
        worse than the leak it prevents.
      * files listed in ``DATASET_SCAN_EXEMPT`` -- see that constant for the per-file reason.

    ``code_only_patterns`` apply to ``jnwb/`` alone: an external project's name that docs may
    cite and code may not.

    The scan is textual and pattern-bound: it proves the listed tokens are absent, not that a
    surface is free of study-specific content in general.

    This docstring is load-bearing. It previously described a narrower surface than the code
    actually scanned (``docs/*.md``, non-recursive, with ``examples/`` unmentioned), and an
    audit that read it rather than the implementation reported a coverage gap that did not
    exist. Keep it synchronised with the globs below.
    """
    root = repo_root or REPO_ROOT
    violations = []
    
    forbidden_patterns = [
        (re.compile(r"\bAXAB\b"), "experiment condition token 'AXAB'"),
        (re.compile(r"\bBXBA\b"), "experiment condition token 'BXBA'"),
        (re.compile(r"S\+/S-"), "experiment condition token 'S+/S-'"),
        (re.compile(r"O\+/O-"), "experiment condition token 'O+/O-'"),
        (re.compile(r"\bO\+\+?\b"), "omission unit class token 'O+' or 'O++'"),
        (re.compile(r"\bomission-linked\b"), "study-specific concept 'omission-linked'"),
        (re.compile(r"\bomission-relative\b"), "study-specific concept 'omission-relative'"),
        (re.compile(r"p\s*=\s*0\.053\b"), "omission manuscript result 'p = 0.053'"),
        (re.compile(r"p\s*=\s*0\.875\b"), "omission manuscript result 'p = 0.875'"),
        (re.compile(r"\b74\.8\s*%"), "omission manuscript deltaT result '74.8%'"),
        (re.compile(r"\b104\s*/\s*139\b"), "omission manuscript cell count '104/139'"),
        (re.compile(r"\b187\s*/\s*4130\b"), "omission manuscript cell count '187/4130'"),
        (re.compile(r"beta\s*/\s*gamma\s+temporal\s+resolvability"), "omission study finding 'beta/gamma temporal resolvability'"),
        (re.compile(r"beta/gamma\s*>\s*theta/alpha"), "omission study finding 'beta/gamma > theta/alpha'"),
        (re.compile(r"early-decrease\s*/\s*late-increase"), "omission sign timing claim 'early-decrease / late-increase'"),
        (re.compile(r"area\s+and\s+subject\s+are\s+partially\s+confounded"), "omission area-subject confounding claim"),
        (re.compile(r"\bLFP\s+drives\s+SPK\b"), "forbidden causal assertion 'LFP drives SPK'"),
        (re.compile(r"\bSPK\s+drives\s+LFP\b"), "forbidden causal assertion 'SPK drives LFP'"),
    ]
    # Names jnwb/ code, docstrings included, may not carry; docs may cite them.
    code_only_patterns = [
        (re.compile(r"Paper2Agent", re.IGNORECASE),
         "external project name 'Paper2Agent' (docs may cite it; code may not)"),
    ]

    target_files: List[Path] = []
    
    # 1. jnwb/ Python files
    for py_file in (root / "jnwb").rglob("*.py"):
        if "__pycache__" not in py_file.parts:
            target_files.append(py_file)
            
    # 2. skills/ markdown files
    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.rglob("*.md"):
            target_files.append(skill_file)
            
    # 3. Core harness authority and developer guides
    for harness_name in ["AGENTS.md", ".github/CONTRIBUTING.md"]:
        harness_file = root / harness_name
        if harness_file.exists():
            target_files.append(harness_file)
            
    # 4. docs/ markdown files, recursively -- includes docs/tutorials/
    docs_dir = root / "docs"
    if docs_dir.exists():
        for doc_file in docs_dir.rglob("*.md"):
            if doc_file not in target_files:
                target_files.append(doc_file)

    # 5. Every example surface, recursively: executable tutorials, their support modules, the
    #    quickstart, and notebooks. Previously only examples/tutorials/[0-9][0-9]_*.py was
    #    scanned, which left examples/quickstart_jnwb.py, examples/notebooks/*.ipynb and any
    #    non-numbered helper module unscanned -- all of them user-facing.
    examples_dir = root / "examples"
    if examples_dir.exists():
        for pattern in ("*.py", "*.ipynb"):
            for example_file in examples_dir.rglob(pattern):
                if "__pycache__" in example_file.parts:
                    continue
                if example_file not in target_files:
                    target_files.append(example_file)

    # 6. Root-level user-facing documents (README.md above all -- the most-read file here).
    for doc_name in DATASET_SCAN_ROOT_DOCS:
        root_doc = root / doc_name
        if root_doc.exists() and root_doc not in target_files:
            target_files.append(root_doc)

    # 7. Every file under tests/, except the reviewed plants that carry a token on purpose.
    planted = {rel for rel, _reason in TESTS_PLANTED_TOKENS}
    tests_dir = root / "tests"
    if tests_dir.exists():
        for test_file in tests_dir.rglob("*"):
            if (test_file.is_file() and "__pycache__" not in test_file.parts
                    and test_file.relative_to(root).as_posix() not in planted):
                target_files.append(test_file)

    target_files = [f for f in target_files
                    if f.relative_to(root).as_posix() not in DATASET_SCAN_EXEMPT]
                
    for target in target_files:
        text = target.read_text(encoding="utf-8", errors="replace")
        rel_path = target.relative_to(root).as_posix()
        patterns = forbidden_patterns + (code_only_patterns if rel_path.startswith("jnwb/") else [])
        for pat, desc in patterns:
            if pat.search(text):
                violations.append(f"DATASET_LEAKAGE: Found {desc} in {rel_path}")
                
    return violations


#: The public NWB entry points Gate 13 holds the onboarding surface to.
NWB_ONBOARDING_SYMBOLS = ("jnwb.inspect", "jnwb.events", "jnwb.event_onsets")


def check_nwb_onboarding_alignment(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 13: README, tutorials, and skill agree on the public NWB workflow.

    This was a presence check and passed a tree it should have rejected: a README saying
    the three symbols are REMOVED still contains their names, nine tutorials whose whole
    body is ``raise SystemExit`` still exist as files, and a nav line commented out in
    mkdocs.yml is still a substring of the file. Each of the three is now checked for the
    property it was standing in for -- a call, a runnable module, a parsed nav entry.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    readme = root / "README.md"
    if not readme.exists():
        violations.append("NWB_ONBOARDING: README.md missing")
    else:
        text = readme.read_text(encoding="utf-8")
        for symbol in NWB_ONBOARDING_SYMBOLS:
            # A call, not a mention: "jnwb.inspect is REMOVED" mentions it too.
            if f"{symbol}(" not in text:
                violations.append(
                    f"NWB_ONBOARDING: README never calls {symbol}; naming it is not the same "
                    f"as showing a reader how to use it"
                )

    expected_scripts = [
        "00_your_own_file.py",
        "01_nwb_basics.py",
        "02_addressing_and_metadata.py",
        "03_spiking.py",
        "04_lfp_and_spectral.py",
        "05_statistics.py",
        "06_laminar.py",
        "07_ensembles.py",
        "08_end_to_end_pipeline.py",
    ]
    tutorial_dir = root / "examples" / "tutorials"
    for name in expected_scripts:
        script = tutorial_dir / name
        if not script.exists():
            violations.append(f"NWB_ONBOARDING: missing tutorial script {name}")
            continue
        source = script.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(script))
        except SyntaxError as exc:
            violations.append(f"NWB_ONBOARDING: {name} does not parse: {exc}")
            continue
        # A file that exists is not a tutorial that runs. Nine of them rewritten to
        # `raise SystemExit(...)` passed this gate, because the check was existence.
        if any(isinstance(node, ast.Raise) for node in tree.body):
            violations.append(
                f"NWB_ONBOARDING: {name} raises at module level, so importing or running it "
                f"never reaches the workflow it documents"
            )
        functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        if "main" not in functions:
            violations.append(f"NWB_ONBOARDING: {name} defines no main()")

    for name in expected_scripts:
        md_name = name.replace(".py", ".md")
        md_path = root / "docs" / "tutorials" / md_name
        if not md_path.exists():
            violations.append(f"NWB_ONBOARDING: missing tutorial doc {md_name}")
            continue
        snippet = f'--8<-- "examples/tutorials/{name}"'
        if snippet not in md_path.read_text(encoding="utf-8"):
            violations.append(f"NWB_ONBOARDING: {md_name} not snippet-linked to {name}")

    # Each symbol is checked in the skill whose routing row holds it, read with the parser the
    # skill tests use. A fixed skill path passed a tree whose `jnwb.events` row had moved to
    # another skill, because an example line left behind still held the call.
    from tests.test_skill_router_reach import _ROW_HEAD_END, _routed_operations

    def _row_head(line: str) -> str:
        # The call is read from the row head: up to the colon that ends it, or up to the arrow
        # that introduces the return value. A call in the description is a mention, and a row
        # that names the symbol and calls it only there passed when the whole line was read.
        # With neither separator, the head ends at the first whitespace after the first span.
        end = _ROW_HEAD_END.search(line)
        if end:
            return line[: end.start() + 1].split("→", 1)[0]
        if "→" in line:
            return line.split("→", 1)[0]
        span = re.match(r"- `[^`]*`\S*", line)
        return span.group() if span else line

    pages = [(p.parent.name, p) for p in sorted((root / "skills").glob("*/SKILL.md"))]
    pages += [(p.parent.parent.name, p)
              for p in sorted((root / "skills").glob("*/references/*.md"))]
    if not pages:
        violations.append("NWB_ONBOARDING: no skills/*/SKILL.md to route the NWB symbols")
    rows = [
        (skill, line)
        for skill, path in pages
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    for symbol in NWB_ONBOARDING_SYMBOLS:
        routing = [(skill, line) for skill, line in rows if symbol in _routed_operations(line)]
        if pages and not routing:
            violations.append(f"NWB_ONBOARDING: no skill has a routing row for {symbol}")
        for skill, line in routing:
            if f"`{symbol}(" not in _row_head(line):
                violations.append(
                    f"NWB_ONBOARDING: skills/{skill} has a routing row for {symbol} but the row "
                    f"never routes a call to it"
                )

    mkdocs = root / "mkdocs.yml"
    if not mkdocs.exists():
        violations.append("NWB_ONBOARDING: mkdocs.yml missing")
    else:
        # Parsed, not substring-matched: a commented-out nav line is still a substring of
        # the file, so the page would be missing from the built site while this passed.
        import yaml

        try:
            config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            config = {}
            violations.append(f"NWB_ONBOARDING: mkdocs.yml does not parse: {exc}")

        def _pages(node) -> List[str]:
            if isinstance(node, str):
                return [node]
            if isinstance(node, dict):
                return [p for value in node.values() for p in _pages(value)]
            if isinstance(node, list):
                return [p for item in node for p in _pages(item)]
            return []

        nav_pages = set(_pages(config.get("nav", [])))
        for name in expected_scripts:
            page = f"tutorials/{name.replace('.py', '.md')}"
            if page not in nav_pages:
                violations.append(
                    f"NWB_ONBOARDING: {page} is not in the mkdocs nav, so the built site "
                    f"does not carry it"
                )

    return violations
