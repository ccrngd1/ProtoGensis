"""
RAG Pipeline using AWS Bedrock Knowledge Base + Claude generation.
Supports both real AWS mode and mock mode for testing.
"""

import json
import time
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from config import settings


@dataclass
class RetrievalResult:
    """Result from knowledge base retrieval."""
    chunks: List[str]
    sources: List[str]
    relevance_scores: List[float]


@dataclass
class RAGResult:
    """Complete RAG pipeline result."""
    query: str
    retrieved_context: str
    generated_response: str
    retrieval_latency_ms: float
    generation_latency_ms: float
    total_latency_ms: float
    input_tokens: int
    output_tokens: int
    retrieval_chunks: List[str]


class BedrockRAGPipeline:
    """RAG pipeline using Bedrock Knowledge Base and Claude."""

    def __init__(self, mock_mode: bool = None):
        """
        Initialize RAG pipeline.

        Args:
            mock_mode: If True, use mock data. If None, use settings.mock_mode
        """
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_mode

        if not self.mock_mode:
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 is required for non-mock mode")
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=settings.aws_region
            )
            self.bedrock_agent_client = boto3.client(
                'bedrock-agent-runtime',
                region_name=settings.aws_region
            )

    def retrieve(self, query: str, top_k: int = 5) -> RetrievalResult:
        """
        Retrieve relevant chunks from Bedrock Knowledge Base.

        Args:
            query: User query
            top_k: Number of chunks to retrieve

        Returns:
            RetrievalResult with retrieved chunks
        """
        if self.mock_mode:
            return self._mock_retrieve(query, top_k)

        try:
            response = self.bedrock_agent_client.retrieve(
                knowledgeBaseId=settings.bedrock_kb_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': top_k
                    }
                }
            )

            chunks = []
            sources = []
            scores = []

            for result in response.get('retrievalResults', []):
                chunks.append(result['content']['text'])
                sources.append(result.get('location', {}).get('s3Location', {}).get('uri', 'unknown'))
                scores.append(result.get('score', 0.0))

            return RetrievalResult(chunks=chunks, sources=sources, relevance_scores=scores)

        except ClientError as e:
            raise Exception(f"Bedrock retrieval failed: {e}")

    def _mock_retrieve(self, query: str, top_k: int) -> RetrievalResult:
        """Mock retrieval for testing without AWS."""
        # Simulate retrieval latency
        time.sleep(random.uniform(0.05, 0.15))

        # Generate mock chunks based on query keywords
        query_lower = query.lower()
        mock_chunks = []

        if "s3" in query_lower:
            mock_chunks.append(
                "Amazon S3 is an object storage service offering industry-leading "
                "scalability, data availability, security, and performance."
            )
        elif "lambda" in query_lower:
            mock_chunks.append(
                "AWS Lambda lets you run code without provisioning or managing servers. "
                "You pay only for the compute time you consume."
            )
        elif "ec2" in query_lower:
            mock_chunks.append(
                "Amazon EC2 provides secure, resizable compute capacity in the cloud. "
                "It gives you complete control of your computing resources."
            )
        else:
            # Generic AWS context
            mock_chunks.append(
                "AWS provides a broad set of global cloud-based products including compute, "
                "storage, databases, analytics, networking, mobile, developer tools, "
                "management tools, IoT, security, and enterprise applications."
            )

        # Pad to top_k chunks
        while len(mock_chunks) < top_k:
            mock_chunks.append(f"Additional context chunk {len(mock_chunks) + 1} for query: {query}")

        return RetrievalResult(
            chunks=mock_chunks[:top_k],
            sources=[f"s3://mock-bucket/doc{i}.txt" for i in range(top_k)],
            relevance_scores=[0.9 - (i * 0.1) for i in range(top_k)]
        )

    def generate(self, query: str, context: str) -> Tuple[str, int, int]:
        """
        Generate response using Claude on Bedrock.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Tuple of (response, input_tokens, output_tokens)
        """
        if self.mock_mode:
            return self._mock_generate(query, context)

        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer based strictly on the information provided in the context above. If the context doesn't contain enough information to answer the question, say so."""

        try:
            response = self.bedrock_client.converse(
                modelId=settings.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.1
                }
            )

            output_text = response['output']['message']['content'][0]['text']
            input_tokens = response['usage']['inputTokens']
            output_tokens = response['usage']['outputTokens']

            return output_text, input_tokens, output_tokens

        except ClientError as e:
            raise Exception(f"Bedrock generation failed: {e}")

    def _mock_generate(self, query: str, context: str) -> Tuple[str, int, int]:
        """Mock generation for testing without AWS."""
        # Simulate generation latency
        time.sleep(random.uniform(0.5, 1.5))

        # Simple mock response
        response = f"Based on the provided context, {query.lower().replace('what is', 'it is').replace('?', '.')} "
        response += "This is a mock response generated for testing purposes."

        # Estimate tokens
        input_tokens = len(context.split()) + len(query.split()) + 50  # Include prompt overhead
        output_tokens = len(response.split())

        return response, input_tokens, output_tokens

    def run(self, query: str, top_k: int = 5) -> RAGResult:
        """
        Run complete RAG pipeline: retrieve + generate.

        Args:
            query: User query
            top_k: Number of chunks to retrieve

        Returns:
            RAGResult with complete pipeline output
        """
        # Retrieval
        retrieval_start = time.time()
        retrieval_result = self.retrieve(query, top_k)
        retrieval_latency = (time.time() - retrieval_start) * 1000

        # Combine chunks into context
        context = "\n\n".join(retrieval_result.chunks)

        # Generation
        generation_start = time.time()
        response, input_tokens, output_tokens = self.generate(query, context)
        generation_latency = (time.time() - generation_start) * 1000

        return RAGResult(
            query=query,
            retrieved_context=context,
            generated_response=response,
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=generation_latency,
            total_latency_ms=retrieval_latency + generation_latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retrieval_chunks=retrieval_result.chunks
        )


def main():
    """Demo the RAG pipeline."""
    pipeline = BedrockRAGPipeline(mock_mode=True)

    test_queries = [
        "What is Amazon S3?",
        "How does AWS Lambda pricing work?",
        "What are the benefits of Amazon EC2?"
    ]

    print("=" * 80)
    print("RAG Pipeline Demo (Mock Mode)")
    print("=" * 80)

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 80)

        result = pipeline.run(query)

        print(f"\nRetrieved Context ({len(result.retrieval_chunks)} chunks):")
        for i, chunk in enumerate(result.retrieval_chunks, 1):
            print(f"  {i}. {chunk[:100]}...")

        print(f"\nGenerated Response:")
        print(f"  {result.generated_response}")

        print(f"\nMetrics:")
        print(f"  Retrieval Latency: {result.retrieval_latency_ms:.2f}ms")
        print(f"  Generation Latency: {result.generation_latency_ms:.2f}ms")
        print(f"  Total Latency: {result.total_latency_ms:.2f}ms")
        print(f"  Input Tokens: {result.input_tokens}")
        print(f"  Output Tokens: {result.output_tokens}")


if __name__ == "__main__":
    main()
