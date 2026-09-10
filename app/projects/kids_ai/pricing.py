"""Kids AI model ids and USD rates per 1 million tokens.

Rates are applied when a call returns usage metadata. Historical
``kids_ai_llm_call`` rows keep the dollars stored at that time.
"""

from decimal import Decimal

# Exact API model ids used in v1.
MODEL_PRIMARY = "claude-sonnet-5"
MODEL_MODERATION_A = "gemini-3.5-flash-lite"
MODEL_MODERATION_B = "gpt-5.6-luna"
MODEL_TITLE = "gemini-3.5-flash-lite"

# USD per 1M tokens. Update when provider list prices change.
PRICING = {
    MODEL_PRIMARY: {"input": Decimal("2"), "output": Decimal("10")},
    MODEL_MODERATION_A: {"input": Decimal("0.30"), "output": Decimal("2.50")},
    MODEL_MODERATION_B: {"input": Decimal("0.20"), "output": Decimal("1.20")},
}


def costs_usd(model, input_tokens, output_tokens):
    """Return (input_cost_usd, output_cost_usd) or (None, None) if unknown model."""
    rates = PRICING.get(model)
    if rates is None:
        return None, None
    inp = int(input_tokens or 0)
    out = int(output_tokens or 0)
    million = Decimal("1000000")
    return (
        (Decimal(inp) / million) * rates["input"],
        (Decimal(out) / million) * rates["output"],
    )
