"""Contracts command - emit data contracts and schemas for a profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from hotpass.config import load_industry_profile

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    """Build the contracts command parser."""
    parser = subparsers.add_parser(
        "contracts",
        help="Emit data contracts and schemas for a profile",
        description=(
            "Generate data contracts, schemas, and specifications for a given profile. "
            "Useful for API consumers, data quality tools, and documentation."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "action",
        type=str,
        nargs="?",
        default="emit",
        choices=["emit", "validate"],
        help="Action to perform (default: emit)",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)",
    )

    parser.add_argument(
        "--format",
        type=str,
        default="yaml",
        choices=["yaml", "json"],
        help="Output format (default: yaml)",
    )

    parser.add_argument(
        "--include-examples",
        action="store_true",
        help="Include example data in the contract",
    )

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="contracts",
        help="Emit data contracts and schemas for a profile",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    """Handle the contracts command execution."""
    console = Console()

    # Get profile name from CLI profile
    profile_name = "generic"
    if profile:
        profile_name = profile.industry_profile or "generic"

    # Load profile
    try:
        industry_profile = load_industry_profile(profile_name)
        console.print(
            f"[cyan]Loading profile:[/cyan] {industry_profile.display_name}",
            file=sys.stderr,
        )
    except Exception as e:
        console.print(f"[red]Error loading profile:[/red] {e}", file=sys.stderr)
        return 1

    if namespace.action == "emit":
        return emit_contracts(namespace, industry_profile, console)
    elif namespace.action == "validate":
        return validate_contracts(namespace, industry_profile, console)
    else:
        console.print(f"[red]Unknown action:[/red] {namespace.action}", file=sys.stderr)
        return 1


def emit_contracts(namespace: argparse.Namespace, industry_profile: Any, console: Console) -> int:
    """Emit data contracts for the profile."""
    try:
        # Build contract structure
        contract = {
            "version": "1.0",
            "profile": {
                "name": industry_profile.name,
                "display_name": industry_profile.display_name,
            },
            "schema": {
                "fields": build_schema_fields(industry_profile),
                "required_fields": getattr(industry_profile, "required_fields", []),
                "optional_fields": getattr(industry_profile, "optional_fields", []),
            },
            "validation": {
                "email_threshold": getattr(industry_profile, "email_validation_threshold", 0.85),
                "phone_threshold": getattr(industry_profile, "phone_validation_threshold", 0.85),
                "website_threshold": getattr(
                    industry_profile, "website_validation_threshold", 0.75
                ),
            },
            "metadata": {
                "organization_term": getattr(industry_profile, "organization_term", "organization"),
                "default_country_code": getattr(industry_profile, "default_country_code", "ZA"),
            },
        }

        # Add column synonyms
        if hasattr(industry_profile, "column_synonyms"):
            contract["mappings"] = {"column_synonyms": industry_profile.column_synonyms}

        # Add source priorities
        if hasattr(industry_profile, "source_priorities"):
            contract["sources"] = {"priorities": industry_profile.source_priorities}

        # Add examples if requested
        if namespace.include_examples:
            contract["examples"] = generate_examples(industry_profile)

        # Format and output
        if namespace.format == "json":
            output_text = json.dumps(contract, indent=2, ensure_ascii=False)
        else:  # yaml
            output_text = yaml.dump(contract, default_flow_style=False, allow_unicode=True)

        if namespace.output:
            output_path = Path(namespace.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text)
            console.print(f"[green]✓[/green] Contract written to {output_path}", file=sys.stderr)
        else:
            console.print(output_text)

        return 0

    except Exception as e:
        console.print(f"[red]Error emitting contract:[/red] {e}", file=sys.stderr)
        return 1


def validate_contracts(
    namespace: argparse.Namespace, industry_profile: Any, console: Console
) -> int:
    """Validate existing contracts against the profile."""
    console.print("[yellow]Contract validation not yet implemented[/yellow]", file=sys.stderr)
    return 0


def build_schema_fields(profile: Any) -> dict[str, Any]:
    """Build schema field definitions from profile."""
    fields = {}

    # Standard SSOT fields
    standard_fields = [
        ("organization_id", "string", "Unique organization identifier"),
        ("organization_name", "string", "Organization name"),
        ("organization_name_normalized", "string", "Normalized organization name"),
        ("contact_primary_email", "string", "Primary contact email"),
        ("contact_primary_phone", "string", "Primary contact phone"),
        ("website", "string", "Organization website URL"),
        ("province", "string", "Province or region"),
        ("address_primary", "string", "Primary address"),
    ]

    for field_name, field_type, description in standard_fields:
        fields[field_name] = {
            "type": field_type,
            "description": description,
            "required": field_name in getattr(profile, "required_fields", []),
        }

    return fields


def generate_examples(profile: Any) -> dict[str, Any]:
    """Generate example data for the profile."""
    return {
        "valid_record": {
            "organization_name": "Example Flight School",
            "contact_primary_email": "info@example.com",
            "contact_primary_phone": "+27123456789",
            "website": "https://example.com",
            "province": "Gauteng",
        },
        "minimal_record": {
            "organization_name": "Minimal Organization",
        },
    }
