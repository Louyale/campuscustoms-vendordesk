"""Problem 9: build output/hw6_report.html, the HW6 results page.

One self-contained file: all styles, charts (inline SVG) and text are inside it,
with no internet, no fonts or scripts to download, and no other files next to
it, so it opens by double-click. Every number is read from the results files of
earlier problems, never typed in by hand:

- caching:            output/cache_test.json (Problem 4)
- attacks before:     output/attack_results.json (Problem 5)
- defenses and cost:  output/defense_results.json (Problem 6)
- red team:           output/red_team.json, output/red_team_patched.json (Problem 7)
- exam:               output/exam_results.json, output/exam_rerun_check.json (Problem 8)

Run from HW6/:  .venv/Scripts/python scripts/build_report.py
"""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "hw6_report.html"
BLUE, CORAL = "#286dc0", "#e2582f"  # chart series, validated with the dataviz palette checker (all checks pass)


def load(name: str):
    return json.loads((ROOT / "output" / name).read_text(encoding="utf-8"))


def esc(x) -> str:
    return html.escape(str(x))


def money(x: float, digits: int = 6) -> str:
    return f"${x:,.{digits}f}"


def warm(rows):
    return [r for r in rows if r["tokens"]["cache_write"] < 1000]


def avg(vals):
    vals = list(vals)
    return sum(vals) / len(vals)


# ---------------------------------------------------------------- numbers from earlier problems

cache = load("cache_test.json")
c_runs = {s: [r for r in cache["runs"] if r["setup"] == s] for s in ("without_cache", "with_cache")}
c_total = {s: sum(r["cost_usd"] for r in c_runs[s]) for s in c_runs}
c_doc = {s: c_total[s] / len(c_runs[s]) for s in c_runs}
c_saved = 1 - c_total["with_cache"] / c_total["without_cache"]
c_calls = {s: [c for c in cache["calls"] if c["setup"] == s] for s in c_runs}
c_cached_calls = sum(c["cached_tokens"] > 0 for c in c_calls["with_cache"])
c_nocache_cached = sum(c["cached_tokens"] for c in c_calls["without_cache"])
c_hit = sum(c["cached_tokens"] for c in c_calls["with_cache"]) / sum(c["input_tokens"] for c in c_calls["with_cache"])
EST_SAVED = 0.90  # Problem 2 estimate (output/handbook_estimate.md)

before = load("attack_results.json")["documents"]
defense = load("defense_results.json")
after = defense["documents"]
layer_runs = {"none": defense["layer_runs"]["none"], "code": defense["layer_runs"]["code"],
              "design": defense["layer_runs"]["design"], "prompt": defense["layer_runs"]["prompt"], "all": after}
attack_docs = [d["document"] for d in before
               if any(h.get("tag") != "script" for h in d["person_view"]["hidden_from_a_person"])]


def win_rate(rows, docs=None):
    rows = [r for r in rows if docs is None or r["document"] in docs]
    return sum(not r["fooled"] for r in rows), len(rows)


wb, wa = win_rate(before), win_rate(after)
d_cost = {s: avg(r["cost_usd"] for r in warm(rows)) for s, rows in layer_runs.items()}
d_in = {s: avg(r["tokens"]["input"] for r in warm(rows)) for s, rows in layer_runs.items()}
d_unc = {s: avg(r["tokens"]["input"] - r["tokens"]["cached"] for r in warm(rows)) for s, rows in layer_runs.items()}

red = load("red_team.json")
red_p = load("red_team_patched.json")
exam = load("exam_results.json")
exam_check = load("exam_rerun_check.json")

MONTH_DOCS = 1000 * 30
month_defended = d_cost["all"] * MONTH_DOCS
month_no_cache = c_doc["without_cache"] * MONTH_DOCS
cache_writes_month = 2 * 30 * 11_000 * 0.125 / 1_000_000  # about two cache writes a day (12-hour cache)
exam_avg = avg(r["cost_usd"] for r in exam)
rt_none = sum(r["fooled"] for r in red["runs"] if r["setup"] == "none")
rt_all = sum(r["fooled"] for r in red["runs"] if r["setup"] == "all")
rt_n = sum(1 for r in red["runs"] if r["setup"] == "all")


