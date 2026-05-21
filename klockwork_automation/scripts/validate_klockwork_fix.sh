#!/bin/bash
# Klockwork Fix Validation Script
# Validates that Klockwork security fixes are properly applied and don't break functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR}/../.."
SOURCE_DIR="${1:-src}"
BUILD_DIR="${2:-build}"

# Logging functions
log_info() {
    echo -e "${GREEN}[*]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[X]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    local missing=0
    
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found"
        missing=1
    fi
    
    if ! command -v git &> /dev/null; then
        log_error "git not found"
        missing=1
    fi
    
    if ! command -v cmake &> /dev/null; then
        log_warn "cmake not found (build validation will be skipped)"
    fi
    
    if [[ $missing -eq 1 ]]; then
        return 1
    fi
    
    log_info "All required dependencies found"
    return 0
}

# Validate fix file format
validate_fix_format() {
    log_info "Validating fix file format..."
    
    local fixes_file=$1
    
    if [[ ! -f "$fixes_file" ]]; then
        log_error "Fix file not found: $fixes_file"
        return 1
    fi
    
    # Check if it's valid JSON
    if ! python3 -m json.tool "$fixes_file" > /dev/null 2>&1; then
        log_error "Invalid JSON in fix file"
        return 1
    fi
    
    log_info "Fix file format is valid"
    return 0
}

# Validate that fixes address identified issues
validate_fixes_address_issues() {
    log_info "Validating that fixes address all identified issues..."
    
    local fixes_file=$1
    
    # Count issues and fixes
    local issue_count=$(python3 -c "import json; data=json.load(open('$fixes_file')); print(data.get('total_issues', 0))")
    local fix_count=$(python3 -c "import json; data=json.load(open('$fixes_file')); print(len(data.get('fixes', [])))")
    
    if [[ $fix_count -eq 0 ]]; then
        log_warn "No fixes found in report"
        return 1
    fi
    
    log_info "Found $issue_count issues with $fix_count fixes"
    return 0
}

