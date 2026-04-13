#!/bin/bash
# Run remaining experiments (E6-E17 only, E1-E2 already complete)

# AWS_BEARER_TOKEN_BEDROCK should be set in your environment before running this script
# Example: export AWS_BEARER_TOKEN_BEDROCK="your-token-here"
if [ -z "$AWS_BEARER_TOKEN_BEDROCK" ]; then
    echo "Error: AWS_BEARER_TOKEN_BEDROCK environment variable is not set"
    exit 1
fi

echo "=========================================="
echo "E6: MMLU-100 Full Ensemble"
echo "=========================================="
for run in 1 2 3; do
  for config in opus-fast opus-thinking vote self-consistency; do
    echo "Running E6 - MMLU - $config - Run $run..."
    python3 run_multi_benchmark.py --benchmark mmlu --config $config --run $run
  done
done

echo ""
echo "=========================================="
echo "E7: GPQA-50 Full Ensemble"
echo "=========================================="
for run in 1 2 3; do
  for config in opus-fast opus-thinking vote self-consistency; do
    echo "Running E7 - GPQA - $config - Run $run..."
    python3 run_multi_benchmark.py --benchmark gpqa --config $config --run $run
  done
done

echo ""
echo "=========================================="
echo "E8: HumanEval-50 Full Ensemble"
echo "=========================================="
for run in 1 2 3; do
  for config in opus-fast opus-thinking vote self-consistency; do
    echo "Running E8 - HumanEval - $config - Run $run..."
    python3 run_multi_benchmark.py --benchmark humaneval --config $config --run $run
  done
done

echo ""
echo "=========================================="
echo "E14: Budget Baselines"
echo "=========================================="
for run in 1 2 3; do
  for model in haiku-fast sonnet-fast; do
    echo "Running E14 - $model - Run $run..."
    python3 run_theory_tests.py --experiment e14 --model $model --run $run
  done
done

echo ""
echo "=========================================="
echo "E15: SC on Haiku"
echo "=========================================="
for run in 1 2 3; do
  echo "Running E15 - Haiku SC - Run $run..."
  python3 run_theory_tests.py --experiment e15 --model haiku-fast --run $run
done

echo ""
echo "=========================================="
echo "E17: SC on Sonnet"
echo "=========================================="
for run in 1 2 3; do
  echo "Running E17 - Sonnet SC - Run $run..."
  python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run $run
done

echo ""
echo "=========================================="
echo "ALL REMAINING EXPERIMENTS COMPLETE!"
echo "=========================================="
