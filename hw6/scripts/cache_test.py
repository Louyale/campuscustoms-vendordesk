"""Problem 4: With and without cached tokens.

Runs the vendor desk agent on all 12 practice documents in two setups:

- without_cache: every request opens with a fresh random tag, so nothing can
  be reused from the prompt cache (agent.py, build_agent(..., setup="without_cache"))
- with_cache: the normal agent, whose prompt.md + handbook prefix is reused

Every model call (each run makes 2: one to ask for read_document, one to
answer) is saved to output/cache_test.json with its setup, document, every
token count the API reported, and dollars from data/prices.json. The summary
tables go to output/cache_test.md.

Run from HW6/:        .venv/Scripts/python scripts/cache_test.py
Rebuild tables only:  .venv/Scripts/python scripts/cache_test.py --report-only
(Lou's notes after the "<!-- surprises -->" line in cache_test.md are kept on rebuild.)
"""

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai.usage import RequestUsage  # noqa: E402

from agent import MODEL_NAME, NO_DEFENSES, RATES, ROOT, cost_of, review  # noqa: E402
from tools import now  # noqa: E402

DOCS = ROOT / "data" / "practice_docs"
JSON_OUT = ROOT / "output" / "cache_test.json"
MD_OUT = ROOT / "output" / "cache_test.md"
KEY = json.loads((ROOT / "data" / "practice_key.json").read_text(encoding="utf-8"))
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]
SETUP_ORDER = ["without_cache", "with_cache"]
SETUP_NAMES = {"without_cache": "Without cache", "with_cache": "With cache"}
MARKER = "<!-- surprises -->"
# Red circled asterisk for the headline surprises. GitHub renders $...$ as math, and math can be colored.
STAR = r"$\color{red}{\circledast}$"

# Problem 2 estimate (output/handbook_estimate.md): handbook only, per call.
EST_TOKENS = 10_058
EST_UNCACHED = 0.0010058
EST_CACHED = 0.00010058


async def run_all() -> dict:
    calls, runs = [], []
    for setup in SETUP_ORDER:
        for k in KEY:
            doc = DOCS / k["file"]
            report, usage = await review(doc, label=f"cache_test_{setup}", setup=setup, defenses=NO_DEFENSES)
            got = report.model_dump()
            wrong = [f for f in FIELDS if got[f] != k[f]]
            runs.append({
                "setup": setup, "document": k["file"], "requests": usage.requests,
                "input_tokens": usage.input_tokens, "cached_tokens": usage.cached_tokens,
                "cache_write_tokens": usage.cache_write_tokens, "output_tokens": usage.output_tokens,
                "reasoning_tokens": usage.reasoning_tokens, "cost_usd": usage.cost_usd, "seconds": usage.seconds,
                "decision": report.decision, "correct": not wrong, "wrong_fields": wrong,
            })
            for c in usage.calls:
                parts = cost_of(RequestUsage(input_tokens=c.input_tokens, cache_read_tokens=c.cached_tokens,
                                             cache_write_tokens=c.cache_write_tokens, output_tokens=c.output_tokens))
                calls.append({
                    "setup": setup, "document": k["file"], "request": c.request, "model": MODEL_NAME,
                    "input_tokens": c.input_tokens, "cached_tokens": c.cached_tokens,
                    "cache_write_tokens": c.cache_write_tokens,
                    "uncached_input_tokens": c.input_tokens - c.cached_tokens - c.cache_write_tokens,
                    "output_tokens": c.output_tokens, "reasoning_tokens": c.reasoning_tokens,
                    "cost_usd": parts,
                })
            print(f"{setup:13} {k['file']:28} cached={usage.cached_tokens:>6,}/{usage.input_tokens:,} "
                  f"write={usage.cache_write_tokens:>6,} ${usage.cost_usd:.6f} {'OK' if not wrong else 'WRONG'}")
    data = {
        "generated": now(), "model": MODEL_NAME, "prices_per_1m": RATES,
        "setups": {
            "without_cache": "Every request opens with a fresh random tag, so no prefix repeats and nothing is reused from cache.",
            "with_cache": "The normal agent: the prompt.md + handbook prefix is identical on every request and reused from cache.",
        },
        "calls": calls, "runs": runs,
    }
    JSON_OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def money(x: float) -> str:
    if x < 0.01:
        return f"${x:.6f}"
    return f"${x:,.4f}" if x < 1 else f"${x:,.2f}"


