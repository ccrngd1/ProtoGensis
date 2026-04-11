#!/usr/bin/env python3
"""
Use Claude to extract final numeric answers from GSM8K responses.

Since automated regex extraction keeps grabbing intermediate values,
use Claude to read the response and extract just the final answer.
This is more reliable for math word problems where there are many
intermediate calculations.
"""

import json
import anthropic
import os
from pathlib import Path

# Initialize Claude client
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def extract_answer_with_claude(response_text, question_text):
    """
    Use Claude to extract the final numeric answer from a response.
    """
    prompt = f"""Here is a math word problem and a solution:

QUESTION:
{question_text}

SOLUTION:
{response_text}

Extract ONLY the final numeric answer from the solution. Return just the number, nothing else.
For example, if the solution calculates $18, return: 18
If the solution ends with 540 meters, return: 540
If the solution says 20 cups, return: 20

Return only the number, no units, no explanation."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6-20250909",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = message.content[0].text.strip()
        # Remove any remaining units or symbols
        answer = answer.replace('$', '').replace(',', '').strip()

        return answer
    except Exception as e:
        print(f"  Error extracting: {e}")
        return None

def process_pilot_file():
    """
    Process the pilot file using Claude for extraction.
    """
    pilot_file = 'results/benchmarks/gsm8k/pilot_responses.json'

    with open(pilot_file) as f:
        data = json.load(f)

    print("=" * 80)
    print("GSM8K-20 PILOT - CLAUDE-ASSISTED EXTRACTION")
    print("=" * 80)
    print()
    print("Processing 20 prompts × 2 models = 40 extractions...")
    print("This will cost approximately $0.20-0.30")
    print()
    input("Press Enter to continue or Ctrl+C to cancel...")
    print()

    correct_by_model = {}
    total_by_model = {}

    for i, item in enumerate(data, 1):
        prompt_id = item['prompt']['id']
        question = item['prompt']['text']
        ground_truth = item['prompt']['ground_truth']

        print(f"\n[{i}/20] {prompt_id} (expected: {ground_truth})")

        for model_key, resp in item['responses'].items():
            if model_key not in correct_by_model:
                correct_by_model[model_key] = 0
                total_by_model[model_key] = 0

            response_text = resp['answer']

            # Extract using Claude
            extracted = extract_answer_with_claude(response_text, question)

            # Normalize for comparison
            try:
                extracted_norm = str(int(float(extracted))) if extracted else None
                ground_truth_norm = str(int(float(ground_truth)))
            except (ValueError, TypeError):
                extracted_norm = extracted
                ground_truth_norm = ground_truth

            is_correct = (extracted_norm == ground_truth_norm)

            total_by_model[model_key] += 1
            if is_correct:
                correct_by_model[model_key] += 1

            status = "✓" if is_correct else "✗"
            print(f"  {model_key}: extracted {extracted} {status}")

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    for model_key in sorted(correct_by_model.keys()):
        correct = correct_by_model[model_key]
        total = total_by_model[model_key]
        accuracy = (correct / total * 100) if total > 0 else 0

        print(f"\n{model_key}:")
        print(f"  Correct: {correct}/{total}")
        print(f"  Accuracy: {accuracy:.1f}%")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    process_pilot_file()
