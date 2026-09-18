"""
tests/test_skills_validation.py -- Deterministic verification of canonical repository skills.
"""
from pathlib import Path
import ast
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
    """Verify exactly the 8 intended canonical skill directories exist."""
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


def _routing_matrix_section(skill_text: str) -> str:
    if "## 2. Task-to-Primitive Routing Matrix" not in skill_text:
        return ""
    return skill_text.split("## 2. Task-to-Primitive Routing Matrix", 1)[1].split("## 3.", 1)[0]


def _routing_calls(skill_text: str):
    r"""Every ``jnwb.name(...)`` in the routing matrix, with balanced parentheses.

    The previous pattern was ``\(([^)]*)\)``, which cannot span a nested parenthesis, so
    it silently skipped every row carrying a tuple default -- 7 of the 61 rows, including
    ``assign_outer_folds``, ``zflip``, ``wpli`` and ``save_figure_suite``. A row that is not
    matched is not checked, and nothing said so.
    """
    section = _routing_matrix_section(skill_text)
    for match in re.finditer(r"`jnwb\.(\w+)\(", section):
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
            assert hasattr(jnwb, func_name), (
                f"{skill_name}: jnwb.{func_name} referenced in routing matrix is missing"
            )
            checked += 1
            sig = inspect.signature(getattr(jnwb, func_name))
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

    assert checked >= 61, (
        f"only {checked} routing rows were matched; rows that are not matched are not "
        f"checked, which is how 7 of them went unread"
    )


def test_all_referenced_symbols_exist():
    """Verify every jnwb.<symbol> referenced in skills exists in jnwb package."""
    pattern = re.compile(r"\bjnwb\.([a-zA-Z0-9_]+)")

    for skill_name in CANONICAL_SKILLS:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        matches = pattern.findall(content)

        for symbol in matches:
            assert hasattr(jnwb, symbol), f"Symbol jnwb.{symbol} referenced in {skill_name} does not exist!"


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

    def test_the_conflict_rule_is_still_stated_in_the_skill(self):
        text = Path("skills/jnwb-fact-action/SKILL.md").read_text(encoding="utf-8")
        assert "MUST NOT autonomously add, edit, or delete facts" in text
        assert "empirical receipts and discriminating tests" in text

    def test_conflicting_conclusions_are_resolved_by_receipts_not_consensus(self):
        text = Path("skills/jnwb-fact-action/SKILL.md").read_text(encoding="utf-8")
        assert "never through voting or consensus" in text
