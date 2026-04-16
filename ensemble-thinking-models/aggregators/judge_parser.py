#!/usr/bin/env python3
"""
Robust Judge Response Parser

This module provides centralized, validated parsing for all judge-based aggregators.
Replaces fragile regex/heuristic fallbacks with structured parsing and comprehensive logging.

Design principles:
1. Try structured format first (SELECTED:, FINAL_ANSWER:, REASONING:)
2. Fall back to heuristics with explicit logging
3. Validate all extracted values
4. Return parse confidence score
5. Never fail silently

Usage:
    from aggregators.judge_parser import JudgeParser

    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])
    result = parser.parse_selection(judge_response)

    if result.confidence < 0.8:
        print(f"Warning: Low confidence parse ({result.confidence:.0%})")
        print(f"Strategy: {result.strategy}")

    selected_model = result.selected_model
"""

import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ParseStrategy(Enum):
    """Strategy used to parse judge response"""
    STRUCTURED = "structured_format"  # SELECTED:, FINAL_ANSWER:, etc.
    EXPLICIT_SELECTION = "explicit_selection"  # "SELECTING opus-fast"
    STANDALONE_LINE = "standalone_line"  # Model name on its own line
    POSITIVE_PHRASES = "positive_phrases"  # "opus-fast is the best"
    SENTIMENT_SCORING = "sentiment_scoring"  # Count positive vs negative mentions
    FIRST_VALID = "first_valid"  # First mentioned valid model (lowest confidence)


@dataclass
class ParseResult:
    """Result of parsing judge response"""
    selected_model: Optional[str]
    final_answer: Optional[str]
    reasoning: Optional[str]
    confidence: float  # 0.0-1.0, how confident we are in the parse
    strategy: ParseStrategy  # Which strategy succeeded
    warnings: List[str]  # Any parsing issues encountered

    def is_valid(self) -> bool:
        """Check if parse produced valid result"""
        return self.selected_model is not None and self.confidence >= 0.5


