"""
The Practitioner's Guide to MoA on Bedrock

A hands-on Mixture-of-Agents implementation using AWS Bedrock.
Focus: economics, latency, and practical deployment decisions.
"""

from .core import MoA, Layer, ModelConfig, create_moa_from_recipe
from .cost_tracker import CostTracker
from .latency_tracker import LatencyTracker
from .bedrock_client import BedrockClient
from .judge import QualityJudge, JudgeScore

__version__ = "1.0.0"

__all__ = [
    "MoA",
    "Layer",
    "ModelConfig",
    "CostTracker",
    "LatencyTracker",
    "BedrockClient",
    "QualityJudge",
    "JudgeScore",
    "create_moa_from_recipe",
]
