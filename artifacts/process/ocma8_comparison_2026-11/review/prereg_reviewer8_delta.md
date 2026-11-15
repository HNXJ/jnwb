# prereg reviewer8_delta (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: ACCEPT

All six changed passages do what was asked. I found no contradiction, no judgment left to the unblinded orchestrator, and no broken measure definition that is blocking.

1. Helper report (finding 1): lines 33 and 108 now cover the helper in both the ledger and the fix-round forwarding. The provenance mapping at line 55 still works, since it keys on report and role.
2. Closing review that ends "no report" (finding 2): line 32 now reads "or at that run's ending", consistent with lines 118-121.
3. Cross-family V (finding 5): lines 69-70 leave a task marked "no cross-family" out of that figure, which matches the marking rule at lines 19-21.
4. Sensitivity set (finding 4): lines 208-209 define the one-pair and empty cases, consistent with the T1/T2 enumeration rule at lines 99-101.
5. Owner instruction (cap): lines 123-125 say the cap is per dispatch and not an equal total budget. They report cap compliance per run, and runs, agent seconds, tokens and cost per cell. This matches the instruction and does not conflict with the critical-path seconds defined at line 26.

Non-blocking defects:
- Lines 141-143, diff scrub: "a path or added line that holds a role or agent name is replaced with `AGENT`" does not say whether the whole line or only the name is replaced. Replacing a whole line can change code. The words helper, checker, worker and reviewer are common identifiers, and T2 is a splitter refactor. The adjudicator judges the scrubbed trees, so a corrupted line could surface as a false "wrong-behaviour" row and flip `V`. Fix: replace only the matched token, and require the scrubbed copy to still pass the acceptance command.
- Line 205: "On one-part tasks (T3, T4)" is stale if T1 or T2 becomes one-part under line 101. Fix: "one-part tasks (T3, T4 and any joining them)".

Examined: the full diff 87514cca..a900f664, the whole file at a900f664, and the reviewer7 report. I ran only the `git diff` and `git show` reads.

