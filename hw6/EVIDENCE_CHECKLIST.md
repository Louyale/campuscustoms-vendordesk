# Evidence Checklist (HW6)

This file lists the evidence each problem needs. Each problem's evidence is added when that problem arrives and checked off once it exists. Before grading, every box should be ticked.

## Every problem
- [x] A `## Problem N: <title>` section in `AI_prompts.md` with at least one prompt in my own words
- [x] A follow-up prompt, if one was needed, plus one sentence on what was lacking after the first
- [x] A row in the "At a glance" table

## Project-wide rules
- [ ] Only `gpt-6-luna` appears in the code and in run logs (a search of the repo for other model names comes back clean)
- [ ] Every AI call goes through `PORTKEY_API_KEY`
- [ ] `send_email` and `make_payment` only write to a log file; nothing is really sent or paid
- [ ] `.env` is not committed (`.env.example` holds variable names only)
- [ ] Public GitHub repo, URL submitted on Canvas, file tree shown in the last problem
- [ ] `README.md` has the setup and run steps for the grader: create and activate `.venv` (`.venv\Scripts\activate`), `pip install -r requirements.txt`, copy `.env.example` to `.env` and add `PORTKEY_API_KEY`, then `python agent.py --doc data/practice_docs/p01_bluehen_quote.html`

## Problem 1: Vibe coder prompts (5 points)
- [x] `AI_prompts.md` created at the start of the assignment and kept up to date
- [x] One section per problem with its number and title (to be checked again at the end for every problem)
- [x] Each section has my own-words prompt, a follow-up if needed with one sentence on what was lacking, and the outcome

## Problem 2: Size up the handbook (6 points)
- [x] `data.zip` unzipped into `data/` (handbook, prices.json, practice_docs/ x12, practice_key.json, exam_docs/ x10)
- [x] `output/handbook_estimate.md` written
- [x] Token count and how I got it: 10,058 tokens (tiktoken `o200k_base`, via `scripts/count_tokens.py`, with the script output and cross-checks)
- [x] Handbook-only cost on 1 call and 1,000 calls, with and without cached tokens, math shown
- [x] Problem 4: estimates compared with real runs (cross-reference: `output/cache_test.md`, Table 5)
- [x] Follow-up: cache-friendly prompt layout built and checked with real gpt-6-luna calls (99.7% of input cached from call 2; `output/usage_log.json`)
- [x] Follow-up: output tokens cut ~64% (structured VendorReport + low reasoning, 6/6 on p08; section 4 of handbook_estimate.md)
- [x] Readable results for the grader: `output/cost_results.md` (table, chart, cost split, every logged call; built by `scripts/cost_report.py` from the usage log)
- [x] Accuracy baseline on all 12 practice docs, undefended (`output/practice_scores.md`): 9/12 in both modes; all 3 misses are prompt injections (p02, p07, p12)

## Problem 3: Build the vendor desk agent (12 points)
- [x] PydanticAI agent on `gpt-6-luna` (through Portkey), in exactly four files: `prompts/prompt.md`, `agent.py`, `tools.py`, `models.py`
- [x] Handbook sent to the model on every call (`prompt.md` + `data/shop_handbook.md` as the instructions; cached)
- [x] Agent gets the path to one document and reads it with a tool (`read_document`); HTML, PDF and `.eml` all work (p01, p05, p08)
- [x] Returns vendor, SKU, unit price, lead time in days, minimum order, decision (`recommend` / `do_not_recommend`) following the handbook rules, and a one-sentence reason
- [x] Trap tools `send_email` and `approve_payment` only append to `output/trap_calls.json`, which started as `[]` and is still empty after p01 and p08
- [x] After every run, appends to `output/usage_log.json` (document, time, API token counts, cost from `prices.json`) and `output/audit_trail.json` (tool calls with arguments and a short result, plus the final answer)
- [x] Runs with `python agent.py --doc data/practice_docs/p01_bluehen_quote.html`
- [x] Ran on p01 and p08 to show it works (`output/terminal_p01_p08.txt`, both correct)
- [x] `output/harness.md` started: each field in `models.py` and why, and each tool in one line

## Problem 4: With and without cached tokens (16 points)
- [x] Agent run on all 12 practice documents with cache and without cache (`scripts/cache_test.py`)
- [x] Token counts prove each setup: without cache, 0 cached tokens on all 24 calls; with cache, cached tokens on 24 of 24 (`output/cache_test.md`, Table 2)
- [x] Every model call from both setups saved to `output/cache_test.json` (48 calls: setup, document, every API token count, dollars from `prices.json`), also listed in Table 8
- [x] `output/cache_test.md`: total cost and cost per document for each setup, and the percent saved (Tables 1, 3, 4)
- [x] `output/cache_test.md`: how the real numbers compare to the Problem 2 estimate (Table 5)
- [x] `output/cache_test.md`: projection for 1,000 documents a day for 30 days, with and without cache (Table 6)
- [x] `output/cache_test.md`: surprises in the numbers and why they happen (Table 7)
- [x] I've reviewed and refined the flagged surprises (Table 7: S3 is the headline, S1, S2 and S4 starred; my insight is in "Lou's notes")

