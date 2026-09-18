# Analyzing with an Agent

`jnwb` is usable by a coding agent, but almost none of that is automatic. This page says
exactly what reaches your machine from `pip install jnwb`, what does not, and how to supply
the rest.

## What the installed package gives you

| Surface | Ships in the wheel | What it covers |
|---|---|---|
| The library | yes | Every symbol in `jnwb.__all__`, with docstrings |
| MCP server | yes (needs the `mcp` extra) | File inspection only — three tools, listed below |
| Skills | **no** | The routing and scientific safeguards |
| `AGENTS.md` | **no** (in the sdist) | Repository map, working rules, recipes |

An agent given only the installed package can discover the API from docstrings and
[the public API page](api.md). What it will not discover is the part that stops it producing
confident nonsense: averaging decibels, shuffling across a nested design, calling a lag
asymmetry a cause. Those live in the skills and in
[Common mistakes](common_mistakes.md).

## The MCP server

Three tools, all of them ingest: the server reads NWB files and returns what it found. It writes nothing, and it has no tool that registers another tool. The table below is the whole surface -- it is checked against the server's live registry, so a tool without a row here is a failure, not an omission.

Install the extra and run the module:

```bash
pip install "jnwb[mcp]"
python -m jnwb.mcp_server
```

| Tool | Signature | Returns |
|---|---|---|
| `inspect_nwb` | `(file_path)` | Structure and metadata: acquisitions, units, electrodes, every interval table with columns and sample values |
| `get_event_codes_and_timings` | `(file_path, event_group_path=None)` | Event and trial codes with their timestamps |
| `prepare_signal_reference` | `(file_path, dataset_path)` | A lazy handle to a large dataset, without loading it |

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

Nine skills live in [`skills/`](https://github.com/HNXJ/jnwb/tree/main/skills) in the
repository, and in the sdist. Each is a `SKILL.md` with a description and routing rules,
alongside an `agents/openai.yaml` manifest. They are not in the wheel: the canonical tree is
`skills/`, and a copy under `jnwb/` would be a second tree, which the repository's own gates
forbid. To use them, clone the repository or unpack the sdist and point your agent at that
directory.

| Skill | Covers |
|---|---|
| `jnwb` | Router, scientific safeguards, entry point |
| `jnwb-fact-action` | Execution control, authority loading order, independent verification |
| `jnwb-nwb-data` | NWB inspection, paths, metadata, electrodes, addressing |
| `jnwb-spiking` | Raster/PSTH, latency, causal smoothing, unit QC |
| `jnwb-lfp-spectral` | Filtering, TFR, band power, artifact repair |
| `jnwb-statistics` | Bootstrap, permutation, multiple comparisons, RNG |
| `jnwb-population` | Decoding, trajectories, jRSA, population geometry |
| `jnwb-connectivity` | Granger, PSI, transfer entropy |
| `jnwb-figures` | Visual QC, plotting, figure export |

The router skill carries the safeguards worth reading even if you never install a skill:
spikes and LFP are distinct observables and are not pooled; association, directionality and
causality are three different claims; raw power is averaged before any logarithm; wavelet
coefficients inside the cone of influence are masked; smoothing is causal so that no future
leaks into an onset; a `Generator` is passed explicitly and the global RNG is never mutated;
and measures built on the imaginary cross-spectrum reduce sensitivity to zero-lag coupling
without conferring immunity to volume conduction.

## Without any of that

An agent with nothing but the installed package and this documentation site can still work
well, given three instructions:

1. Start from [`00_your_own_file.py`](tutorials/00_your_own_file.md), which discovers a
   layout instead of assuming one.
2. Read [Common mistakes](common_mistakes.md) before writing analysis code, not after a
   result looks surprising.
3. Treat every jnwb refusal as the instruction it is. `AmbiguousIntervalTableError` names
   the tables, `ColumnNotFoundError` names the columns, and an unknown keyword argument names
   the options the function accepts. The fix is always to pass the missing argument, never to
   fall back to a default.
