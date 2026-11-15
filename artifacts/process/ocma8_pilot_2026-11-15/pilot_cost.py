"""Cost of each pilot agent at public API prices, per message. Usage: pilot_cost.py <subagents dir> <usage.csv>

Prices in USD per million tokens, read 2026-11-15 from https://platform.claude.com/docs/en/about-claude/pricing
(model pricing table): (input, 5m cache write, 1h cache write, cache read, output). Haiku 5.5 has a second tier for
prompts over 100K tokens; a message's prompt is input + cache write + cache read. Where a usage row does not split
cache writes by lifetime, the 1h price is used (upper bound).
"""
import csv
import json
import sys
from pathlib import Path

PRICE = {
    "claude-haiku-5-5": {"low": (0.10, 0.125, 0.20, 0.01, 0.50), "high": (0.50, 0.625, 1.0, 0.05, 2.50)},
    "claude-sonnet-5-5": {"low": (2.0, 2.50, 4.0, 0.10, 10.0)},
}
root = Path(sys.argv[1])
arms = {}
print("arm,role,usd,messages,messages_over_100k,write_5m,write_1h,write_unsplit")
for row in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
    turns = {}
    for ln in (root / f"agent-{row['agent']}.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(ln).get("message")
        except (ValueError, AttributeError):
            continue
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            turns[msg.get("id") or f"row{len(turns)}"] = (msg["usage"], msg.get("model"))
    usd = 0.0
    over = w5 = w1 = wu = 0
    for u, model in turns.values():
        i, cw, cr, o = (u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                    "cache_read_input_tokens", "output_tokens"))
        tiers = PRICE[model]
        high = "high" in tiers and i + cw + cr > 100_000
        over += high
        p = tiers["high" if high else "low"]
        split = u.get("cache_creation") or {}
        a5, a1 = split.get("ephemeral_5m_input_tokens", 0) or 0, split.get("ephemeral_1h_input_tokens", 0) or 0
        rest = cw - a5 - a1
        assert rest >= 0, "cache write split must not exceed the total"
        w5, w1, wu = w5 + a5, w1 + a1, wu + rest
        usd += (i * p[0] + a5 * p[1] + (a1 + rest) * p[2] + cr * p[3] + o * p[4]) / 1e6
    arms[row["arm"]] = arms.get(row["arm"], 0.0) + usd
    print(f"{row['arm']},{row['role']},{usd:.4f},{len(turns)},{over},{w5},{w1},{wu}")
for arm, usd in arms.items():
    print(f"TOTAL,{arm},{usd:.4f}")
