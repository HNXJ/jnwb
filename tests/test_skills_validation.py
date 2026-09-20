"""
tests/test_skills_validation.py -- Deterministic verification of canonical repository skills.
"""
from pathlib import Path
import ast
import dataclasses
import inspect
import re
try:
    import yaml
    def _yaml_load(s: str) -> dict:
        return yaml.safe_load(s)
except ImportError:
    try:
        import ruamel.yaml as ruamel_yaml
        _ryaml = ruamel_yaml.YAML(typ="safe")
        def _yaml_load(s: str) -> dict:
            return _ryaml.load(s)
    except ImportError:
        def _yaml_load(s: str) -> dict:
            res = {}
            for line in s.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res

import numpy as np
import pytest
import pandas as pd
import jnwb

CANONICAL_SKILLS = {
    "jnwb",
    "jnwb-fact-action",
    "jnwb-nwb-data",
    "jnwb-spiking",
    "jnwb-lfp-spectral",
    "jnwb-statistics",
    "jnwb-population",
    "jnwb-connectivity",
    "jnwb-figures",
}

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"
DOCS_DIR = ROOT_DIR / "docs"


def test_canonical_skills_directories_exist():
    """Verify exactly the 9 intended canonical skill directories exist."""
    assert SKILLS_DIR.exists(), f"Skills directory missing: {SKILLS_DIR}"
    actual_skills = {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}
    assert actual_skills == CANONICAL_SKILLS, f"Skills mismatch: {actual_skills ^ CANONICAL_SKILLS}"


def test_skills_frontmatter_and_openai_yaml():
    """Verify each skill has valid YAML frontmatter in SKILL.md and agents/openai.yaml."""
    for skill_name in CANONICAL_SKILLS:
        skill_path = SKILLS_DIR / skill_name
        skill_md = skill_path / "SKILL.md"
        agent_yaml = skill_path / "agents" / "openai.yaml"

        assert skill_md.exists(), f"Missing SKILL.md for {skill_name}"
        assert agent_yaml.exists(), f"Missing agents/openai.yaml for {skill_name}"

        # Parse frontmatter from SKILL.md
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{skill_name}/SKILL.md missing frontmatter start"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{skill_name}/SKILL.md malformed frontmatter"
        frontmatter = _yaml_load(parts[1])
        assert isinstance(frontmatter, dict)
        assert frontmatter.get("name") == skill_name
        assert "description" in frontmatter and len(frontmatter["description"]) > 10

        # Parse agents/openai.yaml
        agent_data = _yaml_load(agent_yaml.read_text(encoding="utf-8"))
        assert isinstance(agent_data, dict)
        assert "interface" in agent_data
        assert agent_data["interface"].get("display_name") == skill_name
        assert "description" in agent_data["interface"]
        assert agent_data.get("policy", {}).get("allow_implicit_invocation") is True


#: Every inline ``jnwb.name(`` occurrence, counted by a pattern that does no parsing.
#: `_routing_calls` walks parentheses to extract arguments; this one only finds openings.
#: Two independent readings of the same corpus, which is the point -- see
#: `test_every_inline_routing_call_is_reached_by_the_parser`.
_CALL_OPENING = re.compile(r"`jnwb\.(?:\w+\.)*\w+\(")


def _routing_matrix_section(skill_text: str) -> str:
    """The text routing rows are read from: the whole file.

    This used to return only the ``## 2. Task-to-Primitive Routing Matrix`` window, so a
    default-bearing row written anywhere else was invisible. Widening it to the whole file
    changed the corpus from 116 rows to 116: **no row currently lives outside the window**,
    in any of the nine skills. The widening is therefore worth nothing today and is kept
    because it removes the class rather than the instance -- a row added to ``## 3.`` is now
    checked instead of silently skipped.

    Fenced code blocks stay out on their own: every pattern here requires a leading
    backtick, and a ``## 4. Minimal Workflow`` block is not inline code. That is why the two
    counts agree rather than the window having been doing useful work.
    """
    return skill_text


