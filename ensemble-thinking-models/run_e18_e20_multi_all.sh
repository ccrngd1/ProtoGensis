#!/bin/bash
#
# Master Script: E18-E20 Multi-Benchmark Experiments
#
# Runs all correctness-based experiments across 4 benchmarks:
# - E18: Correctness-based vote (3 proposers + correctness judge)
# - E19: Correctness-based best-of-N (5 samples + correctness judge)
# - E20: Two-stage judging (agreement → correctness)
#
# Total experiments: 3 methods × 4 benchmarks × 3 runs = 36 experiments
#
# Estimated costs:
# - E18: ~$18/benchmark × 4 = ~$72
# - E19: ~$24/benchmark × 4 = ~$96
# - E20: ~$24/benchmark × 4 = ~$96
# TOTAL: ~$264
#
# Estimated time:
# - E18: ~3h/benchmark × 4 = ~12h
# - E19: ~3h/benchmark × 4 = ~12h
# - E20: ~4.5h/benchmark × 4 = ~18h
# TOTAL: ~42h (can run benchmarks in parallel)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for AWS token
if [ -z "$AWS_BEARER_TOKEN_BEDROCK" ]; then
    echo -e "${RED}ERROR: AWS_BEARER_TOKEN_BEDROCK not set${NC}"
    echo "Please export AWS_BEARER_TOKEN_BEDROCK before running this script"
    exit 1
fi

# Create results directory
mkdir -p results/phase3_multi

# Function to print section header
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Track start time
START_TIME=$(date +%s)

print_header "Multi-Benchmark Experiments: E18-E20"
echo "Running across 4 benchmarks: GSM8K, MMLU, HumanEval, GPQA"
echo "3 runs per experiment for statistical validity"
echo ""
echo -e "${YELLOW}WARNING: This will take ~42 hours and cost ~\$264${NC}"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ============================================================================
# E18: Correctness-Based Vote
# ============================================================================

print_header "E18: Correctness-Based Vote (4 benchmarks × 3 runs)"

for run in 1 2 3; do
    echo -e "${GREEN}Run $run/3${NC}"

    echo "  GSM8K..."
    python3 run_e18_multi_benchmark.py --benchmark gsm8k --run $run

    echo "  MMLU..."
    python3 run_e18_multi_benchmark.py --benchmark mmlu --run $run

    echo "  HumanEval..."
    python3 run_e18_multi_benchmark.py --benchmark humaneval --run $run

    echo "  GPQA..."
    python3 run_e18_multi_benchmark.py --benchmark gpqa --run $run

    echo ""
done

# ============================================================================
# E19: Correctness-Based Best-of-N
# ============================================================================

print_header "E19: Correctness-Based Best-of-N (4 benchmarks × 3 runs)"

for run in 1 2 3; do
    echo -e "${GREEN}Run $run/3${NC}"

    echo "  GSM8K..."
    python3 run_e19_multi_benchmark.py --benchmark gsm8k --run $run

    echo "  MMLU..."
    python3 run_e19_multi_benchmark.py --benchmark mmlu --run $run

    echo "  HumanEval..."
    python3 run_e19_multi_benchmark.py --benchmark humaneval --run $run

    echo "  GPQA..."
    python3 run_e19_multi_benchmark.py --benchmark gpqa --run $run

    echo ""
done

# ============================================================================
# E20: Two-Stage Judging
# ============================================================================

print_header "E20: Two-Stage Judging (4 benchmarks × 3 runs)"

for run in 1 2 3; do
    echo -e "${GREEN}Run $run/3${NC}"

    echo "  GSM8K..."
    python3 run_e20_multi_benchmark.py --benchmark gsm8k --run $run

    echo "  MMLU..."
    python3 run_e20_multi_benchmark.py --benchmark mmlu --run $run

    echo "  HumanEval..."
    python3 run_e20_multi_benchmark.py --benchmark humaneval --run $run

    echo "  GPQA..."
    python3 run_e20_multi_benchmark.py --benchmark gpqa --run $run

    echo ""
done

# ============================================================================
# Summary
# ============================================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))

print_header "All Experiments Complete!"

echo "Results saved to: results/phase3_multi/"
echo ""
echo "Files created:"
echo "  E18 (vote): e18_{gsm8k,mmlu,humaneval,gpqa}_run{1,2,3}.json (12 files)"
echo "  E19 (best-of-N): e19_{gsm8k,mmlu,humaneval,gpqa}_run{1,2,3}.json (12 files)"
echo "  E20 (two-stage): e20_{gsm8k,mmlu,humaneval,gpqa}_run{1,2,3}.json (12 files)"
echo ""
echo "Total experiments: 36"
echo "Elapsed time: ${HOURS}h ${MINUTES}m"
echo ""
echo -e "${GREEN}Next step: Run analysis script to compare results across benchmarks${NC}"
echo "  python3 analyze_multi_benchmark.py"
