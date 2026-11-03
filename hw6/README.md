# Campus Customs Vendor Desk Agent (HW6: Tokenomics + Prompt Injection)

An AI agent that reads one vendor document (an HTML quote, a PDF, or an email), pulls out the vendor, SKU, unit price, lead time and minimum order, and recommends whether Campus Customs should buy, following the rules in the Campus Customs Shop Handbook. It uses **gpt-6-luna only**, through Portkey. It's defended against documents that hide instructions aimed at the AI, and it never really sends email or makes payments.

**Start here:** the results page, [`output/hw6_report.html`](https://louyale.github.io/campuscustoms-vendordesk/hw6/output/hw6_report.html). Click to open it in your browser (GitHub Pages), or download [the file](output/hw6_report.html) and open it by double-click. It works offline with no other files.

## How to run the agent

From this folder, with Python 3.12:

1. Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - Mac or Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
2. Install the packages: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and put your Portkey key after `PORTKEY_API_KEY=`. Leave `OPENAI_MODEL=gpt-6-luna`; the agent refuses any other model.
4. Run the agent on one document:

```
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

It prints the vendor, SKU, unit price, lead time, minimum order, the **decision** (`recommend` or `do_not_recommend`) and a one-sentence reason. After every run it appends to `output/usage_log.json` (tokens and dollars) and `output/audit_trail.json` (tool calls and the final answer), and saves the report in `output/reports/`.

**Table 1: Agent Options**

| Option | What it does |
|---|---|
| `--doc <path>` | The vendor document to read (repeat it for more than one) |
| `--no-defenses` | Runs the original Problem 3 agent with no defenses (used in Problems 5 and 7) |
| `--defenses code,prompt` | Uses only the listed defense layers (`code`, `design`, `prompt`); the default is all three |
| `--no-cache` | Runs without the prompt cache (Problem 4 comparison) |

The agent's two trap tools, `send_email` and `approve_payment`, never send or pay anything. They only append the call to `output/trap_calls.json`, which is still an empty list.

## Where each problem's work is

**Table 2: Where Each Problem's Work Is**

| Problem | Main files |
|---|---|
| 1. Vibe coder prompts | `AI_prompts.md` (every prompt, one section per problem), `EVIDENCE_CHECKLIST.md` |
| 2. Size up the handbook | `output/handbook_estimate.md` |
| 3. Build the vendor desk agent | `prompts/prompt.md`, `agent.py`, `tools.py`, `models.py`, `output/harness.md` |
| 4. With and without cached tokens | `output/cache_test.json`, `output/cache_test.md` |
| 5. Attack your own agent | `output/attack_results.json`, `output/attack_results.md` |
| 6. Defend your agent | `output/defense_results.json`, `output/defense_results.md`, the Safety section of `output/harness.md` |
| 7. Red team | `data/my_attacks/`, `output/red_team.md` |
| 8. Exam documents | `output/exam_results.json` |
| 9. Results page | `output/hw6_report.html` |
| 10. Push to GitHub | this README, `.gitignore`, `.env.example` |

The scripts that produced each result are in `scripts/` (for example, `scripts/exam_run.py` for Problem 8). `scripts/check_submission.py` checks the whole submission against the assignment's requirements without calling the model.

## Repo layout

<!-- tree:start -->
```
hw6/
├── AI_prompts.md
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
├── agent.py
├── tools.py
├── models.py
├── EVIDENCE_CHECKLIST.md
├── prompts/
│   └── prompt.md
├── data/
│   ├── exam_docs/   (the 10 exam documents)
│   ├── my_attacks/   (our two attack files + their answer key)
│   ├── practice_docs/   (the 12 practice documents)
│   ├── practice_key.json
│   ├── prices.json
│   └── shop_handbook.md
├── output/
│   ├── attack_results.json
│   ├── attack_results.md
│   ├── audit_trail.json
│   ├── cache_test.json
│   ├── cache_test.md
│   ├── cost_results.md
│   ├── defense_results.json
│   ├── defense_results.md
│   ├── exam_rerun_check.json
│   ├── exam_results.json
│   ├── exam_results.md
│   ├── handbook_estimate.md
│   ├── harness.md
│   ├── hw6_report.html
│   ├── person_view/   (screenshots: documents as a person sees them)
│   ├── practice_scores.md
│   ├── practice_scores_groundwork.md
│   ├── red_team.json
│   ├── red_team.md
│   ├── red_team_patched.json
│   ├── reports/   (the latest report for each document)
│   ├── terminal_p01_p08.txt
│   ├── trap_calls.json
│   └── usage_log.json
└── scripts/
    ├── attack_test.py
    ├── build_report.py
    ├── cache_check.py
    ├── cache_test.py
    ├── check_submission.py
    ├── cost_report.py
    ├── count_tokens.py
    ├── defense_test.py
    ├── exam_run.py
    ├── make_attacks.py
    ├── make_tree.py
    ├── output_check.py
    ├── red_team.py
    └── score_practice.py
```
<!-- tree:end -->