def _routing_calls(skill_text: str):
    r"""Every ``jnwb.name(...)`` in the routing matrix, with balanced parentheses.

    The previous pattern was ``\(([^)]*)\)``, which cannot span a nested parenthesis, so
    it silently skipped every row carrying a tuple default -- 7 of the 61 rows, including
    ``assign_outer_folds``, ``zflip``, ``wpli`` and ``save_figure_suite``. A row that is not
    matched is not checked, and nothing said so.
    """
    section = _routing_matrix_section(skill_text)
    # Dotted attributes too: `jnwb.StatisticalAnalysis.exploratory_compare(...)` did not match
    # `jnwb\.(\w+)\(` at all, so every StatisticalAnalysis row went unchecked -- which is how
    # a row stating n_bootstrap=10000 against a live default of 2000 passed this file.
    for match in re.finditer(r"`jnwb\.((?:\w+\.)*\w+)\(", section):
        depth, i = 1, match.end()
        while i < len(section) and depth:
            depth += {"(": 1, ")": -1}.get(section[i], 0)
            i += 1
        if depth == 0:
            yield match.group(1), section[match.end():i - 1]


def _mentioned_parameters(args_str: str):
    """(name, written_default_or_None, written_positionally) for each argument in a row.

    ``...`` as a value means the row is declining to state the default, which is allowed;
    it is returned as the string ``"..."`` and compared against nothing.
    """
    out, depth, token, keyword_only = [], 0, "", False
    for ch in args_str + ",":
        if ch == "," and depth == 0:
            token = token.strip()
            if token == "*":
                # Everything a row writes after a bare * is keyword-only, as in the signature.
                keyword_only = True
            elif token and token not in ("...", "/") and not token.startswith("**"):
                name, sep, default = token.partition("=")
                name = name.split(":")[0].strip()
                out.append((name, default.strip() if sep else None,
                            not sep and not keyword_only))
            token = ""
            continue
        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(ch, 0)
        token += ch
    return out


def _is_enumeration(written: str) -> bool:
    """``scheme="within_group"|"global"`` states the admissible values, not a default.

    A row may say what a required argument accepts; that is routing information and the
    reason several rows use this notation. It is not a claim about a default, so the default
    checks do not apply to it -- but the parameter must still exist and still be in order.
    """
    return "|" in written


def _live_default_matches(live, written: str) -> bool:
    """Compare a stated default against the live one by value, then by text."""
    try:
        return ast.literal_eval(written) == live
    except (ValueError, SyntaxError):
        return str(live) == written


