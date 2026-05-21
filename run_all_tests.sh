#!/bin/bash
# run_all_tests.sh
# Master test runner for complete SDLC Automation test suite

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Configuration
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TEST_DIR="$REPO_ROOT/tests/automation"
LOG_DIR="/tmp/sdlc_automation_test_$(date +%s)"

mkdir -p "$LOG_DIR"

# Logging functions
log_test_start() {
    echo ""
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

log_skip() {
    echo -e "${YELLOW}[⊘]${NC} $1"
}

log_info() {
    echo -e "${BLUE}[*]${NC} $1"
}

# Run a single test
run_test() {
    local test_name=$1
    local test_script=$2
    
    ((TOTAL_TESTS++))
    log_test_start "$test_name"
    
    if [[ ! -f "$test_script" ]]; then
        log_skip "Script not found: $test_script"
        ((SKIPPED_TESTS++))
        return 0
    fi
    
    # Make script executable
    chmod +x "$test_script"
    
    # Run test and capture output
    local log_file="$LOG_DIR/$(basename $test_script).log"
    
    if bash "$test_script" > "$log_file" 2>&1; then
        log_pass "$test_name"
        ((PASSED_TESTS++))
        return 0
    else
        log_fail "$test_name"
        ((FAILED_TESTS++))
        echo "  See log: $log_file"
        return 1
    fi
}

# Main test suite
main() {
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║    SDLC Automation Complete Test Suite                  ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║ Test logs directory: $LOG_DIR"
    echo "╚══════════════════════════════════════════════════════════╝"
    
    cd "$REPO_ROOT"
    
    # Section 1: Build and Environment
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ Section 1: Build & Environment                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    
    run_test "Build and Validation" "$TEST_DIR/test_build_validation.sh"
    
    # Section 2: Unit Test Automation
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ Section 2: Unit Test Automation                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    
    run_test "Unit Test Collection Phase" "$TEST_DIR/test_unit_test_collection.sh"
    
    # Section 3: Klockwork Automation
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ Section 3: Klockwork Automation                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    
    run_test "Klockwork Automation" "$TEST_DIR/test_klockwork_validation.sh"
    
    # Section 4: Integration
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ Section 4: Integration Testing                        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    
    run_test "Integration Test" "$TEST_DIR/test_integration.sh"
    
    # Summary
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                    Test Summary                         ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    
    local pass_rate=0
    if [[ $TOTAL_TESTS -gt 0 ]]; then
        pass_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    fi
    
    echo -e "║ Total Tests:    $TOTAL_TESTS"
    echo -e "║ ${GREEN}Passed:        $PASSED_TESTS ✅${NC}"
    if [[ $FAILED_TESTS -gt 0 ]]; then
        echo -e "║ ${RED}Failed:        $FAILED_TESTS ❌${NC}"
    else
        echo -e "║ Failed:        $FAILED_TESTS"
    fi
    if [[ $SKIPPED_TESTS -gt 0 ]]; then
        echo -e "║ ${YELLOW}Skipped:       $SKIPPED_TESTS ⊘${NC}"
    else
        echo -e "║ Skipped:       $SKIPPED_TESTS"
    fi
    
    echo "║"
    echo -e "║ Pass Rate: ${GREEN}${pass_rate}%${NC}"
    echo "╚══════════════════════════════════════════════════════════╝"
    
    echo ""
    echo "Log files saved to: $LOG_DIR"
    
    # Return appropriate exit code
    if [[ $FAILED_TESTS -gt 0 ]]; then
        echo -e "${RED}Some tests failed. Please check logs.${NC}"
        return 1
    else
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    fi
}

# Show usage
show_usage() {
    cat << EOF
SDLC Automation Test Runner

Usage: $0 [OPTIONS]

Options:
    --help          Show this help message
    --verbose       Show full test output (don't capture to files)
    --keep-logs     Keep log files after completion
    --quick         Run only essential tests

Examples:
    $0                      # Run all tests
    $0 --quick              # Run quick test subset
    $0 --verbose            # Show all output in console
    $0 --keep-logs          # Save logs for inspection

EOF
}

# Parse arguments
VERBOSE=false
KEEP_LOGS=false
QUICK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            show_usage
            exit 0
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --keep-logs)
            KEEP_LOGS=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Run main test suite
if main; then
    if [[ "$KEEP_LOGS" == false ]]; then
        # Optionally clean up logs
        echo ""
        echo "To keep logs for inspection, run with --keep-logs"
        # rm -rf "$LOG_DIR"  # Uncomment to auto-clean
    fi
    exit 0
else
    echo ""
    echo "Test suite failed. Logs saved to: $LOG_DIR"
    exit 1
fi
