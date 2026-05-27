#!/usr/bin/env python3
"""
klocwork_analyzer.py
--------------------
Reads the git diff of changed C/C++ files, sends each changed file's
full source + the diff context to GitHub Models, and gets back a
JSON list of Klocwork-style issues with suggested fixes.

Usage:
    python3 scripts/klocwork_analyzer.py \
        --base origin/main --head HEAD \
        [--rules rules/klocwork_rules.json] \
        [--severity 1,2,3]      # comma-separated max severities to include
        [--output klocwork_report.json]
        [--model gpt-4o]

Requirements:
    pip install requests
    Environment variable: GITHUB_TOKEN  (with models:read permission)
    OR set: OPENAI_API_KEY / ANTHROPIC_API_KEY depending on --provider
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
DEFAULT_RULES_PATH = Path(__file__).parent.parent / "rules" / "klocwork_rules.json"
DEFAULT_OUTPUT     = "klocwork_report.json"
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
SUPPORTED_EXTENSIONS   = {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def run(cmd: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[WARN] Command failed: {' '.join(cmd)}\n{result.stderr}", file=sys.stderr)
    return result.stdout.strip()


def get_changed_files(base: str, head: str) -> list[str]:
    """Return list of changed C/C++ file paths relative to repo root."""
    output = run(["git", "diff", "--name-only", base, head])
    files = [f for f in output.splitlines() if Path(f).suffix in SUPPORTED_EXTENSIONS]
    return files


def get_file_diff(path: str, base: str, head: str) -> str:
    """Get the unified diff for a single file."""
    return run(["git", "diff", base, head, "--", path])


def read_file_content(path: str) -> str:
    """Read current file content (HEAD version)."""
    content = run(["git", "show", f"HEAD:{path}"])
    if not content:
        # fall back to reading from disk (uncommitted changes)
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
    return content


def load_rules(rules_path: Path, max_severities: set[int]) -> list[dict]:
    """Load checker rules filtered by severity."""
    with open(rules_path) as f:
        data = json.load(f)
    rules = [r for r in data["checkers"] if r["severity"] in max_severities]
    return rules


def build_system_prompt(rules: list[dict]) -> str:
    """Build the system prompt with inline rule table."""
    rule_lines = "\n".join(
        f"  - {r['id']} (sev {r['severity']}): {r['desc']}"
        for r in rules
    )
    return textwrap.dedent(f"""
        You are an expert C/C++ static analysis engine that emulates Klocwork.
        Analyse the provided source file and its diff, then identify ALL issues
        that match the Klocwork checkers listed below.

        CHECKER RULES TO APPLY (from official Klocwork 2026.1 reference):
        {rule_lines}

        SEVERITY SCALE: 1 = Critical, 2 = Error, 3 = Warning, 4 = Review

        For EVERY issue found, produce a JSON entry with EXACTLY these fields:
        {{
          "checker":     "<CHECKER_ID from the list above>",
          "severity":    <integer 1-4>,
          "file":        "<relative file path>",
          "line":        <integer, best estimate from diff context>,
          "column":      <integer or null>,
          "description": "<clear one-sentence description of the specific issue>",
          "code_snippet":"<the exact problematic code line(s) from the diff>",
          "fix_description": "<concise explanation of how to fix it>",
          "fixed_code":  "<the corrected replacement code snippet (NOT the whole file)>"
        }}

        Return a JSON object with ONE key "issues" whose value is an array of
        the above entries. If no issues are found return {{"issues": []}}.

        IMPORTANT:
        - Only report real issues visible in the diff or directly caused by changed code.
        - Do not report style nits unrelated to the checkers.
        - "fixed_code" must be a minimal, compilable replacement for "code_snippet".
        - Respond with ONLY the JSON object – no markdown fences, no preamble.
    """).strip()


def build_user_message(file_path: str, file_content: str, diff: str) -> str:
    return textwrap.dedent(f"""
        FILE: {file_path}

        === FULL SOURCE (HEAD) ===
        {file_content}

        === DIFF (base → HEAD) ===
        {diff}
    """).strip()


def call_github_models(system_prompt: str, user_message: str, model: str, token: str) -> str:
    """Call GitHub Models endpoint (OpenAI-compatible)."""
    import urllib.request
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_message}
        ],
        "temperature": 0.1,
        "max_tokens":  4096,
        "response_format": {"type": "json_object"}
    }).encode()

    req = urllib.request.Request(
        f"{GITHUB_MODELS_ENDPOINT}/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())

    return body["choices"][0]["message"]["content"]


def call_openai_compatible(system_prompt: str, user_message: str,
                           model: str, api_key: str, base_url: str) -> str:
    """Generic OpenAI-compatible call (also works with local Ollama, etc.)."""
    import urllib.request
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_message}
        ],
        "temperature": 0.1,
        "max_tokens":  4096
    }).encode()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())
    return body["choices"][0]["message"]["content"]


def analyse_file(file_path: str, base: str, head: str,
                 system_prompt: str, model: str,
                 provider: str, token: str, base_url: str) -> list[dict]:
    """Run analysis on a single file, return list of issue dicts."""
    content = read_file_content(file_path)
    diff    = get_file_diff(file_path, base, head)

    if not diff:
        print(f"  [SKIP] No diff for {file_path}")
        return []

    user_msg = build_user_message(file_path, content, diff)

    print(f"  [ANALYSE] {file_path} ({model}) …")
    try:
        if provider == "github":
            raw = call_github_models(system_prompt, user_msg, model, token)
        else:
            raw = call_openai_compatible(system_prompt, user_msg, model, token, base_url)

        # Strip possible markdown fences the model might still emit
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.splitlines()[:-1])

        data = json.loads(raw)
        issues = data.get("issues", [])
        # Stamp the file path in case model omitted it
        for iss in issues:
            iss.setdefault("file", file_path)
        return issues

    except Exception as exc:
        print(f"  [ERROR] {file_path}: {exc}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Klocwork-style static analysis on git diff")
    parser.add_argument("--base",      default="origin/main", help="Base git ref")
    parser.add_argument("--head",      default="HEAD",        help="Head git ref")
    parser.add_argument("--rules",     default=str(DEFAULT_RULES_PATH),
                        help="Path to klocwork_rules.json")
    parser.add_argument("--severity",  default="1,2,3",
                        help="Comma-separated severity levels to include (1=critical)")
    parser.add_argument("--output",    default=DEFAULT_OUTPUT,
                        help="Output JSON file path")
    parser.add_argument("--model",     default="gpt-4o",
                        help="Model name (gpt-4o, gpt-4o-mini, Meta-Llama-3.1-70B-Instruct, etc.)")
    parser.add_argument("--provider",  default="github",
                        choices=["github", "openai", "anthropic", "local"],
                        help="API provider")
    parser.add_argument("--base-url",  default="",
                        help="Override base URL (for local Ollama, etc.)")
    args = parser.parse_args()

    # ── Token ──
    token = ""
    if args.provider == "github":
        token = os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
        if not token:
            sys.exit("[ERROR] Set GITHUB_TOKEN env var for GitHub Models provider.")
    elif args.provider == "openai":
        token = os.environ.get("OPENAI_API_KEY", "")
        if not args.base_url:
            args.base_url = "https://api.openai.com/v1"
    elif args.provider == "anthropic":
        sys.exit("[ERROR] Use provider=openai with base_url for Anthropic-compatible endpoint.")
    elif args.provider == "local":
        args.base_url = args.base_url or "http://localhost:11434/v1"

    # ── Rules ──
    severities = {int(s.strip()) for s in args.severity.split(",")}
    rules = load_rules(Path(args.rules), severities)
    print(f"[INFO] Loaded {len(rules)} Klocwork checkers (severities: {sorted(severities)})")

    # ── Changed files ──
    files = get_changed_files(args.base, args.head)
    if not files:
        print("[INFO] No C/C++ files changed. Nothing to analyse.")
        result = {"summary": {"files_analysed": 0, "total_issues": 0}, "issues": []}
        Path(args.output).write_text(json.dumps(result, indent=2))
        return

    print(f"[INFO] Changed C/C++ files: {files}")

    # ── System prompt (built once) ──
    system_prompt = build_system_prompt(rules)

    # ── Analyse each file ──
    all_issues: list[dict] = []
    for fp in files:
        issues = analyse_file(
            fp, args.base, args.head,
            system_prompt, args.model,
            args.provider, token, args.base_url
        )
        all_issues.extend(issues)
        if issues:
            print(f"  → {len(issues)} issue(s) found in {fp}")

    # Sort by severity then file/line
    all_issues.sort(key=lambda x: (x.get("severity", 9), x.get("file",""), x.get("line", 0)))

    result = {
        "summary": {
            "base":           args.base,
            "head":           args.head,
            "files_analysed": len(files),
            "total_issues":   len(all_issues),
            "by_severity": {
                "1_critical": sum(1 for i in all_issues if i.get("severity") == 1),
                "2_error":    sum(1 for i in all_issues if i.get("severity") == 2),
                "3_warning":  sum(1 for i in all_issues if i.get("severity") == 3),
                "4_review":   sum(1 for i in all_issues if i.get("severity") == 4),
            }
        },
        "issues": all_issues
    }

    Path(args.output).write_text(json.dumps(result, indent=2))
    print(f"\n[DONE] {len(all_issues)} issue(s) written to {args.output}")


if __name__ == "__main__":
    main()
