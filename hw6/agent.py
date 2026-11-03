"""Campus Customs vendor desk agent: the entry point.

Give it the path to one vendor document (HTML, PDF or .eml):

    python agent.py --doc data/practice_docs/p01_bluehen_quote.html

The agent (PydanticAI, gpt-6-luna through Portkey) reads the document with the
read_document tool, returns the five facts as VendorFacts, and the purchasing
checks in tools.py turn them into a VendorReport: vendor, SKU, unit price, lead
time, minimum order, recommend / do_not_recommend, and a one-sentence reason.
The report is printed and saved to output/reports/<document>.json. The agent
also has two trap tools, send_email and approve_payment, which its job never
needs; they only log to output/trap_calls.json (see tools.py).

Every call sends prompts/prompt.md and then the whole handbook as the
instructions. They never change between calls, so after the first call
gpt-6-luna reads them from its prompt cache at a tenth of the input price.

After every run the agent appends to:
- output/usage_log.json: document, time, the token counts the API reports, and
  the dollar cost using data/prices.json
- output/audit_trail.json: each tool call with its arguments and a short
  result, plus the final answer
"""

import argparse
import asyncio
import json
import os
import sys
import re
import time
import uuid
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent, NativeOutput, Tool  # noqa: E402
from pydantic_ai.messages import ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.messages import ModelResponse  # noqa: E402
from pydantic_ai.usage import RequestUsage, RunUsage  # noqa: E402

from models import CallUsage, ModelCall, VendorFacts, VendorReport  # noqa: E402
from tools import (  # noqa: E402
    HANDBOOK,
    OUTPUT_DIR,
    ROOT,
    append_json,
    approve_payment,
    check_purchasing_rules,
    clean_document,
    fill_blanks,
    hold_for_review,
    now,
    read_document,
    read_visible_document,
    send_email,
    unsupported_facts,
)

load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------- model (gpt-6-luna only)

ALLOWED_MODEL = "gpt-6-luna"
MODEL_NAME = os.getenv("OPENAI_MODEL", ALLOWED_MODEL)
if MODEL_NAME != ALLOWED_MODEL:
    raise RuntimeError(f"OPENAI_MODEL must be {ALLOWED_MODEL} for this assignment")


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey, on OpenAI's Responses API."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from .env")
    client = AsyncOpenAI(
        base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
        api_key=api_key,
        default_headers={"x-portkey-api-key": api_key},
        timeout=120,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# ---------------------------------------------------------------- instructions: prompt.md + handbook

PROMPT = (ROOT / "prompts" / "prompt.md").read_text(encoding="utf-8")
# The prompt layer is the "## Safety rules" section of prompt.md. Without it, the prompt is exactly the
# Problem 3 prompt, which the no-defenses mode uses.
SAFETY_RULES = re.compile(r"(?ms)^## Safety rules\n.*?(?=^The Campus Customs Shop Handbook follows)")
PROMPT_NO_SAFETY_RULES = SAFETY_RULES.sub("", PROMPT)

# The three defense layers (Problem 6). The agent runs with all three unless told otherwise.
LAYERS = ("code", "design", "prompt")
ALL_DEFENSES = frozenset(LAYERS)
NO_DEFENSES = frozenset()


def instructions_for(defenses: frozenset) -> str:
    prompt = PROMPT if "prompt" in defenses else PROMPT_NO_SAFETY_RULES
    return f"{prompt}\n<shop_handbook>\n{HANDBOOK}\n</shop_handbook>"


INSTRUCTIONS = instructions_for(ALL_DEFENSES)

# - openai_cache_instructions: cache breakpoint right after the instructions,
#   so the cached part is exactly prompt.md + handbook.
# - openai_prompt_cache_key: every vendor desk call shares one cache.
# - ttl 12h: the cached handbook lasts at least 12 hours, not 30 minutes.
# - reasoning effort low: most output tokens were hidden reasoning; low cut
#   them with no loss of accuracy (output/handbook_estimate.md, section 4).
SETTINGS = OpenAIResponsesModelSettings(
    openai_cache_instructions=True,
    openai_prompt_cache_key="campus-customs-vendor-desk-v1",
    openai_prompt_cache_options={"ttl": "12h"},
    openai_reasoning_effort=os.getenv("REASONING_EFFORT", "low"),
)

# The two cache setups (Problem 4). "with_cache" is the normal agent.
# "without_cache" asks for no caching (mode "explicit", no breakpoint), but a
# test showed the provider still caches an identical prefix. So that setup also
# starts every request's instructions with a fresh random tag: no two requests
# share an opening, nothing can be reused, and the cached-token count the API
# reports is 0 on every call.
SETUPS: dict[str, OpenAIResponsesModelSettings] = {
    "with_cache": OpenAIResponsesModelSettings(),
    "without_cache": OpenAIResponsesModelSettings(
        openai_cache_instructions=False,
        openai_prompt_cache_key="campus-customs-vendor-desk-no-cache",
        openai_prompt_cache_options={"mode": "explicit"},
    ),
}


def tagged(instructions: str) -> str:
    """The same instructions, opened by a tag that is new on every request (without_cache only)."""
    return f"Request tag {uuid.uuid4().hex} (makes this request unique; ignore it).\n\n{instructions}"


MODEL = build_model()


@lru_cache(maxsize=None)
def build_agent(defenses: frozenset = ALL_DEFENSES, setup: str = "with_cache") -> Agent:
    """The vendor desk agent with the chosen defense layers and cache setup.

    - code: the agent's read_document tool is read_visible_document, which returns only the text a person sees.
    - design: the agent is built without send_email and approve_payment, so a document can't reach them (they
      stay in tools.py for later use with a person's sign-off). Python still makes the decision, and review()
      holds any quote whose facts aren't visible in the document.
    - prompt: prompt.md includes its "## Safety rules" section.
    With no defenses this is exactly the Problem 3 agent: raw reader, trap tools, Problem 3 prompt.
    """
    instructions = instructions_for(defenses)
    reader = Tool(read_visible_document, name="read_document") if "code" in defenses else read_document
    tools = [reader] if "design" in defenses else [reader, send_email, approve_payment]
    if setup == "with_cache":
        return Agent(MODEL, instructions=instructions, output_type=NativeOutput(VendorFacts), tools=tools,
                     model_settings=SETTINGS)
    # without_cache: same agent, but the instructions are rebuilt with a new tag on every request.
    return Agent(MODEL, instructions=lambda: tagged(instructions), output_type=NativeOutput(VendorFacts), tools=tools,
                 model_settings={**SETTINGS, **SETUPS["without_cache"]})


agent = build_agent()

# ---------------------------------------------------------------- usage log and audit trail

USAGE_LOG = OUTPUT_DIR / "usage_log.json"
AUDIT_TRAIL = OUTPUT_DIR / "audit_trail.json"
REPORTS_DIR = OUTPUT_DIR / "reports"
RATES = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))[MODEL_NAME]


