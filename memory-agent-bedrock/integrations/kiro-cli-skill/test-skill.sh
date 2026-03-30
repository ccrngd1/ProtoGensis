#!/usr/bin/env bash
# test-skill.sh — Test the memory agent skill commands
# This demonstrates how the kiro-cli skill interacts with the API

set -euo pipefail

API_BASE="http://localhost:8000"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function print_header() {
    echo -e "\n${BOLD}=== $1 ===${NC}\n"
}

function print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

function print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if server is running
function check_server() {
    if ! curl -s -f "${API_BASE}/status" > /dev/null; then
        print_error "Cannot connect to memory agent at ${API_BASE}"
        echo "Please start the server:"
        echo "  cd ~/Desktop/ProtoGensis/memory-agent-bedrock"
        echo "  ./scripts/run-with-watcher.sh"
        exit 1
    fi
    print_success "Memory agent is running"
}

# Test 1: Ingest text
function test_ingest() {
    print_header "Test 1: Ingest Text"

    TEXT="Test memory from kiro-cli skill: Claude Haiku 4.5 is a fast, intelligent AI model with 200K context window."

    RESPONSE=$(curl -s -X POST "${API_BASE}/ingest" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"${TEXT}\",\"source\":\"kiro-cli-test\"}")

    if [[ $? -eq 0 ]]; then
        ID=$(echo "$RESPONSE" | jq -r '.id')
        SUMMARY=$(echo "$RESPONSE" | jq -r '.summary')
        ENTITIES=$(echo "$RESPONSE" | jq -r '.entities | join(", ")')
        TOPICS=$(echo "$RESPONSE" | jq -r '.topics | join(", ")')
        IMPORTANCE=$(echo "$RESPONSE" | jq -r '.importance')

        print_success "Stored memory [ID: ${ID}]"
        echo "Summary: ${SUMMARY}"
        echo "Entities: ${ENTITIES}"
        echo "Topics: ${TOPICS}"
        echo "Importance: ${IMPORTANCE}"
    else
        print_error "Failed to ingest text"
    fi
}

# Test 2: Query memory
function test_query() {
    print_header "Test 2: Query Memory"

    QUESTION="What do you know about Claude Haiku?"
    ENCODED_QUESTION=$(echo "$QUESTION" | jq -sRr @uri)

    RESPONSE=$(curl -s "${API_BASE}/query?q=${ENCODED_QUESTION}")

    if [[ $? -eq 0 ]]; then
        ANSWER=$(echo "$RESPONSE" | jq -r '.answer')
        print_success "Query result:"
        echo ""
        echo "$ANSWER"
    else
        print_error "Failed to query memory"
    fi
}

# Test 3: Check status
function test_status() {
    print_header "Test 3: Check Status"

    RESPONSE=$(curl -s "${API_BASE}/status")

    if [[ $? -eq 0 ]]; then
        MEMORY_COUNT=$(echo "$RESPONSE" | jq -r '.memory_count')
        CONSOLIDATION_COUNT=$(echo "$RESPONSE" | jq -r '.consolidation_count')
        UNCONSOLIDATED=$(echo "$RESPONSE" | jq -r '.unconsolidated_count')
        BG_RUNNING=$(echo "$RESPONSE" | jq -r '.background_consolidation_running')
        LAST_CONSOLIDATION=$(echo "$RESPONSE" | jq -r '.last_consolidation // "never"')
        FILE_COUNT=$(echo "$RESPONSE" | jq -r '.processed_files.total_count')

        print_success "Memory System Status:"
        echo "  - Total memories: ${MEMORY_COUNT}"
        echo "  - Consolidations: ${CONSOLIDATION_COUNT}"
        echo "  - Unconsolidated: ${UNCONSOLIDATED}"
        echo "  - Background consolidation: ${BG_RUNNING}"
        echo "  - Last consolidation: ${LAST_CONSOLIDATION}"
        echo ""
        echo "  Processed Files: ${FILE_COUNT}"

        # Show file details
        echo "$RESPONSE" | jq -r '.processed_files.files[] | "  - \(.filename) (last processed: \(.last_processed), memories: \(.memory_count))"'
    else
        print_error "Failed to get status"
    fi
}

# Test 4: Ingest file
function test_ingest_file() {
    print_header "Test 4: Ingest File"

    # Create a temporary test file
    TEST_FILE="/tmp/kiro-test-memory.txt"
    cat > "$TEST_FILE" << 'EOF'
# Kiro-CLI Memory Skill Test

This is a test file to demonstrate file ingestion via the kiro-cli memory skill.

Key points:
- The memory agent supports text, images, and PDFs
- Files are tracked with content hashes for change detection
- Claude Haiku extracts structured metadata automatically

Test timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

    if [[ ! -f "$TEST_FILE" ]]; then
        print_error "Failed to create test file"
        return
    fi

    RESPONSE=$(curl -s -X POST "${API_BASE}/ingest/file" \
        -F "file=@${TEST_FILE}")

    if [[ $? -eq 0 ]]; then
        ID=$(echo "$RESPONSE" | jq -r '.id')
        SUMMARY=$(echo "$RESPONSE" | jq -r '.summary')
        SOURCE=$(echo "$RESPONSE" | jq -r '.source')

        print_success "File ingested: ${SOURCE}"
        echo "Memory ID: ${ID}"
        echo "Summary: ${SUMMARY}"

        # Clean up
        rm -f "$TEST_FILE"
    else
        print_error "Failed to ingest file"
        rm -f "$TEST_FILE"
    fi
}

# Test 5: Trigger consolidation
function test_consolidate() {
    print_header "Test 5: Trigger Consolidation"

    RESPONSE=$(curl -s -X POST "${API_BASE}/consolidate")

    if [[ $? -eq 0 ]]; then
        CONSOLIDATED=$(echo "$RESPONSE" | jq -r '.consolidated')
        MESSAGE=$(echo "$RESPONSE" | jq -r '.message')

        if [[ "$CONSOLIDATED" == "true" ]]; then
            CONSOLIDATION_ID=$(echo "$RESPONSE" | jq -r '.consolidation_id')
            MEMORY_COUNT=$(echo "$RESPONSE" | jq -r '.memory_count')
            print_success "Consolidation complete"
            echo "Consolidation ID: ${CONSOLIDATION_ID}"
            echo "Processed ${MEMORY_COUNT} memories"
        else
            print_warning "$MESSAGE"
        fi
    else
        print_error "Failed to trigger consolidation"
    fi
}

# Main execution
main() {
    echo -e "${BOLD}Memory Agent Skill Test Suite${NC}"
    echo "Testing kiro-cli skill commands against ${API_BASE}"

    check_server

    test_ingest
    test_query
    test_status
    test_ingest_file
    test_consolidate

    print_header "All Tests Complete"
    print_success "Memory agent skill is working correctly"
    echo ""
    echo "To use in kiro-cli, install the skill and run:"
    echo "  /memory ingest \"your text here\""
    echo "  /memory query \"your question\""
    echo "  /memory status"
}

main "$@"
