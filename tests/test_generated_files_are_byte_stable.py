r"""Generated tracked files must not depend on the platform that generated them.

`Path.write_text` without `newline=` emits `os.linesep`, so a generator run on Windows writes
CRLF and the same generator on Linux writes LF. With `core.autocrlf=false` and no
`.gitattributes` in this repository, those bytes go straight into the blob: running a
generator on the other half of the CI matrix rewrote every line of its own tracked output.

`check_api_md_is_generated` could not see it. It compares `api_path.read_text()` against the
generator's string, and `read_text` normalizes every ending to `\n`, so the check passed
before and after a whole-file churn. A test of this property therefore cannot use `read_text`
anywhere -- every assertion below reads bytes.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The tracked files a script in this repository regenerates, and the scripts that write them.
# TestTheTwoListsDescribeEachOther keeps the pair honest: a new generated file that no listed
# writer names, or a writer that names none of these files, fails rather than passing quietly.
GENERATED_FILES = (
    "docs/api.md",
    "artifacts/benchmarks/import_profile.txt",
    "artifacts/benchmarks/import_breakdown.json",
    "artifacts/benchmarks/vflip_calibration_0.2.4.md",
    "artifacts/benchmarks/vflip_calibration_0.2.4_raw.json",
)

WRITERS = (
    "scripts/generate_api_md.py",
    "scripts/benchmark_import.py",
    "scripts/calibrate_vflip.py",
)


def text_writes_without_newline(source: str) -> list[int]:
    r"""Line numbers of text-mode writes that let the platform choose the line ending.

    Found in the syntax tree rather than by grep: `write_text(...)` and `open(..., "w")`
    both translate `\n` to `os.linesep` unless `newline=` is passed, and a regex over the
    call text cannot tell a keyword that is present from one that merely appears nearby.
    """
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else None)
        if name not in ("write_text", "open"):
            continue
        if name == "open":
            # The positional mode sits at a different index in the two call forms:
            # `open(path, "w")` carries it at args[1], `Path(path).open("w")` at args[0].
            # Reading only args[1] missed every attribute-form call, which is how this
            # sweep passed over constructed input that contains one.
            mode = ""
            positional = 1 if isinstance(node.func, ast.Name) else 0
            if len(node.args) > positional and isinstance(node.args[positional], ast.Constant):
                mode = node.args[positional].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            # A mode, not any string containing "w": the attribute form's first positional
            # argument is a mode for `Path(p).open("w")` and a member name for
            # `zipfile.open("workflow.yml")`, and only the first is made of mode characters.
            if not (isinstance(mode, str) and mode and set(mode) <= set("rwxabt+")
                    and "w" in mode and "b" not in mode):
                continue
        if not any(kw.arg == "newline" for kw in node.keywords):
            offenders.append(node.lineno)
    return offenders


class TestTheSweepFindsWhatItIsFor:
    """The live scripts are clean, so the sweep must be driven over a defect too."""

    def test_it_flags_a_write_text_that_omits_newline(self):
        assert text_writes_without_newline(
            'from pathlib import Path\nPath("x").write_text("a\\n", encoding="utf-8")\n'
        ) == [2]

    def test_it_accepts_a_write_text_that_passes_newline(self):
        assert text_writes_without_newline(
            'from pathlib import Path\n'
            'Path("x").write_text("a\\n", encoding="utf-8", newline="\\n")\n'
        ) == []

    def test_it_flags_text_mode_open_and_ignores_binary(self):
        assert text_writes_without_newline('open("x", "w").write("a")\n') == [1]
        assert text_writes_without_newline('open("x", "wb").write(b"a")\n') == []

    def test_a_keyword_named_elsewhere_does_not_count_as_passing_newline(self):
        """The reason this reads the tree: `newline` appears, but not as this call's keyword."""
        assert text_writes_without_newline(
            'newline = "\\n"\nopen("x", "w").write(newline)\n'
        ) == [2]


class TestTheTwoListsDescribeEachOther:
    def test_every_generated_file_is_named_by_a_listed_writer(self):
        sources = {rel: (REPO_ROOT / rel).read_text(encoding="utf-8") for rel in WRITERS}
        unclaimed = [
            rel for rel in GENERATED_FILES
            if not any(Path(rel).name in src for src in sources.values())
        ]
        assert not unclaimed, f"no listed writer names {unclaimed}"

    def test_every_listed_writer_names_a_generated_file(self):
        basenames = {Path(rel).name for rel in GENERATED_FILES}
        idle = [
            rel for rel in WRITERS
            if not any(name in (REPO_ROOT / rel).read_text(encoding="utf-8")
                       for name in basenames)
        ]
        assert not idle, f"{idle} generate none of the files this module pins"


class TestGeneratorsPinTheirLineEndings:
    @pytest.mark.parametrize("rel", WRITERS)
    def test_no_generator_lets_the_platform_choose(self, rel: str):
        offenders = text_writes_without_newline(
            (REPO_ROOT / rel).read_bytes().decode("utf-8"))
        assert not offenders, (
            f"{rel} lines {offenders} write text without newline=; on Linux they emit LF and "
            f"on Windows CRLF, so regenerating rewrites every line of a tracked file"
        )


class TestGeneratedFilesAreLf:
    @pytest.mark.parametrize("rel", GENERATED_FILES)
    def test_the_stored_bytes_contain_no_carriage_return(self, rel: str):
        """The index, not the working tree.

        An earlier version of this test read the file from disk and failed on both Windows
        CI legs while passing here, because the runners leave `core.autocrlf` at its
        Windows default of true and rewrite LF to CRLF on checkout. The working tree's
        endings are therefore a property of the checkout's configuration, not of the
        repository, and asserting them tests the runner. What has to be LF is what is
        stored, so that the two halves of the matrix agree on the bytes and a regeneration
        on either one is a no-op.
        """
        eol = subprocess.run(
            ["git", "ls-files", "--eol", "--", rel], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True).stdout
        assert eol.strip(), f"{rel} is not tracked, so it has no stored bytes"
        index_eol = eol.split()[0]
        assert index_eol in ("i/lf", "i/none"), (
            f"{rel} is stored as {index_eol}; the script that generates it emits LF, so "
            f"anything else makes the next regeneration a whole-file diff"
        )

    @pytest.mark.parametrize("rel", GENERATED_FILES)
    def test_the_file_is_tracked(self, rel: str):
        """An untracked file would satisfy the byte check while being local residue."""
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel], cwd=REPO_ROOT,
            capture_output=True, text=True)
        assert tracked.returncode == 0, f"{rel} is not tracked: {tracked.stderr.strip()}"


class TestTheApiDocIsByteIdenticalToItsGenerator:
    def test_regenerating_it_would_change_no_stored_byte(self):
        """`check_api_md_is_generated` compares normalized text and cannot see endings.

        Compared against the stored blob rather than the file on disk, for the same
        reason as TestGeneratedFilesAreLf: a checkout with `core.autocrlf` true holds
        CRLF whatever the repository stores.
        """
        from scripts.generate_api_md import generate_api_markdown

        generated = generate_api_markdown(REPO_ROOT).encode("utf-8")
        stored = subprocess.run(
            ["git", "show", ":docs/api.md"], cwd=REPO_ROOT,
            capture_output=True, check=True).stdout
        assert generated == stored, (
            "docs/api.md's stored bytes differ from its generator's; --check passes "
            "because it compares read_text output, which normalizes endings away"
        )