class JudgeParser:
    """
    Robust parser for judge responses with fallback strategies and logging.

    Attempts parsing in order of reliability:
    1. Structured format (SELECTED:, FINAL_ANSWER:, REASONING:) - 1.0 confidence
    2. Explicit selection phrases - 0.9 confidence
    3. Standalone line with model name - 0.8 confidence
    4. Positive selection phrases - 0.7 confidence
    5. Sentiment scoring (positive vs negative mentions) - 0.5 confidence
    6. First valid model mentioned - 0.3 confidence (very unreliable)
    """

    def __init__(self, valid_models: List[str], logger: Optional[logging.Logger] = None):
        """
        Initialize parser.

        Args:
            valid_models: List of valid model names (e.g., ['opus-fast', 'sonnet-fast'])
            logger: Optional logger for warnings. If None, creates default logger.
        """
        self.valid_models = valid_models
        self.logger = logger or self._create_default_logger()

    def _create_default_logger(self) -> logging.Logger:
        """Create default logger for parser warnings"""
        logger = logging.getLogger('JudgeParser')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)
        return logger

    def parse_selection(self, response: str) -> ParseResult:
        """
        Parse judge response to extract selected model.

        Args:
            response: Full judge response text

        Returns:
            ParseResult with selected model and metadata
        """
        warnings = []

        # Try each strategy in order of reliability
        strategies = [
            (self._try_structured_format, ParseStrategy.STRUCTURED, 1.0),
            (self._try_explicit_selection, ParseStrategy.EXPLICIT_SELECTION, 0.9),
            (self._try_standalone_line, ParseStrategy.STANDALONE_LINE, 0.8),
            (self._try_positive_phrases, ParseStrategy.POSITIVE_PHRASES, 0.7),
            (self._try_sentiment_scoring, ParseStrategy.SENTIMENT_SCORING, 0.5),
            (self._try_first_valid, ParseStrategy.FIRST_VALID, 0.3),
        ]

        for strategy_func, strategy_name, base_confidence in strategies:
            result = strategy_func(response)
            if result:
                selected, final_answer, reasoning = result

                # Validate selected model
                if selected not in self.valid_models:
                    warnings.append(f"Parsed model '{selected}' not in valid list: {self.valid_models}")
                    selected = self._fuzzy_match_model(selected)
                    if selected:
                        warnings.append(f"Fuzzy matched to: {selected}")
                    else:
                        continue  # Try next strategy

                # Log if using fallback strategy
                if strategy_name != ParseStrategy.STRUCTURED:
                    self.logger.warning(
                        f"Judge parser used fallback strategy: {strategy_name.value} "
                        f"(confidence: {base_confidence:.0%})"
                    )

                return ParseResult(
                    selected_model=selected,
                    final_answer=final_answer,
                    reasoning=reasoning,
                    confidence=base_confidence,
                    strategy=strategy_name,
                    warnings=warnings
                )

        # All strategies failed
        self.logger.error(
            f"Judge parser FAILED: Could not extract model selection\n"
            f"Valid models: {self.valid_models}\n"
            f"Response preview: {response[:200]}..."
        )

        # Return default (first valid model) with low confidence
        return ParseResult(
            selected_model=self.valid_models[0] if self.valid_models else None,
            final_answer=None,
            reasoning=response,
            confidence=0.0,
            strategy=ParseStrategy.FIRST_VALID,
            warnings=["All parsing strategies failed, using default model"]
        )

    def _try_structured_format(self, response: str) -> Optional[tuple]:
        """
        Try to parse structured format:
        SELECTED: model-name
        FINAL_ANSWER: answer
        REASONING: reasoning text
        """
        selected = None
        final_answer = None
        reasoning = None

        # Look for SELECTED: line
        selected_match = re.search(r'SELECTED:\s*([^\n]+)', response, re.IGNORECASE)
        if selected_match:
            selected = selected_match.group(1).strip().lower()

        # Look for FINAL_ANSWER: line
        answer_match = re.search(r'FINAL_ANSWER:\s*([^\n]+)', response, re.IGNORECASE)
        if answer_match:
            final_answer = answer_match.group(1).strip()

        # Look for REASONING: section
        reasoning_match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()

        if selected:
            return (selected, final_answer, reasoning or response)

        return None

    def _try_explicit_selection(self, response: str) -> Optional[tuple]:
        """
        Try to find explicit selection phrases:
        - "SELECTING opus-fast"
        - "CHOICE: opus-fast"
        - "I SELECT opus-fast"
        """
        patterns = [
            r'SELECTING\s+([a-z\-]+)',
            r'CHOICE:\s*([a-z\-]+)',
            r'I\s+SELECT\s+([a-z\-]+)',
            r'SELECTED\s+MODEL:\s*([a-z\-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                selected = match.group(1).strip().lower()
                return (selected, None, response)

        return None

    def _try_standalone_line(self, response: str) -> Optional[tuple]:
        """
        Try to find model name on a line by itself.
        Check first line and last 5 lines (common patterns).
        """
        lines = response.strip().split('\n')

        # Check first line (pattern: "OPUS\n\n**Reasoning:**")
        if lines:
            first_line = lines[0].strip().strip('*').strip().lower()
            for model in self.valid_models:
                if first_line == model.lower():
                    return (model, None, response)

        # Check last 5 lines
        for line in reversed(lines[-5:]):
            stripped = line.strip().strip('*').strip().lower()
            for model in self.valid_models:
                if stripped == model.lower():
                    return (model, None, response)

        return None

    def _try_positive_phrases(self, response: str) -> Optional[tuple]:
        """
        Try to find positive selection phrases in last 200 chars:
        - "opus-fast's clear advantage"
        - "opus-fast is the best"
        - "makes opus-fast the best choice"
        """
        last_200 = response[-200:].upper()

        for model in self.valid_models:
            model_upper = model.upper()

            positive_phrases = [
                f"{model_upper}'S CLEAR",
                f"{model_upper}'S EXPLANATION",
                f"MAKES {model_upper} THE BEST",
                f"{model_upper} IS THE BEST",
                f"{model_upper} PROVIDES THE MOST",
            ]

            for phrase in positive_phrases:
                if phrase in last_200:
                    return (model, None, response)

        return None

    def _try_sentiment_scoring(self, response: str) -> Optional[tuple]:
        """
        Count positive vs negative mentions in last 500 chars.
        This is the LEAST reliable strategy - use only as fallback.
        """
        last_500 = response[-500:].upper()
        scores = {}

        for model in self.valid_models:
            model_upper = model.upper()

            # Positive indicators
            positive = (
                last_500.count(f"{model_upper} PROVIDES THE MOST") * 2 +
                last_500.count(f"{model_upper} IS SUPERIOR") * 2 +
                last_500.count(f"{model_upper} IS THE BETTER") * 2 +
                last_500.count(f"{model_upper}'S") * 0.5  # Possessive, weak signal
            )

            # Negative indicators (stronger signal)
            negative = (
                last_500.count(f"{model_upper} PROVIDES NO") * 3 +
                last_500.count(f"{model_upper} IS COMPLETELY EMPTY") * 3 +
                last_500.count(f"{model_upper} PROVIDES NOTHING") * 3 +
                last_500.count(f"{model_upper} FAILS") * 3
            )

            scores[model] = positive - negative

        # Select model with highest positive score > 0
        valid_scores = [(k, v) for k, v in scores.items() if v > 0]

        if valid_scores:
            selected = max(valid_scores, key=lambda x: x[1])[0]
            return (selected, None, response)

        return None

    def _try_first_valid(self, response: str) -> Optional[tuple]:
        """
        Find first valid model name mentioned anywhere in response.
        This is VERY unreliable - model might be mentioned negatively.
        """
        response_lower = response.lower()

        for model in self.valid_models:
            if model.lower() in response_lower:
                return (model, None, response)

        return None

    def _fuzzy_match_model(self, parsed_model: str) -> Optional[str]:
        """
        Try to fuzzy match parsed model name to valid model.
        E.g., "OPUS" -> "opus-fast", "sonnet" -> "sonnet-fast"
        """
        parsed_lower = parsed_model.lower()

        for model in self.valid_models:
            # Check if parsed is substring of valid model
            if parsed_lower in model.lower():
                return model

            # Check if valid model is substring of parsed
            if model.lower() in parsed_lower:
                return model

        return None


def get_parser_stats(parser_results: List[ParseResult]) -> Dict[str, Any]:
    """
    Generate statistics from multiple parse results.
    Useful for auditing judge parsing reliability.

    Args:
        parser_results: List of ParseResult objects

    Returns:
        Dictionary with statistics
    """
    if not parser_results:
        return {}

    total = len(parser_results)

    # Count by strategy
    strategy_counts = {}
    for result in parser_results:
        strategy_counts[result.strategy.value] = strategy_counts.get(result.strategy.value, 0) + 1

    # Count failures (confidence < 0.5)
    low_confidence = sum(1 for r in parser_results if r.confidence < 0.5)

    # Average confidence
    avg_confidence = sum(r.confidence for r in parser_results) / total

    # Count warnings
    total_warnings = sum(len(r.warnings) for r in parser_results)

    return {
        'total_parses': total,
        'avg_confidence': avg_confidence,
        'low_confidence_count': low_confidence,
        'low_confidence_rate': low_confidence / total,
        'strategy_distribution': strategy_counts,
        'total_warnings': total_warnings,
        'warnings_per_parse': total_warnings / total
    }
