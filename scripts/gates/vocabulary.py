"""Vocabulary gates: project identifiers, internal process terms, the changelog template, library identifiers."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


#: Projects built on jnwb. A code string or identifier in jnwb/ containing one gives that
#: project privileged meaning in the library.
PROJECT_IDENTIFIERS = ("omission",)


def check_no_project_identifiers_in_code(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 12 (Project Identifiers): no jnwb/ code string or name contains a project name.

    Gate 1 sees imports and Gate 6 sees a fixed list of study tokens. Neither saw 0.1.3's
    MCP tool defaulting to a project's event table ('omission_glo_passive'), so both
    passed. This gate parses jnwb/ and checks every string constant and identifier.
    Docstrings and comments are skipped; they may cite where code came from.
    """
    root = repo_root or REPO_ROOT
    violations = []
    for py in sorted((root / "jnwb").rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        # A string standing alone as a statement is documentation (a docstring, or an
        # attribute docstring under a dataclass field); it never reaches running code.
        docstrings = {
            id(node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstrings:
                    continue
                text = node.value
            elif isinstance(node, ast.Name):
                text = node.id
            elif isinstance(node, ast.Attribute):
                text = node.attr
            elif isinstance(node, ast.arg):
                text = node.arg
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                text = node.name
            elif isinstance(node, ast.alias):
                text = node.name
            else:
                continue
            for project in PROJECT_IDENTIFIERS:
                if project in text.lower():
                    violations.append(
                        f"PROJECT_IDENTIFIER: {py.relative_to(root).as_posix()}:{node.lineno} "
                        f"uses {text[:60]!r}. A project's names belong in the project; take "
                        f"the value as an argument instead."
                    )
    return violations


#: Terms naming a mechanism of this repository's own process of building jnwb, gated as phrases
#: rather than as words.
#:
#: The one-sentence rule: a term belongs here when it names part of how this repository is worked
#: on -- the delegation packets, the two stacks, the worktrees, the harness gates, the role files
#: -- and is spelled specifically enough that no sentence about what jnwb does for a caller can
#: contain it.
#:
#: The second half is the whole difficulty, and 06-02 retired a rule that failed it. The old rule
#: gated the word "agent", which is a proxy: agents, skills and routing are public jnwb
#: capabilities and five published pages describe them. Each exclusion below was resolved against
#: the live corpus rather than assumed, because a gate justified by a guess is the same defect one
#: layer up:
#:
#:   "agent", "skill", "routing"  -- public capabilities; `docs/agents.md` is an entire page of them
#:   "batch"                      -- `docs/02:11` "batch jobs", `docs/api.md` `batch_size=`
#:   "authority"                  -- ordinary English; its one published use left with the process skill
#:   "actor", "critic", "verifier" -- ordinary English before they are role names here
#:
#: Four of the six stems under `artifacts/agents/` are ordinary English, so only the two that are
#: internal by construction appear here. **This gate therefore does not claim that no internal
#: vocabulary reaches `docs/`; it claims that these terms do not.**
#:
#: "packet" was held out of this list while one legitimate-looking use remained --
#: `docs/documentation_form.md:23` used it in its internal sense, and gating it then would have
#: been gating a common word to catch one sentence, which is the 06-02 failure mode. That
#: sentence now reads "any change that trims, retitles or reformats documentation", and `grep`
#: across `docs/` finds **zero** remaining occurrences of the word in any form, so the bare term
#: is gated and its live zero is a true negative rather than a gap (P-98). The use that would
#: legitimately reintroduce it is a networking one -- a streaming page describing packets on the
#: wire -- and that is the case to revisit this entry for, not a reason to leave it ungated now.
INTERNAL_PROCESS_TERMS: Tuple[str, ...] = (
    # "delegation packet" was removed when "packet" was added: the bare term subsumes it, so it
    # could never be the sole reason for a violation and every hit would be reported twice. A
    # term that cannot fire on its own is the dead-entry class this module already carries a
    # scar from -- three multi-word terms were silently dead while the gate reported PASS.
    "packet",
    "todo stack",
    "todo_stack.md",
    "problem stack",
    "problem_stack.md",
    "open stack",
    "open_stack.md",
    "fact_stack.md",
    "harness gate",
    "harness_gate.py",
    "worktree",
    "fan-out",
    "artifacts/agents/",
    "docs-harness",
    "jnwb-developer",
)


def _internal_term_pattern(term: str) -> Any:
    """Match one gated term allowing plural, case and space/hyphen variation.

    Spelling the terms as plain literals would let "Delegation Packets" and "fan out" through,
    which is a gate passing for the wrong reason rather than a gate with a narrow scope.

    Built by splitting and rejoining rather than by patching `re.escape`'s output. Escaping first
    and then replacing "\\ " and "\\-" in sequence was tried and is silently wrong: the first
    substitution inserts a "[\\s\\-]+" that contains "\\-", which the second substitution then
    rewrites into "[\\s[\\s\\-]+]+". That compiles, matches nothing that matters, and made three
    of the multi-word terms dead while the gate still reported PASS.
    """
    body = r"[\s\-]+".join(re.escape(part) for part in re.split(r"[\s-]+", term))
    # The edges guard against `\w` and not against `[\w-]`. Excluding a neighbouring hyphen was
    # tried and loses the compounds these terms are most often written as: "worktree-local" and
    # "harness-gate-adjacent" both escaped it while meaning exactly the gated thing.
    pattern = f"(?<!\\w){body}s?"
    # Only guard the right edge when the term ends in a word character: `artifacts/agents/` is
    # always followed by a filename, and a trailing `(?!\w)` would make it match nothing.
    if term[-1].isalnum() or term[-1] == "_":
        pattern += "(?!\\w)"
    return re.compile(pattern, re.IGNORECASE)


def check_internal_process_vocabulary(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 14 (Internal Process Vocabulary): repository-process terms stay out of public docs.

    06-02 ruled the boundary on 2026-09-19: public documentation may describe agents, skills and
    routing, because those are jnwb capabilities a caller uses; internal repository-agent roles,
    harness and process vocabulary, private coordination state and implementation-only
    terminology may not appear there. The ruling says to gate the distinction mechanically *where
    practical*, and that qualifier is load-bearing -- the rule it replaced gated the word "agent"
    and was broken by four published pages the day it was written.

    Scope is `docs/**/*.md`, which is the surface 06-02 and 06-68 both name. A generated or
    included page is scanned like any other, and its fix goes to the generator.

    `README.md` is scanned as well: it is the PyPI description, the most public page there is.
    It was held out while it linked `artifacts/todo_stack.md` from its Contributing section; the
    2026-09-23 ruling removed the link, so the page is held to the same terms as `docs/`.
    `artifacts/agents.md` is the agent entry page `README.md` links to, and is held to them too.

    `skills/**/*.md` and `skills/**/*.yaml` are scanned too: the skills ship in the sdist and are published at
    `jnwb.SKILLS_URL`, so they are public. The skills about working on this repository live
    under `artifacts/skills/`, which is not scanned.
    """
    root = repo_root or REPO_ROOT
    violations = []

    # A sweep that finds no files reports no violations, which reads exactly like a clean tree.
    # Gate 8's three `if not path.exists()` blocks exist for the same reason.
    pages: List[Path] = []
    for surface in ("docs", "skills"):
        found = sorted((root / surface).rglob("*.md")) if (root / surface).is_dir() else []
        if surface == "skills" and found:
            found += sorted((root / surface).rglob("*.yaml"))  # agents/openai.yaml ships too
        if not found:
            return [
                "INTERNAL_VOCABULARY: no public documentation found to scan under "
                f"{root / surface}; the sweep is broken, not the tree"
            ]
        pages += found
    pages += [
        page for page in (root / "README.md", root / "artifacts" / "agents.md") if page.is_file()
    ]

    patterns = [(term, _internal_term_pattern(term)) for term in INTERNAL_PROCESS_TERMS]
    for page in pages:
        rel = page.relative_to(root).as_posix()
        for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            for term, pattern in patterns:
                found = pattern.search(line)
                if found:
                    violations.append(
                        f"INTERNAL_VOCABULARY: {rel}:{lineno} says {found.group(0)!r}. "
                        f"{term!r} names part of how this repository is worked on and has no "
                        "public-interface use. Say what the reader can do, or move the sentence "
                        "out of the published documentation."
                    )
    return violations


#: The kinds a release may head its entries with. The template adopted 2026-10-12 allows these six.
CHANGELOG_KINDS: Tuple[str, ...] = ("Breaking", "Added", "Changed", "Deprecated", "Removed", "Fixed")

#: The release blocks CHANGELOG.md keeps; older blocks move to the archive file.
CHANGELOG_RELEASES_KEPT = 5

#: The longest entry line in characters. The template says "about 120"; the gate takes 120.
CHANGELOG_ENTRY_LIMIT = 120

#: Phrases the CHANGELOG may not carry, each naming a repository role or a verification artifact.
#: The bare words "agent" and "worker" are not listed: a public page names agents as a capability,
#: a parallel job runs on workers, and "closure" is a perception term. The docs scan went wrong on
#: a bare role word, so each role is listed by a phrase only a repository role uses.
CHANGELOG_PROCESS_TERMS: Tuple[str, ...] = (
    "receipt",
    "AGENTS.md",
    "audit RG",
    "closure pass",
    "subagent",
    "agent lane",
    "worker agent",
    "worker lane",
    "worker packet",
)

#: A file or test name: `vis.py`, `pyproject.toml`, `docs/api.md`, `test_csd`.
CHANGELOG_NAME = re.compile(r"[\w./-]+\.(?:py|md|json|ya?ml|toml|txt|cff|ipynb)(?!\w)|\btest_\w+")

#: The seed kinds a `[results change]` marker may name; `deterministic` for a change no seed drives.
CHANGELOG_SEED_KINDS: Tuple[str, ...] = ("int seed", "Generator", "deterministic")

#: Entries under a release heading at or after this version meet the full template. Older entries
#: are checked for process phrases and kind headings only. `[Unreleased]` is the next release.
CHANGELOG_TEMPLATE_FROM: Tuple[int, ...] = (0, 2, 12)

#: Process phrases matched in their written capitals only: `docs/agents.md` is the public agent
#: page, and the file the rule means is the capitalised one.
CHANGELOG_CASE_SENSITIVE: Tuple[str, ...] = ("AGENTS.md",)

#: Process phrases allowed only in a bullet that also names package content, its continuation lines
#: included: the file ships in the sdist and wheel and is listed in MANIFEST.in, so an entry about
#: shipping it names one of them.
CHANGELOG_PACKAGE_SCOPED: Tuple[str, ...] = ("AGENTS.md",)

#: Package content for CHANGELOG_PACKAGE_SCOPED: `sdist` and `wheel` in any case, `MANIFEST` only as
#: the capitalised file name.
CHANGELOG_PACKAGE_CONTENT = re.compile(r"(?i:\bsdist\b|\bwheel\b)|\bMANIFEST\b")


def _held_to_template(version: str) -> bool:
    """Whether a release heading's entries meet the full template, read from the heading itself.

    A heading whose version does not parse is held to the template: an unreadable version is not
    a waiver.
    """
    if version == "Unreleased":
        return True
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        return True
    return tuple(int(part) for part in version.split(".")) >= CHANGELOG_TEMPLATE_FROM


def _changelog_term_pattern(term: str) -> Any:
    pattern = _internal_term_pattern(term)
    return re.compile(pattern.pattern) if term in CHANGELOG_CASE_SENSITIVE else pattern


def _changelog_entry_violations(root: Path, lineno: int, line: str) -> List[str]:
    """Length, named file and seed kind of one changelog entry line."""
    found = []
    if len(line) > CHANGELOG_ENTRY_LIMIT:
        found.append(
            f"CHANGELOG.md:{lineno} is {len(line)} characters; an entry is one line of at most "
            f"{CHANGELOG_ENTRY_LIMIT} characters."
        )
    names = CHANGELOG_NAME.findall(line)
    if not names:
        found.append(
            f"CHANGELOG.md:{lineno} names no test or file; an entry names the test or the file "
            "it changes."
        )
    for name in names:
        if "/" in name and not (root / name).exists():
            found.append(f"CHANGELOG.md:{lineno} names {name!r}, which is not in the tree.")
        elif name.startswith("test_") and "." not in name and not (root / "tests" / f"{name}.py").is_file():
            found.append(f"CHANGELOG.md:{lineno} names the test {name!r}, which is not in tests/.")
    if "[results change]" in line and not any(
            re.search(rf"\b{re.escape(kind)}\b", line) for kind in CHANGELOG_SEED_KINDS):
        found.append(
            f"CHANGELOG.md:{lineno} carries [results change] but names neither 'int seed', "
            "'Generator' nor 'deterministic'."
        )
    return found


def _bullet_scopes(lines: List[str]) -> List[str]:
    """The text each line is judged against for a package-scoped phrase.

    A bullet (`- ` line) and its indented, non-blank continuation lines share one scope, the
    bullet's joined text. Any other line is its own scope.
    """
    scopes = list(lines)
    members: List[int] = []

    def close() -> None:
        if members:
            text = "\n".join(lines[j] for j in members)
            for j in members:
                scopes[j] = text
            members.clear()

    for i, line in enumerate(lines):
        if line.startswith("- "):
            close()
            members.append(i)
        elif members and line[:1] in (" ", "\t") and line.strip():
            members.append(i)
        else:
            close()
    close()
    return scopes


def check_changelog_form(repo_root: Optional[Path] = None) -> List[str]:
    """CHANGELOG.md in the entry template: six kinds, no process phrase, and five releases
    throughout (a patch counts with its release). From 0.2.12 on, one line per entry of at most
    120 characters that names its test or file, and a seed kind on each `[results change]`.

    Every line is searched for the phrases, and every release block for the rest. A file with no
    release block is a violation: it would pass every other rule without reading one.
    """
    root = repo_root or REPO_ROOT
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return [f"CHANGELOG.md: {path} is missing, so the entry template cannot be read."]
    lines = path.read_text(encoding="utf-8").splitlines()
    scopes = _bullet_scopes(lines)
    patterns = [(term, _changelog_term_pattern(term)) for term in CHANGELOG_PROCESS_TERMS]
    violations: List[str] = []
    releases: List[str] = []
    in_release = False
    held = False
    entry_open = False
    for lineno, line in enumerate(lines, 1):
        package_line = CHANGELOG_PACKAGE_CONTENT.search(scopes[lineno - 1]) is not None
        for term, pattern in patterns:
            found = pattern.search(line)
            if found and not (term in CHANGELOG_PACKAGE_SCOPED and package_line):
                violations.append(
                    f"CHANGELOG.md:{lineno} says {found.group(0)!r}. {term!r} names part of how "
                    "this repository is worked on; name the change and its test or file instead."
                )
        if line.startswith("## "):
            head = re.match(r"## \[([^\]]+)\]", line)
            in_release = head is not None
            held = bool(head) and _held_to_template(head.group(1))
            entry_open = False
            if head and head.group(1) != "Unreleased":
                releases.append(head.group(1))
            continue
        if not in_release:
            continue
        if line.startswith("### "):
            entry_open = False
            kind = line[4:].strip()
            if kind not in CHANGELOG_KINDS:
                violations.append(
                    f"CHANGELOG.md:{lineno} heads entries '### {kind}'; the template allows "
                    f"{', '.join(CHANGELOG_KINDS)} and no other."
                )
        elif line.startswith("- "):
            entry_open = True
            if held:
                violations.extend(_changelog_entry_violations(root, lineno, line))
        elif held and line[:1] in (" ", "\t") and line.strip() and entry_open:
            violations.append(
                f"CHANGELOG.md:{lineno} continues an entry on a second line; the template allows "
                "one line per change."
            )
    # A patch counts with its release: 0.2.6.1 is the 0.2.6 release's patch, one release.
    kept = {".".join(version.split(".")[:3]) for version in releases}
    if not releases:
        violations.append(
            "CHANGELOG.md has no release block, so there is nothing to hold to the template."
        )
    elif len(kept) > CHANGELOG_RELEASES_KEPT:
        violations.append(
            f"CHANGELOG.md holds {len(kept)} releases; the template keeps "
            f"{CHANGELOG_RELEASES_KEPT} and archives the older ones."
        )
    return violations


#: An item or problem identifier from the coordination stacks: `P-29`, `p-29`, `P-C7`,
#: `P-1000`, `06-55`, `items/06-55`, `0.2.4-04`, and a review finding: `REV-07`,
#: `0.2.3-REV-07`, `EXT-REV-003`. The item form requires a leading zero because two-digit
#: ranges are ordinary library prose (`14-30 Hz`), and every edge excludes a neighbouring
#: word character, dot, slash or hyphen, so a full date (`2026-09-23`), a version (`0.2.6`)
#: and a DOI fragment (`s41593-020-00744-x`) never match -- except through the `items/`
#: prefix, which names the stack the identifier comes from. A bare `MM-DD` with a calendar
#: day (`09-23`) is a date, not an item, and is filtered at the scan; a day past 31
#: (`06-55`) cannot be one, so it still matches. A decimal after the match ends it as a number
#: (`p-0.05`).
PROCESS_IDENTIFIER = re.compile(
    r"(?<![\w./\-])(?:[Pp]-C?\d{1,4}|(?:items/)?0\d-\d{2,3}|\d+\.\d+\.\d+-\d{2,3}"
    r"|(?:\d+\.\d+\.\d+-|[A-Z]{2,}-)?REV-\d{2,3})(?![\w\-]|\.\d)"
)


def _is_month_day(token: str) -> bool:
    """A bare `MM-DD` date (`09-23`), which the item form above otherwise matches.

    The shapes are genuinely ambiguous -- an item numbered 09-23 would read the same --
    so the rule is the calendar: a leading-zero month with a day of 01-31 is a date. The
    `items/` prefix names the stack, so a prefixed token is an item whatever its digits.
    """
    if token.startswith("items/"):
        return False
    month, dash, day = token.partition("-")
    return (dash == "-" and len(month) == 2 and "01" <= month <= "09"
            and len(day) == 2 and "01" <= day <= "31")


#: A pymdownx.snippets include on one line: `--8<-- "path"`, any run of dashes on either side,
#: either quote. A leading `;` escapes it, and an escaped include is not followed.
SNIPPET_INLINE = re.compile(r"""^[ \t]*(;*)-+8<-+[ \t]+(["'])(.+?)\2[ \t]*$""")
#: A bare marker line, which opens and closes a block of one included path per line.
SNIPPET_BLOCK = re.compile(r"^[ \t]*(;*)-+8<-+[ \t]*$")


def _snippet_base_paths(root: Path) -> List[Path]:
    """The directories pymdownx.snippets resolves includes against, from `mkdocs.yml`.

    The extension's own default, the working directory, is the repository root when the site
    is built from it; that is also the answer when `mkdocs.yml` is absent or does not configure
    the extension.
    """
    mkdocs = root / "mkdocs.yml"
    if mkdocs.is_file():
        import yaml

        config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
        for extension in config.get("markdown_extensions") or []:
            if isinstance(extension, dict) and "pymdownx.snippets" in extension:
                base = (extension["pymdownx.snippets"] or {}).get("base_path", ["."])
                return [root / b for b in ([base] if isinstance(base, str) else base)]
    return [root]


def _snippet_names(text: str) -> List[str]:
    """Every path a page includes through pymdownx.snippets, in order.

    Fenced code is not masked: the extension is a preprocessor and expands an include inside a
    code fence, which is where every tutorial page puts its script.
    """
    names, in_block = [], False
    for line in text.splitlines():
        block = SNIPPET_BLOCK.match(line)
        if block:
            if not block.group(1):
                in_block = not in_block
            continue
        if in_block:
            name = line.strip()
            if name and not name.startswith(";"):
                names.append(name)
            continue
        inline = SNIPPET_INLINE.match(line)
        if inline and not inline.group(1):
            names.append(inline.group(3))
    return names


def _resolve_snippet(name: str, bases: List[Path]) -> Optional[Path]:
    """The file an include names, trying it whole and then without `:start:end` or `:section`."""
    candidates = [name]
    while ":" in candidates[-1]:
        candidates.append(candidates[-1].rsplit(":", 1)[0])
    for candidate in candidates:
        for base in bases:
            path = base / candidate
            if path.is_file():
                return path
    return None


def _included_sources(root: Path, pages: List[Path]) -> Tuple[List[Tuple[Path, Path]], List[str]]:
    """``(included file, page that includes it)`` for every snippet the pages pull in, recursively.

    A file is scanned whole even when a page includes only a line range or a section of it,
    because a range moves when the file is edited. An include that resolves to no file is
    returned as a violation: the extension drops it silently, and a sweep that cannot find a
    file cannot say it is clean.
    """
    bases = _snippet_base_paths(root)
    seen = set(pages)
    included: List[Tuple[Path, Path]] = []
    unresolved: List[str] = []
    queue = list(pages)
    while queue:
        page = queue.pop(0)
        for name in _snippet_names(page.read_text(encoding="utf-8")):
            if "://" in name:
                continue  # a remote include needs `url_download`, which the site does not enable
            path = _resolve_snippet(name, bases)
            if path is None:
                unresolved.append(
                    f"PROCESS_IDENTIFIER: {_rel(page, root)} includes {name!r}, which resolves to "
                    "no file under the snippet base path; the sweep cannot scan it"
                )
            elif path not in seen:
                seen.add(path)
                included.append((path, page))
                queue.append(path)
    return included, unresolved


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def check_no_process_identifiers_in_library(repo_root: Optional[Path] = None) -> List[str]:
    """Part of gate 14: no item or problem identifier in `jnwb/**/*.py`, `docs/**/*.md`,
    `README.md`, or any file a page includes through pymdownx.snippets.

    The head rule of `AGENTS.md` keeps internal process terminology out of the library surface,
    comments and docstrings included, and out of the published pages. Identifiers were the form
    it took there: behaviour was explained by citing the stack row that changed it, which tells a
    reader nothing. The scan is textual, so comments, docstrings and string constants are all
    covered.

    An included file is published as part of the page that includes it, so it is scanned too.
    The tutorial pages are almost entirely `--8<--` includes of `examples/tutorials/*.py`, and a
    scan of `docs/` alone saw none of that text. Includes resolve against the `base_path` that
    `mkdocs.yml` gives the extension.
    """
    root = repo_root or REPO_ROOT
    modules = sorted(
        py for py in (root / "jnwb").rglob("*.py") if "__pycache__" not in py.parts
    )
    if not modules:
        return [
            f"PROCESS_IDENTIFIER: no library source found to scan under {root / 'jnwb'}; the "
            "sweep is broken, not the tree"
        ]
    pages = sorted((root / "docs").rglob("*.md"))
    # README.md is the most-read page and carries the same obligation as docs/; it is scanned
    # itself and its includes are followed like any page's.
    readme = root / "README.md"
    scan_pages = pages + ([readme] if readme.is_file() else [])
    included, violations = _included_sources(root, scan_pages)
    targets = [(path, "") for path in modules + scan_pages]
    targets += [(path, f" (published by {_rel(page, root)})") for path, page in included]
    for path, via in targets:
        rel = _rel(path, root)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in PROCESS_IDENTIFIER.finditer(line):
                if _is_month_day(found.group(0)):
                    continue
                violations.append(
                    f"PROCESS_IDENTIFIER: {rel}:{lineno}{via} cites {found.group(0)!r}. State the "
                    "behaviour it stands for instead; the identifier means nothing to a reader "
                    "of the library."
                )
    return violations
