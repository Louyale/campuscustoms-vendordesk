# Handbook Estimate (Problem 2: Size up the handbook)

The vendor desk agent sends the whole Campus Customs Shop Handbook (`data/shop_handbook.md`) to `gpt-6-luna` on every call. This file records how many tokens the handbook is and what it costs on its own: on one call and on 1,000 calls, with and without cached tokens. Problem 4 checks these estimates against real runs.

## Summary

**Table 1: Handbook Token Count and Cost Summary**

| Item | Value |
|---|---|
| Handbook token count | **10,058 tokens** |
| One call, without cache | **$0.0010058** (about 1/10 of a cent) |
| One call, with cache (cache hit) | **$0.00010058** (about 1/100 of a cent) |
| 1,000 calls, without cache | **$1.0058** |
| 1,000 calls, with cache (all 1,000 are hits) | **$0.10058** |
| 1,000 calls, with cache (1 cache write + 999 hits) | **$0.10174** |
| Saving from caching over 1,000 calls | about **$0.90, or 90%** |

## 1. The token count and how I got it

**Count: 10,058 tokens.**

**Method:**

1. The data was already unzipped: `data.zip` (downloaded as `data (2).zip`) was extracted into `HW6/data/`, which holds `shop_handbook.md`, `prices.json`, `practice_docs/` (12 documents), `practice_key.json` and `exam_docs/` (10 documents).
2. I wrote [`scripts/count_tokens.py`](../scripts/count_tokens.py). It reads the handbook as UTF-8 and encodes it with **tiktoken**, OpenAI's open-source tokenizer library, using the **`o200k_base`** encoding. That's the tokenizer for OpenAI's current model families, and it's the closest local match to what `gpt-6-luna` will count.
3. I ran it from `HW6/` with `.venv/Scripts/python scripts/count_tokens.py`.

**Script output:**

```
File: data\shop_handbook.md
Characters: 28,903  Words: 6,127  Lines: 338
Tokens (o200k_base): 10,058
Rule of thumb (chars / 4): 7,226
```

**Cross-checks:**

**Table 2: Token Count Cross-Checks**

| Method | Tokens | Notes |
|---|---|---|
| tiktoken `o200k_base` (used) | 10,058 | Current OpenAI tokenizer |
| tiktoken `cl100k_base` (the older OpenAI tokenizer) | 10,184 | Within about 1% of the count we used |
| Characters ÷ 4 rule of thumb | 7,226 | Undercounts by about 28% |
| Assignment's figure | "about 10,000" | Matches the tiktoken count |

The rule of thumb undercounts because the handbook is not plain prose. It's full of tables, pipes, SKU codes (`CC-HD-006`), prices and email addresses, and those break into many short tokens, so the real ratio is about 2.9 characters per token. My earlier "about 7,000" figure in the setup notes came from that rule of thumb. The tiktoken count of **10,058** replaces it.

**Caveat for Problem 4:** gpt-6-luna's tokenizer isn't published, so 10,058 is a close estimate, not the bill. A real call will also report a few more input tokens, because the request adds message formatting and our own instructions around the handbook. Problem 4 compares this estimate with the `input_tokens` and `cached_tokens` that the real runs report.

## 2. What the handbook alone costs

**Prices** (`data/prices.json`, gpt-6-luna, per 1 million tokens):

**Table 3: gpt-6-luna Prices**

| Rate | $ per 1M tokens | $ per token |
|---|---|---|
| Input (not cached) | $0.10 | $0.0000001 |
| Cached input (cache hit) | $0.01 | $0.00000001 |
| Cache write (first time the handbook is stored) | $0.125 | $0.000000125 |
| Output | $0.50 | (not used here: the handbook is input only) |

**Formula:** cost = tokens × rate ÷ 1,000,000

### One call

**Table 4: Handbook Cost on One Call**

| Case | Math | Cost |
|---|---|---|
| Without cache | 10,058 × $0.10 ÷ 1,000,000 | **$0.0010058** |
| With cache (cache hit) | 10,058 × $0.01 ÷ 1,000,000 | **$0.00010058** |
| First cached call (cache write) | 10,058 × $0.125 ÷ 1,000,000 | $0.00125725 |

### 1,000 calls

**Table 5: Handbook Cost on 1,000 Calls**

| Case | Math | Cost |
|---|---|---|
| Without cache | 1,000 × $0.0010058 | **$1.0058** |
| With cache, all hits | 1,000 × $0.00010058 | **$0.10058** |
| With cache, realistic (the first call writes the cache, the next 999 hit it) | $0.00125725 + (999 × $0.00010058) = $0.00125725 + $0.10047942 | **$0.10174** |

**Saving from caching on 1,000 calls:** $1.0058 − $0.10174 = **$0.90406**, about **90% cheaper**. The one cache write costs a little more than a normal call ($0.00126 vs $0.00101), but it pays for itself on the second call.

### Notes for cross-referencing

- These numbers are for the **handbook only**. Each real call also pays for the vendor document, our instructions, and the output tokens at $0.50 per 1M. Problem 4 measures the full bill.
- Caching only works if the handbook is the **same, unchanged text at the start of every request**. If we put the vendor document or anything that changes before it, every call is a cache miss and costs the uncached rate.
- A cache doesn't last forever. If calls are spread out, the cache may expire and need another write. The "1 write + 999 hits" line assumes the 1,000 calls run close together.

