# Klocwork Static Analysis Feature

AI-powered Klocwork-style static analysis on C/C++ git diffs.  
Uses an LLM (GitHub Models / OpenAI) to identify issues matching **official Klocwork 2026.1 checkers**, then suggests and optionally applies fixes — all left **unstaged** for your review.

---

## Directory layout

```
klocwork_feature/
├── rules/
│   └── klocwork_rules.json      ← 200+ checkers from official Klocwork 2026.1 docs
├── scripts/
│   ├── klocwork_analyzer.py     ← Runs LLM analysis on changed files
│   ├── apply_fixes.py           ← Applies suggested fixes (unstaged)
│   ├── generate_report.py       ← Generates Markdown report from JSON
│   └── run_klocwork.sh          ← One-shot wrapper for all three steps
└── README.md
```

Copy this folder into your repo next to the existing `unit_test_automation/` folder.

---

## Quick start

### 1 — Prerequisites

```bash
pip install requests          # only for non-stdlib HTTP (optional, uses urllib by default)
```

### 2 — Set your API token

**GitHub Models (default):**
```bash
export GITHUB_TOKEN=ghp_...   # needs models:read scope
```

**OpenAI:**
```bash
export OPENAI_API_KEY=sk-...
```

**Local Ollama (no key needed):**
```bash
# Start Ollama with a code model first:
# ollama pull codellama:13b
# No token needed
```

### 3 — Run

```bash
# Full run: analyse, report, preview fixes (dry-run)
bash klocwork_feature/scripts/run_klocwork.sh --dry-run

# Apply critical + error fixes automatically (left unstaged)
bash klocwork_feature/scripts/run_klocwork.sh --apply

# Interactive mode — confirm each fix
bash klocwork_feature/scripts/run_klocwork.sh --apply --interactive

# Custom refs
bash klocwork_feature/scripts/run_klocwork.sh \
    --base origin/main --head feature/my-branch \
    --apply

# Use a different model
bash klocwork_feature/scripts/run_klocwork.sh \
    --model gpt-4o-mini --apply

# Use OpenAI provider
bash klocwork_feature/scripts/run_klocwork.sh \
    --provider openai --model gpt-4o --apply

# Use local Ollama
bash klocwork_feature/scripts/run_klocwork.sh \
    --provider local --model codellama:13b --apply
```

### 4 — Review changes

Fixes are written directly to your source files but **NOT staged**:

```bash
git diff                  # see all changes
git diff src/calculator.cpp   # see changes in one file
git add -p                # interactively pick hunks to stage
git add src/calculator.cpp    # stage entire file
git restore src/calculator.cpp  # discard a fix you don't want
```

---

## Running steps individually

```bash
# Step 1: analyse only
python3 klocwork_feature/scripts/klocwork_analyzer.py \
    --base origin/main --head HEAD \
    --severity 1,2,3 \
    --output klocwork_report.json

# Step 2: generate report
python3 klocwork_feature/scripts/generate_report.py \
    --report klocwork_report.json \
    --output klocwork_report.md

# Step 3: apply fixes
python3 klocwork_feature/scripts/apply_fixes.py \
    --report klocwork_report.json \
    --severity 1,2 \
    --interactive
```

---

## Checker coverage

Rules are sourced directly from the **official Klocwork 2026.1 C/C++ checker reference**  
(`https://help.klocwork.com/current/en-us/concepts/candccheckerreference.htm`).

| Family      | Coverage                                         |
|-------------|--------------------------------------------------|
| `NPD`       | Null pointer dereference (14 variants)           |
| `ABV`       | Buffer overflows / array bounds (9 variants)     |
| `MLK/CL`    | Memory leaks incl. class destructors (11)        |
| `UFM/FMM/FNH/FUM` | Use/free of freed/mismatched/non-heap memory (16) |
| `UNINIT`    | Uninitialized variables, arrays, heap (9)        |
| `DBZ`       | Division by zero (6 variants)                    |
| `CONC`      | Concurrency: deadlock, missing lock/unlock (6)   |
| `RH`        | Resource handle leaks                            |
| `SV`        | Security: format strings, tainted input, injection, banned APIs (40+) |
| `HCC`       | Hardcoded credentials                            |
| `RCA`       | Risky/weak cryptographic algorithms              |
| `CWARN`     | C++ class warnings, destructor issues (20+)      |
| `ITER`      | Iterator misuse (6 variants)                     |
| `LOCRET`    | Returning address of local variable              |
| `FUNCRET/RETVOID` | Missing/wrong return values               |
| `INFINITE_LOOP` | Infinite loops                               |
| `CERT`      | CERT C/C++ standard mappings (10+)               |
| `NUM`       | Numeric overflow/wraparound                      |
| `SPECTRE`   | Spectre Variant 1                                |
| `UNREACH`   | Unreachable code                                 |
| Others      | RNPD, RABV, PRECISON, PORTING, ASSIGCOND, EFFECT, SEMICOL, … |

**Total: 200+ checkers** (vs the original ~7)

---

## Severity levels

| Level | Label    | Auto-applied by default |
|-------|----------|------------------------|
| 1     | Critical | ✅ Yes (`--apply`)      |
| 2     | Error    | ✅ Yes (`--apply`)      |
| 3     | Warning  | ❌ No (add `--apply-severity 1,2,3`) |
| 4     | Review   | ❌ No                   |

---

## Filtering checkers

Edit `rules/klocwork_rules.json` and set `"enabled": false` for any checker  
you want to suppress — the LLM prompt will not include disabled rules.

---

## Notes

- The LLM is prompted with `"response_format": {"type": "json_object"}` so output  
  is always parseable JSON (GPT-4o and newer only; disable for older models).
- For very large files, consider passing `--severity 1,2` only to keep prompts shorter.
- The `apply_fixes.py` does a string-replace of `code_snippet → fixed_code`;  
  for complex multi-line patches you may need to adjust manually.
