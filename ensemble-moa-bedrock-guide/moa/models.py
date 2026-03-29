"""
Model definitions and Bedrock pricing table.

Pricing as of March 2026. Always verify current pricing at:
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


# Current Bedrock pricing (March 2026)
# Note: Prices vary by region. These are us-east-1 on-demand prices.
BEDROCK_MODELS = {
    # Amazon Nova models
    "nova-micro": ModelPricing(
        model_id="us.amazon.nova-micro-v1:0",
        name="Nova Micro",
        input_price_per_1k=0.000035,
        output_price_per_1k=0.00014,
        context_window=128000,
        category="cheap"
    ),
    "nova-lite": ModelPricing(
        model_id="us.amazon.nova-lite-v1:0",
        name="Nova Lite",
        input_price_per_1k=0.00006,
        output_price_per_1k=0.00024,
        context_window=300000,
        category="cheap"
    ),
    "nova-pro": ModelPricing(
        model_id="us.amazon.nova-pro-v1:0",
        name="Nova Pro",
        input_price_per_1k=0.0008,
        output_price_per_1k=0.0032,
        context_window=300000,
        category="mid"
    ),

    # Anthropic Claude models
    "haiku": ModelPricing(
        model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        name="Claude 3.5 Haiku",
        input_price_per_1k=0.001,
        output_price_per_1k=0.005,
        context_window=200000,
        category="cheap"
    ),
    "sonnet": ModelPricing(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        name="Claude 3.5 Sonnet",
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
        context_window=200000,
        category="strong"
    ),
    "opus": ModelPricing(
        model_id="us.anthropic.claude-opus-4-20250514-v1:0",
        name="Claude Opus 4",
        input_price_per_1k=0.015,
        output_price_per_1k=0.075,
        context_window=200000,
        category="strong"
    ),

    # Meta Llama models
    "llama-3-8b": ModelPricing(
        model_id="meta.llama3-8b-instruct-v1:0",
        name="Llama 3 8B",
        input_price_per_1k=0.0003,
        output_price_per_1k=0.0006,
        context_window=8192,
        category="cheap"
    ),
    "llama-3-70b": ModelPricing(
        model_id="meta.llama3-70b-instruct-v1:0",
        name="Llama 3 70B",
        input_price_per_1k=0.00265,
        output_price_per_1k=0.0035,
        context_window=8192,
        category="mid"
    ),
    "llama-3.1-8b": ModelPricing(
        model_id="meta.llama3-1-8b-instruct-v1:0",
        name="Llama 3.1 8B",
        input_price_per_1k=0.00022,
        output_price_per_1k=0.00022,
        context_window=128000,
        category="cheap"
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
RECIPES = {
    "ultra-cheap": {
        "name": "Ultra-Cheap Ensemble",
        "description": "Minimum viable cost for testing",
        "proposers": ["nova-micro", "mistral-7b", "llama-3.1-8b"],
        "aggregator": "nova-lite",
        "layers": 2,
        "use_case": "High-volume, low-stakes queries"
    },
    "code-generation": {
        "name": "Code Generation",
        "description": "Balanced cost/quality for code tasks",
        "proposers": ["nova-pro", "mixtral-8x7b", "llama-3-70b"],
        "aggregator": "haiku",
        "layers": 2,
        "use_case": "Code completion, generation, refactoring"
    },
    "reasoning": {
        "name": "Reasoning Tasks",
        "description": "Higher-quality models for complex reasoning",
        "proposers": ["nova-pro", "haiku", "llama-3-70b"],
        "refiners": ["mixtral-8x7b", "nova-pro"],
        "aggregator": "haiku",
        "layers": 3,
        "use_case": "Multi-step reasoning, analysis"
    },
    "creative-writing": {
        "name": "Creative Writing",
        "description": "Diverse perspectives for creative tasks",
        "proposers": ["nova-lite", "mistral-7b", "llama-3.1-8b", "haiku"],
        "aggregator": "nova-pro",
        "layers": 2,
        "use_case": "Content generation, storytelling"
    },
}


def get_recipe(recipe_name: str) -> dict:
    """Get a pre-defined ensemble recipe."""
    if recipe_name not in RECIPES:
        raise ValueError(f"Unknown recipe: {recipe_name}. Available: {list(RECIPES.keys())}")
    return RECIPES[recipe_name]