def test_skill_routing_signatures_match_runtime():
    """Routing rows must be callable as written, not merely name real parameters.

    The previous test asserted ``pname in sig.parameters`` and nothing else. Every one of
    these passed it: ``paired_fire_prob_test(fires_null, fires_target, ...)`` with the first
    two arguments swapped, which negates ``risk_difference`` and raises nothing;
    ``epoch_continuous(data, onsets, win_s, fs)`` against a keyword-only signature;
    ``nested_cv_linear_svm(..., n_splits=5)`` where ``n_splits`` has no default;
    ``band_power(..., normalize=False)`` where the live default is ``True`` and raises
    without a baseline.
    """
    checked = 0
    for skill_name in CANONICAL_SKILLS:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for func_name, args_str in _routing_calls(content):
            target = jnwb
            for attr in func_name.split("."):
                assert hasattr(target, attr), (
                    f"{skill_name}: jnwb.{func_name} referenced in routing matrix is missing"
                )
                target = getattr(target, attr)
            checked += 1
            sig = inspect.signature(target)
            order = list(sig.parameters)
            written = _mentioned_parameters(args_str)
            where = f"{skill_name}: jnwb.{func_name}({args_str})"

            for name, default, positional in written:
                param = sig.parameters.get(name)
                assert param is not None, (
                    f"{where} has no parameter {name!r}; live: {order!r}"
                )
                if positional:
                    assert param.kind is not param.KEYWORD_ONLY, (
                        f"{where} passes {name!r} positionally, but it is keyword-only"
                    )
                # `rng=...` says "pass something here", not "the default is ...", so it
                # states nothing about a default and is checked for neither.
                if default is not None and default != "..." and not _is_enumeration(default):
                    assert param.default is not param.empty, (
                        f"{where} gives {name}={default}, but {name!r} has no default"
                    )
                    assert _live_default_matches(param.default, default), (
                        f"{where} gives {name}={default}; the live default is "
                        f"{param.default!r}"
                    )

            # Only positionally written arguments have an order to be wrong about: a row
            # that writes `groups=None, scheme=...` is calling by keyword, and keyword order
            # is free. A positional argument, though, binds by position, so the k-th one
            # written must be the k-th parameter -- which is what
            # `paired_fire_prob_test(fires_null, fires_target, ...)` was not.
            for k, name in enumerate(n for n, _, positional in written if positional):
                assert order.index(name) == k, (
                    f"{where} passes {name!r} as positional argument {k}, but it is "
                    f"parameter {order.index(name)} of {order!r}"
                )

            required = [
                n for n, p in sig.parameters.items()
                if p.default is p.empty
                and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            ]
            named = {n for n, _, _ in written}
            missing = [n for n in required if n not in named]
            assert not missing, (
                f"{where} omits required parameter(s) {missing!r}; a reader copying this row "
                f"gets a TypeError, or supplies them in the wrong order"
            )

    assert checked >= 65, (
        f"only {checked} routing rows were matched; rows that are not matched are not "
        f"checked, which is how 7 tuple-bearing rows and 4 StatisticalAnalysis rows went "
        f"unread"
    )


def test_every_inline_routing_call_is_reached_by_the_parser():
    """The parser must read every routing row that exists, not every row it can parse.

    `_routing_calls` decides its own corpus twice over: it picks a section, then walks
    parentheses, and a row lost at either step is a row nothing checks. That has happened --
    7 tuple-bearing rows and 4 dotted `StatisticalAnalysis` rows were each silently dropped,
    and the count assertion below them stayed green because it only ever saw the survivors.

    So the corpus here is counted by `_CALL_OPENING`, which finds call openings and parses
    nothing. A test whose case set comes from the machinery under test cannot reach the case
    that machinery loses; these two readings are independent, so a divergence is a dropped
    row and names the skill it was dropped from.
    """
    divergences = []
    total_found = 0
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        found = len(_CALL_OPENING.findall(content))
        parsed = len(list(_routing_calls(content)))
        total_found += found
        if found != parsed:
            divergences.append(
                f"{skill_name}: {found} inline `jnwb.<name>(` openings in the file, "
                f"{parsed} reached by _routing_calls"
            )
    assert divergences == [], (
        "routing rows exist that the parser never yields, so nothing checks them: "
        + "; ".join(divergences)
    )
    assert total_found >= 65, (
        f"only {total_found} routing rows found in the whole skill corpus; agreement "
        f"between two readings of an empty corpus is not evidence of anything"
    )


#: `jnwb.<name>` references that are not public API and are not routing targets.
#: `__all__` and `__version__` are the package's own metadata, named when a skill talks
#: about the API rather than routing to a function.
_PACKAGE_METADATA = re.compile(r"^__\w+__$")

#: Known breaches of the publicity invariant, owned elsewhere. Asserted by **equality**:
#: a new private route fails, and repairing one of these without deleting its entry also
#: fails, so the quarantine cannot outlive the defect.
#:
#: P-59: `skills/jnwb-nwb-data/SKILL.md` routes at `jnwb.nwb_inspect.CONTINUOUS_KEYS`.
#: `nwb_inspect` is a submodule, reachable by attribute and absent from `__all__`. The
#: skill file is not this lane's to edit; the proxy in this test was.
_NON_PUBLIC_ROUTES_PENDING_REPAIR = {
    ("jnwb-nwb-data", "nwb_inspect"),
}


