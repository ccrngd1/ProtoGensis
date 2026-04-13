#!/bin/bash
#
# Run E18-E20: Correctness-Based Judging Experiments
#
# Tests the hypothesis: "Is the judge doing the wrong task?"
#
# E18: Correctness-based vote (vs E1's agreement-based vote)
# E19: Correctness-based best-of-N (vs E2's quality-based best-of-N)
# E20: Two-stage (agreement grouping + correctness evaluation)
#
# Total: 9 runs (3 experiments × 3 runs each)
# Total cost: ~$60 (~$6-8 per run)
# Total time: ~10 hours
#

set -e  # Exit on error

# Check for AWS token
if [ -z "$AWS_BEARER_TOKEN_BEDROCK" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    echo "Please export it before running this script"
    exit 1
fi

echo "========================================"
echo "E18-E20: Correctness-Based Judging"
echo "========================================"
echo ""
echo "Total experiments: 9 runs (3 × 3)"
echo "Estimated cost: ~\$60"
echo "Estimated time: ~10 hours"
echo ""
echo "Press Ctrl+C to cancel, or wait 5 seconds to start..."
sleep 5

START_TIME=$(date +%s)

# E18: Correctness-Based Vote
echo ""
echo "========================================"
echo "E18: Correctness-Based Vote (3 runs)"
echo "========================================"
for run in 1 2 3; do
    echo ""
    echo "Starting E18 run $run..."
    python3 run_e18_correctness_vote.py --run $run
    echo "✓ E18 run $run complete"
done

# E19: Correctness-Based Best-of-N
echo ""
echo "========================================"
echo "E19: Correctness-Based Best-of-N (3 runs)"
echo "========================================"
for run in 1 2 3; do
    echo ""
    echo "Starting E19 run $run..."
    python3 run_e19_correctness_best_of_n.py --run $run
    echo "✓ E19 run $run complete"
done

# E20: Two-Stage Judging
echo ""
echo "========================================"
echo "E20: Two-Stage Judging (3 runs)"
echo "========================================"
for run in 1 2 3; do
    echo ""
    echo "Starting E20 run $run..."
    python3 run_e20_two_stage.py --run $run
    echo "✓ E20 run $run complete"
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))

echo ""
echo "========================================"
echo "ALL E18-E20 EXPERIMENTS COMPLETE! ✅"
echo "========================================"
echo ""
echo "Total time: ${HOURS}h ${MINUTES}m"
echo ""
echo "Results saved to results/phase2/:"
echo "  - e18_correctness_vote_run{1,2,3}.json"
echo "  - e19_correctness_best_of_n_run{1,2,3}.json"
echo "  - e20_two_stage_run{1,2,3}.json"
echo ""
echo "Next step: Run analysis script to compare against E1-E2"
echo ""