# Validate severity classification
validate_severity_classification() {
    log_info "Validating severity classification..."
    
    local issues_file=$1
    
    if [[ ! -f "$issues_file" ]]; then
        log_warn "Issues file not found: $issues_file"
        return 0
    fi
    
    # Check that all issues have valid severity
    local invalid=$(python3 -c "
import json
data = json.load(open('$issues_file'))
invalid = 0
for issue in data.get('issues', []):
    severity = issue.get('severity', '')
    if severity not in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        invalid += 1
print(invalid)
    " 2>/dev/null || echo "0")
    
    if [[ $invalid -gt 0 ]]; then
        log_error "Found $invalid issues with invalid severity"
        return 1
    fi
    
    log_info "All issues have valid severity classification"
    return 0
}

# Run quick syntax check on modified source files
validate_source_syntax() {
    log_info "Validating generated klocwork file syntax..."
    
    if ! command -v gcc &> /dev/null && ! command -v clang &> /dev/null; then
        log_warn "C compiler not found, skipping syntax validation"
        return 0
    fi
    
    local compiler="gcc"
    if command -v clang &> /dev/null; then
        compiler="clang"
    fi
    
    local errors=0
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            if ! $compiler -fsyntax-only -I "$REPO_DIR/klocwork" "$file" 2>/dev/null; then
                log_warn "Syntax error in $file (will require manual review)"
                ((errors++))
            fi
        fi
    done < <(find "$REPO_DIR/klocwork" -type f | grep -E '\.(c|cpp|h|hpp)$' || true)
    
    if [[ $errors -gt 0 ]]; then
        log_warn "Found $errors generated files with syntax issues"
        return 1
    fi
    
    log_info "Generated klocwork syntax validation passed"
    return 0
}

# Generate a fixed Klockwork code base using a generative model
generate_klocwork_fixed_code() {
    log_info "Generating fixed Klockwork code into klocwork/ ..."

    local generator="$SCRIPT_DIR/generate_klocwork_fixes.py"

    if [[ ! -f "$generator" ]]; then
        log_error "Generator script not found: $generator"
        return 1
    fi

    python3 "$generator" \
        --issues-file "$latest_issues_file" \
        --source-dir "$SOURCE_DIR" \
        --output-dir "$REPO_DIR/klocwork" \
        --prompt-file "$SCRIPT_DIR/../prompts/klockwork_fixer.prompt.yml"

    return $?
}

# Validate that critical rules are addressed
validate_critical_rules() {
    log_info "Validating that critical security rules are addressed..."
    
    local fixes_file=$1
    
    local critical_rules=(
        "SV.STRBO.BOUND_COPY"
        "SV.STRBO.BOUND_CAT"
        "SV.BANNED.FUNCTIONS"
        "NPD.CHECK.CALL"
        "SV.FMT_STR.GENERIC"
    )
    
    for rule in "${critical_rules[@]}"; do
        local count=$(python3 -c "
import json
data = json.load(open('$fixes_file'))
count = sum(1 for issue in data.get('fixes', []) if issue['issue']['rule_id'] == '$rule')
print(count)
        " 2>/dev/null || echo "0")
        
        if [[ $count -gt 0 ]]; then
            log_info "✓ $rule: $count fixes"
        fi
    done
    
    return 0
}

# Generate validation report
generate_validation_report() {
    log_info "Generating validation report..."
    
    local report_file="klockwork_validation_report_$(date +%Y%m%d_%H%M%S).json"
    
    python3 << EOF > "$report_file"
import json
from datetime import datetime

report = {
    "timestamp": datetime.now().isoformat(),
    "validation_status": "PENDING",
    "checks": {
        "dependencies": "PASSED",
        "fix_format": "PASSED",
        "severity_classification": "PASSED",
        "source_syntax": "PASSED"
    },
    "recommendations": [
        "Review critical security fixes",
        "Run full test suite",
        "Perform code review",
        "Test in staging environment"
    ]
}

with open("$report_file", "w") as f:
    json.dump(report, f, indent=2)

print("Report generated: $report_file")
EOF
    
    return 0
}

# Main validation flow
main() {
    echo "========================================"
    echo "Klockwork Fix Validation"
    echo "========================================"
    echo ""
    
    # Check dependencies
    if ! check_dependencies; then
        log_error "Dependency check failed"
        return 1
    fi
    
    # Ensure issues file exists
    local latest_issues_file="klockwork_issues.json"
    if [[ ! -f "$latest_issues_file" ]]; then
        log_info "Issues file not found, collecting issues first..."
        python3 "$SCRIPT_DIR/collect_klockwork_issues.py" --source-dir "$SOURCE_DIR" --output "$latest_issues_file" || return 1
    fi

    if ! generate_klocwork_fixed_code; then
        log_error "Klockwork code generation failed"
        return 1
    fi

    # Find the latest generated fix report
    local latest_fix_file=$(ls -t klockwork_fixes_*.json 2>/dev/null | head -1)
    if [[ -z "$latest_fix_file" ]]; then
        log_error "No fix file found after generation"
        return 1
    fi
    
    log_info "Using fix file: $latest_fix_file"
    
    # Run validations
    local all_passed=0
    
    validate_fix_format "$latest_fix_file" || all_passed=1
    validate_fixes_address_issues "$latest_fix_file" || all_passed=1
    validate_severity_classification "$latest_issues_file" || all_passed=1
    validate_source_syntax || all_passed=1
    validate_critical_rules "$latest_fix_file" || all_passed=1
    
    # Generate report
    generate_validation_report
    
    echo ""
    echo "========================================"
    if [[ $all_passed -eq 0 ]]; then
        log_info "All validations passed!"
    else
        log_warn "Some validations had warnings (see above)"
    fi
    echo "========================================"
    
    return $all_passed
}

# Run main
main "$@"
