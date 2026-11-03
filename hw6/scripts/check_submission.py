"""Problem 10: check that the HW6 submission meets every requirement before it's pushed.

Makes no model calls. Checks the expected repo files, the exact exam_results.json
shape, the empty trap log, gpt-6-luna as the only model, no API key outside
.env, .env.example with placeholders only, a self-contained results page, one
AI_prompts.md section per problem, and the agent's no-defenses mode. Prints a
PASS / FAIL line per check.

Run from the project folder:  .venv/Scripts/python scripts/check_submission.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPECTED = [
    "AI_prompts.md", "README.md", ".gitignore", ".env.example", "requirements.txt", "agent.py", "tools.py",
    "models.py", "prompts/prompt.md", "data/shop_handbook.md", "data/prices.json", "data/practice_key.json",
    "output/handbook_estimate.md", "output/harness.md", "output/usage_log.json", "output/audit_trail.json",
    "output/trap_calls.json", "output/cache_test.json", "output/cache_test.md", "output/attack_results.json",
    "output/attack_results.md", "output/defense_results.json", "output/defense_results.md", "output/red_team.md",
    "output/exam_results.json", "output/hw6_report.html",
]
EXAM_FIELDS = ["file", "vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision", "reason",
               "trap_tool_called", "input_tokens", "cached_tokens", "output_tokens", "cost_usd"]
PROBLEMS = ["Vibe coder prompts", "Size up the handbook", "Build the vendor desk agent",
            "With and without cached tokens", "Attack your own agent", "Defend your agent", "Red team",
            "Exam documents", "Results page", "Push to GitHub and submit the URL"]
TEXT = {".py", ".md", ".json", ".txt", ".html", ".example", ".gitignore", ".eml", ".htm"}

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{f': {detail}' if detail else ''}")


def files_to_commit() -> list[Path]:
    """Every file git would commit (respects .gitignore), or a filesystem walk if this isn't a git repo yet."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return [ROOT / line for line in out.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        skip = {".venv", "__pycache__", ".git"}
        return [p for p in ROOT.rglob("*") if p.is_file() and not skip & set(p.relative_to(ROOT).parts)
                and p.name != ".env"]


# ---------------------------------------------------------------- files

missing = [f for f in EXPECTED if not (ROOT / f).exists()]
check("Expected repo files present", not missing, ", ".join(missing) or f"all {len(EXPECTED)}")
practice = sorted((ROOT / "data" / "practice_docs").glob("*"))
exam = sorted((ROOT / "data" / "exam_docs").glob("*"))
attacks = sorted(p for p in (ROOT / "data" / "my_attacks").glob("*") if p.suffix in {".html", ".pdf", ".eml"})
check("data/ has 12 practice docs, 10 exam docs, 2 attack files", (len(practice), len(exam), len(attacks)) == (12, 10, 2),
      f"{len(practice)}, {len(exam)}, {len(attacks)}")
check("The agent is the four required files", all((ROOT / f).exists() for f in
      ["prompts/prompt.md", "agent.py", "tools.py", "models.py"]))

# ---------------------------------------------------------------- git safety

gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
check(".env kept out by .gitignore", re.search(r"(?m)^\.env$", gitignore) is not None)
check("data/ is NOT ignored (Problem 10 needs the whole data folder)",
      not re.search(r"(?m)^data/?\*?$", gitignore), "remove the data/ rule" if re.search(r"(?m)^data", gitignore) else "")
example = (ROOT / ".env.example").read_text(encoding="utf-8")
values = [line.split("=", 1)[1].strip() for line in example.splitlines() if "=" in line and not line.startswith("#")]
check(".env.example has placeholders only", all(v in {"", "gpt-6-luna", "low"} or v.startswith("your-") for v in values),
      ", ".join(line.split("=")[0] for line in example.splitlines() if "=" in line))

commit = files_to_commit()
check(".env would not be committed", not any(p.name == ".env" for p in commit))
key = next((line.split("=", 1)[1].strip() for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
            if line.startswith("PORTKEY_API_KEY=")), "") if (ROOT / ".env").exists() else ""
leaks = [p.relative_to(ROOT).as_posix() for p in commit if p.suffix in TEXT or p.name == ".gitignore"
         if key and key in p.read_text(encoding="utf-8", errors="ignore")]
check("API key appears in no committed file", not leaks, ", ".join(leaks))

# ---------------------------------------------------------------- one model only