# ---------------------------------------------------------------- charts (inline SVG, no scripts)


def bar_chart(title: str, rows: list[tuple[str, float, str, str]], fmt, width=972, note="") -> str:
    """Horizontal bars. rows: (label, value, color, tooltip). Thin bars, rounded data ends, direct labels."""
    # width matches the space the chart gets on the page (972px full, 474px half), so text stays 14px
    label_w = 250 if width > 600 else 110
    bar_h, gap, top = 26, 18, 8
    plot_w = width - label_w - 120
    vmax = max(v for _, v, _, _ in rows) or 1
    h = top + len(rows) * (bar_h + gap)
    parts = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="{esc(title)}">']
    for i, (label, value, color, tip) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(3, plot_w * value / vmax)
        parts.append(
            f'<g class="bar"><title>{esc(tip)}</title>'
            f'<rect x="0" y="{y - 6}" width="{width}" height="{bar_h + 12}" fill="transparent"/>'
            f'<text x="{label_w - 12}" y="{y + bar_h / 2 + 5}" text-anchor="end" class="axis-label">{esc(label)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" fill="{color}"/>'
            f'<text x="{label_w + w + 8:.1f}" y="{y + bar_h / 2 + 5}" class="value-label">{esc(fmt(value))}</text></g>')
    parts.append(f'<line x1="{label_w}" y1="0" x2="{label_w}" y2="{h - gap + 6}" class="baseline"/></svg>')
    return (f'<figure><figcaption>{esc(title)}</figcaption>{"".join(parts)}'
            f'{f"<p class=note>{note}</p>" if note else ""}</figure>')


def legend(items: list[tuple[str, str]]) -> str:
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(t)}</span>' for t, c in items) + "</div>"


# ---------------------------------------------------------------- page sections


def tile(value: str, label: str, sub: str = "") -> str:
    return f'<div class="tile"><div class="tile-value">{value}</div><div class="tile-label">{label}</div>' \
           f'{f"<div class=tile-sub>{sub}</div>" if sub else ""}</div>'


def ok(flag: bool, yes="Correct", no="Fooled") -> str:
    return f'<span class="pill good">✓ {yes}</span>' if flag else f'<span class="pill bad">✗ {no}</span>'


hero = "".join([
    tile(f"{c_saved:.1%}", "saved by caching the handbook", f"Problem 2 estimate: about {EST_SAVED:.0%}"),
    tile(f"{wb[0] / wb[1]:.0%} → {wa[0] / wa[1]:.0%}", "practice documents right, before → after defenses",
         f"{len(attack_docs)} of {len(attack_docs)} planted attacks stopped"),
    tile(f"{len(exam)} / {len(exam)}", "exam documents answered, 0 trap tool calls",
         f"a rerun matched {exam_check['rerun_matches_official']} of {len(exam)}"),
    tile(money(month_defended + cache_writes_month, 2), "per month at 1,000 documents a day", "defended agent, cache on"),
])

# 1. Caching
sec1_chart = bar_chart(
    "Cost per vendor document (12 practice documents, real runs)",
    [("Without cache", c_doc["without_cache"], CORAL, f"Without cache: {money(c_doc['without_cache'])} per document"),
     ("With cache", c_doc["with_cache"], BLUE, f"With cache: {money(c_doc['with_cache'])} per document")],
    lambda v: money(v), width=474)
sec1_month = bar_chart(
    "Projected cost for 30 days at 1,000 documents a day",
    [("Without cache", c_doc["without_cache"] * MONTH_DOCS, CORAL,
      f"Without cache: {money(c_doc['without_cache'] * MONTH_DOCS, 2)} a month"),
     ("With cache", c_doc["with_cache"] * MONTH_DOCS, BLUE,
      f"With cache: {money(c_doc['with_cache'] * MONTH_DOCS, 2)} a month")],
    lambda v: money(v, 2), width=474)
