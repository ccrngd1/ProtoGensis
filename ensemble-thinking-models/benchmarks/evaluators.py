#!/usr/bin/env python3
"""
Benchmark-Specific Evaluators

Handles answer extraction and evaluation for different benchmark types.
Each benchmark has unique answer formats that need specialized parsing.
"""

import re
from typing import Any, Dict, Optional


def extract_number_from_text(text: str) -> Optional[float]:
    """
    Extract a numeric answer from model response text.
    Handles various formats:
    - "The answer is 72"
    - "72 clips"
    - "Therefore, 72."
    - "$1,234.56"
    - "Answer: 72"
    """
    if not text:
        return None

    # Clean text
    text = text.strip()

    # Look for explicit answer markers
    patterns = [
        r'(?:answer|result|total|solution)(?:\s+is)?:?\s*(-?\d+(?:,\d+)*(?:\.\d+)?)',
        r'####\s*(-?\d+(?:,\d+)*(?:\.\d+)?)',  # GSM8K format
        r'=\s*(-?\d+(?:,\d+)*(?:\.\d+)?)\s*$',  # Ends with = number
        r'\$?\s*(-?\d+(?:,\d+)*(?:\.\d+)?)\s*(?:clips|dollars|items|units)?\.?\s*$',  # Final number with units
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(',', '')
            try:
                return float(num_str)
            except ValueError:
                continue

    # Fallback: try to find any number in the last sentence
    sentences = text.split('.')
    if sentences:
        last_sentence = sentences[-1] if sentences[-1].strip() else sentences[-2] if len(sentences) > 1 else ""
        numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', last_sentence)
        if numbers:
            try:
                return float(numbers[-1].replace(',', ''))
            except ValueError:
                pass

    # Last resort: find last number in entire text
    numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', text)
    if numbers:
        try:
            return float(numbers[-1].replace(',', ''))
        except ValueError:
            pass

    return None


def evaluate_gsm8k(model_answer: str, ground_truth: str) -> bool:
    """
    Evaluate GSM8K math problem.
    Extract final numeric answer and compare to ground truth.

    Args:
        model_answer: Full model response text
        ground_truth: Expected numeric answer (as string)

    Returns:
        True if answers match (within tolerance for floats)
    """
    model_num = extract_number_from_text(model_answer)
    if model_num is None:
        return False

    try:
        expected_num = float(ground_truth.replace(',', ''))
    except (ValueError, AttributeError):
        return False

    # For integer answers, exact match
    if expected_num == int(expected_num):
        return abs(model_num - expected_num) < 0.01

    # For float answers, allow small tolerance
    return abs(model_num - expected_num) < 0.01 * abs(expected_num)


def extract_multiple_choice(text: str, choices: list) -> Optional[str]:
    """
    Extract A/B/C/D answer from model response.
    Handles various formats:
    - "The answer is B"
    - "B) 4"
    - "I choose option C"
    - Just "B"
    """
    if not text:
        return None

    text = text.strip()

    # Look for explicit patterns
    patterns = [
        r'\b([A-Z])\)',  # A) format
        r'(?:answer|choice|option|select)\s+(?:is\s+)?([A-Z])\b',  # "answer is B"
        r'\b([A-Z])\.',  # A. format
        r'^([A-Z])$',  # Just the letter alone
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            letter = match.group(1).upper()
            if letter in [c.upper() for c in choices]:
                return letter

    # Fallback: look for any single letter that's in choices
    for letter in 'ABCDEF':
        if letter in choices and re.search(r'\b' + letter + r'\b', text.upper()):
            return letter

    return None


def evaluate_mmlu(model_answer: str, ground_truth: str, choices: list) -> bool:
    """
    Evaluate MMLU multiple choice question.
    Extract letter choice and compare to ground truth.

    Args:
        model_answer: Full model response text
        ground_truth: Expected answer letter (A/B/C/D)
        choices: List of choice letters available

    Returns:
        True if extracted choice matches ground truth
    """
    model_choice = extract_multiple_choice(model_answer, choices)
    if model_choice is None:
        return False

    return model_choice.upper() == ground_truth.upper()


def extract_python_code(text: str) -> Optional[str]:
    """
    Extract Python code from model response.
    Handles various formats:
    - ```python ... ```
    - ```... ```
    - Plain code
    """
    if not text:
        return None

    # Try to find code in markdown code blocks
    code_block_pattern = r'```(?:python)?\s*\n(.*?)```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    if matches:
        # Return the last code block (usually the complete function)
        return matches[-1].strip()

    # Fallback: assume entire text is code if it contains def
    if 'def ' in text:
        return text.strip()

    return None


def evaluate_humaneval(model_answer: str, ground_truth: Dict[str, Any]) -> bool:
    """
    Evaluate HumanEval code problem.
    Extract code, execute test cases.

    Args:
        model_answer: Full model response with code
        ground_truth: Dict with test_cases, canonical_solution, entry_point, prompt

    Returns:
        True if code passes test cases
    """
    import signal
    from contextlib import contextmanager

    @contextmanager
    def time_limit(seconds):
        """Context manager for timeout."""
        def signal_handler(signum, frame):
            raise TimeoutError("Execution timed out")
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)

    # Extract code from model response
    extracted_code = extract_python_code(model_answer)
    if not extracted_code:
        return False

    # Get test case and entry point
    test_code = ground_truth.get('test', '')
    entry_point = ground_truth.get('entry_point', '')

    if not test_code or not entry_point:
        return False

    # Build complete code to execute
    # Model's code + test cases
    full_code = f"{extracted_code}\n\n{test_code}\n\ncheck({entry_point})"

    try:
        # Execute with timeout (5 seconds)
        with time_limit(5):
            # Create restricted namespace
            namespace = {
                '__builtins__': {
                    'abs': abs, 'all': all, 'any': any, 'bool': bool,
                    'dict': dict, 'enumerate': enumerate, 'float': float,
                    'int': int, 'len': len, 'list': list, 'max': max,
                    'min': min, 'range': range, 'reversed': reversed,
                    'round': round, 'set': set, 'sorted': sorted,
                    'str': str, 'sum': sum, 'tuple': tuple, 'zip': zip,
                    'isinstance': isinstance, 'type': type, 'Exception': Exception,
                    'ValueError': ValueError, 'TypeError': TypeError,
                    'print': print,  # Allow print for debugging
                }
            }

            # Execute the code
            exec(full_code, namespace)

            # If we get here without exception, tests passed
            return True

    except TimeoutError:
        # Code took too long
        return False
    except Exception as e:
        # Test failed or code has errors
        return False


def evaluate_benchmark(prompt: Dict[str, Any], model_answer: str) -> bool:
    """
    Route to appropriate evaluator based on benchmark type.

    Args:
        prompt: Prompt dict with benchmark metadata
        model_answer: Model's response text

    Returns:
        True if answer is correct according to benchmark criteria
    """
    benchmark = prompt.get('benchmark', 'unknown')
    ground_truth = prompt.get('ground_truth')
    evaluation_criteria = prompt.get('evaluation_criteria', 'string_match')

    if benchmark == 'gsm8k' or evaluation_criteria == 'numeric_match':
        return evaluate_gsm8k(model_answer, ground_truth)

    elif benchmark == 'mmlu' or evaluation_criteria == 'multiple_choice':
        choices = prompt.get('choices', ['A', 'B', 'C', 'D'])
        return evaluate_mmlu(model_answer, ground_truth, choices)

    elif benchmark == 'humaneval' or evaluation_criteria == 'code_execution':
        return evaluate_humaneval(model_answer, ground_truth)

    else:
        # Fallback: simple string matching
        if isinstance(ground_truth, str):
            return ground_truth.lower() in model_answer.lower()
        return False


# Test functions
def test_gsm8k_evaluation():
    """Test GSM8K evaluation with sample cases"""
    test_cases = [
        ("The answer is 72", "72", True),
        ("Natalia sold 72 clips in total.", "72", True),
        ("72", "72", True),
        ("The total is 72.", "72", True),
        ("The answer is 71", "72", False),
        ("I don't know", "72", False),
        ("48 + 24 = 72", "72", True),
        ("Therefore, 1,234 is the answer", "1234", True),
    ]

    print("Testing GSM8K evaluation:")
    for answer, truth, expected in test_cases:
        result = evaluate_gsm8k(answer, truth)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{answer}' vs '{truth}' -> {result} (expected {expected})")


def test_mmlu_evaluation():
    """Test MMLU evaluation with sample cases"""
    test_cases = [
        ("The answer is B", "B", ['A', 'B', 'C', 'D'], True),
        ("B) 4", "B", ['A', 'B', 'C', 'D'], True),
        ("I choose option C", "C", ['A', 'B', 'C', 'D'], True),
        ("A is correct", "A", ['A', 'B', 'C', 'D'], True),
        ("The answer is B", "A", ['A', 'B', 'C', 'D'], False),
        ("I don't know", "B", ['A', 'B', 'C', 'D'], False),
    ]

    print("\nTesting MMLU evaluation:")
    for answer, truth, choices, expected in test_cases:
        result = evaluate_mmlu(answer, truth, choices)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{answer}' vs '{truth}' -> {result} (expected {expected})")


if __name__ == "__main__":
    print("="*70)
    print("Benchmark Evaluator Tests")
    print("="*70)
    print()
    test_gsm8k_evaluation()
    test_mmlu_evaluation()
    print()
    print("="*70)
