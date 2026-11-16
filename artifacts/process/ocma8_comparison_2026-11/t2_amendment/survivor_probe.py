"""Probe: can w_hdr2 (naive header split) and w_maxsplit (15-split cap) be observed at a public reader entry point?"""
import json
import pathlib
import sys

sys.path.insert(0, "D:/repos/_work/exp_t2diff")
import t2_differential_r2 as d  # noqa: E402

B = d.BSL
W = "D:/repos/_work"
V = "D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/trees"
sep = lambda n: "|" + "---|" * n
docs = {}
# header escapes at the fact readers: in each header cell in turn
for reader, prefix, header, row in (
        ("fact.facts", "## Boundary\n\n", ["ID", "Domain", "Predicate", "Held by", "Ruled"],
         ["`F1`", "boundary", "the rule holds", "`mod.a`", "2026-01-02"]),
        ("fact.constants", "## Constants\n\n", ["Constant", "Values", "Ruled"], ["`N_BINS`", "`8`, `16`", "2026-01-02"]),
        ("fact.references", "## Methods\n\n", ["Reference", "Result implemented", "Functions"],
         ["[Smith 2001](https://doi.org/10.1000/x1)", "Result A", "`fn_a`"])):
    for j in range(len(header)):
        for place in ("mid", "start", "end"):
            cell = header[j]
            new = {"mid": cell[:1] + B + "|" + cell[1:], "start": B + "|" + cell, "end": cell + B + "|"}[place]
            h = header[:j] + [new] + header[j + 1:]
            doc = prefix + "| " + " | ".join(h) + " |\n" + sep(len(h)) + "\n| " + " | ".join(row) + " |\n"
            docs[f"{reader}|hdr{j}{place}"] = (reader, doc)
        # an extra header cell holding only an escaped pipe, and a matching extra row cell
        h = header + ["x" + B + "|y"]
        doc = prefix + "| " + " | ".join(h) + " |\n" + sep(len(h)) + "\n| " + " | ".join(row + ["z"]) + " |\n"
        docs[f"{reader}|hdrextra"] = (reader, doc)
    # wide rows: 18 cells in header and row
    wide_h = header + [f"h{i}" for i in range(14)]
    wide_r = row + [f"c{i}" for i in range(14)]
    doc = prefix + "| " + " | ".join(wide_h) + " |\n" + sep(len(wide_h)) + "\n| " + " | ".join(wide_r) + " |\n"
    docs[f"{reader}|wide"] = (reader, doc)
for reader, prefix in (("release.table_data", ""), ("learning.ledger", ""), ("docs.vocabulary", "# Contract\n\n## Vocabulary\n\n")):
    spec = next(r for r in d.READERS if r[0] == reader)
    header = list(spec[3]) + [f"h{i}" for i in range(16)]
    row = [p[0] for p in spec[4]] + [f"c{i}" for i in range(16)]
    docs[f"{reader}|wide"] = (reader, prefix + "| " + " | ".join(header) + " |\n" + sep(len(header)) + "\n| " + " | ".join(row) + " |\n")

inputs = [{"id": k, "reader": r, "doc": doc, "base_doc": doc.replace(B + "|", B + d.BROKEN)} for k, (r, doc) in docs.items()]
path = pathlib.Path("D:/pytest_temp/t2diff_survivor_inputs.json")
path.write_text(json.dumps(inputs), encoding="utf-8")
base = d.run_child(pathlib.Path(f"{W}/exp_prereq/t2/base"), path, "base_doc")["results"]
for name, tree in (("pos2", f"{W}/exp_t2beh/pos2"), ("w_hdr2", f"{V}/w_hdr2"), ("w_maxsplit", f"{V}/w_maxsplit")):
    res = d.run_child(pathlib.Path(tree), path, "doc")["results"]
    bad = [k for k in docs if d.norm(res[k]) != d.norm(base[k])]
    print(f"{name}: {len(bad)} of {len(docs)} probes differ from the oracle: {bad}")
    for k in bad[:3]:
        print("   doc", repr(docs[k][1][-120:]), "\n   tree", json.dumps(res[k])[:160], "\n   base", json.dumps(base[k])[:160])