def test_all_referenced_symbols_exist():
    """A routed symbol must be *public*, not merely reachable by attribute.

    This asserted `hasattr(jnwb, symbol)` and nothing else. Every submodule satisfies that,
    so the test green-lit `jnwb.nwb_inspect.CONTINUOUS_KEYS` -- a private constant behind a
    submodule that `__all__` does not export and `docs/` does not document. Reachability is
    the proxy; membership of `__all__` is the invariant, because `__all__` is what
    `AGENTS.md` section 0 calls the authoritative symbol list and what the API docs are
    generated from. An import that works today and is renamed tomorrow without a
    deprecation is exactly what routing an agent at a non-export buys.

    Both halves are asserted: a name in `__all__` that does not resolve is equally a broken
    route, and asserting only membership would trade one proxy for another.
    """
    pattern = re.compile(r"\bjnwb\.([a-zA-Z0-9_]+)")
    public = set(jnwb.__all__)

    checked = 0
    breaches = set()
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for symbol in pattern.findall(content):
            if _PACKAGE_METADATA.match(symbol):
                continue
            checked += 1
            assert hasattr(jnwb, symbol), (
                f"jnwb.{symbol} referenced in {skill_name} does not resolve"
            )
            if symbol not in public:
                breaches.add((skill_name, symbol))

    assert checked >= 100, (
        f"only {checked} jnwb.<symbol> references were examined across the skill corpus; "
        f"a pattern that stops matching passes this test without checking anything"
    )
    assert breaches == _NON_PUBLIC_ROUTES_PENDING_REPAIR, (
        "skills route at symbols that jnwb.__all__ does not export.\n"
        f"  newly private: {sorted(breaches - _NON_PUBLIC_ROUTES_PENDING_REPAIR)}\n"
        f"  repaired, delete from the quarantine: "
        f"{sorted(_NON_PUBLIC_ROUTES_PENDING_REPAIR - breaches)}"
    )

    unresolved = [s for s in jnwb.__all__ if not hasattr(jnwb, s)]
    assert unresolved == [], f"jnwb.__all__ exports names that do not resolve: {unresolved}"


#: A row saying the return is of some named type, optionally naming fields on it.
_CLAIM_RETURN_TYPE = re.compile(
    r"[Rr]eturn(?:s|ing)\s+`([A-Z]\w*)`(?:\s+with\s+((?:`\w+`(?:,\s*)?(?:and\s+)?)+))?"
)
#: A row saying the return carries a record of something.
_CLAIM_CARRIES = re.compile(r"\b(?:named|recorded) in the result\b", re.I)
#: A row saying the return carries no record -- the negative of the above, and equally a
#: claim about contents. An agent acts on it by storing the choice itself.
_CLAIM_BARE_ARRAY = re.compile(r"\bbare array\b", re.I)
_CLAIM_RECORDS_NO = re.compile(r"\brecords no (\w+)\b", re.I)


def _probe_complex_tfr():
    rng = np.random.default_rng(7)
    return jnwb.complex_tfr(rng.normal(size=(2, 128)), fs=1000.0,
                            freqs=np.array([10.0, 20.0, 40.0]))


def _probe_vflip():
    freqs = np.linspace(1.0, 150.0, 80)
    psd = np.stack([
        (3.0 if c < 8 else 0.5) * np.exp(-((freqs - 20.0) ** 2) / 50.0)
        + (0.5 if c < 8 else 3.0) * np.exp(-((freqs - 90.0) ** 2) / 400.0)
        + 1.0 / freqs
        for c in range(16)
    ])
    return jnwb.vflip(psd, freqs)


