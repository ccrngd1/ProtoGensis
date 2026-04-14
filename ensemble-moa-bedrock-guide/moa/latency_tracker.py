"""
Latency tracking for MoA pipeline execution.

Measures wall-clock time per model, per layer, and total pipeline.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ModelLatency:
    """Single model invocation latency data."""

    model_key: str
    model_name: str
    layer: int
    duration_ms: float


@dataclass
class LayerLatency:
    """Latency for an entire layer (parallel execution)."""

    layer: int
    duration_ms: float
    model_latencies: List[ModelLatency] = field(default_factory=list)

    def add_model(self, model_latency: ModelLatency):
        """Add a model latency to this layer."""
        self.model_latencies.append(model_latency)


@dataclass
class PipelineLatency:
    """Total latency breakdown for an MoA pipeline execution."""

    total_duration_ms: float = 0.0
    layers: List[LayerLatency] = field(default_factory=list)

    def add_layer(self, layer_latency: LayerLatency):
        """Add a layer latency to the pipeline."""
        self.layers.append(layer_latency)

    def get_summary(self) -> dict:
        """Get a summary of the pipeline latency."""
        return {
            "total_duration_ms": round(self.total_duration_ms, 2),
            "total_duration_s": round(self.total_duration_ms / 1000, 2),
            "num_layers": len(self.layers),
            "layer_breakdown": [
                {
                    "layer": layer.layer,
                    "duration_ms": round(layer.duration_ms, 2),
                    "num_models": len(layer.model_latencies),
                    "models": [
                        {
                            "model": m.model_name,
                            "duration_ms": round(m.duration_ms, 2)
                        }
                        for m in layer.model_latencies
                    ]
                }
                for layer in self.layers
            ]
        }


class LatencyTracker:
    """Tracks latency across MoA pipeline invocations."""

    def __init__(self):
        self.pipeline_latencies: List[PipelineLatency] = []
        self.current_pipeline: PipelineLatency | None = None
        self.current_layer: LayerLatency | None = None
        self._pipeline_start: float | None = None
        self._layer_start: float | None = None

    def start_pipeline(self):
        """Start tracking a new pipeline execution.

        Raises:
            RuntimeError: If a pipeline is already in progress
        """
        if self.current_pipeline is not None:
            raise RuntimeError(
                "Pipeline already in progress. Call end_pipeline() first or use reset()."
            )
        self.current_pipeline = PipelineLatency()
        self._pipeline_start = time.time()

    def end_pipeline(self) -> PipelineLatency:
        """End the current pipeline tracking and return the latency data."""
        if not self.current_pipeline or self._pipeline_start is None:
            raise RuntimeError("No pipeline in progress")

        duration = (time.time() - self._pipeline_start) * 1000  # Convert to ms
        self.current_pipeline.total_duration_ms = duration

        pipeline = self.current_pipeline
        self.pipeline_latencies.append(pipeline)
        self.current_pipeline = None
        self._pipeline_start = None
        return pipeline

    def start_layer(self, layer_num: int):
        """Start tracking a layer execution.

        Args:
            layer_num: Layer number to track

        Raises:
            RuntimeError: If a layer is already in progress
        """
        if self.current_layer is not None:
            raise RuntimeError(
                f"Layer already in progress. Call end_layer() first before starting layer {layer_num}."
            )
        self.current_layer = LayerLatency(layer=layer_num, duration_ms=0.0)
        self._layer_start = time.time()

    def end_layer(self):
        """End the current layer tracking."""
        if not self.current_layer or self._layer_start is None:
            raise RuntimeError("No layer in progress")

        duration = (time.time() - self._layer_start) * 1000  # Convert to ms
        self.current_layer.duration_ms = duration

        if self.current_pipeline:
            self.current_pipeline.add_layer(self.current_layer)

        self.current_layer = None
        self._layer_start = None

    @contextmanager
    def track_model(self, model_key: str, model_name: str, layer: int):
        """
        Context manager to track a single model invocation.

        Usage:
            with tracker.track_model('nova-lite', 'Nova Lite', 0):
                # model invocation here
                pass
        """
        start = time.time()
        try:
            yield
        finally:
            duration = (time.time() - start) * 1000  # Convert to ms
            model_latency = ModelLatency(
                model_key=model_key,
                model_name=model_name,
                layer=layer,
                duration_ms=duration
            )

            if self.current_layer is not None:
                self.current_layer.add_model(model_latency)

    def get_average_latency(self) -> float:
        """Get average total latency across all tracked pipelines (in ms)."""
        if not self.pipeline_latencies:
            return 0.0
        return sum(p.total_duration_ms for p in self.pipeline_latencies) / len(self.pipeline_latencies)

    def get_average_layer_latency(self, layer: int) -> float:
        """Get average latency for a specific layer across all pipelines (in ms)."""
        layer_durations = []
        for pipeline in self.pipeline_latencies:
            for layer_lat in pipeline.layers:
                if layer_lat.layer == layer:
                    layer_durations.append(layer_lat.duration_ms)

        if not layer_durations:
            return 0.0
        return sum(layer_durations) / len(layer_durations)

    def reset(self):
        """Reset all tracked latencies."""
        self.pipeline_latencies = []
        self.current_pipeline = None
        self.current_layer = None
        self._pipeline_start = None
        self._layer_start = None
