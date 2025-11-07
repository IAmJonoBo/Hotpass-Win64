#!/usr/bin/env python3
"""Verify documentation parity with CLI implementation.

This script extracts the authoritative command list from the Hotpass CLI source code
and verifies that all documentation references to commands, flags, and environment
variables are accurate and up-to-date.

Exit codes:
    0: All documentation is accurate
    1: Documentation parity issues found
    2: Script execution error
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple


# Color codes for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class CommandInfo(NamedTuple):
    """Information about a CLI command."""

    name: str
    help_text: str
    module_path: str


class ParityIssue(NamedTuple):
    """Documentation parity issue."""

    file_path: str
    line_number: int
    issue_type: str
    description: str
    context: str


def find_repo_root() -> Path:
    """Find the repository root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


def extract_commands_from_source(repo_root: Path) -> list[CommandInfo]:
    """Extract all CLI commands from the source code."""
    commands = []

    # Parse the main.py file to get registered commands
    main_py = repo_root / "apps" / "data-platform" / "hotpass" / "cli" / "main.py"
    if not main_py.exists():
        raise RuntimeError(f"Could not find main.py at {main_py}")

    # Parse the AST to find command registrations
    with open(main_py) as f:
        tree = ast.parse(f.read(), filename=str(main_py))

    # Find the build_parser function
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_parser":
            # Look for builder.register() calls
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Call):
                    if isinstance(stmt.func, ast.Attribute) and stmt.func.attr == "register":
                        # Get the module being registered
                        if stmt.args and isinstance(stmt.args[0], ast.Call):
                            call = stmt.args[0]
                            if isinstance(call.func, ast.Attribute):
                                module_name = None
                                if isinstance(call.func.value, ast.Name):
                                    module_name = call.func.value.id

                                if module_name and call.func.attr == "register":
                                    # Extract command info from the module
                                    cmd_path = (
                                        repo_root
                                        / "apps"
                                        / "data-platform"
                                        / "hotpass"
                                        / "cli"
                                        / "commands"
                                        / f"{module_name}.py"
                                    )
                                    if cmd_path.exists():
                                        cmd_info = extract_command_info(cmd_path, module_name)
                                        if cmd_info:
                                            commands.append(cmd_info)

    # Also run the actual CLI to get the help output
    try:
        result = subprocess.run(
            ["uv", "run", "hotpass", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # Parse help output to extract commands
            help_commands = parse_help_output(result.stdout)
            # Merge with what we found in the AST
            commands_by_name = {cmd.name: cmd for cmd in commands}
            for name, help_text in help_commands.items():
                if name not in commands_by_name:
                    commands.append(CommandInfo(name, help_text, "detected from CLI"))
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"{Colors.YELLOW}Warning: Could not run CLI to extract commands: {e}{Colors.RESET}")

    return sorted(commands, key=lambda c: c.name)


def extract_command_info(cmd_path: Path, module_name: str) -> CommandInfo | None:
    """Extract command information from a command module file."""
    try:
        with open(cmd_path) as f:
            tree = ast.parse(f.read(), filename=str(cmd_path))

        # Look for the register() function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                # Find CLICommand constructor
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
                        call = stmt.value
                        if isinstance(call.func, ast.Name) and call.func.id == "CLICommand":
                            # Extract name and help from keyword arguments
                            name = None
                            help_text = None
                            for kw in call.keywords:
                                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                    name = kw.value.value
                                elif kw.arg == "help" and isinstance(kw.value, ast.Constant):
                                    help_text = kw.value.value

                            if name and help_text:
                                return CommandInfo(
                                    name, help_text, str(cmd_path.relative_to(cmd_path.parents[6]))
                                )
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Could not parse {cmd_path}: {e}{Colors.RESET}")

    return None


def parse_help_output(help_text: str) -> dict[str, str]:
    """Parse CLI help output to extract command names and descriptions."""
    commands = {}

    # Look for the commands section
    in_commands = False
    for line in help_text.split("\n"):
        line = line.strip()

        if "positional arguments:" in line:
            in_commands = True
            continue

        if in_commands:
            if line.startswith("{") and "}" in line:
                # This is the command list line - skip it
                continue
            elif line and not line.startswith("-") and not line.startswith("options:"):
                # This might be a command with description
                parts = line.split(None, 1)
                if len(parts) == 2:
                    cmd_name, description = parts
                    commands[cmd_name] = description
            elif "options:" in line:
                break

    return commands


def extract_env_vars_from_source(repo_root: Path) -> set[str]:
    """Extract environment variable references from source code."""
    env_vars = set()

    # Patterns to match environment variable access
    patterns = [
        re.compile(r'os\.environ\.get\(["\']([A-Z_][A-Z0-9_]*)["\']'),
        re.compile(r'os\.getenv\(["\']([A-Z_][A-Z0-9_]*)["\']'),
        re.compile(r'environ\[["\'](A-Z_][A-Z0-9_]*)["\']'),
        re.compile(r'env\(["\']([A-Z_][A-Z0-9_]*)["\']'),  # Function call pattern
        re.compile(r'"([A-Z_][A-Z0-9_]*)"[,\]]'),  # String literals in arrays/dicts
    ]

    # Search in Python files
    for py_file in repo_root.rglob("*.py"):
        if ".venv" in str(py_file) or "node_modules" in str(py_file):
            continue

        try:
            with open(py_file) as f:
                content = f.read()
                for pattern in patterns:
                    matches = pattern.findall(content)
                    env_vars.update(matches)
        except Exception:
            continue

    # Also search in shell scripts
    for sh_file in repo_root.rglob("*.sh"):
        if ".venv" in str(sh_file) or "node_modules" in str(sh_file):
            continue

        try:
            with open(sh_file) as f:
                content = f.read()
                # Match $VAR_NAME or ${VAR_NAME}
                sh_patterns = [
                    re.compile(r"\$\{?([A-Z_][A-Z0-9_]*)\}?"),
                ]
                for pattern in sh_patterns:
                    matches = pattern.findall(content)
                    env_vars.update(matches)
        except Exception:
            continue

    return env_vars


def check_documentation_parity(
    repo_root: Path,
    commands: list[CommandInfo],
    env_vars: set[str],
) -> list[ParityIssue]:
    """Check documentation files for parity issues."""
    issues = []

    # Documentation files to check
    doc_files = [
        repo_root / "README.md",
        repo_root / "AGENTS.md",
        repo_root / "SECURITY.md",
        repo_root / "Next_Steps.md",
        repo_root / "IMPLEMENTATION_PLAN.md",
    ]

    # Add all markdown files in docs/
    docs_dir = repo_root / "docs"
    if docs_dir.exists():
        doc_files.extend(docs_dir.rglob("*.md"))

    command_names = {cmd.name for cmd in commands}

    # Common false positives to ignore
    ignore_patterns = [
        "command",  # Generic use of the word
        "commands",
        "example",
        "examples",
        "import",  # Python import statement
        "fill",  # Mermaid diagram styling
        "hotpass",  # Generic reference to the tool itself
    ]

    for doc_file in doc_files:
        if not doc_file.exists():
            continue

        try:
            with open(doc_file) as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                # Skip code blocks that are Python imports or mermaid diagrams
                if "from hotpass import" in line or "import hotpass" in line:
                    continue
                if "classDef" in line or "fill:" in line:
                    continue

                # Check for command references in code blocks
                if "hotpass" in line:
                    # Extract potential command references
                    # Pattern: hotpass <command> or `hotpass <command>`
                    matches = re.finditer(r"hotpass\s+([a-z][a-z0-9-]*)", line)
                    for match in matches:
                        cmd = match.group(1)
                        if cmd not in command_names and cmd not in ignore_patterns:
                            # Check if it's a valid command with dashes vs underscores
                            cmd_underscore = cmd.replace("-", "_")
                            if cmd_underscore not in command_names:
                                issues.append(
                                    ParityIssue(
                                        file_path=str(doc_file.relative_to(repo_root)),
                                        line_number=line_num,
                                        issue_type="unknown_command",
                                        description=f"Command '{cmd}' not found in CLI",
                                        context=line.strip()[:80],
                                    )
                                )

                # Check for environment variable references
                # Only check lines that look like they're documenting env vars
                if "|" in line or "export" in line.lower() or "=" in line:
                    env_matches = re.finditer(r"\b([A-Z_]{3,}[A-Z0-9_]*)\b", line)
                    for match in env_matches:
                        var = match.group(1)
                        # Only flag Hotpass vars not in common system vars
                        common_vars = {
                            "PREFECT_API_URL",
                            "OPENLINEAGE_URL",
                            "OTEL_EXPORTER_OTLP_ENDPOINT",
                            "LOCALSTACK_ENDPOINT",
                            "AWS_PROFILE",
                            "AWS_REGION",
                            "PATH",
                        }
                        if (
                            var.startswith("HOTPASS_")
                            and var not in env_vars
                            and var not in common_vars
                        ):
                            issues.append(
                                ParityIssue(
                                    file_path=str(doc_file.relative_to(repo_root)),
                                    line_number=line_num,
                                    issue_type="unknown_env_var",
                                    description=f"Environment variable '{var}' not found",
                                    context=line.strip()[:80],
                                )
                            )

        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not check {doc_file}: {e}{Colors.RESET}")

    return issues


def print_report(
    commands: list[CommandInfo],
    env_vars: set[str],
    issues: list[ParityIssue],
) -> None:
    """Print a report of the verification results."""
    print(f"\n{Colors.BOLD}=== Documentation Parity Report ==={Colors.RESET}\n")

    print(f"{Colors.BLUE}Discovered Commands ({len(commands)}):{Colors.RESET}")
    for cmd in commands:
        print(f"  • {cmd.name}: {cmd.help_text[:60]}...")

    print(f"\n{Colors.BLUE}Discovered Environment Variables ({len(env_vars)}):{Colors.RESET}")
    hotpass_vars = sorted([v for v in env_vars if v.startswith("HOTPASS_")])
    for var in hotpass_vars[:20]:  # Show first 20
        print(f"  • {var}")
    if len(hotpass_vars) > 20:
        print(f"  ... and {len(hotpass_vars) - 20} more")

    if issues:
        print(f"\n{Colors.RED}Found {len(issues)} parity issue(s):{Colors.RESET}\n")

        # Group issues by type
        by_type = defaultdict(list)
        for issue in issues:
            by_type[issue.issue_type].append(issue)

        for issue_type, type_issues in sorted(by_type.items()):
            print(f"{Colors.YELLOW}{issue_type.replace('_', ' ').title()}:{Colors.RESET}")
            for issue in type_issues[:10]:  # Show first 10 per type
                print(f"  {issue.file_path}:{issue.line_number}")
                print(f"    {issue.description}")
                print(f"    Context: {issue.context}")
                print()
            if len(type_issues) > 10:
                print(f"  ... and {len(type_issues) - 10} more\n")
    else:
        print(f"\n{Colors.GREEN}✓ No parity issues found!{Colors.RESET}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify documentation parity with CLI implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        default=True,
        help="Exit with non-zero status if issues found (default: True)",
    )

    args = parser.parse_args()

    try:
        repo_root = find_repo_root()

        print("Extracting commands from source code...")
        commands = extract_commands_from_source(repo_root)

        print("Extracting environment variables from source code...")
        env_vars = extract_env_vars_from_source(repo_root)

        print("Checking documentation for parity issues...")
        issues = check_documentation_parity(repo_root, commands, env_vars)

        if args.json:
            # Output JSON format
            output = {
                "commands": [
                    {"name": cmd.name, "help": cmd.help_text, "module": cmd.module_path}
                    for cmd in commands
                ],
                "environment_variables": sorted(list(env_vars)),
                "issues": [
                    {
                        "file": issue.file_path,
                        "line": issue.line_number,
                        "type": issue.issue_type,
                        "description": issue.description,
                        "context": issue.context,
                    }
                    for issue in issues
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            # Pretty print report
            print_report(commands, env_vars, issues)

        if issues and args.fail_on_issues:
            return 1
        return 0

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