def _probe_xflip():
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=300), rng.normal(size=300)
    data = np.stack([(a if c < 6 else b) + 0.3 * rng.normal(size=300) for c in range(12)])
    return jnwb.xflip(data, n_surrogates=20, rng=np.random.default_rng(1))


def _probe_aperiodic_fit():
    freqs = np.linspace(2.0, 100.0, 60)
    return jnwb.aperiodic_fit(freqs, 10.0 * freqs ** -1.5, (2.0, 100.0))


def _probe_directed_connectivity():
    rng = np.random.default_rng(11)
    X = rng.normal(size=200)
    Y = np.zeros(200)
    Y[1:] = 0.5 * X[:-1] + 0.5 * rng.normal(size=199)
    return jnwb.directed_connectivity(X, Y, method="granger", order=2,
                                      n_surrogates=10, seed=42)


def _probe_relative_power():
    rng = np.random.default_rng(5)
    return jnwb.relative_power(rng.random((4, 8)) + 1.0, rng.random((4, 8)) + 1.0,
                               model="mean_of_ratios", axis=1)


#: One executed call per routed symbol that makes a claim about its return's contents.
#: The oracle is the returned object. A return *annotation* would be the same authors'
#: second claim about the same thing, and `-> ComplexTFR` on a function that returns a
#: dict reads identically to one that does not.
_RETURN_CONTENT_PROBES = {
    "complex_tfr": _probe_complex_tfr,
    "vflip": _probe_vflip,
    "xflip": _probe_xflip,
    "aperiodic_fit": _probe_aperiodic_fit,
    "directed_connectivity": _probe_directed_connectivity,
    "relative_power": _probe_relative_power,
}


def _is_record(obj) -> bool:
    """Can this object carry a named field at all?"""
    return dataclasses.is_dataclass(type(obj)) or hasattr(type(obj), "_fields")


def _return_content_claims():
    """(skill, line, symbol, kind, payload) for every claim a row makes about its return."""
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), 1):
            head = re.match(r"- `jnwb\.((?:\w+\.)*\w+)\(", line)
            if not head:
                continue
            sym = head.group(1)
            for m in _CLAIM_RETURN_TYPE.finditer(line):
                fields = re.findall(r"`(\w+)`", m.group(2)) if m.group(2) else []
                yield skill_name, line_no, sym, "type", (m.group(1), fields)
            if _CLAIM_CARRIES.search(line):
                yield skill_name, line_no, sym, "carries", None
            if _CLAIM_BARE_ARRAY.search(line):
                yield skill_name, line_no, sym, "bare", None
            for m in _CLAIM_RECORDS_NO.finditer(line):
                yield skill_name, line_no, sym, "records_no", m.group(1)