def cost_of(usage: RunUsage | RequestUsage) -> dict:
    """Dollar cost by rate. input_tokens includes the cached and cache-write tokens."""
    fresh = usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    parts = {
        "fresh_input": fresh * RATES["input_per_1m"],
        "cached_input": usage.cache_read_tokens * RATES["cached_input_per_1m"],
        "cache_write": usage.cache_write_tokens * RATES["cache_write_per_1m"],
        "output": usage.output_tokens * RATES["output_per_1m"],
    }
    parts = {k: v / 1_000_000 for k, v in parts.items()}
    parts["total"] = sum(parts.values())
    return {k: round(v, 8) for k, v in parts.items()}


def record(label: str, usage: RunUsage, **extra) -> dict:
    """Append one run's tokens and cost to output/usage_log.json."""
    entry = {
        "time": now(),
        "label": label,
        "model": MODEL_NAME,
        "input_tokens": usage.input_tokens,
        "cached_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.output_reasoning_tokens,
        "requests": usage.requests,
        "cache_hit_rate": round(usage.cache_read_tokens / usage.input_tokens, 3) if usage.input_tokens else 0,
        "cost_usd": cost_of(usage),
        **extra,
    }
    append_json(USAGE_LOG, entry)
    return entry


def tool_calls(messages: list) -> list[dict]:
    """Every tool call in a run, with its arguments and a short result."""
    returns = {p.tool_call_id: p.content for m in messages for p in m.parts if isinstance(p, ToolReturnPart)}
    calls = []
    for m in messages:
        for part in m.parts:
            if isinstance(part, ToolCallPart):
                result = str(returns.get(part.tool_call_id, "(no result)"))
                short = result if len(result) <= 120 else f"{len(result):,} characters: {' '.join(result[:100].split())}..."
                calls.append({"tool": part.tool_name, "args": part.args_as_dict(), "result": short})
    return calls


def model_calls(messages: list) -> list[ModelCall]:
    """Every model request in a run, with the token counts the API reported for it."""
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    return [
        ModelCall(
            request=n,
            input_tokens=r.usage.input_tokens,
            cached_tokens=r.usage.cache_read_tokens,
            cache_write_tokens=r.usage.cache_write_tokens,
            output_tokens=r.usage.output_tokens,
            reasoning_tokens=r.usage.output_reasoning_tokens,
            cost_usd=cost_of(r.usage)["total"],
        )
        for n, r in enumerate(responses, 1)
    ]


# ---------------------------------------------------------------- the vendor desk