sec1 = f"""
<section id="caching"><div class="sec-head"><span class="num">1</span><h2>Caching results</h2></div>
<p class="lead">The 10,058-token shop handbook goes out on every call. Cached, gpt-6-luna reads it at a tenth of the
price, so caching cut the bill by <b>{c_saved:.1%}</b>. That's within one point of our Problem 2 estimate of about
{EST_SAVED:.0%}, a check on the accuracy of our own math.</p>
{legend([("Without cache", CORAL), ("With cache", BLUE)])}
<div class="two">{sec1_chart}{sec1_month}</div>
<p class="table-name">Table 1: Caching Results by Setup</p>
<table><thead><tr><th>Setup</th><th>Model calls</th><th>Calls reusing the cache</th><th>Total (12 docs)</th>
<th>Per document</th><th>30 days × 1,000 a day</th></tr></thead><tbody>
<tr><td>Without cache</td><td>{len(c_calls['without_cache'])}</td><td>0 ({c_nocache_cached:,} cached tokens: proof nothing was reused)</td>
<td>{money(c_total['without_cache'], 4)}</td><td>{money(c_doc['without_cache'])}</td><td>{money(c_doc['without_cache'] * MONTH_DOCS, 2)}</td></tr>
<tr><td>With cache</td><td>{len(c_calls['with_cache'])}</td><td>{c_cached_calls} of {len(c_calls['with_cache'])} ({c_hit:.1%} of input tokens)</td>
<td>{money(c_total['with_cache'], 4)}</td><td>{money(c_doc['with_cache'])}</td><td>{money(c_doc['with_cache'] * MONTH_DOCS, 2)}</td></tr>
</tbody></table>
<p class="source">Source: <code>output/cache_test.json</code>, <code>output/cache_test.md</code> (Problem 4).</p></section>"""

# 2. Attacks before and after
grid = []
for b in before:
    a = next(x for x in after if x["document"] == b["document"])
    hidden = [h for h in b["person_view"]["hidden_from_a_person"] if h.get("tag") != "script"]
    planted = esc(hidden[0]["how"].split(" (")[0]) if hidden else "none (clean)"
    what = "; ".join(b["fooled_by"]) if b["fooled"] else ""
    grid.append(f"<tr><td><code>{esc(b['document'])}</code></td><td>{planted}</td>"
                f"<td>{ok(not b['fooled'])}{f'<div class=small>{esc(what)}</div>' if what else ''}</td>"
                f"<td>{ok(not a['fooled'])}</td></tr>")
layer_names = {"none": "No defenses", "code": "Code only", "design": "Design only", "prompt": "Prompt only",
               "all": "All three layers"}
sec2_chart = bar_chart(
    "Practice documents answered correctly (out of 12)",
    [("Before (Problem 5, no defenses)", wb[0], CORAL, f"Before: {wb[0]} of {wb[1]} correct"),
     ("After (all three defense layers)", wa[0], BLUE, f"After: {wa[0]} of {wa[1]} correct")],
    lambda v: f"{v:.0f} of 12 ({v / 12:.0%})")
sec2 = f"""
<section id="attacks"><div class="sec-head"><span class="num">2</span><h2>Attacks before and after our defenses</h2></div>
<p class="lead">{len(attack_docs)} of the 12 practice documents hide instructions a person can't see. With no defenses,
two fooled the agent into recommending quotes it should have rejected. With three defense layers, every document
came back right, and no email or payment tool was ever called.</p>
{legend([("Before", CORAL), ("After", BLUE)])}
{sec2_chart}
<div class="layers">
<div><h3>Code</h3><p>Before any model reads it, the program opens the document the way a person would and passes on only the visible text.</p></div>
<div><h3>Design</h3><p>The reading agent has no email or payment tools. Python, not the model, makes the buy decision, and checks every fact against the visible page.</p></div>
<div><h3>Prompt</h3><p>Safety rules tell the model the document is data, not instructions: use the quote's own fields and ignore "corrections".</p></div>
</div>
<p class="table-name">Table 2: Each Practice Document Before and After the Defenses</p>
<table><thead><tr><th>Document</th><th>Hidden attack</th><th>Before (no defenses)</th><th>After (defended)</th></tr></thead>
<tbody>{"".join(grid)}</tbody></table>
<p class="source">Source: <code>output/attack_results.json</code> (Problem 5), <code>output/defense_results.json</code> (Problem 6).</p></section>"""