def test_skill_return_contents_claims_match_runtime():
    """What a row says the return *contains* is settled by calling it.

    The signature harness above reads `inspect.signature`, so it cannot see one word of
    this: `relative_power` was documented as naming its estimand in the result, and returns
    a bare `float64` array with no `model` anywhere on it. `mean_of_ratios` and
    `ratio_of_means` differ by 7% on the same input here, so an agent that believed the row
    had no way to tell two different quantities apart downstream.

    The case set is the skill text, because the skill text is the claim; the oracle is the
    live call, because the library is the truth. Every claim must have a probe -- a claim
    nobody executes is the defect, not an exemption -- and both directions are checked, so
    a row asserting an absence fails once the API grows the field.
    """
    claims = list(_return_content_claims())
    assert len(claims) >= 5, (
        f"only {len(claims)} return-contents claims were recognised in the skill corpus; "
        f"a claim pattern that stops matching passes this test by finding nothing"
    )

    uncovered = sorted({c[2] for c in claims} - set(_RETURN_CONTENT_PROBES))
    assert uncovered == [], (
        f"these routed symbols claim something about their return and no probe calls them, "
        f"so the claim is unverified: {uncovered}"
    )

    live = {name: probe() for name, probe in _RETURN_CONTENT_PROBES.items()}

    for skill_name, line_no, sym, kind, payload in claims:
        out = live[sym]
        where = f"{skill_name}/SKILL.md:{line_no} jnwb.{sym}"
        if kind == "type":
            claimed_type, claimed_fields = payload
            assert type(out).__name__ == claimed_type, (
                f"{where} says it returns `{claimed_type}`; the call returns "
                f"{type(out).__name__}"
            )
            missing = [f for f in claimed_fields if not hasattr(out, f)]
            assert not missing, (
                f"{where} names {missing!r} on the returned `{claimed_type}`; the object "
                f"has no such attribute"
            )
        elif kind == "carries":
            assert _is_record(out), (
                f"{where} says a value is named in the result, but the call returns "
                f"{type(out).__name__}, which carries no named field at all"
            )
        elif kind == "bare":
            assert not _is_record(out), (
                f"{where} calls the return a bare array; the call returns "
                f"{type(out).__name__}, which does carry named fields -- the row now "
                f"understates what an agent can read back"
            )
        elif kind == "records_no":
            assert not hasattr(out, payload), (
                f"{where} says the return records no {payload!r}; the returned "
                f"{type(out).__name__} has that attribute, so the row is stale"
            )


def test_all_referenced_docs_paths_exist():
    """Verify every referenced docs/*.md file exists in docs/."""
    pattern = re.compile(r"docs/(\d\d_[a-zA-Z0-9_]+\.md)")

    for skill_name in CANONICAL_SKILLS:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        matches = pattern.findall(content)

        for doc_file in matches:
            target_path = DOCS_DIR / doc_file
            assert target_path.exists(), f"Doc file {doc_file} referenced in {skill_name} missing at {target_path}"


def test_no_forbidden_skill_trees_or_ide_authority():
    """Verify no .claude/skills, .cursor, or .agents directory exists in skills/ or acts as skill authority."""
    assert not (SKILLS_DIR / ".claude").exists()
    assert not (SKILLS_DIR / ".cursor").exists()
    assert not (SKILLS_DIR / ".agents").exists()
    assert not (ROOT_DIR / ".claude" / "skills").exists()


def test_no_omission_leakage_in_generic_skills():
    """Verify generic skills contain no omission-specific semantics or terms."""
    forbidden_terms = [
        "omission_identity",
        "condition_code",
        "target_trial",
        "cue_onset",
        "sub-C31o",
        "ses-230831",
    ]

    for skill_name in CANONICAL_SKILLS:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term.lower() not in content, f"Forbidden term '{term}' leaked into generic skill {skill_name}"


