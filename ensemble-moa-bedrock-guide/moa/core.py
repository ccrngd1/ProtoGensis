"""
Core MoA (Mixture of Agents) implementation.

Orchestrates multi-layer LLM ensembles with configurable architectures,
parallel execution, cost tracking, and latency measurement.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional

from .bedrock_client import BedrockClient
from .cost_tracker import CostTracker
from .latency_tracker import LatencyTracker
from .models import get_model_pricing


@dataclass
class ModelConfig:
    """Configuration for a single model in the ensemble."""

    model_key: str  # Key from models.py (e.g., 'nova-lite')
    persona: Optional[str] = None  # Optional persona prefix to inject
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class Layer:
    """Configuration for a single layer in the MoA architecture."""

    models: List[ModelConfig]
    layer_type: str  # 'proposer', 'refiner', or 'aggregator'

    def __post_init__(self):
        if self.layer_type not in ['proposer', 'refiner', 'aggregator']:
            raise ValueError(f"Invalid layer_type: {self.layer_type}")


@dataclass
class MoAResponse:
    """Response from an MoA pipeline execution."""

    final_response: str
    layer_responses: List[List[str]]  # Responses from each layer
    cost_summary: dict
    latency_summary: dict
    metadata: dict


class MoA:
    """
    Mixture of Agents orchestrator.

    Coordinates multi-layer LLM ensembles with parallel execution,
    cost tracking, and latency measurement.
    """

    def __init__(
        self,
        layers: List[Layer],
        client: Optional[BedrockClient] = None,
        track_cost: bool = True,
        track_latency: bool = True
    ):
        """
        Initialize MoA orchestrator.

        Args:
            layers: List of Layer configurations defining the architecture
            client: Bedrock client (optional, will create default if not provided)
            track_cost: Whether to track costs
            track_latency: Whether to track latency
        """
        if not layers:
            raise ValueError("At least one layer is required")

        self.layers = layers
        self.track_cost = track_cost
        self.track_latency = track_latency

        # Initialize client
        if client:
            self.client = client
        else:
            self.client = BedrockClient()

        # Initialize trackers
        self.cost_tracker = CostTracker() if track_cost else None
        self.latency_tracker = LatencyTracker() if track_latency else None

    async def run(self, prompt: str) -> MoAResponse:
        """
        Execute the MoA pipeline on a prompt.

        Args:
            prompt: Input prompt to process

        Returns:
            MoAResponse with final output and tracking data
        """
        # Start tracking
        if self.cost_tracker:
            self.cost_tracker.start_pipeline()
        if self.latency_tracker:
            self.latency_tracker.start_pipeline()

        layer_responses = []
        current_context = prompt

        # Execute each layer
        for layer_idx, layer in enumerate(self.layers):
            if self.latency_tracker:
                self.latency_tracker.start_layer(layer_idx)

            # Execute layer
            responses = await self._execute_layer(
                layer=layer,
                layer_idx=layer_idx,
                context=current_context,
                previous_responses=layer_responses
            )

            if self.latency_tracker:
                self.latency_tracker.end_layer()

            layer_responses.append(responses)

            # Prepare context for next layer
            if layer.layer_type == 'aggregator':
                # Aggregator produces the final output
                current_context = responses[0]
            else:
                # Include all previous responses in context for next layer
                current_context = self._build_context(prompt, layer_responses)

        # Get final response
        final_response = layer_responses[-1][0] if layer_responses else ""

        # End tracking
        cost_summary = {}
        if self.cost_tracker:
            pipeline_cost = self.cost_tracker.end_pipeline()
            cost_summary = pipeline_cost.get_summary()

        latency_summary = {}
        if self.latency_tracker:
            pipeline_latency = self.latency_tracker.end_pipeline()
            latency_summary = pipeline_latency.get_summary()

        return MoAResponse(
            final_response=final_response,
            layer_responses=layer_responses,
            cost_summary=cost_summary,
            latency_summary=latency_summary,
            metadata={
                "num_layers": len(self.layers),
                "total_models_invoked": sum(len(layer.models) for layer in self.layers)
            }
        )

    async def _execute_layer(
        self,
        layer: Layer,
        layer_idx: int,
        context: str,
        previous_responses: List[List[str]]
    ) -> List[str]:
        """
        Execute all models in a layer in parallel.

        Args:
            layer: Layer configuration
            layer_idx: Layer index (0-based)
            context: Current context/prompt
            previous_responses: Responses from all previous layers

        Returns:
            List of responses from this layer
        """
        # Create tasks for parallel execution
        tasks = []
        for model_config in layer.models:
            task = self._invoke_model(
                model_config=model_config,
                layer_idx=layer_idx,
                context=context,
                layer_type=layer.layer_type
            )
            tasks.append(task)

        # Execute all models in parallel
        responses = await asyncio.gather(*tasks)

        return responses

    async def _invoke_model(
        self,
        model_config: ModelConfig,
        layer_idx: int,
        context: str,
        layer_type: str
    ) -> str:
        """
        Invoke a single model with tracking.

        Args:
            model_config: Model configuration
            layer_idx: Layer index
            context: Input context
            layer_type: Type of layer ('proposer', 'refiner', 'aggregator')

        Returns:
            Model response text
        """
        model_pricing = get_model_pricing(model_config.model_key)
        model_id = model_pricing.model_id
        model_name = model_pricing.name

        # Build prompt based on layer type
        if layer_type == 'aggregator':
            prompt = self._build_aggregator_prompt(context)
        elif layer_type == 'refiner':
            prompt = self._build_refiner_prompt(context)
        else:  # proposer
            prompt = context

        # Inject persona if specified
        if model_config.persona:
            prompt = f"{model_config.persona}\n\n{prompt}"

        # Track latency
        if self.latency_tracker:
            with self.latency_tracker.track_model(
                model_config.model_key,
                model_name,
                layer_idx
            ):
                result = await self.client.invoke_model(
                    model_id=model_id,
                    prompt=prompt,
                    max_tokens=model_config.max_tokens,
                    temperature=model_config.temperature
                )
        else:
            result = await self.client.invoke_model(
                model_id=model_id,
                prompt=prompt,
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature
            )

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.track_invocation(
                model_key=model_config.model_key,
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                layer=layer_idx
            )

        return result["response"]

    def _build_context(self, original_prompt: str, layer_responses: List[List[str]]) -> str:
        """
        Build context for the next layer by including previous responses.

        Args:
            original_prompt: Original input prompt
            layer_responses: All responses from previous layers

        Returns:
            Context string for next layer
        """
        context_parts = [f"Original prompt: {original_prompt}\n"]

        for layer_idx, responses in enumerate(layer_responses):
            context_parts.append(f"\nLayer {layer_idx + 1} responses:\n")
            for response_idx, response in enumerate(responses):
                context_parts.append(f"\nResponse {response_idx + 1}:\n{response}\n")

        return "".join(context_parts)

    def _build_refiner_prompt(self, context: str) -> str:
        """Build prompt for refiner layer."""
        return f"""{context}