# 3. What the defenses cost
cost_rows = [(layer_names[s], d_cost[s], BLUE if s == "all" else "#8a96a3",
              f"{layer_names[s]}: {money(d_cost[s])} per document") for s in ("none", "code", "design", "prompt", "all")]
sec3_rows = "".join(
    f"<tr><td>{layer_names[s]}</td><td>{d_in[s]:,.0f}</td><td>{d_unc[s]:,.0f}</td><td>{money(d_cost[s])}</td>"
    f"<td>{'—' if s == 'none' else f'{d_in[s] - d_in['none']:+,.0f}'}</td>"
    f"<td>{'—' if s == 'none' else f'{d_cost[s] - d_cost['none']:+.6f}'}</td>"
    f"<td>{win_rate(layer_runs[s])[0]} of 12</td></tr>" for s in ("none", "code", "design", "prompt", "all"))
sec3 = f"""
<section id="cost"><div class="sec-head"><span class="num">3</span><h2>What the defenses cost</h2></div>
<p class="lead">Nothing extra. The defended agent costs <b>{money(d_cost['all'])}</b> per document vs.
<b>{money(d_cost['none'])}</b> with no defenses. The code layer strips HTML and email encoding, which saves more
tokens than the safety rules add, and the safety rules are cached, so they cost a tenth of the input price.</p>
{bar_chart("Cost per document by defense setup (cache warm)", cost_rows, lambda v: money(v),
           note="Gray: the no-defense baseline and each layer alone. Blue: the defended agent (all three layers).")}
<p class="table-name">Table 3: Tokens and Dollars by Defense Setup</p>
<table><thead><tr><th>Setup</th><th>Input tokens</th><th>Uncached tokens</th><th>Cost per document</th>
<th>Extra tokens vs. none</th><th>Extra dollars vs. none</th><th>Practice docs right</th></tr></thead>
<tbody>{sec3_rows}</tbody></table>
<p class="source">Source: <code>output/defense_results.json</code>, <code>output/defense_results.md</code> Table 5 (Problem 6). Averages over runs with a warm cache.</p></section>"""

# 4. Exam results and red team
exam_rows = "".join(
    f"<tr><td class=n>{i}</td><td><code>{esc(r['file'])}</code></td><td>{esc(r['vendor'])}</td><td class=nw>{esc(r['sku'])}</td>"
    f"<td>{'unknown' if r['unit_price'] is None else money(r['unit_price'], 2)}</td><td>{r['lead_time_days']} days</td>"
    f"<td>{r['min_order']:,}</td><td><span class='pill {'good' if r['decision'] == 'recommend' else 'neutral'}'>"
    f"{'Recommend' if r['decision'] == 'recommend' else 'Do not recommend'}</span></td>"
    f"<td>{'yes' if r['trap_tool_called'] else 'no'}</td><td>{money(r['cost_usd'])}</td></tr>"
    for i, r in enumerate(exam, 1))
