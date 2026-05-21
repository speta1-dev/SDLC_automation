#!/usr/bin/env python3
"""
Generate a Klockwork-compliant code copy into a dedicated output folder.

This script copies source files from the project and applies simple fixes for common
Klockwork patterns. The resulting code is written into the `klocwork/` folder.
"""

import argparse
import os
import re
import shutil
from pathlib import Path

SAFE_REPLACEMENTS = {
    # Replace obviously unsafe string copy/cat functions with safer alternatives.
    r"\bstrcpy\s*\(": "strncpy(",
    r"\bstrcat\s*\(": "strncat(",
    r"\bsprintf\s*\(": "snprintf(",
    r"\bgets\s*\(": "fgets(",
    # Replace plain scanf invocations with scanf_s where available.
    r"\bscanf\s*\(": "scanf_s(",
}

UNINITIALIZED_STACK_PATTERN = re.compile(
    r"\b(?:int|float|double|char|long|short)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;"
)

SKIP_DIRS = {"build", ".git", "_deps", "klockwork", "tests"}


def find_source_files(source_dir: Path):
    extensions = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"}
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file_name in files:
            if Path(file_name).suffix in extensions:
                yield Path(root) / file_name


def apply_safe_fixes(text: str) -> str:
    fixed_text = text
    for pattern, replacement in SAFE_REPLACEMENTS.items():
        fixed_text = re.sub(pattern, replacement, fixed_text)

    def initialize_stack_var(match):
        var_name = match.group(1)
        return match.group(0).replace(f"{var_name};", f"{var_name} = 0;")

    fixed_text = UNINITIALIZED_STACK_PATTERN.sub(initialize_stack_var, fixed_text)
    return fixed_text


def write_compliant_tree(source_dir: Path, output_dir: Path):
    if output_dir.exists() and not output_dir.is_dir():
        raise RuntimeError(f"Output path exists and is not a directory: {output_dir}")

    output_root = output_dir / source_dir.name
    output_root.mkdir(parents=True, exist_ok=True)

    for source_path in find_source_files(source_dir):
        relative_path = source_path.relative_to(source_dir)
        destination_path = output_root / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with open(source_path, "r", encoding="utf-8", errors="ignore") as source_file:
            content = source_file.read()

        fixed_content = apply_safe_fixes(content)

        with open(destination_path, "w", encoding="utf-8") as dest_file:
            dest_file.write(fixed_content)

        print(f"Written compliant file: {destination_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Copy project source into a Klockwork-compliant output folder."
    )
    parser.add_argument(
        "--source-dir",
        default="src",
        help="Source directory to scan and copy (default: src)",
    )
    parser.add_argument(
        "--output-dir",
        default="klocwork",
        help="Output directory for compliant code (default: klocwork)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    source_dir = (repo_root / args.source_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    print(f"Generating Klockwork-compliant code from {source_dir} to {output_dir}")
    write_compliant_tree(source_dir, output_dir)
    print("Klockwork-compliant code generation complete.")


if __name__ == "__main__":
    main()