Your task: Review the responses above, identify strengths and weaknesses, and provide an improved response that synthesizes the best insights while addressing any gaps or errors."""

    def _build_aggregator_prompt(self, context: str) -> str:
        """Build prompt for aggregator layer."""
        return f"""{context}

Your task: Synthesize all the above responses into a single, coherent final answer. Extract the most valuable insights from each response, resolve any contradictions, and provide a comprehensive, well-reasoned response to the original prompt."""


# Convenience function for quick MoA setup
def create_moa_from_recipe(recipe_name: str) -> MoA:
    """
    Create an MoA instance from a predefined recipe.

    Args:
        recipe_name: Name of the recipe from models.RECIPES

    Returns:
        Configured MoA instance
    """
    from .models import get_recipe, PERSONAS

    recipe = get_recipe(recipe_name)
    layers = []

    def _parse_model_spec(spec):
        """Parse model spec which can be 'model_key' or ('model_key', 'persona_key')."""
        if isinstance(spec, tuple):
            model_key, persona_key = spec
            persona = PERSONAS.get(persona_key, None)
            return ModelConfig(model_key=model_key, persona=persona)
        else:
            return ModelConfig(model_key=spec)

    # Proposer layer
    if 'proposers' in recipe:
        proposer_models = [
            _parse_model_spec(spec)
            for spec in recipe['proposers']
        ]
        layers.append(Layer(models=proposer_models, layer_type='proposer'))

    # Refiner layer (optional)
    if 'refiners' in recipe:
        refiner_models = [
            _parse_model_spec(spec)
            for spec in recipe['refiners']
        ]
        layers.append(Layer(models=refiner_models, layer_type='refiner'))

    # Aggregator layer
    if 'aggregator' in recipe:
        aggregator_model = _parse_model_spec(recipe['aggregator'])
        layers.append(Layer(models=[aggregator_model], layer_type='aggregator'))

    return MoA(layers=layers)
