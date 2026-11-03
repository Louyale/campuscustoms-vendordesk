"""Groundwork experiment (Problem 2 follow-up). Results are recorded in
output/handbook_estimate.md; the prompt has changed since, so a rerun will differ a little.

Prove the handbook prefix is cached (Problem 2 follow-up).

Sends three tiny requests through the real prompt layout, back to back. Call 1
should write the cache; calls 2 and 3 should read about 10,000 cached tokens.
Each call is logged to output/usage_log.json.

Run from HW6/:  .venv/Scripts/python scripts/cache_check.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent  # noqa: E402

from agent import ROOT, SETTINGS, build_model, record  # noqa: E402
from agent import instructions_for, NO_DEFENSES  # noqa: E402

STATIC_INSTRUCTIONS = instructions_for(NO_DEFENSES)  # the prompt as it was for this groundwork experiment

# The cache settings without the reasoning effort, as they were for this experiment.
CACHE_SETTINGS = {k: v for k, v in SETTINGS.items() if k != "openai_reasoning_effort"}


def user_message(document_text: str) -> str:
    return f"<vendor_document>
{document_text}
</vendor_document>"

agent = Agent(build_model(), instructions=STATIC_INSTRUCTIONS, model_settings=CACHE_SETTINGS)

for i in range(1, 4):
    result = agent.run_sync(user_message(f"Cache check {i}. No vendor document today. Reply with the single word OK."))
    diag = (result.response.provider_details or {}).get("prompt_cache_diagnostics")
    e = record(f"cache_check_{i}", result.usage, diagnostics=diag)
    print(
        f"call {i}: input={e['input_tokens']:,} cached={e['cached_tokens']:,} "
        f"write={e['cache_write_tokens']:,} output={e['output_tokens']} "
        f"cost=${e['cost_usd']['total']:.6f} reply={result.output!r} diag={diag}"
    )
