"""Configuration management for RAG verification project."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_profile: str = "default"

    # Bedrock Configuration
    bedrock_kb_id: Optional[str] = None
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514"

    # SageMaker Endpoints
    sagemaker_nli_endpoint: Optional[str] = None
    sagemaker_encoder_endpoint: Optional[str] = None

    # Mock Mode
    mock_mode: bool = True

    # Cost Estimation (per 1K tokens)
    claude_input_cost_per_1k: float = 0.003
    claude_output_cost_per_1k: float = 0.015
    sagemaker_compute_cost_per_sec: float = 0.000392  # ~$1.41/hr for ml.g5.xlarge

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
EVALUATORS_DIR = PROJECT_ROOT / "evaluators"
