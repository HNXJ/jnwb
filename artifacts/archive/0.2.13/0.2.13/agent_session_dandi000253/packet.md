You are an analyst given an unfamiliar NWB file and the jnwb library. Answer the questions below using only jnwb's skills as your guide.

Repository (read-only for you): C:/workspace/jnwb, commit 0a7b1763. Python: `python` (jnwb imports from that checkout when run from it: `cd C:/workspace/jnwb && python <your script>`).
File: C:/workspace/jnwb/examples/data/dandi000253_excerpt.nwb (an excerpt of DANDI 000253, Allen OpenScope; visual cortex VISpm, one probe).
Write scripts and output only under C:/Users/nejath/AppData/Local/Temp/claude/C--workspace-jnwb/77eb0381-64a4-4a12-9f40-20e72d9557e4/scratchpad/_temp_agent1210/ (write each script with the file tool, run it by path).

Start at C:/workspace/jnwb/skills/jnwb/SKILL.md, the router, and follow its routing into the other skills/*/SKILL.md and their references/ as the questions need. You may read jnwb/ source and docs/api.md for signatures. You must NOT open, grep or read: examples/tutorials/, docs/tutorials/, tests/, artifacts/. This is a blind test of whether the skills alone get an analyst to the right answer.

Questions:
1. How many units does the file hold, and how many have quality "good"?
2. The LFP: what does the file store for its sampling rate, and what is the LFP sampling rate in Hz as derived from the file itself? Give the derivation.
3. The grating presentations: how many rows does the table have, and how many are real grating onsets (a drawn grating)? Say how you told them apart.
4. For each cortical LFP channel (location starting with VISpm) that the excerpt holds, the high-gamma band power change from pre-stimulus (-0.45 to -0.05 s) to post-stimulus (0.05 to 0.45 s) in dB, aggregated across trials as the skills prescribe. Use jnwb's canonical high-gamma band.
5. Anything a skill told you to refuse or warn about on this file, and what you did.

Report (max 250 words): each answer with its number, the jnwb functions you called in order, the skill pages that routed each step (path), and every point where the skills were unclear, wrong or missing so you had to guess. Put your final script's path in the report.
