#!/usr/bin/env bash
# run_klocwork.sh
# ───────────────
# Convenience wrapper that runs all three Klocwork analysis steps:
#   1. Analyse changed C/C++ files with the LLM
#   2. Generate a Markdown report
#   3. Optionally apply fixes (unstaged)
#
# Usage:
#   bash scripts/run_klocwork.sh [OPTIONS]
#
# Options (all optional, override defaults via env or flags):
#   --base       BASE_REF         (default: origin/main)
#   --head       HEAD_REF         (default: HEAD)
#   --severity   1,2,3            (default: 1,2,3)
#   --model      MODEL_NAME       (default: gpt-4o)
#   --provider   github|openai|local  (default: github)
#   --apply      apply severity-1,2 fixes automatically (unstaged)
#   --dry-run    print fixes but don't write files
#   --interactive confirm each fix
#   --no-report  skip markdown report generation
#
# Required env:
#   GITHUB_TOKEN   (if --provider github, default)
#   OPENAI_API_KEY (if --provider openai)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Defaults ──────────────────────────────────
BASE="origin/main"
HEAD="HEAD"
SEVERITY="1,2,3"
MODEL="gpt-4o"
PROVIDER="github"
APPLY=false
DRY_RUN=false
INTERACTIVE=false
NO_REPORT=false
APPLY_SEVERITY="1,2"
OUTPUT_JSON="klocwork_report.json"
OUTPUT_MD="klocwork_report.md"
RULES="${ROOT_DIR}/rules/klocwork_rules.json"

# ── Parse args ────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --base)          BASE="$2";           shift 2 ;;
    --head)          HEAD="$2";           shift 2 ;;
    --severity)      SEVERITY="$2";       shift 2 ;;
    --model)         MODEL="$2";          shift 2 ;;
    --provider)      PROVIDER="$2";       shift 2 ;;
    --output-json)   OUTPUT_JSON="$2";    shift 2 ;;
    --output-md)     OUTPUT_MD="$2";      shift 2 ;;
    --apply)         APPLY=true;          shift ;;
    --dry-run)       DRY_RUN=true;        shift ;;
    --interactive)   INTERACTIVE=true;    shift ;;
    --no-report)     NO_REPORT=true;      shift ;;
    --apply-severity) APPLY_SEVERITY="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Banner ────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    SDLC Automation – Klocwork Analysis   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Base ref  : ${BASE}"
echo "  Head ref  : ${HEAD}"
echo "  Model     : ${MODEL} (${PROVIDER})"
echo "  Severities: ${SEVERITY}"
echo "  Rules     : ${RULES}"
echo ""

# ── Step 1: Analyse ───────────────────────────
echo "▶ Step 1/3 — Static analysis …"
python3 "${SCRIPT_DIR}/klocwork_analyzer.py" \
  --base       "${BASE}"        \
  --head       "${HEAD}"        \
  --rules      "${RULES}"       \
  --severity   "${SEVERITY}"    \
  --output     "${OUTPUT_JSON}" \
  --model      "${MODEL}"       \
  --provider   "${PROVIDER}"

echo ""

# ── Step 2: Report ────────────────────────────
if [ "${NO_REPORT}" = false ]; then
  echo "▶ Step 2/3 — Generating Markdown report …"
  python3 "${SCRIPT_DIR}/generate_report.py" \
    --report "${OUTPUT_JSON}" \
    --output "${OUTPUT_MD}"
  echo ""
fi

# ── Step 3: Apply fixes ───────────────────────
echo "▶ Step 3/3 — Fix applicator …"

if [ "${APPLY}" = false ] && [ "${DRY_RUN}" = false ]; then
  echo "  (skipped – pass --apply or --dry-run to enable)"
else
  APPLY_ARGS=(
    --report   "${OUTPUT_JSON}"
    --severity "${APPLY_SEVERITY}"
  )
  [ "${DRY_RUN}"    = true ] && APPLY_ARGS+=(--dry-run)
  [ "${INTERACTIVE}"= true ] && APPLY_ARGS+=(--interactive)

  python3 "${SCRIPT_DIR}/apply_fixes.py" "${APPLY_ARGS[@]}"
fi

echo ""
echo "✔  Analysis complete."
echo "   JSON report : ${OUTPUT_JSON}"
[ "${NO_REPORT}" = false ] && echo "   MD report   : ${OUTPUT_MD}"
echo ""
echo "   To review unstaged fixes:"
echo "     git diff"
echo "   To interactively stage:"
echo "     git add -p"
echo ""