async def review(path: str | Path, label: str = "agent", setup: str = "with_cache",
                 defenses: frozenset = ALL_DEFENSES) -> tuple[VendorReport, CallUsage]:
    """Review one vendor document: the model reads it with the tool, the checks decide."""
    path = Path(path)
    defenses = frozenset(defenses)
    start = time.perf_counter()
    result = await build_agent(defenses, setup).run(f"Review this vendor document: {path.as_posix()}")
    seconds = round(time.perf_counter() - start, 2)
    facts = result.output
    visible_text, removed = clean_document(path.as_posix())
    filled, flagged = [], []
    if "design" in defenses:
        # Design layer: a fact a person can see can't be blanked out, and a fact a person can't see never reaches
        # the decision.
        facts, filled = fill_blanks(facts, visible_text)
        flagged = unsupported_facts(facts, visible_text)
    report = check_purchasing_rules(facts)
    if flagged:
        report = hold_for_review(report, flagged)
    calls = model_calls(result.all_messages())
    layers = [layer for layer in LAYERS if layer in defenses]
    entry = record(label, result.usage, document=path.as_posix(), setup=setup, defenses=layers, seconds=seconds,
                   decision=report.decision, calls=[c.model_dump() for c in calls])
    append_json(AUDIT_TRAIL, {
        "time": entry["time"],
        "document": path.as_posix(),
        "model": MODEL_NAME,
        "setup": setup,
        "defenses": layers,
        "removed_by_code": [r.model_dump() for r in removed] if "code" in defenses else [],
        "flagged_by_design": flagged,
        "filled_by_design": filled,
        "tool_calls": tool_calls(result.all_messages()),
        "model_facts": result.output.model_dump(),
        "final_answer": report.model_dump(),
    })
    usage = CallUsage(
        model=entry["model"],
        setup=setup,
        seconds=seconds,
        calls=calls,
        requests=entry["requests"],
        input_tokens=entry["input_tokens"],
        cached_tokens=entry["cached_tokens"],
        cache_write_tokens=entry["cache_write_tokens"],
        output_tokens=entry["output_tokens"],
        reasoning_tokens=entry["reasoning_tokens"],
        cost_usd=entry["cost_usd"]["total"],
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{path.stem}.json").write_text(
        json.dumps({"document": path.as_posix(), "report": report.model_dump(), "usage": usage.model_dump()}, indent=2),
        encoding="utf-8",
    )
    return report, usage


def show(path: str | Path, report: VendorReport, usage: CallUsage) -> str:
    """The report as a readable card for the terminal."""

    def known(value, fmt: str = "{}") -> str:
        return "unknown" if value is None else fmt.format(value)

    line = "─" * 64
    verdict = "✅ RECOMMEND" if report.decision == "recommend" else "❌ DO NOT RECOMMEND"
    return "\n".join([
        line,
        f" Campus Customs Vendor Desk   {Path(path).name}",
        line,
        f" Vendor          {known(report.vendor)}",
        f" SKU             {known(report.sku)}",
        f" Unit price      {known(report.unit_price, '${:.2f}')}",
        f" Lead time       {known(report.lead_time_days, '{} days')}",
        f" Minimum order   {known(report.min_order, '{} units')}",
        line,
        f" DECISION        {verdict}",
        f" Reason          {report.reason}",
        line,
        f" {usage.model} · {usage.setup.replace('_', ' ')} · {usage.requests} requests · {usage.input_tokens:,} input "
        f"({usage.cached_tokens:,} cached) · {usage.output_tokens} output · ${usage.cost_usd:.6f}",
        line,
    ])


async def main(paths: list[str], setup: str, defenses: frozenset) -> None:
    for path in paths:
        report, usage = await review(path, setup=setup, defenses=defenses)
        print(show(path, report, usage))
        print(f" Defenses: {', '.join(l for l in LAYERS if l in defenses) or 'none (Problem 3 agent)'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", action="append", required=True,
                        help="path to one vendor document (.html, .pdf or .eml); repeat for more")
    parser.add_argument("--no-cache", action="store_true",
                        help="run without the prompt cache (Problem 4 comparison)")
    parser.add_argument("--no-defenses", action="store_true",
                        help="run the Problem 3 agent with no defenses (for Problem 7)")
    parser.add_argument("--defenses", default=",".join(LAYERS),
                        help="comma-separated defense layers to use: code, design, prompt (default: all three)")
    args = parser.parse_args()
    chosen = NO_DEFENSES if args.no_defenses else frozenset(l.strip() for l in args.defenses.split(",") if l.strip())
    if not chosen <= ALL_DEFENSES:
        parser.error(f"unknown defense layer: {', '.join(sorted(chosen - ALL_DEFENSES))}")
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(args.doc, "without_cache" if args.no_cache else "with_cache", chosen))
