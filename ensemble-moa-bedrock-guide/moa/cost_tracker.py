"""
Cost tracking for MoA invocations.

Calculates actual per-invocation costs based on token counts
and current Bedrock pricing.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from .models import get_model_pricing


@dataclass
class ModelInvocation:
    """Single model invocation cost data."""

    model_key: str
    model_name: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    layer: int


@dataclass
class PipelineCost:
    """Total cost breakdown for an MoA pipeline execution."""

    invocations: List[ModelInvocation] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    layer_costs: Dict[int, float] = field(default_factory=dict)

    def add_invocation(self, invocation: ModelInvocation):
        """Add an invocation to the cost tracking."""
        self.invocations.append(invocation)
        self.total_cost += invocation.total_cost
        self.total_input_tokens += invocation.input_tokens
        self.total_output_tokens += invocation.output_tokens

        if invocation.layer not in self.layer_costs:
            self.layer_costs[invocation.layer] = 0.0
        self.layer_costs[invocation.layer] += invocation.total_cost

    def get_summary(self) -> dict:
        """Get a summary of the pipeline cost."""
        return {
            "total_cost": round(self.total_cost, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "num_invocations": len(self.invocations),
            "layer_costs": {f"layer_{k}": round(v, 6) for k, v in self.layer_costs.items()},
            "cost_per_layer": [
                {
                    "layer": inv.layer,
                    "model": inv.model_name,
                    "cost": round(inv.total_cost, 6),
                    "input_tokens": inv.input_tokens,
                    "output_tokens": inv.output_tokens
                }
                for inv in self.invocations
            ]
        }


class CostTracker:
    """Tracks costs across MoA pipeline invocations."""

    def __init__(self):
        self.pipeline_costs: List[PipelineCost] = []
        self.current_pipeline: PipelineCost | None = None

    def start_pipeline(self):
        """Start tracking a new pipeline execution."""
        self.current_pipeline = PipelineCost()

    def track_invocation(
        self,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        layer: int
    ) -> ModelInvocation:
        """
        Track a single model invocation.

        Args:
            model_key: Key identifying the model (e.g., 'nova-lite')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            layer: Layer number (0-indexed)

        Returns:
            ModelInvocation with calculated costs
        """
        pricing = get_model_pricing(model_key)

        input_cost = (input_tokens / 1000) * pricing.input_price_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_price_per_1k
        total_cost = input_cost + output_cost

        invocation = ModelInvocation(
            model_key=model_key,
            model_name=pricing.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            layer=layer
        )

        if self.current_pipeline:
            self.current_pipeline.add_invocation(invocation)

        return invocation

    def end_pipeline(self) -> PipelineCost:
        """End the current pipeline tracking and return the cost data."""
        if not self.current_pipeline:
            raise RuntimeError("No pipeline in progress")

        pipeline = self.current_pipeline
        self.pipeline_costs.append(pipeline)
        self.current_pipeline = None
        return pipeline

    def get_average_cost(self) -> float:
        """Get average cost across all tracked pipelines."""
        if not self.pipeline_costs:
            return 0.0
        return sum(p.total_cost for p in self.pipeline_costs) / len(self.pipeline_costs)

    def get_total_cost(self) -> float:
        """Get total cost across all tracked pipelines."""
        return sum(p.total_cost for p in self.pipeline_costs)

    def reset(self):
        """Reset all tracked costs."""
        self.pipeline_costs = []
        self.current_pipeline = None
