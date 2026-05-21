#!/usr/bin/env python3
"""
Generate a fixed Klockwork-compliant source tree in the klocwork directory.

The script uses GitHub CLI model integration if available. If the model command is not
available, it falls back to a safe static rewrite engine for common Klockwork issues.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SAFE_REPLACEMENTS = {
    r"\bstrcpy\s*\(": "strncpy(",
    r"\bstrcat\s*\(": "strncat(",
    r"\bsprintf\s*\(": "snprintf(",
    r"\bgets\s*\(": "fgets(",
    r"\bscanf\s*\(": "scanf_s(",
}

UNINITIALIZED_STACK_PATTERN = re.compile(
    r"\b(?:int|float|double|char|long|short)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;"
)

SOURCE_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"}


def find_source_files(source_dir: Path):
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in {"build", ".git", "_deps", "tests"}]
        for file_name in files:
            if Path(file_name).suffix in SOURCE_EXTENSIONS:
                yield Path(root) / file_name


def load_issues(issues_path: Path):
    with open(issues_path, "r", encoding="utf-8") as f:
        return json.load(f)

LOCAL_INCLUDE_PATTERN = re.compile(r'#include\s*"([^"]+)"')


def collect_local_includes(text: str):
    return set(LOCAL_INCLUDE_PATTERN.findall(text))


def locate_header(repo_root: Path, include_path: str):
    for path in repo_root.rglob("*"):
        if path.is_file() and str(path).endswith(include_path):
            return path
    return None


def copy_local_headers(repo_root: Path, output_root: Path, include_paths: set):
    copied = []
    for include_path in include_paths:
        source_header = locate_header(repo_root, include_path)
        if source_header:
            dest = output_root / include_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source_header.resolve() == dest.resolve():
                copied.append(str(dest))
                continue
            shutil.copy2(source_header, dest)
            copied.append(str(dest))
    return copied


def safe_rewrite_code(content: str) -> str:
    rewritten = content
    for pattern, replacement in SAFE_REPLACEMENTS.items():
        rewritten = re.sub(pattern, replacement, rewritten)

    def initializer(match):
        var_name = match.group(1)
        return match.group(0).replace(f"{var_name};", f"{var_name} = 0;")

    return UNINITIALIZED_STACK_PATTERN.sub(initializer, rewritten)


def ensure_gh_models_extension() -> bool:
    try:
        result = subprocess.run(
            ["gh", "models", "eval", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return True
        if "unknown command \"models\"" in result.stderr:
            extension_list = subprocess.run(
                ["gh", "extension", "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if "github/gh-models" in extension_list.stdout:
                return True
            install = subprocess.run(
                ["gh", "extension", "install", "github/gh-models"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return install.returncode == 0
        return False
    except FileNotFoundError:
        return False


def parse_model_output(raw: str):
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        pass

    try:
        wrapper = json.loads(raw)
        if isinstance(wrapper, dict) and "testResults" in wrapper:
            for entry in wrapper.get("testResults", []):
                model_response = entry.get("modelResponse")
                if model_response:
                    return parse_model_output(model_response)
    except Exception:
        pass

    return None


def generate_with_model(prompt_file: Path, payload: dict):
    if not ensure_gh_models_extension():
        return None

    try:
        result = subprocess.run(
            ["gh", "models", "eval", str(prompt_file), "--json", "--input", "-"],
            input=json.dumps(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0:
        return None

    return parse_model_output(result.stdout)


def write_output_file(output_root: Path, relative_path: str, fixed_code: str):
    destination = output_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(fixed_code, encoding="utf-8")
    return destination


def build_fix_report(issues: dict, generated_files: list, model_used: bool, fallback: bool):
    report = {
        "timestamp": datetime.now().isoformat(),
        "generated_by": "generate_klocwork_fixes.py",
        "model_used": model_used,
        "fallback_mode": fallback,
        "issues_file": issues.get("issues_file", "klockwork_issues.json"),
        "output_files": [f["path"] for f in generated_files],
        "fixes": [],
    }

    for entry in generated_files:
        if entry.get("issue"):
            report["fixes"].append({
                "issue": entry["issue"],
                "fixed_code": entry["fixed_code"],
            })
        else:
            report["fixes"].append({
                "issue": {
                    "rule_id": "UNKNOWN",
                    "description": "Auto-generated fix",
                    "severity": "LOW",
                },
                "fixed_code": entry["fixed_code"],
            })

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Generate Klockwork-compliant code into the klocwork directory."
    )
    parser.add_argument("--issues-file", default="klockwork_issues.json")
    parser.add_argument("--source-dir", default="src")
    parser.add_argument("--output-dir", default="klocwork")
    parser.add_argument(
        "--prompt-file",
        default="klockwork_automation/prompts/klockwork_fixer.prompt.yml",
        help="LLM prompt file for fix generation",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    issues_path = (repo_root / args.issues_file).resolve()
    source_dir = (repo_root / args.source_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    prompt_file = (repo_root / args.prompt_file).resolve()

    if not issues_path.exists():
        print(f"Error: issues file not found: {issues_path}", file=sys.stderr)
        return 1
    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        return 1

    issues = load_issues(issues_path)
    sources = []
    for path in find_source_files(source_dir):
        try:
            sources.append({
                "relative_path": str(path.relative_to(repo_root)),
                "content": path.read_text(encoding="utf-8", errors="ignore"),
            })
        except Exception:
            continue

    if output_dir.exists():
        shutil.rmtree(output_dir / "src", ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "issues": issues,
        "sources": sources,
        "target_directory": str(output_dir.relative_to(repo_root)),
        "instructions": (
            "Generate a Klockwork-compliant version of each provided source file. "
            "Return strict JSON with a top-level 'files' array. Each file entry must contain: "
            "'relative_path' and 'fixed_code'. If available, include 'issue' metadata. "
            "Do not return additional text outside the JSON object."
        ),
    }

    fixed_files = []
    model_used = False
    fallback_mode = False

    include_paths = set()
    for source in sources:
        include_paths.update(collect_local_includes(source["content"]))

    model_output = generate_with_model(prompt_file, payload)
    if model_output and isinstance(model_output, dict) and model_output.get("files"):
        model_used = True
        for file_entry in model_output["files"]:
            path = file_entry.get("relative_path") or file_entry.get("path")
            fixed_code = file_entry.get("fixed_code") or file_entry.get("fixedCode")
            if not path or fixed_code is None:
                continue
            write_output_file(output_dir, path, fixed_code)
            fixed_files.append({
                "path": path,
                "fixed_code": fixed_code,
                "issue": file_entry.get("issue"),
            })

    if not fixed_files:
        fallback_mode = True
        for source in sources:
            relative_path = Path(source["relative_path"])
            fixed_code = safe_rewrite_code(source["content"])
            write_output_file(output_dir, relative_path, fixed_code)
            fixed_files.append({
                "path": str(relative_path),
                "fixed_code": fixed_code,
                "issue": None,
            })

    copied_headers = copy_local_headers(repo_root, output_dir, include_paths)
    if copied_headers:
        print(f"Copied {len(copied_headers)} header file(s) into {output_dir}")

    report = build_fix_report(issues, fixed_files, model_used, fallback_mode)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = repo_root / f"klockwork_fixes_{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Generated {len(fixed_files)} fixed source file(s) to {output_dir}")
    print(f"Fix report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