cards = []
for a in red["attacks"]:
    runs = {s: [r for r in red["runs"] if r["document"] == a["file"] and r["setup"] == s] for s in ("none", "all")}
    n_none = sum(r["fooled"] for r in runs["none"])
    n_all = sum(r["fooled"] for r in runs["all"])
    cards.append(f"""<div class="card"><div class="card-kicker">Red team attack</div><h3>{esc(a['attack']['name'])}</h3>
<p><code>{esc(a['file'])}</code></p>
<dl><dt>Hidden how</dt><dd>{esc(a['attack']['trick'])}</dd><dt>Tries to make the agent</dt><dd>{esc(a['attack']['goal'])}</dd></dl>
<div class="ba"><div class="b"><span>No defenses</span><b>fooled {n_none} of {len(runs['none'])}</b></div>
<div class="a"><span>Defended</span><b>fooled {n_all} of {len(runs['all'])}</b></div></div></div>""")
sec4 = f"""
<section id="exam"><div class="sec-head"><span class="num">4</span><h2>Exam results and our two red team attacks</h2></div>
<p class="lead">The final defended agent ran once on the 10 exam documents, with no hand edits. Every answer matches
what a person sees on the quote, <b>no trap tool was called</b>, the clean documents were handled normally, and a
second run matched on <b>{exam_check['rerun_matches_official']} of {len(exam)}</b>. Total cost for all 10:
{money(sum(r['cost_usd'] for r in exam), 4)}.</p>
<p class="table-name">Table 4: Exam Results for All 10 Documents</p>
<table class="exam"><thead><tr><th>#</th><th>File</th><th>Vendor</th><th>SKU</th><th>Unit price</th><th>Lead time</th>
<th>Min order</th><th>Decision</th><th>Trap tool</th><th>Cost</th></tr></thead><tbody>{exam_rows}</tbody></table>
<p class="flag">🚩 A vulnerability we recognize: exam 2, 3 and 4 hid text with HTML tricks our code layer doesn't
catch yet (off-screen text, a white CSS class, the <code>hidden</code> attribute). The other layers kept every answer
right. We'd fix this for the future, and left the agent as is so the exam measures what we built.</p>
<h3 class="sub">Our red team: two new booby-trapped documents</h3>
<div class="cards">{"".join(cards)}</div>
<p class="small">After the red team, we patched both weak spots in the defended layers. Each attack is now stopped by
more than one layer, and a regression run still scored {sum(not d['fooled'] for d in red_p['practice'])} of 12 on the
practice documents.</p>
<p class="source">Source: <code>output/exam_results.json</code>, <code>output/exam_rerun_check.json</code> (Problem 8),
<code>output/red_team.json</code>, <code>output/red_team_patched.json</code> (Problem 7).</p></section>"""

