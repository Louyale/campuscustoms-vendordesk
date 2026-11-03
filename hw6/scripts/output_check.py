"""Groundwork experiment (Problem 2 follow-up). Results are recorded in
output/handbook_estimate.md; the prompt has changed since, so a rerun will differ a little.

Compare output styles on one real practice document (Problem 2 follow-up).

Runs p08 (a plain-text email, no hidden text) through the cached prompt layout
in four ways and scores each answer against data/practice_key.json:

  A  free-text reply, default reasoning      (the layout before this change)
  B  VendorReport structured output, default reasoning
  C  VendorReport, reasoning effort "low"
  D  VendorReport, reasoning effort "minimal"

Each variant runs twice. Every call is logged to output/usage_log.json.

Run from HW6/:  .venv/Scripts/python scripts/output_check.py
"""

import email
import json
import os
import sys
from email import policy
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent, NativeOutput  # noqa: E402

from models import VendorReport  # noqa: E402
from agent import ROOT, SETTINGS, build_model, record  # noqa: E402
from agent import instructions_for, NO_DEFENSES  # noqa: E402

STATIC_INSTRUCTIONS = instructions_for(NO_DEFENSES)  # the prompt as it was for this groundwork experiment

# The cache settings without the reasoning effort, as they were for this experiment.
CACHE_SETTINGS = {k: v for k, v in SETTINGS.items() if k != "openai_reasoning_effort"}


def user_message(document_text: str) -> str:
    return f"<vendor_document>
{document_text}
</vendor_document>"

DOC = "p08_chapelst_email.eml"
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]

msg = email.message_from_bytes((ROOT / "data" / "practice_docs" / DOC).read_bytes(), policy=policy.default)
text = f"Subject: {msg['subject']}\nFrom: {msg['from']}\n\n{msg.get_body(('plain',)).get_content()}"
key = next(k for k in json.loads((ROOT / "data" / "practice_key.json").read_text()) if k["file"] == DOC)

model = build_model()
variants = {
    "A_free_text": (str, {}),
    "B_structured": (NativeOutput(VendorReport), {}),
    "C_structured_low": (NativeOutput(VendorReport), {"openai_reasoning_effort": "low"}),
    "D_structured_minimal": (NativeOutput(VendorReport), {"openai_reasoning_effort": "minimal"}),
}

for name, (output_type, extra) in variants.items():
    agent = Agent(model, instructions=STATIC_INSTRUCTIONS, output_type=output_type,
                  model_settings={**CACHE_SETTINGS, **extra})
    for run in (1, 2):
        try:
            result = agent.run_sync(user_message(text))
        except Exception as exc:  # e.g. a reasoning effort the model does not accept
            print(f"{name} run {run}: ERROR {type(exc).__name__}: {str(exc)[:160]}")
            break
        out = result.output
        if isinstance(out, VendorReport):
            got = out.model_dump()
            correct = sum(got[f] == key[f] for f in FIELDS)
            score = f"{correct}/{len(FIELDS)}"
        else:
            score = "n/a (free text)"
        e = record(f"output_check_{name}", result.usage, document=DOC, score=score)
        print(f"{name} run {run}: cached={e['cached_tokens']:,}/{e['input_tokens']:,} "
              f"output={e['output_tokens']} (reasoning {e['reasoning_tokens']}) "
              f"cost=${e['cost_usd']['total']:.6f} score={score}")
        print("   ", out if isinstance(out, str) else out.model_dump_json())