def pct(part: float, whole: float) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def report(data: dict) -> None:
    calls, runs = data["calls"], data["runs"]
    by = {s: [r for r in runs if r["setup"] == s] for s in SETUP_ORDER}
    cby = {s: [c for c in calls if c["setup"] == s] for s in SETUP_ORDER}
    tot = {s: sum(r["cost_usd"] for r in by[s]) for s in SETUP_ORDER}
    per_doc = {s: tot[s] / len(by[s]) for s in SETUP_ORDER}
    saved = 1 - tot["with_cache"] / tot["without_cache"]
    month = {s: per_doc[s] * 30_000 for s in SETUP_ORDER}

    def total(s: str, key: str) -> int:
        return sum(r[key] for r in by[s])

    def split(s: str, key: str) -> float:
        return sum(c["cost_usd"][key] for c in cby[s])

    secs = {s: sum(r["seconds"] for r in by[s]) / len(by[s]) for s in SETUP_ORDER}
    sd = {s: statistics.stdev(r["seconds"] for r in by[s]) for s in SETUP_ORDER}
    lo, hi = min(r["seconds"] for r in runs), max(r["seconds"] for r in runs)
    correct = {s: sum(r["correct"] for r in by[s]) for s in SETUP_ORDER}
    wrong = {s: [r["document"][:3] for r in by[s] if not r["correct"]] for s in SETUP_ORDER}
    writes_nc = sum(c["cache_write_tokens"] for c in cby["without_cache"])
    plain = sum((c["input_tokens"] - c["cached_tokens"]) * RATES["input_per_1m"] / 1e6
                + c["output_tokens"] * RATES["output_per_1m"] / 1e6 for c in cby["without_cache"])
    req1 = {s: [c for c in cby[s] if c["request"] == 1] for s in SETUP_ORDER}
    avg_in1 = sum(c["input_tokens"] for c in req1["with_cache"]) / len(req1["with_cache"])
    avg_in_all = {s: sum(c["input_tokens"] for c in cby[s]) / len(cby[s]) for s in SETUP_ORDER}
    first_cached = by["with_cache"][0]["cached_tokens"]
    tail_writes = [r["cache_write_tokens"] for r in by["with_cache"]]
    traps = json.loads((ROOT / "output" / "trap_calls.json").read_text(encoding="utf-8"))

    # Surprises in the numbers (Problem 4, last bullet), each with the numbers and why it happens.
    surprises = [
        ("“Without cache” still paid the cache-write rate",
         f"{writes_nc:,} of {total('without_cache', 'input_tokens'):,} input tokens were reported as cache writes "
         f"({money(split('without_cache', 'cache_write'))} at $0.125/1M), not plain input at $0.10/1M",
         "The provider writes every new prompt to its cache automatically, even when nothing can be reused. "
         "It also ignored our request to turn caching off. So uncached input costs 25% more than the $0.10 rate "
         "Problem 2 used."),
        ("Each document costs 2 model calls, so the handbook is paid for twice",
         f"{len(calls)} calls for 24 document runs. Real cost per document is {money(per_doc['without_cache'])} "
         f"without cache ({per_doc['without_cache'] / EST_UNCACHED:.1f}× the Problem 2 per-call estimate) and "
         f"{money(per_doc['with_cache'])} with cache ({per_doc['with_cache'] / EST_CACHED:.1f}×)",
         "Reading the document with a tool is a loop: call 1 asks for `read_document`, and call 2 resends "
         "everything plus the document to get the answer."),
        ("The saving still matched the estimate almost exactly",
         f"{saved:.1%} saved, vs. about 90% predicted in Problem 2",
         "The interesting part is why it held even though every cost doubled: each document takes 2 calls in both "
         "setups, so the doubling hits both sides equally. In each call, the same ~10,900-token handbook prefix "
         "is almost all of the input, and the cache prices it at a tenth. The parts the cache can't touch (the "
         "document, call 2's new tokens and the ~88 output tokens) are small, so the ratio stays near 90%. "
         "It's a concrete check on the accuracy of our work: the Problem 2 estimate, made before any real run, "
         "predicted the saving to within one percentage point."),
        ("No measurable speed difference from caching",
         f"{secs['without_cache']:.1f} s per document without cache vs. {secs['with_cache']:.1f} s with. The gap is "
         f"smaller than the run-to-run spread (±{sd['without_cache']:.1f} s and ±{sd['with_cache']:.1f} s; "
         f"{lo:.1f}–{hi:.1f} s)",
         "Likely, not proven: at about 11,000 tokens a prompt, reading the prompt is a small share of the time, "
         "and most of it is probably the network round trip through Portkey and writing the answer, which "
         "caching doesn't change."),
        ("The with-cache run never paid a full cache write",
         f"Document 1 already read {first_cached:,} cached tokens",
         "The handbook prefix was still cached from the Problem 3 runs earlier the same day (12-hour cache "
         "lifetime). In daily use, that's normal: only the first call after the cache expires pays the write."),
        ("Even cached calls write a little to the cache",
         f"{min(tail_writes)}–{max(tail_writes)} cache-write tokens per document with cache "
         f"({money(split('with_cache', 'cache_write'))} in total)",
         "Likely: the part of each request after the handbook (the document and the tool exchange) is new, so "
         "it's written to the cache, and call 2 can then reuse call 1's part. The token counts fit this, but the "
         "API doesn't say which tokens were written."),
        ("With cache, the handbook is still the biggest cost",
         f"Cached input {money(split('with_cache', 'cached_input'))} "
         f"({pct(split('with_cache', 'cached_input'), tot['with_cache'])}), output "
         f"{money(split('with_cache', 'output'))} ({pct(split('with_cache', 'output'), tot['with_cache'])}), "
         f"cache writes {money(split('with_cache', 'cache_write'))} "
         f"({pct(split('with_cache', 'cache_write'), tot['with_cache'])})",
         "Even at a tenth of the price, ~21,750 cached tokens per document outweigh ~88 output tokens. The next "
         "savings are sending the handbook once per document instead of twice, or sending less of it."),
        ("A hidden-price attack worked in one setup and not the other",
         f"Without cache {correct['without_cache']}/12 correct (missed {', '.join(wrong['without_cache'])}); "
         f"with cache {correct['with_cache']}/12 (missed {', '.join(wrong['with_cache'])}). Across all 5 full runs of "
         "the 12 practice documents so far, **p02's hidden $5.11 price fooled the agent in 3 of 5**: both "
         "groundwork runs (`practice_scores_groundwork.md`) and this without-cache run, but not the Problem 3 run "
         "(`practice_scores.md`) or this with-cache run",
         "Not because of the cache: caching only changes billing, not what the model reads. The model's answers "
         "vary from run to run, so the same hidden price fools it some runs and not others. One clean run doesn't "
         "prove a document is safe, so each attack should be run several times."),
        ("No trap tool was called",
         f"`output/trap_calls.json` has {len(traps)} entries after 24 runs, including p06, which asks for the "
         "max-cost list to be emailed",
         "The fact is solid: the model didn't act on p06's request in these 24 runs. Why isn't tested yet; the "
         "prompt asking for only the five facts may play a part. The prompt-injection problems will test it "
         "properly, and this is their undefended baseline."),
    ]
    # Lou's picks: the estimate-matched surprise is the headline and moves to the top as S1. It's a concrete
    # check on the accuracy of our work. S1 to S4 are the starred headline surprises.
    surprises = [surprises[2], surprises[0], surprises[1], *surprises[3:]]
    starred = {1, 2, 3, 4}

    L = [
        "# Cache Test: With and Without Cached Tokens (Problem 4)",
        "",
        f"The vendor desk agent ran on all 12 practice documents in two setups, using {data['model']} only. "
        f"**Every model call is saved** in `output/cache_test.json` and listed in Table 8 below: {len(calls)} calls, "
        "because each document takes 2 requests (one to ask for `read_document`, one to answer). Each call records "
        "its setup, document, every token count the API reported, and the dollar cost from `data/prices.json` "
        "($0.10 input, $0.01 cached input, $0.125 cache write, $0.50 output, per 1M tokens). "
        f"Run on {data['generated'][:10]} by `scripts/cache_test.py`.",
        "",
        "- **Without cache:** every request opens with a fresh random tag, so no two requests share a prefix and "
        "nothing can be reused from the cache. Asking the API for no caching wasn't enough: in a test, two "
        "identical requests sent with caching set to `explicit` (no automatic caching) still showed 0 then 10,552 "
        "cached tokens. So the random tag is what guarantees it.",
        "- **With cache:** the normal agent. The `prompt.md` + handbook prefix is identical on every request and is "
        "reused from the cache.",
        "",
        "## Problem 4 answers at a glance",
        "",
        "**Table 1: Problem 4 Answers at a Glance**",
        "",
        "| What Problem 4 asks for | Answer | Details |",
        "|---|---|---|",
        f"| Total cost and cost per document for each setup, and the percent saved | **Without cache:** "
        f"{money(tot['without_cache'])} total, {money(per_doc['without_cache'])} per document. **With cache:** "
        f"{money(tot['with_cache'])} total, {money(per_doc['with_cache'])} per document. **Saved: {saved:.1%}** "
        f"({money(tot['without_cache'] - tot['with_cache'])} on 12 documents). | Tables 3 and 4 |",
        f"| How the real numbers compare to the Problem 2 estimate | The saving matched (**{saved:.1%}** real vs. "
        f"about 90% estimated), but real costs are about **{per_doc['without_cache'] / EST_UNCACHED:.1f}× higher "
        f"without cache and {per_doc['with_cache'] / EST_CACHED:.1f}× higher with cache** per document, because "
        f"each document takes 2 calls, each call carries ~{avg_in1 - EST_TOKENS:,.0f} tokens beyond the handbook, "
        "and uncached input is billed as cache writes. | Table 5 |",
        f"| A projection for 1,000 documents a day for 30 days, with and without cache | **Without cache: "
        f"{money(month['without_cache'])}. With cache: {money(month['with_cache'])}. Saved: "
        f"{money(month['without_cache'] - month['with_cache'])}** over 30,000 documents. | Table 6 |",
        f"| Anything in the numbers that surprised us, and why it happens | **Headline (S1 {STAR}): the saving still "
        f"matched the estimate ({saved:.1%} vs. about 90%) even though every cost doubled**, a concrete check on the "
        "accuracy of our work. Also starred: S2 " + STAR + " “without cache” still paid the higher cache-write "
        "rate; S3 " + STAR + " the handbook is paid for twice per document; S4 " + STAR + " no measurable speed "
        f"difference from caching. {len(surprises)} surprises in all. | Table 7 |",
        "",
        "## Proof each setup did what we think",
        "",
        "**Table 2: Cache Check from the API's Token Counts**",
        "",
        "| Setup | Model calls | Calls with cached tokens > 0 | Cached tokens (all calls) | Cache-write tokens | Cache hit rate (cached ÷ input) | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in SETUP_ORDER:
        cs = cby[s]
        hits = sum(c["cached_tokens"] > 0 for c in cs)
        cached = sum(c["cached_tokens"] for c in cs)
        inp = sum(c["input_tokens"] for c in cs)
        writes = sum(c["cache_write_tokens"] for c in cs)
        if s == "without_cache":
            verdict = "✅ Nothing reused: 0 cached tokens on every call" if cached == 0 else "❌ INVALID: cached tokens found"
        else:
            verdict = f"✅ Handbook reused on {hits} of {len(cs)} calls"
        L.append(f"| {SETUP_NAMES[s]} | {len(cs)} | {hits} | {cached:,} | {writes:,} | {cached / inp:.1%} | {verdict} |")

    L += [
        "",
        "## Cost for each setup",
        "",
        "**Table 3: Total Cost, Cost per Document and Percent Saved**",
        "",
        "| Setup | Documents | Model calls | Input tokens | Cached | Cache write | Output tokens | Total cost | Cost per document | Avg seconds per document | Documents correct |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in SETUP_ORDER:
        L.append(
            f"| {SETUP_NAMES[s]} | {len(by[s])} | {len(cby[s])} | {total(s, 'input_tokens'):,} | {total(s, 'cached_tokens'):,} "
            f"| {total(s, 'cache_write_tokens'):,} | {total(s, 'output_tokens'):,} | **{money(tot[s])}** | "
            f"**{money(per_doc[s])}** | {secs[s]:.1f} | {correct[s]}/12 |"
        )
    L += [
        f"| **Saved with cache** | | | | | | | **{money(tot['without_cache'] - tot['with_cache'])}** | "
        f"**{money(per_doc['without_cache'] - per_doc['with_cache'])}** | | |",
        "",
        f"**Percent saved with cache: {saved:.1%}.**",
        "",
        "**Table 4: Without-Cache Cost, as Billed vs. at the Plain Input Rate**",
        "",
        "| Without-cache cost | Total (12 docs) | Per document | Percent saved by caching |",
        "|---|---|---|---|",
        f"| As the API reported it (input billed as cache writes, $0.125/1M) | {money(tot['without_cache'])} | "
        f"{money(per_doc['without_cache'])} | {saved:.1%} |",
        f"| If the same input were billed at the plain $0.10/1M input rate | {money(plain)} | {money(plain / 12)} | "
        f"{1 - tot['with_cache'] / plain:.1%} |",
        "",
        "## Real numbers vs. the Problem 2 estimate",
        "",
        "Problem 2 estimated the **handbook alone** at 10,058 tokens: $0.0010058 per call without cache and "
        "$0.00010058 with cache. Real calls also carry `prompt.md`, the tool definitions, the output format, the "
        "vendor document and the output, and **each document takes 2 calls**, each resending the handbook.",
        "",
        "**Table 5: Problem 2 Estimate vs. Real Runs**",
        "",
        "| Measure | Problem 2 estimate | Real (without cache) | Real (with cache) | Why they differ |",
        "|---|---|---|---|---|",
        f"| Input tokens per model call | 10,058 (handbook only) | {avg_in_all['without_cache']:,.0f} | "
        f"{avg_in_all['with_cache']:,.0f} | `prompt.md`, tool definitions, the output format and the document add to "
        "the handbook. The 2nd call also carries the document text from the 1st. |",
        f"| Input tokens, first call of each document | 10,058 | "
        f"{sum(c['input_tokens'] for c in req1['without_cache']) / 12:,.0f} | {avg_in1:,.0f} | "
        f"About {avg_in1 - EST_TOKENS:,.0f} tokens of `prompt.md`, tools and output format on top of the handbook. |",
        f"| Cost per model call | {money(EST_UNCACHED)} / {money(EST_CACHED)} | "
        f"{money(tot['without_cache'] / len(cby['without_cache']))} | {money(tot['with_cache'] / len(cby['with_cache']))} "
        "| Uncached input is billed as cache writes ($0.125, not $0.10), plus the extra tokens and the output. |",
        f"| Cost per document | (one call assumed) | {money(per_doc['without_cache'])} | {money(per_doc['with_cache'])} | "
        "2 calls per document, so the handbook is paid for twice. |",
        f"| Cost of 1,000 | $1.0058 / $0.1017 (1,000 calls) | {money(per_doc['without_cache'] * 1000)} | "
        f"{money(per_doc['with_cache'] * 1000)} | Per 1,000 documents (2,000 calls). |",
        f"| Percent saved by caching | about 90% | {saved:.1%} | | The cache cuts only the repeated handbook. The "
        "document, the 2nd call's new tokens and the output cost the same either way. |",
        "",
        "## Projection: 1,000 documents a day for 30 days",
        "",
        "Using the measured cost per document from Table 3, for 1,000 documents a day × 30 days = 30,000 documents.",
        "",
        "**Table 6: 30-Day Projection at 1,000 Documents a Day**",
        "",
        "| Setup | Cost per document | Per day (1,000 docs) | 30 days (30,000 docs) |",
        "|---|---|---|---|",
    ]
    for s in SETUP_ORDER:
        L.append(f"| {SETUP_NAMES[s]} | {money(per_doc[s])} | {money(per_doc[s] * 1000)} | **{money(month[s])}** |")
    L += [
        f"| **Saved with cache** | {money(per_doc['without_cache'] - per_doc['with_cache'])} | "
        f"{money((per_doc['without_cache'] - per_doc['with_cache']) * 1000)} | "
        f"**{money(month['without_cache'] - month['with_cache'])}** |",
        "",
        "The with-cache cost assumes the cache stays warm. With a 12-hour cache lifetime and documents arriving all "
        f"day, the handbook is written to the cache only about twice a day, about "
        f"{money(2 * 30 * 11_000 * RATES['cache_write_per_1m'] / 1e6)} over 30 days, which barely changes the total.",
        "",
        "## Surprises in the numbers (reviewed with Lou)",
        "",
        "Flagged for Lou to evaluate, then reviewed and refined with Lou. Lou's own insight is in the notes at the "
        "end of this file.",
        "",
        "**Table 7: Surprises in the Numbers and Why They Happen**",
        "",
        "| # | What surprised us | The numbers | Why it happens |",
        "|---|---|---|---|",
    ]
    for i, (what, nums, why) in enumerate(surprises, 1):
        star = f" {STAR}" if i in starred else ""
        L.append(f"| S{i}{star} | **{what}**{' (headline)' if i == 1 else ''} | {nums} | {why} |")
    L += [
        "",
        STAR + " Headline surprises (red circled asterisk). **S1 is the headline**, followed by S2, S3 and S4.",
        "",
        "## Every model call",
        "",
        f"All {len(calls)} model calls from both setups, as saved in `output/cache_test.json`. Request 1 is the model "
        "asking for `read_document`; request 2 is the model's answer. Token counts are as the API reported them; "
        "costs use `data/prices.json`.",
        "",
        "**Table 8: Every Model Call from Both Setups**",
        "",
        "| # | Setup | Document | Request | Input | Cached | Cache write | Uncached | Output (reasoning) | Cost: cached | Cost: write | Cost: uncached | Cost: output | Total |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(calls, 1):
        p = c["cost_usd"]
        L.append(
            f"| {i} | {SETUP_NAMES[c['setup']]} | {c['document']} | {c['request']} | {c['input_tokens']:,} | "
            f"{c['cached_tokens']:,} | {c['cache_write_tokens']:,} | {c['uncached_input_tokens']:,} | "
            f"{c['output_tokens']} ({c['reasoning_tokens']}) | ${p['cached_input']:.6f} | ${p['cache_write']:.6f} | "
            f"${p['fresh_input']:.6f} | ${p['output']:.6f} | ${p['total']:.6f} |"
        )

    kept = "\n\n## Lou's notes on the surprises\n\n(Space for my own review of Table 7.)\n"
    if MD_OUT.exists() and MARKER in (old := MD_OUT.read_text(encoding="utf-8")) and old.split(MARKER, 1)[1].strip():
        kept = old.split(MARKER, 1)[1]
    MD_OUT.write_text("\n".join(L) + "\n\n" + MARKER + kept, encoding="utf-8")
    print(f"Wrote {MD_OUT.relative_to(ROOT)}: without {money(tot['without_cache'])}, with {money(tot['with_cache'])}, saved {saved:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true", help="rebuild cache_test.md from cache_test.json")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(JSON_OUT.read_text(encoding="utf-8")) if args.report_only else asyncio.run(run_all())
    report(data)
