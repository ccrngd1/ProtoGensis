"""
Model definitions and Bedrock pricing table.

Pricing as of April 2026. Always verify current pricing at:
https://aws.amazon.com/bedrock/pricing/
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class ModelPricing:
    """Per-model pricing for Bedrock models."""

    model_id: str
    name: str
    input_price_per_1k: float  # USD per 1K input tokens
    output_price_per_1k: float  # USD per 1K output tokens
    context_window: int
    category: str  # 'cheap', 'mid', 'strong'
    substitution_note: str = ""  # Note if substituting for unavailable model


# Current Bedrock pricing (April 2026) - AVAILABLE MODELS ONLY
# Using cross-region inference profile IDs (us. prefix) for better availability
BEDROCK_MODELS = {
    # Amazon Nova models
    "nova-lite": ModelPricing(
        model_id="us.amazon.nova-lite-v1:0",
        name="Nova Lite",
        input_price_per_1k=0.00006,
        output_price_per_1k=0.00024,
        context_window=300000,
        category="cheap",
        substitution_note="Substituting for: Mistral 7B, Llama 3.1 8B (both unavailable)"
    ),
    "nova-pro": ModelPricing(
        model_id="us.amazon.nova-pro-v1:0",
        name="Nova Pro",
        input_price_per_1k=0.0008,
        output_price_per_1k=0.0032,
        context_window=300000,
        category="mid",
        substitution_note="Substituting for: Mixtral 8x7B, Llama 3.1 70B (both unavailable)"
    ),
    "nova-premier": ModelPricing(
        model_id="us.amazon.nova-premier-v1:0",
        name="Nova Premier",
        input_price_per_1k=0.002,
        output_price_per_1k=0.008,
        context_window=300000,
        category="strong"
    ),

    # Anthropic Claude models
    "haiku": ModelPricing(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        name="Claude Haiku 4.5",
        input_price_per_1k=0.0008,
        output_price_per_1k=0.004,
        context_window=200000,
        category="cheap"
    ),
    "sonnet": ModelPricing(
        model_id="us.anthropic.claude-sonnet-4-6",
        name="Claude Sonnet 4.6",
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
        context_window=200000,
        category="strong",
        substitution_note="Substituting for: Mistral Large (unavailable)"
    ),
    "opus": ModelPricing(
        model_id="us.anthropic.claude-opus-4-6-v1",
        name="Claude Opus 4.6",
        input_price_per_1k=0.015,
        output_price_per_1k=0.075,
        context_window=200000,
        category="strong"
    ),

    # Mistral models
    "mistral-7b": ModelPricing(
        model_id="mistral.mistral-7b-instruct-v0:2",
        name="Mistral 7B",
        input_price_per_1k=0.00015,
        output_price_per_1k=0.0002,
        context_window=32000,
        category="cheap"
    ),
    "mixtral-8x7b": ModelPricing(
        model_id="mistral.mixtral-8x7b-instruct-v0:1",
        name="Mixtral 8x7B",
        input_price_per_1k=0.00045,
        output_price_per_1k=0.0007,
        context_window=32000,
        category="mid"
    ),
    "mistral-large": ModelPricing(
        model_id="mistral.mistral-large-2402-v1:0",
        name="Mistral Large",
        input_price_per_1k=0.004,
        output_price_per_1k=0.012,
        context_window=32000,
        category="strong"
    ),

    # Meta Llama models
    "llama-3.1-8b": ModelPricing(
        model_id="us.meta.llama3-1-8b-instruct-v1:0",
        name="Llama 3.1 8B",
        input_price_per_1k=0.00022,
        output_price_per_1k=0.00022,
        context_window=128000,
        category="cheap"
    ),
    "llama-3.1-70b": ModelPricing(
        model_id="us.meta.llama3-1-70b-instruct-v1:0",
        name="Llama 3.1 70B",
        input_price_per_1k=0.00072,
        output_price_per_1k=0.00072,
        context_window=128000,
        category="mid"
    ),
}


def get_model_pricing(model_key: str) -> ModelPricing:
    """Get pricing info for a model by its key."""
    if model_key not in BEDROCK_MODELS:
        raise ValueError(f"Unknown model key: {model_key}. Available: {list(BEDROCK_MODELS.keys())}")
    return BEDROCK_MODELS[model_key]


def get_models_by_category(category: str) -> Dict[str, ModelPricing]:
    """Get all models in a category."""
    return {k: v for k, v in BEDROCK_MODELS.items() if v.category == category}


# Pre-defined ensemble recipes
# UPDATED: Using only available models with documented substitutions
RECIPES = {
    "ultra-cheap": {
        "name": "Ultra-Cheap Ensemble",
        "description": "Minimum viable cost using Nova Lite (substituting for Mistral 7B, Llama 3.1 8B)",
        "proposers": ["nova-lite", "mistral-7b", "llama-3.1-8b"],
        "aggregator": "nova-lite",
        "layers": 2,
        "use_case": "High-volume, low-stakes queries",
    },
    "code-generation": {
        "name": "Code Generation",
        "description": "Balanced cost/quality using Nova Pro (substituting for Mixtral 8x7B) and Haiku",
        "proposers": ["nova-pro", "mixtral-8x7b", "llama-3.1-70b"],
        "aggregator": "haiku",
        "layers": 2,
        "use_case": "Code completion, generation, refactoring",
    },
    "reasoning": {
        "name": "Reasoning Tasks",
        "description": "Higher-quality models for complex reasoning (Nova Pro substituting for unavailable models)",
        "proposers": ["nova-pro", "haiku", "llama-3.1-70b"],
        "refiners": ["mixtral-8x7b", "nova-pro"],
        "aggregator": "haiku",
        "layers": 3,
        "use_case": "Multi-step reasoning, analysis",
    },
}


def get_recipe(recipe_name: str) -> dict:
    """Get a pre-defined ensemble recipe."""
    if recipe_name not in RECIPES:
        raise ValueError(f"Unknown recipe: {recipe_name}. Available: {list(RECIPES.keys())}")
    return RECIPES[recipe_name]


def print_substitutions():
    """Print all model substitutions for documentation."""
    print("\n" + "="*80)
    print("MODEL SUBSTITUTIONS (Unavailable → Available)")
    print("="*80)
    subs = [
        ("Mistral 7B", "Nova Lite", "Cheapest available"),
        ("Mixtral 8x7B", "Nova Pro", "Mid-tier substitute"),
        ("Llama 3.1 8B", "Nova Lite", "Cheapest available"),
        ("Llama 3.1 70B", "Nova Pro", "Mid-tier substitute"),
        ("Mistral Large", "Claude Sonnet 4.6", "Strong reasoning model")
    ]

    for original, substitute, reason in subs:
        print(f"  {original:20} → {substitute:20} ({reason})")

    print("="*80 + "\n")
