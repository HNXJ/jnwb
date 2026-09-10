"""
tests/test_skills_validation.py -- Deterministic verification of canonical repository skills.
"""
from pathlib import Path
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
import pandas as pd
import jnwb

CANONICAL_SKILLS = {
    "jnwb",
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
    section = _routing_matrix_section(skill_text)
    pattern = re.compile(r"`jnwb\.(\w+)\(([^)]*)\)`")
    for match in pattern.finditer(section):
        yield match.group(1), match.group(2)


def _mentioned_parameter_names(args_str: str) -> list[str]:
    names = []
    for part in args_str.split(","):
        token = part.strip()
        if not token or token in ("...", "*") or token.startswith("**"):
            continue
        if "=" in token:
            names.append(token.split("=")[0].strip())
        elif ":" in token:
            names.append(token.split(":")[0].strip())
        else:
            names.append(token)
    return names


def test_skill_routing_parameter_names_match_runtime():
    """Routing rows must name real parameters, not invented signatures."""
    for skill_name in CANONICAL_SKILLS:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for func_name, args_str in _routing_calls(content):
            assert hasattr(jnwb, func_name), (
                f"{skill_name}: jnwb.{func_name} referenced in routing matrix is missing"
            )
            sig = inspect.signature(getattr(jnwb, func_name))
            valid = set(sig.parameters)
            for pname in _mentioned_parameter_names(args_str):
                assert pname in valid, (
                    f"{skill_name}: jnwb.{func_name} has no parameter '{pname}' "
                    f"(routing: {args_str!r}; valid: {sorted(valid)!r})"
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
    elec_df = pd.DataFrame({"location": ["V1"], "z": [1200.0]}, index=[10])
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