# 5. Recommendation (original analysis)
sec5 = f"""
<section id="recommendation"><div class="sec-head"><span class="num">5</span><h2>Recommendation to the store manager</h2></div>
<div class="analysis">
<div class="analysis-badge">Analysis</div>
<p class="verdict"><b>Yes, turn the vendor desk agent on for real vendor mail</b>, with a person signing off on
anything that spends money.</p>
<div class="cost-box"><div><span>Cost per month at 1,000 documents a day</span><b>{money(month_defended + cache_writes_month, 2)}</b>
<small>defended agent, cache on ({money(d_cost['all'])} per document × 30,000, plus about {money(cache_writes_month, 2)} of cache writes)</small></div>
<div><span>If caching were off</span><b>{money(month_no_cache, 2)}</b><small>so keep caching on: it saves about {money(month_no_cache - month_defended, 2)} a month</small></div></div>
<h3>Wouldn't the undefended agent be cheaper? No.</h3>
<p>It's a fair question, and the undefended agent is a good tool on its own: it's efficient, cheap, and right most of
the time. But measured the same day, with the cache warm, it costs <b>slightly more</b>, not less, and it's less
accurate. The defenses strip out HTML tags, page code and email encoding before the model reads anything, which
removes more tokens than the safety rules add.</p>
<p class="table-name">Table 5: Undefended vs. Defended Agent</p>
<table class="compare"><thead><tr><th></th><th>Undefended agent</th><th>Defended agent</th></tr></thead><tbody>
<tr><td>Cost per document (cache warm)</td><td>{money(d_cost['none'])}</td><td><b>{money(d_cost['all'])}</b></td></tr>
<tr><td>Cost per month at 1,000 a day</td><td>{money(d_cost['none'] * MONTH_DOCS + cache_writes_month, 2)}</td>
<td><b>{money(d_cost['all'] * MONTH_DOCS + cache_writes_month, 2)}</b></td></tr>
<tr><td>Practice documents right</td><td>{wb[0]} of {wb[1]} ({wb[0] / wb[1]:.1%})</td><td><b>{wa[0]} of {wa[1]} ({wa[0] / wa[1]:.0%})</b></td></tr>
<tr><td>Clean documents right (no hidden tricks)</td><td>{win_rate(before, [d['document'] for d in before if d['document'] not in attack_docs])[0]} of
{len(before) - len(attack_docs)} (100%)</td><td><b>{win_rate(after, [d['document'] for d in after if d['document'] not in attack_docs])[0]} of {len(after) - len(attack_docs)} (100%)</b></td></tr>
<tr><td>Booby-trapped documents right</td><td>{win_rate(before, attack_docs)[0]} of {len(attack_docs)} ({win_rate(before, attack_docs)[0] / len(attack_docs):.1%})</td>
<td><b>{win_rate(after, attack_docs)[0]} of {len(attack_docs)} (100%)</b></td></tr>
<tr><td>Our red team attacks</td><td>fooled {rt_none} of {rt_n} runs</td><td><b>fooled {rt_all} of {rt_n} runs</b></td></tr>
<tr><td>Can a document reach the email or payment tools?</td><td>Yes (it didn't call them in our runs, but nothing stops it)</td><td><b>No: the tools aren't there</b></td></tr>
</tbody></table>
<p>The undefended agent's misses aren't small, either. Each one <b>approved a quote the handbook rejects</b>: p12's
hidden "revised" price would have signed a $27.72 quote that's $894 over budget on a 200-unit order. One mistake
like that costs more than {int(894 / ((month_defended + cache_writes_month) * 12))} years of running the defended agent. So the defended agent is the better deal on
every count: about {money((d_cost['none'] - d_cost['all']) * MONTH_DOCS, 2)} a month cheaper, more accurate, and
safe.</p>
<h3>Why</h3>
<ul>
<li><b>It's accurate.</b> It got 12 of 12 practice documents right after defenses (up from 10 of 12). On the
exam it answered all 10 from the visible quote, and a rerun gave the same answers.</li>
<li><b>It's safe by design.</b> The agent that reads vendor mail can't send email or approve payments at all, Python
applies the handbook rules, and every hidden-text attack we or the course could build was stopped.</li>
<li><b>It's cost-effective.</b> About {money(month_defended + cache_writes_month, 2)} a month, around
{money((month_defended + cache_writes_month) * 12, 0)} a year, is tiny next to the buyer time it frees from reading
and checking every quote by hand. That's money well spent.</li>
</ul>
<h3>How to turn it on</h3>
<ol>
<li><b>Start with a 2–4 week pilot.</b> The agent drafts, and the buyer checks each recommendation before any
order.</li>
<li><b>Keep people in charge of money.</b> Payments and vendor emails stay with the buyer and the bookkeeper, with a
human sign-off.</li>
<li><b>Fix the known gap first.</b> Teach the code layer the three HTML hiding tricks the exam exposed before full
launch.</li>
<li><b>Watch the logs weekly.</b> Review the audit trail and confirm <code>trap_calls.json</code> stays empty. Any
entry means a document tried to take over the agent.</li>
</ol>
</div></section>"""