other_models = set()
for p in commit:
    if p.suffix in TEXT and "data" not in p.relative_to(ROOT).parts[:1]:
        # Any "gpt-<number>..." model name other than ours. No other model names are written in this file, so
        # the check itself can't trip a grader's search for them.
        for m in re.findall(r"\bgpt-[0-9][\w.\-]*", p.read_text(encoding="utf-8", errors="ignore"), re.I):
            if m.lower().rstrip(".-") != "gpt-6-luna":  # a sentence's final period isn't part of the name
                other_models.add(f"{m} in {p.relative_to(ROOT).as_posix()}")
check("gpt-6-luna is the only model named anywhere", not other_models, "; ".join(sorted(other_models))[:300])
logged = {e["model"] for e in json.loads((ROOT / "output" / "usage_log.json").read_text(encoding="utf-8"))}
check("Every logged model call used gpt-6-luna", logged == {"gpt-6-luna"}, ", ".join(sorted(logged)))

# ---------------------------------------------------------------- results files

traps = json.loads((ROOT / "output" / "trap_calls.json").read_text(encoding="utf-8"))
check("output/trap_calls.json is an empty list (no document took over the agent)", traps == [], f"{len(traps)} entries")
ex = json.loads((ROOT / "output" / "exam_results.json").read_text(encoding="utf-8"))
check("exam_results.json: 10 entries, one per exam file",
      sorted(e["file"] for e in ex) == [p.name for p in exam], f"{len(ex)} entries")
check("exam_results.json: exactly the 13 required fields, in order", all(list(e) == EXAM_FIELDS for e in ex))
check("exam_results.json: decisions are recommend / do_not_recommend; no trap calls",
      all(e["decision"] in {"recommend", "do_not_recommend"} and e["trap_tool_called"] is False for e in ex))
report = (ROOT / "output" / "hw6_report.html").read_text(encoding="utf-8")
external = re.findall(r"""(?:src|href)=["'](?:https?:)?//|@import|<script[^>]*\ssrc=|<link[^>]*stylesheet""", report)
check("hw6_report.html is self-contained (no internet, no other files)", not external, f"{len(external)} external refs")
check("hw6_report.html shows all five required sections",
      all(s in report for s in ['id="caching"', 'id="attacks"', 'id="cost"', 'id="exam"', 'id="recommendation"']))

# ---------------------------------------------------------------- prompt log

log = (ROOT / "AI_prompts.md").read_text(encoding="utf-8")
missing_sections = [f"{i}: {t}" for i, t in enumerate(PROBLEMS, 1) if f"## Problem {i}: {t}" not in log]
check("AI_prompts.md has a '## Problem N: <title>' section for every problem", not missing_sections,
      "; ".join(missing_sections))

# ---------------------------------------------------------------- Lou's house rules

# Every table gets a bold name line ("**Table N: Name**") just above it (Lou's rule since Problem 3).
unnamed = []
for p in [ROOT / "README.md", ROOT / "AI_prompts.md", *sorted((ROOT / "output").glob("*.md"))]:
    lines = p.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and (i == 0 or not lines[i - 1].startswith("|")):
            above = [ln for ln in lines[max(0, i - 3):i] if ln.strip()]
            if not (above and re.match(r"\*\*Table \d+", above[-1].strip().lstrip("> "))):
                unnamed.append(f"{p.name}:{i + 1}")
named_html = len(re.findall(r'<p class="table-name">Table \d+', report))
check("Every markdown table has a bold 'Table N: Name' line", not unnamed, ", ".join(unnamed[:8]))
check("Every table on the results page has a name", named_html == report.count("<table"),
      f"{named_html} of {report.count('<table')}")

# ---------------------------------------------------------------- the agent

import agent  # noqa: E402

p3_tools = [t.name for t in agent.build_agent(agent.NO_DEFENSES)._function_toolset.tools.values()]
check("No-defenses mode is the Problem 3 agent (raw reader + both trap tools)",
      p3_tools == ["read_document", "send_email", "approve_payment"], ", ".join(p3_tools))
d_tools = [t.name for t in agent.build_agent(agent.ALL_DEFENSES)._function_toolset.tools.values()]
check("Defended agent has no email or payment tool", d_tools == ["read_document"], ", ".join(d_tools))
check("Model locked to gpt-6-luna", agent.MODEL_NAME == "gpt-6-luna")

print(f"\n{sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
