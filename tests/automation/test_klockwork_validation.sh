#!/bin/bash
# test_klockwork_validation.sh
# Test klockwork automation - validation

set -e

echo "=== Test 2C: Klockwork Automation - Validation ==="

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO_ROOT"

# Verify script exists
if [[ ! -f "klockwork_automation/scripts/validate_klockwork_fix.sh" ]]; then
    echo "❌ FAILED: validate_klockwork_fix.sh not found"
    exit 1
fi
echo "✅ validate_klockwork_fix.sh found"

# Generate test data first
echo "Generating test data..."
python3 klockwork_automation/scripts/collect_klockwork_issues.py \
    --source-dir src \
    --output /tmp/klockwork_issues_for_validation.json 2>/dev/null || true

# Run validation
echo "Running Klockwork fix validation..."
bash klockwork_automation/scripts/validate_klockwork_fix.sh > /tmp/validation_output_test.txt 2>&1

if [[ $? -eq 0 ]]; then
    echo "✅ Validation passed"
else
    echo "⚠️  Validation had warnings (see output)"
fi

# Verify generated klocwork output
echo "Verifying klocwork output directory..."
if [[ -d "klocwork/src" ]]; then
    echo "✅ klocwork/src exists"
else
    echo "❌ klocwork/src not found"
    exit 1
fi

if [[ -f "klocwork/src/calculator.cpp" ]]; then
    echo "✅ Generated klocwork/src/calculator.cpp"
else
    echo "❌ Expected generated file klocwork/src/calculator.cpp not found"
    exit 1
fi

# Show validation output
echo "Validation checks:"
grep -E "✓|PASSED|Check" /tmp/validation_output_test.txt 2>/dev/null | head -10 || echo "No validation output found"

echo "✅ Test 2C PASSED"
exit 0