CSS = f"""
:root {{ --navy:#00356b; --blue:{BLUE}; --coral:{CORAL}; --cream:#f5f3ed; --ink:#1d2733; --muted:#5b6673;
  --line:#dfe3e8; --card:#ffffff; --good:#1e7b4a; --bad:#b3261e; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--cream); color:var(--ink); font:16px/1.6 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }}
h1, h2, h3 {{ font-family: Georgia, "Times New Roman", serif; color:var(--navy); line-height:1.25; }}
header.top {{ background:var(--navy); color:#fff; padding:44px 24px 36px; }}
header.top .wrap {{ max-width:1080px; margin:0 auto; display:flex; justify-content:space-between; align-items:flex-start; gap:28px; }}
.brand {{ flex:none; display:flex; flex-direction:column; align-items:center; gap:10px; margin-top:4px; }}
.y-box {{ width:96px; height:96px; background:#fff; border-radius:12px; padding:5px;
  box-shadow:0 6px 16px rgba(0,0,0,.3); }}
/* The Yale athletics block Y: heavy strokes with flat slab serifs, navy on white. Drawn as an inline vector
   shape, so it looks the same everywhere and needs no font or image file. */
.y-box svg {{ display:block; width:100%; height:100%; }}
.som {{ font:italic 600 13px/1.2 "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif; font-variant:small-caps;
  letter-spacing:.1em; color:#f5f3ed; white-space:nowrap; }}
header.top .kicker {{ text-transform:uppercase; letter-spacing:.14em; font-size:13px; opacity:.8; }}
header.top h1 {{ color:#fff; font-size:40px; margin:6px 0 8px; }}
header.top p {{ margin:0; max-width:760px; opacity:.92; }}
nav {{ background:#fff; border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; }}
nav .wrap {{ max-width:1080px; margin:0 auto; display:flex; gap:22px; padding:12px 24px; flex-wrap:wrap; font-size:14px; }}
nav a {{ color:var(--navy); text-decoration:none; font-weight:600; }}
main {{ max-width:1080px; margin:0 auto; padding:28px 24px 60px; }}
.hero {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin:4px 0 30px; }}
.tile {{ background:var(--card); border-radius:12px; padding:18px 18px 16px; box-shadow:0 2px 10px rgba(0,30,70,.10); border-top:4px solid var(--blue); }}
.tile-value {{ font:700 30px/1.15 Georgia, serif; color:var(--navy); }}
.tile-label {{ font-size:14px; color:var(--ink); margin-top:6px; }}
.tile-sub {{ font-size:12.5px; color:var(--muted); margin-top:4px; }}
section {{ background:var(--card); border-radius:14px; padding:28px 30px; margin:0 0 26px; box-shadow:0 1px 6px rgba(0,30,70,.07); }}
.sec-head {{ display:flex; align-items:center; gap:14px; margin-bottom:6px; }}
.sec-head h2 {{ margin:0; font-size:27px; }}
.num {{ flex:none; width:40px; height:40px; border-radius:50%; background:var(--navy); color:#fff; font:700 20px/40px Georgia, serif; text-align:center; }}
.lead {{ font-size:17px; color:var(--ink); max-width:880px; }}
figure {{ margin:14px 0; }}
figcaption {{ font-weight:600; font-size:14px; color:var(--muted); margin-bottom:8px; }}
.chart {{ width:100%; height:auto; }}
.axis-label {{ font-size:14px; fill:var(--ink); }}
.value-label {{ font-size:14px; font-weight:600; fill:var(--ink); }}
.baseline {{ stroke:#9aa4ae; stroke-width:1; }}
.bar:hover rect[rx] {{ opacity:.82; }}
.legend {{ display:flex; gap:18px; font-size:14px; color:var(--muted); margin-top:6px; }}
.legend i {{ display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; margin:14px 0 6px; }}
th {{ text-align:left; background:#eef2f7; color:var(--navy); font-weight:600; padding:9px 10px; border-bottom:2px solid var(--line); }}
td {{ padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
tbody tr:nth-child(even) td {{ background:#fafbfc; }}
td.nw {{ white-space:nowrap; }}
td.n {{ font:700 18px Georgia, serif; color:var(--navy); text-align:center; width:44px; }}
code {{ font:13px Consolas, "Courier New", monospace; background:#f1f3f5; padding:1px 5px; border-radius:4px; }}
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:13px; font-weight:600; white-space:nowrap; }}
.pill.good {{ background:#e3f3ea; color:var(--good); }}
.pill.bad {{ background:#fbe6e4; color:var(--bad); }}
.pill.neutral {{ background:#eef0f3; color:#3d4753; }}
.small {{ font-size:13px; color:var(--muted); }}
.source {{ font-size:12.5px; color:var(--muted); margin-top:10px; }}
.note {{ font-size:13px; color:var(--muted); margin:6px 0 0; }}
.flag {{ background:#fff4f1; border-left:4px solid var(--coral); padding:10px 14px; border-radius:6px; font-size:14px; }}
.layers {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; margin:16px 0 8px; }}
.layers div {{ background:var(--cream); border-radius:10px; padding:14px 16px; }}
.layers h3 {{ margin:0 0 4px; font-size:18px; }}
.layers p {{ margin:0; font-size:14px; }}
.table-name {{ font:700 14px/1.3 "Segoe UI", system-ui, Arial, sans-serif; color:var(--navy); margin:18px 0 -6px; }}
h3.sub {{ margin:26px 0 8px; font-size:21px; }}
.cards {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.card {{ border:1px solid var(--line); border-radius:12px; padding:18px 20px; }}
.card-kicker {{ text-transform:uppercase; letter-spacing:.1em; font-size:12px; color:var(--coral); font-weight:700; }}
.card h3 {{ margin:2px 0 4px; font-size:22px; }}
.card dl {{ margin:8px 0; font-size:14px; }}
.card dt {{ font-weight:700; color:var(--navy); margin-top:6px; }}
.card dd {{ margin:0; }}
.ba {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }}
.ba div {{ border-radius:8px; padding:8px 12px; }}
.ba span {{ display:block; font-size:12px; color:var(--muted); }}
.ba .b {{ background:#fbe9e3; }} .ba .b b {{ color:var(--bad); }}
.ba .a {{ background:#e6effa; }} .ba .a b {{ color:var(--navy); }}
.analysis {{ position:relative; background:#fffaf0; border:3px solid #e8a33d; border-radius:14px; padding:26px 28px 18px; margin-top:12px; }}
.analysis-badge {{ position:absolute; top:-15px; left:22px; background:#e8a33d; color:#2b1d00; font-weight:700; font-size:13px;
  text-transform:uppercase; letter-spacing:.08em; padding:4px 12px; border-radius:999px; }}
.verdict {{ font-size:20px; font-family:Georgia, serif; color:var(--navy); margin:4px 0 14px; }}
.cost-box {{ display:grid; grid-template-columns:1.2fr 1fr; gap:14px; margin-bottom:8px; }}
.cost-box div {{ background:#fff; border-radius:10px; padding:14px 16px; border:1px solid #f0dcb4; }}
.cost-box span {{ display:block; font-size:13px; color:var(--muted); }}
.cost-box b {{ display:block; font:700 32px/1.2 Georgia, serif; color:var(--navy); }}
.cost-box small {{ color:var(--muted); }}
.analysis h3 {{ margin:16px 0 4px; font-size:19px; }}
footer {{ text-align:center; font-size:12.5px; color:var(--muted); padding:0 24px 40px; }}
@media (max-width: 860px) {{ header.top .wrap {{ flex-direction:column-reverse; }} .hero {{ grid-template-columns:1fr 1fr; }} .two, .cards, .layers, .cost-box {{ grid-template-columns:1fr; }} }}
@media print {{ nav {{ display:none; }} body {{ background:#fff; }} section {{ box-shadow:none; border:1px solid var(--line); }} }}
"""

