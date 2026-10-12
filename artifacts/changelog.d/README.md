# Changelog fragments

One file per change a user would notice, named `<name>.<category>.md`, where `<category>` is one
of `breaking`, `added`, `changed`, `deprecated`, `removed`, `fixed`, `security` or
`documentation`. The file holds one or more top-level `- ` bullets written as they will read in
`CHANGELOG.md`, with LF line endings and no headings.

At release, `python scripts/assemble_changelog.py --version X.Y.Z --date YYYY-MM-DD` inserts the
section below `## [Unreleased]`, one `###` block per category in the order above and fragments
sorted by file name within a block, and deletes the fragments it used. This file is not a
fragment and stays.