def test_representative_routing_probes():
    """Run representative routing probes across all 7 domain areas."""
    rng = np.random.default_rng(42)

    # 1. NWB metadata & addressing
    elec_df = pd.DataFrame({"location": ["V1"], "z": [1200.0], "depth_unit": ["um"]}, index=[10])
    assert jnwb.map_peak_channel_to_area(10, elec_df) == "V1"
    assert jnwb.classify_layer_from_depth(10, elec_df) == "Deep"

    # 2. PSTH & onset fitting
    spikes = np.sort(rng.uniform(0.0, 10.0, 100))
    events = np.array([1.0, 3.0, 5.0, 7.0])
    time_bins, rate_hz, _ = jnwb.raster_psth(spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0)
    smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
    fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 200.0))
    assert "t0" in fit and "bound_status" in fit

    # 3. Complex TFR & accumulator
    fs = 1000.0
    freqs = np.array([10.0, 20.0, 40.0])
    acc = jnwb.TFRAccumulator(shape=(2, len(freqs), 100))
    for _ in range(3):
        trial = rng.normal(size=(2, 100))
        tfr = jnwb.complex_tfr(trial, fs=fs, freqs=freqs)
        acc.add_trial(tfr.z, valid=tfr.coi_mask)
    assert acc.power().shape == (2, len(freqs), 100)

    # 4. Permutation & statistics
    g1 = rng.normal(1.0, 1.0, 20)
    g2 = rng.normal(0.0, 1.0, 20)
    res = jnwb.StatisticalAnalysis.compare_groups(g1, g2)
    p_raw = res["parametric"]["pval"]
    q_vals = jnwb.StatisticalAnalysis.fdr_correct([p_raw, 0.04, 0.01])
    assert len(q_vals) == 3
    labels = np.array([0, 1, 0, 1])
    groups = np.array([1, 1, 2, 2])
    plan = jnwb.build_permutation_plan(labels, groups, n_permutations=5, seed=42)
    assert plan["n_permutations"] == 5

    # 5. Decoding
    X = rng.normal(size=(30, 10))
    y = np.array([0] * 15 + [1] * 15)
    dec = jnwb.nested_cv_linear_svm(X, y, n_splits=3)
    assert dec["accuracy"] >= 0.0

    # 6. Directional coupling
    T = 200
    X_ts = rng.normal(size=T)
    Y_ts = np.zeros(T)
    Y_ts[1:] = 0.5 * X_ts[:-1] + 0.5 * rng.normal(size=T - 1)
    gr = jnwb.granger(X_ts, Y_ts, order=2, n_surrogates=10, seed=42)
    assert gr.x_to_y >= 0.0

    # 7. Publication graphics
    jnwb.setup_vector_graphics()


class TestSkillsDoNotCarryDriftingCounts:
    """A count written into a skill file goes stale silently and misleads an agent.

    skills/jnwb/SKILL.md claimed "All 101 exports resolve" against a live 111, and
    "passes 446+ tests" against 527. Both had drifted without failing anything.
    """

    SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills"

    def _skill_files(self):
        files = sorted(self.SKILL_ROOT.glob("*/SKILL.md"))
        assert files, "no skill files found; this test would pass vacuously"
        return files

    def test_no_hardcoded_export_or_test_counts(self):
        patterns = [
            re.compile(r"\b\d{2,5}\s+(?:public\s+|exported\s+)?(?:exports?|symbols?)\b", re.I),
            re.compile(r"\b\d{2,5}\+?\s+tests?\b", re.I),
            re.compile(r"\bpasses\s+\d{2,5}", re.I),
        ]
        offenders = []
        for path in self._skill_files():
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(p.search(line) for p in patterns):
                    offenders.append(f"{path.parent.name}/SKILL.md:{line_no}: {line.strip()}")
        assert offenders == [], (
            "skill files must not state counts; run the check and let jnwb.__all__ be the "
            "source of truth: " + "; ".join(offenders)
        )

    def test_skills_do_not_reference_a_removed_docs_toolchain(self):
        """A skill telling an agent to run a command that no longer exists wastes a turn."""
        repo_root = self.SKILL_ROOT.parent
        has_sphinx = (repo_root / "docs" / "conf.py").exists()
        offenders = []
        for path in self._skill_files():
            text = path.read_text(encoding="utf-8")
            if "sphinx" in text.lower() and not has_sphinx:
                offenders.append(path.parent.name)
        assert offenders == [], (
            f"these skills reference sphinx, which this repo no longer builds: {offenders}"
        )