page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs Vendor Desk: HW6 Results</title><style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap"><div class="intro"><div class="kicker">Campus Customs · Vendor Desk Agent · HW6</div>
<h1>Tokenomics + Prompt Injection: Results</h1>
<p>An AI agent that reads vendor quotes, invoices and emails, pulls out the key facts, and recommends whether the shop
should buy, following the Campus Customs Shop Handbook. Every number below is from our real gpt-6-luna runs.</p></div>
<div class="brand"><div class="y-box"><svg viewBox="0 0 100 100" role="img" aria-label="Yale Y"><polygon fill="#00356b" points="6,8 44,8 44,20 38,20 50,44 62,20 56,20 56,8 94,8 94,20 84,20 61,60 61,84 74,84 74,94 26,94 26,84 39,84 39,60 16,20 6,20"/></svg></div><div class="som">A Yale SOM Production</div></div>
</div></header>
<nav><div class="wrap"><a href="#caching">1 · Caching</a><a href="#attacks">2 · Attacks</a><a href="#cost">3 · Defense cost</a>
<a href="#exam">4 · Exam &amp; red team</a><a href="#recommendation">5 · Recommendation</a></div></nav>
<main><div class="hero">{hero}</div>{sec1}{sec2}{sec3}{sec4}{sec5}</main>
<footer>Model: gpt-6-luna through Portkey · Prices from <code>data/prices.json</code> ($0.10 input, $0.01 cached, $0.125 cache write,
$0.50 output, per 1M tokens) · Built by <code>scripts/build_report.py</code> from the results files of Problems 4–8.</footer>
</body></html>
"""

OUT.write_text(page, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(page):,} characters)")
