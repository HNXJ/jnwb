"""Write the GitHub Release notes for a version and check their claims before they are used.

The body is three parts, in order: a fenced ``pip install <name>==<version>``, the supported
Python range as ``Supports Python <floor> through <ceiling>.``, and the version's section of
``CHANGELOG.md``. Every value is read from the package metadata by
``scripts/release_gate.py``'s ``release_metadata``, and the finished body is judged by the same
``check_release_body_claims`` the release gate applies to the published Release, so the notes
the workflow writes are held to the rule that would refuse them afterwards.

Exits 0 after writing the body; exits 1, writing nothing, when the version has no
``CHANGELOG.md`` section or the check reports a violation.

    python scripts/release_body.py --tag v0.2.9 --output release_body.md
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import List, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# `append`, as the suite does: inserting would shadow an installed jnwb for an importer.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_gate import (  # noqa: E402
    ReleaseMetadata,
    check_release_body_claims,
    release_metadata,
)


def changelog_section(changelog: str, version: str) -> Optional[str]:
    """The body of ``## [<version>] - <date>`` up to the next level-2 heading, or None.

    None when the heading is absent or the section holds no text: an empty section would
    publish notes that say nothing about the release.
    """
    heading = re.compile(r"^## \[" + re.escape(version) + r"\] - \d{4}-\d{2}-\d{2}[ \t]*$",
                         re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        return None
    following = re.compile(r"^## ", re.MULTILINE).search(changelog, match.end())
    section = changelog[match.end():following.start() if following else len(changelog)]
    section = section.strip("\n")
    return section if section.strip() else None


def render_body(metadata: ReleaseMetadata, section: str) -> str:
    return (
        "```bash\n"
        f"pip install {metadata.name}=={metadata.version}\n"
        "```\n"
        "\n"
        f"Supports Python {metadata.python_floor} through {metadata.python_ceiling}.\n"
        "\n"
        f"{section}\n"
    )


def build_body(root: pathlib.Path, tag: str) -> tuple[Optional[str], List[str]]:
    """``(body, [])`` when the body passes the check, else ``(None, violations)``.

    The Release this body is written for is never marked a prerelease, so a prerelease
    version is reported by the check rather than published with final-release notes.
    """
    metadata = release_metadata(root)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog_section(changelog, metadata.version)
    if section is None:
        return None, [f"CHANGELOG.md has no non-empty section headed "
                      f"'## [{metadata.version}] - YYYY-MM-DD'"]
    body = render_body(metadata, section)
    violations = check_release_body_claims(body, metadata, tag_name=tag, is_prerelease=False)
    return (None, violations) if violations else (body, [])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="the release tag, e.g. v0.2.9")
    parser.add_argument("--output", required=True, type=pathlib.Path,
                        help="where to write the body")
    parser.add_argument("--root", type=pathlib.Path, default=REPO_ROOT,
                        help="the repository whose metadata and changelog are read")
    args = parser.parse_args(argv)

    body, violations = build_body(args.root, args.tag)
    if body is None:
        for violation in violations:
            print(f"::error::release body: {violation}", file=sys.stderr)
        return 1
    args.output.write_text(body, encoding="utf-8", newline="\n")
    print(f"PASS: wrote {args.output} ({len(body)} characters) for {args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
