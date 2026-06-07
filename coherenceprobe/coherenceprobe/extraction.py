"""Claim extraction from agent outputs using LLM or local methods."""

import re
import json
from typing import Optional

from .models import AgentOutput, Claim, CoherenceConfig


def extract_claims(
    outputs: list[AgentOutput],
    config: CoherenceConfig
) -> list[Claim]:
    """Extract atomic factual claims from agent outputs.

    Args:
        outputs: List of agent outputs to process
        config: Configuration including extraction method (LLM or local)

    Returns:
        List of extracted claims
    """
    all_claims = []

    for output in outputs:
        if config.local:
            claims = _extract_claims_local(output)
        else:
            claims = _extract_claims_llm(output, config)

        all_claims.extend(claims)

    if config.verbose:
        print(f"Extracted {len(all_claims)} claims from {len(outputs)} agent outputs")

    return all_claims


def _extract_claims_llm(output: AgentOutput, config: CoherenceConfig) -> list[Claim]:
    """Extract claims using LLM via litellm.

    Args:
        output: Agent output to process
        config: Configuration with model details

    Returns:
        List of extracted claims
    """
    try:
        import litellm
    except ImportError:
        raise ImportError(
            "litellm is required for LLM-based extraction. "
            "Install with: pip install litellm"
        )

    prompt = f"""Extract all atomic factual claims from the following text. Each claim should be:
- A single, independently verifiable statement
- Factual (not opinions or questions)
- Self-contained (understandable without additional context)

Return ONLY a JSON array of strings, each string being one claim. Do not include any other text.

Text:
{output.output}

JSON array of claims:"""

    try:
        response = litellm.completion(
            model=config.model,
            messages=[
                {"role": "system", "content": "You are an expert at extracting factual claims from text. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content.strip()

        # Try to parse JSON - handle markdown code blocks if present
        if content.startswith("```"):
            # Extract JSON from markdown code block
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if match:
                content = match.group(1)

        claim_texts = json.loads(content)

        claims = []
        for claim_text in claim_texts:
            normalized = _normalize_claim(claim_text)
            if normalized:  # Only add non-empty normalized claims
                claims.append(Claim(
                    agent=output.agent,
                    text=claim_text,
                    normalized=normalized,
                    source_sentence=claim_text  # In LLM mode, claim is the source
                ))

        return claims

    except Exception as e:
        if config.verbose:
            print(f"LLM extraction failed for agent {output.agent}: {e}")
            print("Falling back to local extraction")
        # Fallback to local extraction
        return _extract_claims_local(output)


def _extract_claims_local(output: AgentOutput) -> list[Claim]:
    """Extract claims using local spaCy-based method.

    Args:
        output: Agent output to process

    Returns:
        List of extracted claims
    """
    try:
        import spacy
    except ImportError:
        raise ImportError(
            "spaCy is required for local extraction. "
            "Install with: pip install spacy && python -m spacy download en_core_web_sm"
        )

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise OSError(
            "spaCy model 'en_core_web_sm' not found. "
            "Download with: python -m spacy download en_core_web_sm"
        )

    doc = nlp(output.output)

    claims = []
    for sent in doc.sents:
        sentence_text = sent.text.strip()

        # Skip if too short
        if len(sentence_text.split()) < 3:
            continue

        # Skip questions
        if sentence_text.endswith("?"):
            continue

        # Skip if contains high uncertainty markers
        uncertainty_markers = [
            "might", "could", "possibly", "perhaps", "maybe",
            "unclear", "uncertain", "unknown", "may be"
        ]
        if any(marker in sentence_text.lower() for marker in uncertainty_markers):
            continue

        # Check if sentence has a verb (indicates declarative statement)
        has_verb = any(token.pos_ == "VERB" for token in sent)
        if not has_verb:
            continue

        # Normalize and create claim
        normalized = _normalize_claim(sentence_text)
        if normalized:
            claims.append(Claim(
                agent=output.agent,
                text=sentence_text,
                normalized=normalized,
                source_sentence=sentence_text
            ))

    return claims


def _normalize_claim(claim_text: str) -> str:
    """Normalize a claim by removing hedging and standardizing format.

    Args:
        claim_text: Raw claim text

    Returns:
        Normalized claim text
    """
    text = claim_text.strip()

    # Remove common hedging phrases at the start
    hedging_patterns = [
        r'^I think that\s+',
        r'^I believe that\s+',
        r'^It seems that\s+',
        r'^It appears that\s+',
        r'^Possibly,?\s+',
        r'^Perhaps,?\s+',
        r'^Maybe,?\s+',
    ]

    for pattern in hedging_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove trailing punctuation for normalization
    text = text.rstrip('.,;:!?')

    # Convert to lowercase for comparison
    text = text.lower()

    # Remove extra whitespace
    text = ' '.join(text.split())

    return text


async def aextract_claims(
    outputs: list[AgentOutput],
    config: CoherenceConfig
) -> list[Claim]:
    """Async version of extract_claims.

    Args:
        outputs: List of agent outputs to process
        config: Configuration including extraction method

    Returns:
        List of extracted claims
    """
    # For now, just wrap the sync version
    # In production, this could use async litellm calls
    return extract_claims(outputs, config)
