"""Structured types for the vendor desk agent.

VendorFacts is what the model returns after reading a document. VendorReport is
the final answer, the fields handbook section 13 asks for: the facts plus the
recommend / do_not_recommend decision and a one-sentence reason, both set by
the purchasing checks in tools.py. Field names match data/practice_key.json, so
answers can be scored directly. A short structured reply also keeps output
tokens (the priciest, at $0.50 per 1M) to a minimum.
"""

from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["recommend", "do_not_recommend"]


class VendorFacts(BaseModel):
    """The five facts the model reads off the document. Null means the document does not say."""

    vendor: str | None = Field(description="Vendor name, or null if the document does not say")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006, or null")
    unit_price: float | None = Field(description="Quoted unit price in USD, or null if unknown")
    lead_time_days: int | None = Field(description="Lead time in days, or null if unknown")
    min_order: int | None = Field(description="Minimum order in units, or null if unknown")


class VendorReport(VendorFacts):
    """The vendor desk's answer for one document (handbook section 13)."""

    decision: Decision
    reason: str = Field(description="One sentence naming the purchasing check that decided it")


CacheSetup = Literal["with_cache", "without_cache"]
DefenseLayer = Literal["code", "design", "prompt"]


class RemovedText(BaseModel):
    """Text the code layer removed because a person opening the document can't see it."""

    text: str
    how: str = Field(description="How it was hidden, e.g. white text, 0px font, off the page")
    where: str = Field(description="Where it was in the file")


class ModelCall(BaseModel):
    """One request to the model and the token counts the API reported for it."""

    request: int = Field(description="1 = the model asks for read_document; 2 = the model answers")
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float


class CallUsage(BaseModel):
    """Tokens and dollar cost of one agent run, as gpt-6-luna reported them."""

    model: str
    setup: CacheSetup
    requests: int
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float
    seconds: float = Field(description="Wall-clock time of the run")
    calls: list[ModelCall] = Field(description="Every model request in the run")
