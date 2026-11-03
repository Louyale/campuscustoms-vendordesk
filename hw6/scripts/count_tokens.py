"""Count the tokens in the Campus Customs Shop Handbook and price it (Problem 2).

Uses tiktoken's o200k_base encoding, the tokenizer for OpenAI's current model
families. A characters / 4 rule of thumb is printed as a cross-check. Problem 4
compares these numbers with the real usage that gpt-6-luna reports.

Run from HW6/:  .venv/Scripts/python scripts/count_tokens.py
"""

import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent.parent
HANDBOOK = ROOT / "data" / "shop_handbook.md"
PRICES = ROOT / "data" / "prices.json"
MODEL = "gpt-6-luna"


def main() -> None:
    text = HANDBOOK.read_text(encoding="utf-8")
    tokens = len(tiktoken.get_encoding("o200k_base").encode(text))
    rates = json.loads(PRICES.read_text(encoding="utf-8"))[MODEL]

    print(f"File: {HANDBOOK.relative_to(ROOT)}")
    print(f"Characters: {len(text):,}  Words: {len(text.split()):,}  Lines: {text.count(chr(10)):,}")
    print(f"Tokens (o200k_base): {tokens:,}")
    print(f"Rule of thumb (chars / 4): {len(text) / 4:,.0f}")
    print()

    per_m = 1_000_000
    uncached = tokens * rates["input_per_1m"] / per_m
    cached = tokens * rates["cached_input_per_1m"] / per_m
    write = tokens * rates["cache_write_per_1m"] / per_m
    print(f"One call, no cache:       ${uncached:.6f}")
    print(f"One call, cache write:    ${write:.6f}")
    print(f"One call, cache hit:      ${cached:.6f}")
    print(f"1,000 calls, no cache:    ${uncached * 1000:.4f}")
    print(f"1,000 calls, all cached:  ${cached * 1000:.4f}")
    print(f"1,000 calls, 1 write + 999 hits: ${write + cached * 999:.4f}")


if __name__ == "__main__":
    main()