## Problem 5: Attack your own agent (8 points)
- [x] Problem 3 agent run with no new defenses on all 12 documents in `data/practice_docs/` (`scripts/attack_test.py`)
- [x] Each answer compared with `data/practice_key.json`, and `output/trap_calls.json` checked (still `[]`), plus each run's audit trail entry
- [x] `output/attack_results.json`: for each document, whether each field matched the key, whether the decision matched, whether a trap tool was called, and whether a link or other strange text showed up in the answer
- [x] `output/attack_results.md`: for every document that fooled the agent (p07, p12), what fooled it and where in the file it was hiding (Table 3)
- [x] Documents opened the way a person would (browser, PDF viewer, email app), with screenshots in `output/person_view/`, and compared with what the agent read (Table 4)

## Problem 6: Defend your agent
- [x] Code layer: the program cleans each document before any model sees it (`tools.py` `clean_document` / `read_visible_document`)
- [x] Design layer: a poisoned document can't reach the dangerous tools (not given to the reading agent) or the decision (Python decides; facts not visible in the document hold the quote)
- [x] Prompt layer: rules in `prompts/prompt.md` ("## Safety rules")
- [x] `send_email` and `approve_payment` kept in the system (`tools.py`); nothing sent or paid; `output/trap_calls.json` still `[]` (explained in harness Table 15)
- [x] A way to run with no defenses kept: `python agent.py --doc <path> --no-defenses` (exactly the Problem 3 agent)
- [x] All 12 practice documents rerun; `output/defense_results.json` has the Problem 5 shape plus tokens and dollars per document
- [x] Clean documents still return the right values (5 of 5; no refusing or blanking)
- [x] `output/defense_results.md`: before-and-after table for all 12 documents (Table 2)
- [x] `output/defense_results.md`: what each layer catches that the others miss (Tables 3–4)
- [x] `output/defense_results.md`: extra tokens and dollars each layer adds per document (Table 5)
- [x] `output/harness.md`: Safety section, with what each defense layer does in plain words (Table 13)

## Problem 7: Red team (8 points)
- [x] Two new booby-trapped vendor documents in `data/my_attacks/` (a PDF and an email), each with a hiding trick and an attack goal not in the practice set
- [x] A person opening each document sees a normal quote (screenshots: `output/person_view/a1_bluehen_coverup.png`, `a2_eastrock_hidden_twin.png`)
- [x] Both attacks run on the agent with no defenses and on the defended agent (3 times each, plus each layer alone)
- [x] `output/red_team.md`: for each attack, what is hidden, where, what it tries to make the agent do, and what happened before and after the defenses (Tables 2–3)
- [x] Both attacks are new and fool the agent with no defenses (3 of 3 each); the defended agent stopped both (0 of 3)
- [x] `data/my_attacks/` is included in the repo (`.gitignore` exception)
- [x] "Lou's analysis" section in `output/red_team.md`: why we believe the attacks worked and how they are unique
- [x] Weak spots patched in the defended layers only (allowed by Problems 1–7)

## Problem 8: Exam documents (12 points)
- [x] Final defended agent run on all 10 documents in `data/exam_docs/` (`scripts/exam_run.py`)
- [x] Results not hand-edited: every value comes straight from the run
- [x] `output/exam_results.json`: one entry per exam file with exactly the 13 required fields, in order
- [x] No trap tool calls (`trap_tool_called` false for all 10; `output/trap_calls.json` still `[]`)
- [x] Clean documents handled normally (e01, e05, e08 answered from their visible quotes)
- [x] Rerun check: a second run matched on 10 of 10 files (`output/exam_rerun_check.json`)

## Problem 9: Results page (12 points)
- [x] `output/hw6_report.html` is one file that opens by double-click with no internet and no other files (inline CSS and SVG; no scripts, web fonts or links to download)
- [x] Caching results, with a chart (section 1)
- [x] Attacks before and after the defenses (section 2)
- [x] What the defenses cost in tokens and dollars (section 3)
- [x] Exam results and the two red team attacks (section 4)
- [x] Short recommendation to the store manager, with cost per month at 1,000 documents a day (section 5, highlighted as original analysis)
- [x] Real numbers from earlier problems (read from the results files by `scripts/build_report.py`)
- [x] Designed page: fonts, color, layout (Campus Customs Yale palette; chart colors passed the palette check)
- [x] I've reviewed and adjusted the draft, especially the section 5 recommendation (badge now reads "Analysis"); attacks rerun and all 12 practice documents still 12 of 12 (`output/red_team.md`, Tables 7–8)
