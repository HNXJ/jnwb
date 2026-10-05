# Analyzing with an Agent

`jnwb` is usable by a coding agent, but almost none of that is automatic. This page says
what reaches your machine from `pip install jnwb`, what does not, and how to supply
the rest. [Architecture](architecture.md) shows where skills sit relative to the library and
the outcomes a skill can end a task in.

## What the installed package gives you

| Surface | Ships in the wheel | What it covers |
|---|---|---|
| The library | yes | Every symbol in `jnwb.__all__`, with docstrings |
| MCP server | yes (needs the `mcp` extra) | File inspection only — three tools, listed below |
| Skills | **no** | The routing and scientific safeguards |
| `AGENTS.md` | **no** (source checkout only) | Repository map and working rules; the recipes are on [Recipes](recipes.md) |

An agent given only the installed package can discover the API from docstrings and
[the public API page](api.md). What it will not discover is the part that stops it producing
confident nonsense: averaging decibels, shuffling across a nested design, calling a lag
asymmetry a cause. Those live in the skills and in
[Common mistakes](common_mistakes.md).

## The MCP server

Three tools, all of them ingest: the server reads NWB files and returns what it found. It writes nothing, and it has no tool that registers another tool. The table below is the whole surface, checked against the server's live registry: a tool without a row here fails that check.

Install the extra and run the module:

```bash
pip install "jnwb[mcp]"
python -m jnwb.mcp_server
```

| Tool | Signature | Returns |
|---|---|---|
| `inspect_nwb` | `(file_path)` | Structure and metadata: acquisitions, units, electrodes, every interval table with columns and sample values |
| `get_event_codes_and_timings` | `(file_path, event_group_path=None)` | Event and trial codes with their timestamps |
| `prepare_signal_reference` | `(file_path, dataset_path)` | A dataset's shape, scaling, timing and layout, and the jnwb call that reads it in physical units, without loading it |

Wire it into an MCP-speaking client the usual way:

```json
{
  "mcpServers": {
    "jnwb": {
      "command": "python",
      "args": ["-m", "jnwb.mcp_server"]
    }
  }
}
```

There is no analysis tool, by design: the analysis is a Python call, and the agent writes it.
MCP gets the agent to the point where it knows what the file contains — which table, which
column, which acquisition, what sampling rate — so that the code it writes next is addressed
to the real layout instead of an assumed one.

## The skills

The skills live in [`skills/`](https://github.com/HNXJ/jnwb/tree/main/skills) in the
repository, and in the sdist. Each is a `SKILL.md` with a description and routing rules,
alongside an `agents/openai.yaml` manifest. To use them, clone the repository or unpack the
sdist and point your agent at that directory.

`pip install jnwb` does not deliver them, from the wheel or the sdist: the build installs
`jnwb/` and discards everything beside it. An installed copy therefore carries a pointer
rather than the files. `jnwb.SKILLS_URL` names the skills tree for the tag matching
the installed version, so an agent that has only the package can find the skills written
against the API it is holding:

```python
import jnwb

jnwb.SKILLS_URL  # 'https://github.com/HNXJ/jnwb/tree/v0.2.9/skills'
```

The sdist leaves out `docs/` and `AGENTS.md`, so a skill's repository-relative links resolve
only in a checkout.

The entry point is the router skill, `jnwb`. Its routing table, copied here, sends each task to
the skill that covers it:

| Task | Skill |
|---|---|
| NWB files: inspection, event onsets by code, paths, metadata, electrode addressing, census, compression | `jnwb-nwb-data` |
| Experiment structure: interval tables, event rows, epochs around events, recording cycles, condition meaning from documented metadata | `jnwb-paradigm` |
| Spike trains: binning, raster, PSTH, onset latency, response significance, spike-field locking, causal smoothing | `jnwb-spiking` |
| LFP filtering, band power, complex Morlet TFR, multi-trial accumulation, artifact detection and repair (`bad_channels_from_correlation`, `consensus_bad_trials`, `repair_lfp_trials`) | `jnwb-lfp-spectral` |
| Laminar depth: cortical layers, crossover contacts, CSD, probe geometry | `jnwb-lfp-spectral` (its depth estimators read the spectra and correlation matrices it produces); `jnwb-nwb-data` for the electrode table |
| Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG | `jnwb-statistics` |
| Linear SVM decoding, neural trajectories, jRSA, population geometry | `jnwb-population` |
| Directed coupling (Granger, PSI, transfer entropy); lag asymmetry, not causation | `jnwb-connectivity` |
| Matplotlib figures: equal raster trial counts, vector export | `jnwb-figures` |
| Quality control: unit-quality measures and classes, unit and electrode table audits, unit-quality plots, result records of what ran on which inputs | `jnwb-qc` |
| Plotly multi-panel figures with SVG/PNG/HTML export and an argument sidecar (needs the `vis` extra) | `jnwb-landmark-viz` |

The scientific safeguards, worth reading even if you never install a skill, are section 4 of
the [router skill](https://github.com/HNXJ/jnwb/blob/main/skills/jnwb/SKILL.md).

## Without any of that

An agent with nothing but the installed package and this documentation site can still work
well, given these instructions:

1. Start from [`00_your_own_file.py`](tutorials/00_your_own_file.md), which discovers a
   layout instead of assuming one.
2. Read [Common mistakes](common_mistakes.md) before writing analysis code, not after a
   result looks surprising.
3. Treat every jnwb refusal as the instruction it is. `AmbiguousIntervalTableError` names
   the tables, `ColumnNotFoundError` names the columns, and an unknown keyword argument names
   the options the function accepts. The fix is always to pass the missing argument, never to
   fall back to a default.