## 3. Follow-up: making the cache work for real

The estimate above assumes every call after the first gets a cache hit, but nothing yet proved our setup would. So the agent's prompt is now laid out to be cached, and I checked it with real `gpt-6-luna` calls.

**Layout** (`agent.py`):

1. **Static prefix first:** a short role statement, then the handbook exactly as it is on disk, read once and never changed in code.
2. **Vendor document last,** as the user message. It's the only part that changes per call. No dates, file names or per-call text go in the prefix.

**Improvements beyond "handbook first":**

**Table 6: Caching Improvements**

| Improvement | What it does |
|---|---|
| Explicit cache breakpoint after the instructions (`openai_cache_instructions`) | Tells OpenAI exactly where the reusable part ends, instead of leaving it to guess |
| One cache key for every vendor desk call (`openai_prompt_cache_key`) | Sends all our calls to the same cache, so more of them hit it |
| 12-hour cache lifetime (`ttl: 12h`) | The cached handbook lasts at least 12 hours instead of the default 30 minutes, so a day of documents pays for one cache write |
| Usage log on every call (`agent.py` → `output/usage_log.json`) | Records model, input, cached, cache-write and output tokens, cache hit rate, and cost by rate from `prices.json`, for Problems 4 and 5 |
| Model lock (`agent.py`) | `OPENAI_MODEL` must be `gpt-6-luna`, or the program stops before any call |

**Real check** (`scripts/cache_check.py`: three tiny requests back to back, 2026-11-03):

**Table 7: Cache Check: Three Real Calls**

| Call | Input tokens | Cached | Cache write | Output | Cost |
|---|---|---|---|---|---|
| 1 | 10,147 | 0 | 10,144 | 202 | $0.001369 |
| 2 | 10,147 | **10,115** | 29 | 258 | $0.000234 |
| 3 | 10,147 | **10,115** | 29 | 198 | $0.000204 |

- **The cache works.** From call 2 on, 10,115 of 10,147 input tokens (99.7%) came from the cache. The input part of the bill fell from $0.001268 to $0.000105, which matches the ~90% saving estimated above.
- **The estimate held up.** The real input was 10,147 tokens, 89 more than the 10,058 tiktoken count. The extra tokens are the role statement, the `<shop_handbook>` tags and the tiny user message. Problem 4 will do the full comparison.
- **Output is now the bigger cost.** On a cached call, about 200 output tokens at $0.50/1M ($0.0001) cost as much as the whole cached handbook. Keeping replies short is the next lever.

## 4. Follow-up: cutting the output tokens

Section 3 showed that on a cached call, output (at $0.50/1M, 5× the input rate) cost about as much as the whole cached handbook. The usage log also showed where those output tokens went: **most of them were hidden reasoning tokens** (130–202 of about 200), not the reply itself.

**Two changes:**

1. **A structured reply** (`models.py`, `VendorReport`): exactly the seven §13 fields (vendor, SKU, unit price, lead time in days, minimum order, decision, one-sentence reason) as JSON, with no extra wording. The field names match `practice_key.json`, so the answers can be scored automatically.
2. **Low reasoning effort** (`agent.py`, `SETTINGS`, set by `REASONING_EFFORT` in `.env`). gpt-6-luna rejects `minimal` (HTTP 400), so `low` is the lowest setting it accepts.

**Real check** (`scripts/output_check.py`, practice doc `p08_chapelst_email.eml`, two runs each, 2026-11-03). Scores are against `practice_key.json` (vendor, SKU, price, lead time, minimum order, decision):

**Table 8: Output Style Comparison on p08**

| Variant | Output tokens (of which reasoning) | Cost per cached call | Score |
|---|---|---|---|
| A. Free-text reply (before) | 180 / 185 (97 / 102) | $0.000203 / $0.000195 | correct, but free text can't be scored automatically |
| B. Structured, default reasoning | 152 / 146 (85 / 78) | $0.000177 (run 2) | 6/6, 6/6 |
| **C. Structured, low reasoning (adopted)** | **77 / 65 (0 / 0)** | **$0.000137** (run 2) | **6/6, 6/6** |
| D. Structured, minimal reasoning | rejected by gpt-6-luna | | |

- **Output tokens fell by about 64%** (about 180 → 65), and the cost of a cached call fell by about 30% ($0.000195 → $0.000137).
- **Together with caching:** a call is now about **10× cheaper** than the first uncached free-text call ($0.001369 → $0.000137).
- The structured schema changed the request, so the first structured call wrote a new cache (`cached=0`). After that, 10,413 of 10,416 input tokens were cached.
- **Caveat:** p08 is one easy, clean document. Low reasoning still needs to be checked on all 12 practice docs once the full agent reads them, especially the price check against the catalogue and the removed-vendor cases. If accuracy drops, setting `REASONING_EFFORT=medium` in `.env` brings back more reasoning without any code change. The plan is also for Python, not the model, to apply the four purchasing checks, which makes low reasoning safer.

**Results at a glance:** the measured before-and-after table and chart are in [`output/cost_results.md`](cost_results.md).
