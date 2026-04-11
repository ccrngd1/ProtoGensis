#!/bin/bash
# Run All Experiments (E1-E17)
#
# This script runs all 9 experiment types across 3 runs each.
# Total expected cost: ~$200
# Total expected time: ~24 hours
#
# Usage:
#   bash run_all_experiments.sh                    # Run all
#   bash run_all_experiments.sh --experiments e1   # Run specific experiment
#   bash run_all_experiments.sh --runs 1           # Run single run only

set -e  # Exit on error

# Default settings
EXPERIMENTS="e1 e2 e6 e7 e8 e14 e15 e17"
RUNS="1 2 3"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --experiments)
            EXPERIMENTS="$2"
            shift 2
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "Running All Experiments"
echo "========================================"
echo "Experiments: $EXPERIMENTS"
echo "Runs: $RUNS"
echo ""

# Track total cost and time
TOTAL_COST=0
START_TIME=$(date +%s)

# E1: Strong-Judge Vote Ensemble (~$20, 3 runs)
if [[ $EXPERIMENTS == *"e1"* ]]; then
    echo ""
    echo "=========================================="
    echo "E1: Strong-Judge Vote Ensemble"
    echo "Expected: ~$20 for 3 runs"
    echo "=========================================="
    for run in $RUNS; do
        echo "Running E1 - Run $run..."
        python3 run_e1_strong_judge_vote.py --run $run
    done
fi

# E2: Best-of-N with Opus Verifier (~$25, 3 runs)
if [[ $EXPERIMENTS == *"e2"* ]]; then
    echo ""
    echo "=========================================="
    echo "E2: Best-of-N with Opus Verifier"
    echo "Expected: ~$25 for 3 runs"
    echo "=========================================="
    for run in $RUNS; do
        echo "Running E2 - Run $run..."
        python3 run_e2_best_of_n.py --run $run
    done
fi

# E6: MMLU-100 Full Ensemble (~$45, 3 runs)
if [[ $EXPERIMENTS == *"e6"* ]]; then
    echo ""
    echo "=========================================="
    echo "E6: MMLU-100 Full Ensemble Comparison"
    echo "Expected: ~$45 for 3 runs × 4 configs"
    echo "=========================================="
    for run in $RUNS; do
        for config in opus-fast opus-thinking vote self-consistency; do
            echo "Running E6 - MMLU - $config - Run $run..."
            python3 run_multi_benchmark.py --benchmark mmlu --config $config --run $run
        done
    done
fi

# E7: GPQA-50 Full Ensemble (~$30, 3 runs)
if [[ $EXPERIMENTS == *"e7"* ]]; then
    echo ""
    echo "=========================================="
    echo "E7: GPQA-50 Full Ensemble Comparison"
    echo "Expected: ~$30 for 3 runs × 4 configs"
    echo "=========================================="
    for run in $RUNS; do
        for config in opus-fast opus-thinking vote self-consistency; do
            echo "Running E7 - GPQA - $config - Run $run..."
            python3 run_multi_benchmark.py --benchmark gpqa --config $config --run $run
        done
    done
fi

# E8: HumanEval-50 Full Ensemble (~$30, 3 runs)
if [[ $EXPERIMENTS == *"e8"* ]]; then
    echo ""
    echo "=========================================="
    echo "E8: HumanEval-50 Full Ensemble Comparison"
    echo "Expected: ~$30 for 3 runs × 4 configs"
    echo "=========================================="
    for run in $RUNS; do
        for config in opus-fast opus-thinking vote self-consistency; do
            echo "Running E8 - HumanEval - $config - Run $run..."
            python3 run_multi_benchmark.py --benchmark humaneval --config $config --run $run
        done
    done
fi

# E14: Budget Baselines (~$2, 3 runs)
if [[ $EXPERIMENTS == *"e14"* ]]; then
    echo ""
    echo "=========================================="
    echo "E14: Budget Model Baselines"
    echo "Expected: ~$2 for 3 runs × 2 models"
    echo "=========================================="
    for run in $RUNS; do
        for model in haiku-fast sonnet-fast; do
            echo "Running E14 - $model - Run $run..."
            python3 run_theory_tests.py --experiment e14 --model $model --run $run
        done
    done
fi

# E15: Self-Consistency on Haiku (~$3, 3 runs)
if [[ $EXPERIMENTS == *"e15"* ]]; then
    echo ""
    echo "=========================================="
    echo "E15: Self-Consistency Low Baseline (Haiku)"
    echo "Expected: ~$3 for 3 runs"
    echo "=========================================="
    for run in $RUNS; do
        echo "Running E15 - Haiku SC - Run $run..."
        python3 run_theory_tests.py --experiment e15 --model haiku-fast --run $run
    done
fi

# E17: Self-Consistency on Sonnet (~$6, 3 runs)
if [[ $EXPERIMENTS == *"e17"* ]]; then
    echo ""
    echo "=========================================="
    echo "E17: Self-Consistency Mid Baseline (Sonnet)"
    echo "Expected: ~$6 for 3 runs"
    echo "=========================================="
    for run in $RUNS; do
        echo "Running E17 - Sonnet SC - Run $run..."
        python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run $run
    done
fi

# Calculate total time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))

echo ""
echo "========================================"
echo "ALL EXPERIMENTS COMPLETE!"
echo "========================================"
echo "Total time: ${HOURS}h ${MINUTES}m"
echo ""
echo "Results saved to: results/phase2/"
echo ""
echo "Next steps:"
echo "  1. Evaluate results with benchmarks/evaluate_*.py"
echo "  2. Analyze with benchmarks/statistical_analysis.py"
echo "  3. Update documentation with findings"
echo "========================================"
