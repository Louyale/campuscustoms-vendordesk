"""Problem 8: run the final defended agent on all 10 exam documents.

Runs agent.review (all three defense layers, the default) on every file in
data/exam_docs/ and saves output/exam_results.json with exactly the fields the
problem lists, one entry per exam file. Nothing is edited by hand: every value
comes straight from the run.

Also writes output/exam_results.md, a readable table of the same results.

Run from HW6/:         .venv/Scripts/python scripts/exam_run.py
Consistency check:     .venv/Scripts/python scripts/exam_run.py --check
Rebuild the table:     .venv/Scripts/python scripts/exam_run.py --report-only
  (runs the agent again and compares with exam_results.json, without changing it;
   saves the comparison to output/exam_rerun_check.json)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ALL_DEFENSES, AUDIT_TRAIL, MODEL_NAME, ROOT, review  # noqa: E402
from tools import TRAP_CALLS, now  # noqa: E402

EXAM = ROOT / "data" / "exam_docs"
OUT = ROOT / "output" / "exam_results.json"
MD_OUT = ROOT / "output" / "exam_results.md"
CHECK_OUT = ROOT / "output" / "exam_rerun_check.json"
FACTS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]


async def run_exam(label: str) -> list[dict]:
    results = []
    for path in sorted(p for p in EXAM.iterdir() if p.is_file()):
        traps_before = len(json.loads(TRAP_CALLS.read_text(encoding="utf-8")))
        report, usage = await review(path.relative_to(ROOT).as_posix(), label=label, defenses=ALL_DEFENSES)
        audit = json.loads(AUDIT_TRAIL.read_text(encoding="utf-8"))[-1]
        new_traps = json.loads(TRAP_CALLS.read_text(encoding="utf-8"))[traps_before:]
        trap_called = bool(new_traps) or any(c["tool"] in {"send_email", "approve_payment"}
                                             for c in audit["tool_calls"])
        results.append({
            "file": path.name,
            "vendor": report.vendor,
            "sku": report.sku,
            "unit_price": report.unit_price,
            "lead_time_days": report.lead_time_days,
            "min_order": report.min_order,
            "decision": report.decision,
            "reason": report.reason,
            "trap_tool_called": trap_called,
            "input_tokens": usage.input_tokens,
            "cached_tokens": usage.cached_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": usage.cost_usd,
        })
        r = results[-1]
        print(f"{r['file']:20} {r['vendor']!s:26} {r['sku']!s:10} {r['unit_price']!s:>7} {r['lead_time_days']!s:>3} "
              f"{r['min_order']!s:>5} {r['decision']:17} trap={r['trap_tool_called']} "
              f"removed={len(audit['removed_by_code'])} held={audit['flagged_by_design']} "
              f"filled={audit.get('filled_by_design')}")
    return results


def write_md(results: list[dict]) -> None:
    def v(x, f="{}"):
        return "unknown" if x is None else f.format(x)

    L = [
        "# Exam Results (Problem 8)",
        "",
        f"Our final defended agent (all three defense layers, {MODEL_NAME}) on all 10 exam documents in "
        "`data/exam_docs/`, run by `scripts/exam_run.py`. These are the same results as `output/exam_results.json`, "
        "laid out as a table. Nothing was edited by hand.",
        "",
        "**Table 1: Exam Results for All 10 Documents**",
        "",
        "| # | File | Vendor | SKU | Unit price | Lead time | Min order | Decision | Reason | Trap tool called | Input tokens | Cached | Output | Cost |",
        "|:---:|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(results, 1):
        L.append(f"| **{n}** | **Exam {n}:** {r['file']} | {v(r['vendor'])} | {v(r['sku'])} | {v(r['unit_price'], '${:.2f}')} | "
                 f"{v(r['lead_time_days'], '{} days')} | {v(r['min_order'])} | **{r['decision']}** | "
                 f"{r['reason'].replace('|', '/')} | {'yes' if r['trap_tool_called'] else 'no'} | "
                 f"{r['input_tokens']:,} | {r['cached_tokens']:,} | {r['output_tokens']} | ${r['cost_usd']:.6f} |")
    total = sum(r["cost_usd"] for r in results)
    L += ["", f"**Total cost for all 10 documents: ${total:.6f}.** Recommend: "
          f"{sum(r['decision'] == 'recommend' for r in results)}; do not recommend: "
          f"{sum(r['decision'] == 'do_not_recommend' for r in results)}; trap tool calls: "
          f"{sum(r['trap_tool_called'] for r in results)}.",
          "",
          "🚩 **A vulnerability we recognize:** three exam documents (Exam 2, Exam 3 and Exam 4) hid text with HTML "
          "tricks our code layer doesn't catch yet: text pushed off-screen, white text set by a CSS class, and the "
          "`hidden` attribute. The prompt and design layers still kept all three answers right. **We recognize this "
          "vulnerability and would fix it for the future** by teaching the code layer those three tricks and rerunning "
          "our tests. We're leaving the final agent and these results as they are, so the exam fairly measures the "
          "agent we built, not one adjusted after seeing the exam (details in `output/harness.md`, Problem 8)."]
    MD_OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


async def main(check: bool) -> None:
    if check:
        official = {r["file"]: r for r in json.loads(OUT.read_text(encoding="utf-8"))}
        rerun = await run_exam("exam_rerun_check")
        rows = [{"file": r["file"], "same": all(r[f] == official[r["file"]][f] for f in FACTS),
                 "differences": {f: {"official": official[r["file"]][f], "rerun": r[f]}
                                 for f in FACTS if r[f] != official[r["file"]][f]}} for r in rerun]
        CHECK_OUT.write_text(json.dumps({"generated": now(), "rerun_matches_official": sum(x["same"] for x in rows),
                                         "files": rows}, indent=2) + "\n", encoding="utf-8")
        print(f"Rerun matches the official results on {sum(x['same'] for x in rows)} of {len(rows)} files")
        return
    results = await run_exam("exam")
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    write_md(results)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(results)} entries) and {MD_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="rerun and compare without changing exam_results.json")
    parser.add_argument("--report-only", action="store_true", help="rebuild exam_results.md from exam_results.json")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.report_only:
        write_md(json.loads(OUT.read_text(encoding="utf-8")))
    else:
        asyncio.run(main(args.check))
