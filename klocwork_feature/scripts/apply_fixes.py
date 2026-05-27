#!/usr/bin/env python3
"""
apply_fixes.py
--------------
Reads the JSON output from klocwork_analyzer.py and applies the suggested
code fixes directly to the source files.

Changes are left UNSTAGED so the developer can review them with:
    git diff
    git add -p      # selectively stage hunks
    git add <file>  # or stage the whole file

Usage:
    python3 scripts/apply_fixes.py \
        --report klocwork_report.json \
        [--dry-run]          # print patches but don't write files
        [--severity 1,2]     # only apply fixes for these severity levels
        [--interactive]      # confirm each fix before applying
"""

import argparse
import json
import os
import sys
from pathlib import Path


# ANSI colours (disable on Windows / no-tty)
_USE_COLOUR = sys.stdout.isatty() and os.name != "nt"
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

RED    = lambda t: _c("31", t)
GREEN  = lambda t: _c("32", t)
YELLOW = lambda t: _c("33", t)
CYAN   = lambda t: _c("36", t)
BOLD   = lambda t: _c("1",  t)


def load_report(report_path: str) -> dict:
    with open(report_path) as f:
        return json.load(f)


def find_snippet_in_file(lines: list[str], snippet: str) -> int | None:
    """
    Return 0-based index of the first line in `lines` that contains the
    first line of `snippet`. Falls back to a stripped comparison.
    """
    first = snippet.strip().splitlines()[0].strip()
    for i, line in enumerate(lines):
        if first in line:
            return i
    return None


def apply_fix(file_path: str, issue: dict, dry_run: bool) -> bool:
    """
    Replace `code_snippet` with `fixed_code` in the source file.
    Returns True if the patch was applied (or would be in dry-run).
    """
    snippet = issue.get("code_snippet", "").strip()
    fix     = issue.get("fixed_code",   "").strip()

    if not snippet or not fix:
        print(f"  {YELLOW('[SKIP]')} No snippet/fix provided for {issue['checker']} @ line {issue.get('line')}")
        return False

    if snippet == fix:
        print(f"  {YELLOW('[SKIP]')} Snippet and fix are identical for {issue['checker']}")
        return False

    path = Path(file_path)
    if not path.exists():
        print(f"  {RED('[ERROR]')} File not found: {file_path}")
        return False

    original = path.read_text(encoding="utf-8", errors="replace")

    if snippet not in original:
        # Try line-by-line fuzzy: strip each side and match
        lines = original.splitlines()
        idx = find_snippet_in_file(lines, snippet)
        if idx is None:
            print(f"  {YELLOW('[SKIP]')} Snippet not found in {file_path} for {issue['checker']}")
            return False
        # Replace just that line with the fix
        snip_lines = snippet.strip().splitlines()
        fix_lines  = fix.strip().splitlines()
        patched_lines = lines[:idx] + fix_lines + lines[idx + len(snip_lines):]
        patched = "\n".join(patched_lines)
        if original.endswith("\n"):
            patched += "\n"
    else:
        patched = original.replace(snippet, fix, 1)

    if dry_run:
        print(f"  {CYAN('[DRY-RUN]')} Would patch {file_path}")
        _print_diff(snippet, fix)
        return True

    path.write_text(patched, encoding="utf-8")
    print(f"  {GREEN('[APPLIED]')} {file_path}  ({issue['checker']})")
    _print_diff(snippet, fix)
    return True


def _print_diff(old: str, new: str):
    for line in old.splitlines():
        print(f"    {RED('-')} {line}")
    for line in new.splitlines():
        print(f"    {GREEN('+')} {line}")


def confirm(prompt: str) -> bool:
    try:
        ans = input(prompt + " [y/N] ").strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def print_issue_banner(issue: dict):
    sev_colours = {1: RED, 2: lambda t: _c("33;1", t), 3: YELLOW, 4: CYAN}
    sev_labels  = {1: "CRITICAL", 2: "ERROR", 3: "WARNING", 4: "REVIEW"}
    sev  = issue.get("severity", 0)
    clr  = sev_colours.get(sev, str)
    label= sev_labels.get(sev, "UNKNOWN")

    print()
    print(BOLD(f"  ┌─ [{clr(label)}] {issue['checker']}"))
    print(f"  │  File   : {issue.get('file','?')}:{issue.get('line','?')}")
    print(f"  │  Issue  : {issue.get('description','')}")
    print(f"  │  Fix    : {issue.get('fix_description','')}")
    print(f"  └{'─'*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Apply Klocwork fix suggestions to source files (unstaged)"
    )
    parser.add_argument("--report",      default="klocwork_report.json",
                        help="Path to klocwork_report.json")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Show patches without writing files")
    parser.add_argument("--severity",    default="1,2",
                        help="Comma-separated severity levels to auto-apply (default: 1,2)")
    parser.add_argument("--interactive", action="store_true",
                        help="Confirm each fix interactively")
    args = parser.parse_args()

    report = load_report(args.report)
    issues = report.get("issues", [])
    target_severities = {int(s.strip()) for s in args.severity.split(",")}

    if not issues:
        print("[INFO] No issues in report. Nothing to apply.")
        return

    summary  = report.get("summary", {})
    print(BOLD("\n═══ Klocwork Fix Applicator ═══"))
    print(f"  Files analysed : {summary.get('files_analysed', '?')}")
    print(f"  Total issues   : {summary.get('total_issues', len(issues))}")
    by_sev = summary.get("by_severity", {})
    print(f"  Critical(1)    : {by_sev.get('1_critical', 0)}")
    print(f"  Error(2)       : {by_sev.get('2_error', 0)}")
    print(f"  Warning(3)     : {by_sev.get('3_warning', 0)}")
    print(f"  Review(4)      : {by_sev.get('4_review', 0)}")
    print(f"\n  Applying fixes for severity: {sorted(target_severities)}")
    if args.dry_run:
        print(f"  {YELLOW('DRY-RUN MODE – files will NOT be modified')}")

    applied = skipped = 0

    for issue in issues:
        if issue.get("severity") not in target_severities:
            continue

        print_issue_banner(issue)

        if args.interactive:
            if not confirm("  Apply this fix?"):
                print(f"  {YELLOW('[SKIP]')} Skipped by user.")
                skipped += 1
                continue

        ok = apply_fix(issue.get("file", ""), issue, args.dry_run)
        if ok:
            applied += 1
        else:
            skipped += 1

    print()
    print(BOLD("═══ Summary ═══"))
    print(f"  {GREEN('Applied')}: {applied}   {YELLOW('Skipped')}: {skipped}")
    print()

    if not args.dry_run and applied > 0:
        print("  Changes are UNSTAGED. To review:")
        print(CYAN("    git diff"))
        print("  To selectively stage hunks:")
        print(CYAN("    git add -p"))
        print("  To stage all fixes for a file:")
        print(CYAN("    git add <file>"))
        print()


if __name__ == "__main__":
    main()
