"""Per-model pricing and cost calculation for accurate token cost tracking.

Previously, the README noted that "Token tracking uses model-level estimates
rather than per-call provider SDK counts." This module closes that gap by
providing real per-model pricing, enabling the final report to show actual
dollar costs alongside raw token counts.

Pricing is per 1M tokens (input, output). Updated Q3 2026. Prices change —
check provider docs for current rates.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pricing table: (input_price, output_price) per 1M tokens in USD
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # --- Groq (groq.com/pricing) ---
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.2-90b-vision-preview": (0.90, 0.90),
    "deepseek-r1-distill-llama-70b": (0.75, 0.99),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
    # --- OpenAI (openai.com/pricing) ---
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # --- OpenRouter (approximate; actual varies by provider) ---
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "meta-llama/llama-3.3-70b-instruct": (0.59, 0.79),
    "meta-llama/llama-3.1-8b-instruct": (0.05, 0.08),
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD from token counts and known model pricing.

    Falls back to 0.0 for unlisted models (add them to MODEL_PRICING).

    Args:
        model_name: e.g. "llama-3.3-70b-versatile" or "gpt-4o-mini"
        input_tokens: number of input/prompt tokens
        output_tokens: number of output/completion tokens

    Returns:
        Cost in USD, rounded to 6 decimal places.
    """
    input_price, output_price = MODEL_PRICING.get(model_name, (0.0, 0.0))
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return round(input_cost + output_cost, 6)


def format_cost(cost: float) -> str:
    """Human-readable cost string. Micro-costs show all decimals; macro show 2dp."""
    if cost == 0.0:
        return "$0.00 (unpriced model)"
    if cost >= 0.01:
        return f"${cost:.4f}"
    return f"${cost:.6f}"