class TestAmbiguousUnitProbes:
    """0.2.4-09: a skill that routes on depth must not let a unit be guessed.

    Depth in a cortical column is the one quantity where a factor of 1000 still looks
    plausible: 1200 um and 1.2 mm are the same place, and 1.2 um is a different answer
    rather than an obviously broken one. These pin that jnwb never infers the unit from
    the magnitude, that declaring the wrong one changes the answer, and that an
    undeclared or unsupported unit yields no classification at all.
    """

    @staticmethod
    def _row(z, unit=None, index=10):
        data = {"location": ["V1"], "z": [z]}
        if unit is not None:
            data["depth_unit"] = [unit]
        return pd.DataFrame(data, index=[index])

    def test_the_same_physical_depth_classifies_the_same_in_either_unit(self):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, "um")) == "Deep"
        assert jnwb.classify_layer_from_depth(10, self._row(1.2, "mm")) == "Deep"

    def test_the_unit_is_never_inferred_from_the_magnitude(self):
        """1.2 declared as um is 1.2 um, not a mislabelled 1.2 mm."""
        assert jnwb.classify_layer_from_depth(10, self._row(1.2, "um")) == "Superficial"

    def test_an_undeclared_unit_is_not_guessed(self):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0)) == "Unknown"

    @pytest.mark.parametrize("unit", ["furlong", "", "px"])
    def test_an_unsupported_unit_refuses_to_classify(self, unit):
        """Documented invariant: unknown or unsupported units give 'Unknown', never a
        layer. A wrong label here would be silently wrong; 'Unknown' is visibly missing."""
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, unit)) == "Unknown"

    @pytest.mark.parametrize("spelling", ["um", "UM", " um ", "micron", "microns", "micrometer"])
    def test_accepted_spellings_agree(self, spelling):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, spelling)) == "Deep"

    def test_an_explicit_argument_overrides_a_conflicting_table_column(self):
        """Evidence conflict with a deterministic, documented resolution: the caller's
        explicit declaration wins, and the outcome differs, so the conflict is never
        silently averaged or ignored."""
        table_mm = self._row(1200.0, "mm")
        assert jnwb.classify_layer_from_depth(10, table_mm) == "Unknown"
        assert jnwb.classify_layer_from_depth(10, table_mm, depth_unit="um") == "Deep"

    def test_probe_geometry_takes_the_declared_unit_literally(self):
        """Millimetre coordinates declared as micrometres give a 0.05 um pitch rather
        than a silently corrected one. The library does not second-guess the caller, so a
        skill must declare the unit it actually has."""
        millimetres = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 0.05, 0.10, 0.15]}
        )
        assert jnwb.probe_geometry(millimetres, units="um").nominal_pitch == pytest.approx(0.05)
        micrometres = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 50.0, 100.0, 150.0]}
        )
        assert jnwb.probe_geometry(micrometres, units="um").nominal_pitch == pytest.approx(50.0)

    def test_probe_geometry_rejects_an_unsupported_unit(self):
        table = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 50.0, 100.0, 150.0]}
        )
        with pytest.raises(ValueError, match="(?i)unit"):
            jnwb.probe_geometry(table, units="furlong")


class TestEvidenceConflictProbes:
    """0.2.4-09: the fact stack is human-authorized, and nothing may quietly edit it."""

    def test_no_shipped_code_writes_the_fact_stack(self):
        """`jnwb-fact-action` states that agents may read and challenge facts but must
        never autonomously add, edit or delete them. That is only a rule if no code path
        can do it."""
        offenders = []
        for path in list(Path("jnwb").rglob("*.py")) + list(Path("scripts").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "fact_stack" in text and re.search(r"write_text|write_bytes|open\([^)]*['\"][wa]", text):
                offenders.append(str(path))
        assert not offenders, f"code that could rewrite the fact stack: {offenders}"

    # Both read through SKILLS_DIR rather than a bare relative path: a path relative to
    # the current directory resolves only when pytest is run from the repository root.
    def test_the_conflict_rule_is_still_stated_in_the_skill(self):
        text = (SKILLS_DIR / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "MUST NOT autonomously add, edit, or delete facts" in text
        assert "empirical receipts and discriminating tests" in text

    def test_conflicting_conclusions_are_resolved_by_receipts_not_consensus(self):
        text = (SKILLS_DIR / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "never through voting or consensus" in text
