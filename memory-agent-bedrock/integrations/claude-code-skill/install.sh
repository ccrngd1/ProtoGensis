#!/usr/bin/env bash
# install.sh — Install the memory agent skill for Claude Code

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function print_header() {
    echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}\n"
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

function print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Detect Claude Code skills directory
function find_skills_dir() {
    local POSSIBLE_DIRS=(
        "$HOME/.config/claude-code/skills"
        "$HOME/.claude-code/skills"
        "$HOME/Library/Application Support/Claude Code/skills"
        "$HOME/.config/Claude Code/skills"
    )

    for dir in "${POSSIBLE_DIRS[@]}"; do
        if [[ -d "$dir" ]]; then
            echo "$dir"
            return 0
        fi
    done

    # Try to find via 'claude' command config
    if command -v claude &> /dev/null; then
        local CONFIG_DIR=$(claude config --show 2>/dev/null | grep -i "skills" | awk '{print $2}' || echo "")
        if [[ -d "$CONFIG_DIR" ]]; then
            echo "$CONFIG_DIR"
            return 0
        fi
    fi

    return 1
}

# Check prerequisites
function check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if memory agent is accessible
    if curl -s -f http://localhost:8000/status > /dev/null 2>&1; then
        print_success "Memory agent is running at localhost:8000"
    else
        print_warning "Memory agent is NOT running at localhost:8000"
        echo ""
        echo "To start the memory agent, run:"
        echo "  cd ~/Desktop/ProtoGensis/memory-agent-bedrock"
        echo "  ./scripts/run-with-watcher.sh"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Check for jq
    if command -v jq &> /dev/null; then
        print_success "jq is installed"
    else
        print_warning "jq is not installed (recommended for JSON parsing)"
        echo "Install with: sudo apt-get install jq  (Ubuntu/Debian)"
        echo "         or: brew install jq            (macOS)"
    fi

    # Check for curl
    if command -v curl &> /dev/null; then
        print_success "curl is installed"
    else
        print_error "curl is required but not installed"
        exit 1
    fi
}

# Install the skill
function install_skill() {
    print_header "Installing Memory Agent Skill"

    # Find skills directory
    local SKILLS_DIR=""
    if SKILLS_DIR=$(find_skills_dir); then
        print_success "Found Claude Code skills directory: $SKILLS_DIR"
    else
        print_error "Could not find Claude Code skills directory"
        echo ""
        echo "Please provide the path to your Claude Code skills directory:"
        read -p "Skills directory: " SKILLS_DIR

        if [[ ! -d "$SKILLS_DIR" ]]; then
            print_error "Directory does not exist: $SKILLS_DIR"
            read -p "Create it? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                mkdir -p "$SKILLS_DIR"
                print_success "Created directory: $SKILLS_DIR"
            else
                exit 1
            fi
        fi
    fi

    # Copy skill file
    local SKILL_FILE="memory.md"
    local SOURCE_PATH="$(dirname "$0")/$SKILL_FILE"
    local DEST_PATH="$SKILLS_DIR/$SKILL_FILE"

    if [[ ! -f "$SOURCE_PATH" ]]; then
        print_error "Skill file not found: $SOURCE_PATH"
        exit 1
    fi

    if [[ -f "$DEST_PATH" ]]; then
        print_warning "Skill file already exists: $DEST_PATH"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            exit 0
        fi
    fi

    cp "$SOURCE_PATH" "$DEST_PATH"
    print_success "Installed skill to: $DEST_PATH"
}

# Test the installation
function test_installation() {
    print_header "Testing Installation"

    # Test API connectivity
    if curl -s -f http://localhost:8000/status > /dev/null 2>&1; then
        print_success "Memory agent API is accessible"

        # Show current status
        echo ""
        print_info "Current memory system status:"
        echo ""

        if command -v jq &> /dev/null; then
            curl -s http://localhost:8000/status | jq -r '
                "  Memories: \(.memory_count)",
                "  Consolidations: \(.consolidation_count)",
                "  Unconsolidated: \(.unconsolidated_count)",
                "  Background consolidation: \(.background_consolidation_running)",
                "  Processed files: \(.processed_files.total_count)"
            '
        else
            curl -s http://localhost:8000/status
        fi
    else
        print_warning "Memory agent is not accessible"
        echo "Start it with:"
        echo "  cd ~/Desktop/ProtoGensis/memory-agent-bedrock"
        echo "  ./scripts/run-with-watcher.sh"
    fi
}

# Print usage instructions
function print_usage_instructions() {
    print_header "Installation Complete!"

    cat << 'EOF'
The memory agent skill is now installed in Claude Code.

🎯 How to Use:

  The skill activates automatically when you:
  - Ask Claude to remember something
  - Ask what Claude knows about a topic
  - Upload a file to be remembered
  - Check memory system status

  You can also be explicit:
  - "Remember that the Q3 budget is $2.4M"
  - "What do you know about the Q3 budget?"
  - "Show me memory system status"

📚 Documentation:

  See README.md in this directory for:
  - Detailed usage examples
  - Best practices
  - Troubleshooting guide
  - Configuration options

🔧 Next Steps:

  1. Ensure memory agent is running:
     cd ~/Desktop/ProtoGensis/memory-agent-bedrock
     ./scripts/run-with-watcher.sh

  2. Open Claude Code and start using memory:
     "Remember that I'm working on the DataPipeline project"

  3. Check it worked:
     "What projects am I working on?"

⚙️  Configuration:

  Modify memory agent behavior in:
  ~/Desktop/ProtoGensis/memory-agent-bedrock/.env

🐛 Troubleshooting:

  If the skill doesn't work:
  - Check memory agent is running: curl http://localhost:8000/status
  - Verify skill file location
  - Restart Claude Code
  - Check Claude Code logs for errors

EOF
}

# Main installation flow
main() {
    echo -e "${BOLD}${BLUE}"
    cat << 'EOF'
╔════════════════════════════════════════╗
║  Memory Agent Skill Installer          ║
║  for Claude Code                       ║
╚════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    check_prerequisites
    install_skill
    test_installation
    print_usage_instructions

    echo ""
    print_success "Installation complete!"
    echo ""
}

# Run main function
main "$@"
