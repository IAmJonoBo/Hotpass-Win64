"""Credential acquisition, storage, and review helpers."""

from __future__ import annotations

import argparse
import os
import shutil
import webbrowser
from datetime import UTC, datetime
from typing import Any, cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..state import load_state, remove_state, state_path, write_state
from ..utils import CommandExecutionError, format_command, run_command

CREDENTIALS_STATE_FILE = "credentials.json"
AWS_DEFAULT_PROFILE = "hotpass-staging"
AWS_DEFAULT_REGION = "eu-west-1"
DEFAULT_AWS_PORTAL_URL = os.environ.get(
    "HOTPASS_AWS_PORTAL_URL", "https://signin.aws.amazon.com/console"
)
DEFAULT_MARQUEZ_PORTAL_URL = os.environ.get(
    "HOTPASS_MARQUEZ_PORTAL_URL", "https://marquez.example.com"
)
DEFAULT_PREFECT_PORTAL_URL = os.environ.get(
    "HOTPASS_PREFECT_PORTAL_URL", "https://app.prefect.cloud"
)


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "credentials",
        help="Capture and reuse provider credentials",
        description=(
            "Guide operators through acquiring AWS, Marquez, Prefect, and related credentials. "
            "Prompts can open provider portals, run shell-based logins, and store secrets in "
            ".hotpass/credentials.json with restrictive permissions."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cred_subparsers = parser.add_subparsers(dest="credentials_command")

    wizard_parser = cred_subparsers.add_parser(
        "wizard",
        help="Interactive credential acquisition wizard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    wizard_parser.add_argument(
        "--providers",
        nargs="+",
        choices={"aws", "marquez", "prefect", "vpn"},
        help="Restrict the wizard to specific providers",
    )
    wizard_parser.add_argument(
        "--assume-yes",
        action="store_true",
        help="Accept defaults for yes/no prompts. Requires defaults for free-text answers.",
    )
    wizard_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Skip opening provider portals in the default browser.",
    )
    wizard_parser.add_argument(
        "--store-secrets",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist secrets (API keys, access keys) to .hotpass/credentials.json.",
    )
    wizard_parser.set_defaults(handler=_handle_wizard)

    show_parser = cred_subparsers.add_parser(
        "show",
        help="Display stored credentials (secrets masked)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    show_parser.set_defaults(handler=_handle_show)

    clear_parser = cred_subparsers.add_parser(
        "clear",
        help="Remove stored credentials for one or more providers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    clear_parser.add_argument(
        "--providers",
        nargs="+",
        choices={"aws", "marquez", "prefect"},
        help="Specific providers to clear. Omit to remove all stored credentials.",
    )
    clear_parser.set_defaults(handler=_handle_clear)

    parser.set_defaults(handler=_dispatch_default)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="credentials",
        help="Acquire and store provider credentials",
        builder=build,
        handler=_dispatch_default,
    )


def _dispatch_default(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    command = getattr(namespace, "credentials_command", None)
    if command is None:
        namespace.credentials_command = "wizard"
        namespace.handler = _handle_wizard
    handler = getattr(namespace, "handler", None)
    if callable(handler):
        return int(handler(namespace, profile))
    Console().print("[red]No credentials subcommand resolved.[/red]")
    return 1


# ---------------------------------------------------------------------------
# Command handlers


def _handle_wizard(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    assume_yes = bool(getattr(namespace, "assume_yes", False))
    store_secrets = bool(getattr(namespace, "store_secrets", True))
    providers_filter = set(namespace.providers or ["aws", "marquez", "prefect", "vpn"])
    no_browser = bool(getattr(namespace, "no_browser", False))

    credentials = _load_credentials()
    updated = False

    if "aws" in providers_filter:
        if _prompt_confirm(
            message="Configure AWS credentials now?",
            default=not bool(credentials.get("aws")),
            assume_yes=assume_yes,
        ):
            aws_changed = _configure_aws(
                credentials, console, assume_yes, store_secrets, no_browser
            )
            updated = updated or aws_changed

    if "marquez" in providers_filter:
        if _prompt_confirm(
            message="Configure Marquez access?",
            default=not bool(credentials.get("marquez")),
            assume_yes=assume_yes,
        ):
            marquez_changed = _configure_marquez(
                credentials, console, assume_yes, store_secrets, no_browser
            )
            updated = updated or marquez_changed

    if "prefect" in providers_filter:
        if _prompt_confirm(
            message="Configure Prefect credentials?",
            default=not bool(credentials.get("prefect")),
            assume_yes=assume_yes,
        ):
            prefect_changed = _configure_prefect(
                credentials, console, assume_yes, store_secrets, no_browser
            )
            updated = updated or prefect_changed

    if "vpn" in providers_filter:
        _offer_vpn_guidance(console, assume_yes, no_browser)

    if updated:
        _write_credentials(credentials, console)
    else:
        console.print("[yellow]No credential changes recorded.[/yellow]")
    return 0


def _handle_show(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    credentials = _load_credentials()
    if not credentials:
        console.print(
            "[yellow]No stored credentials in .hotpass/credentials.json.[/yellow]"
        )
        return 0

    table = Table(
        title="Stored credentials", show_header=True, header_style="bold cyan"
    )
    table.add_column("Provider")
    table.add_column("Details")

    aws_payload = credentials.get("aws")
    if aws_payload:
        details = [
            f"profile={aws_payload.get('profile', '-')}",
            f"region={aws_payload.get('region', '-')}",
        ]
        if aws_payload.get("access_key_id"):
            details.append(
                f"access_key_id={_mask_secret(aws_payload['access_key_id'])}"
            )
        if aws_payload.get("mode"):
            details.append(f"mode={aws_payload['mode']}")
        table.add_row("AWS", "\n".join(details))

    marquez_payload = credentials.get("marquez")
    if marquez_payload:
        details = [
            f"url={marquez_payload.get('api_url', '-')}",
        ]
        if marquez_payload.get("api_key"):
            details.append(f"api_key={_mask_secret(marquez_payload['api_key'])}")
        table.add_row("Marquez", "\n".join(details))

    prefect_payload = credentials.get("prefect")
    if prefect_payload:
        details = [
            f"profile={prefect_payload.get('profile', '-')}",
            f"workspace={prefect_payload.get('workspace', '-')}",
        ]
        if prefect_payload.get("api_key"):
            details.append(f"api_key={_mask_secret(prefect_payload['api_key'])}")
        table.add_row("Prefect", "\n".join(details))

    console.print(table)
    return 0


def _handle_clear(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    providers = namespace.providers
    if not providers:
        remove_state(CREDENTIALS_STATE_FILE)
        console.print("[green]Removed all stored credentials.[/green]")
        return 0

    credentials = _load_credentials()
    removed_any = False
    for provider in providers:
        if credentials.pop(provider, None) is not None:
            console.print(f"[green]Removed {provider} credentials from store.[/green]")
            removed_any = True
    if removed_any:
        _write_credentials(credentials, console)
    else:
        console.print(
            "[yellow]No matching providers found in credential store.[/yellow]"
        )
    return 0


# ---------------------------------------------------------------------------
# Provider configuration helpers


def _configure_aws(
    credentials: dict[str, Any],
    console: Console,
    assume_yes: bool,
    store_secrets: bool,
    no_browser: bool,
) -> bool:
    aws_payload = credentials.get("aws", {})
    profile_default = (
        aws_payload.get("profile")
        or os.environ.get("AWS_PROFILE")
        or AWS_DEFAULT_PROFILE
    )
    region_default = (
        aws_payload.get("region")
        or os.environ.get("AWS_DEFAULT_REGION")
        or AWS_DEFAULT_REGION
    )

    profile_value = _prompt_text(
        message="AWS profile name",
        default=profile_default,
        assume_yes=assume_yes,
    )
    region_value = _prompt_text(
        message="AWS region",
        default=region_default,
        assume_yes=assume_yes,
    )

    acquisition_mode = _prompt_choice(
        message="Acquire or refresh AWS credentials via",
        choices=["sso-login", "configure-sso", "configure-keys", "skip"],
        default="sso-login" if _aws_cli_available() else "skip",
        assume_yes=assume_yes,
    )

    if acquisition_mode == "configure-sso":
        _run_optional_command(
            console,
            ["aws", "configure", "sso", "--profile", profile_value],
            "aws configure sso",
        )
        acquisition_mode = "sso-login"

    if acquisition_mode == "sso-login":
        if not no_browser:
            _open_portal(console, "AWS IAM Identity Center", DEFAULT_AWS_PORTAL_URL)
        _run_optional_command(
            console,
            ["aws", "sso", "login", "--profile", profile_value],
            "aws sso login",
        )
    elif acquisition_mode == "configure-keys" and store_secrets:
        access_key_id = _prompt_text(
            message="AWS access key ID",
            default=aws_payload.get("access_key_id"),
            assume_yes=assume_yes,
        )
        secret_access_key = _prompt_text(
            message="AWS secret access key",
            default=aws_payload.get("secret_access_key"),
            assume_yes=assume_yes,
            password=True,
        )
        session_token = _prompt_text(
            message="AWS session token (optional)",
            default=aws_payload.get("session_token"),
            assume_yes=assume_yes,
            password=True,
            allow_empty=True,
        )
        aws_payload["access_key_id"] = access_key_id
        aws_payload["secret_access_key"] = secret_access_key
        if session_token:
            aws_payload["session_token"] = session_token
        else:
            aws_payload.pop("session_token", None)
    else:
        # Skip storing long-lived keys when user opts out.
        if not store_secrets:
            aws_payload.pop("access_key_id", None)
            aws_payload.pop("secret_access_key", None)
            aws_payload.pop("session_token", None)

    aws_payload["profile"] = profile_value
    aws_payload["region"] = region_value
    aws_payload["mode"] = acquisition_mode
    aws_payload["updated_at"] = _iso_now()
    credentials["aws"] = aws_payload
    console.print(
        f"[green]AWS credentials recorded for profile '{profile_value}'.[/green]"
    )
    return True


def _configure_marquez(
    credentials: dict[str, Any],
    console: Console,
    assume_yes: bool,
    store_secrets: bool,
    no_browser: bool,
) -> bool:
    marquez_payload = credentials.get("marquez", {})
    api_url_default = (
        marquez_payload.get("api_url")
        or os.environ.get("OPENLINEAGE_URL")
        or os.environ.get("VITE_MARQUEZ_API_URL")
        or "http://127.0.0.1:5000/api/v1"
    )

    api_url = _prompt_text(
        message="Marquez API URL",
        default=api_url_default,
        assume_yes=assume_yes,
    )

    if not no_browser and _prompt_confirm(
        message="Open the Marquez web console to register or copy an API key?",
        default=False,
        assume_yes=assume_yes,
    ):
        _open_portal(console, "Marquez console", DEFAULT_MARQUEZ_PORTAL_URL)

    api_key_value: str | None = marquez_payload.get("api_key")
    if store_secrets and _prompt_confirm(
        message="Store a Marquez API key for reuse?",
        default=bool(api_key_value),
        assume_yes=assume_yes,
    ):
        api_key_value = _prompt_text(
            message="Marquez API key",
            default=api_key_value,
            assume_yes=assume_yes,
            password=True,
        )
        marquez_payload["api_key"] = api_key_value
    elif not store_secrets:
        marquez_payload.pop("api_key", None)

    marquez_payload["api_url"] = api_url
    marquez_payload["updated_at"] = _iso_now()
    credentials["marquez"] = marquez_payload
    console.print("[green]Marquez settings recorded.[/green]")
    return True


def _configure_prefect(
    credentials: dict[str, Any],
    console: Console,
    assume_yes: bool,
    store_secrets: bool,
    no_browser: bool,
) -> bool:
    prefect_payload = credentials.get("prefect", {})
    profile_default = (
        prefect_payload.get("profile") or os.environ.get("PREFECT_PROFILE") or "hotpass"
    )
    workspace_default = (
        prefect_payload.get("workspace")
        or os.environ.get("PREFECT_WORKSPACE")
        or "hotpass/staging"
    )

    profile_value = _prompt_text(
        message="Prefect profile (prefect profile ls to inspect)",
        default=profile_default,
        assume_yes=assume_yes,
    )
    workspace_value = _prompt_text(
        message="Prefect workspace",
        default=workspace_default,
        assume_yes=assume_yes,
    )

    api_key_value: str | None = prefect_payload.get("api_key")
    if not no_browser and _prompt_confirm(
        message="Open Prefect Cloud to generate an API key?",
        default=False,
        assume_yes=assume_yes,
    ):
        _open_portal(console, "Prefect Cloud", DEFAULT_PREFECT_PORTAL_URL)

    if store_secrets and _prompt_confirm(
        message="Store a Prefect API key for reuse?",
        default=bool(api_key_value),
        assume_yes=assume_yes,
    ):
        api_key_value = _prompt_text(
            message="Prefect API key",
            default=api_key_value,
            assume_yes=assume_yes,
            password=True,
        )
        prefect_payload["api_key"] = api_key_value
    elif not store_secrets:
        prefect_payload.pop("api_key", None)

    prefect_payload["profile"] = profile_value
    prefect_payload["workspace"] = workspace_value
    prefect_payload["updated_at"] = _iso_now()
    credentials["prefect"] = prefect_payload
    console.print("[green]Prefect settings recorded.[/green]")
    return True


def _offer_vpn_guidance(console: Console, assume_yes: bool, no_browser: bool) -> None:
    console.print(
        Panel(
            "Use `hotpass net lease --via ssh-bastion --host <bastion>` to open a session tunnel.\n"
            "Lease mode keeps the tunnel alive while the command runs and tears it down on exit.",
            title="Connectivity helper",
        )
    )
    if not no_browser and _prompt_confirm(
        message="Open VPN / bastion access documentation?",
        default=False,
        assume_yes=assume_yes,
    ):
        vpn_url = os.environ.get("HOTPASS_VPN_DOC_URL", "https://vpn.example.com")
        _open_portal(console, "VPN guide", vpn_url)


# ---------------------------------------------------------------------------
# Utility helpers


def _load_credentials() -> dict[str, Any]:
    payload = load_state(CREDENTIALS_STATE_FILE, default={})
    if isinstance(payload, dict):
        return payload
    return {}


def _write_credentials(payload: dict[str, Any], console: Console) -> None:
    write_state(CREDENTIALS_STATE_FILE, payload)
    path = state_path(CREDENTIALS_STATE_FILE)
    try:
        os.chmod(path, 0o600)
    except PermissionError:  # pragma: no cover - Windows/non-POSIX
        console.print(
            "[yellow]Warning: unable to set restrictive permissions on credential store.[/yellow]"
        )
    console.print(
        f"[green]Credential store updated at {path}.[/green] "
        "Keep this file outside version control."
    )


def _prompt_confirm(*, message: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes:
        return default
    return cast(bool, Confirm.ask(message, default=default))


def _prompt_text(
    *,
    message: str,
    default: str | None,
    assume_yes: bool,
    password: bool = False,
    allow_empty: bool = False,
) -> str:
    if assume_yes and default is not None:
        return default
    while True:
        response = cast(str, Prompt.ask(message, default=default, password=password))
        if response or allow_empty:
            return response or ""
        Console().print("[red]Response required.[/red]")


def _prompt_choice(
    *,
    message: str,
    choices: list[str],
    default: str,
    assume_yes: bool,
) -> str:
    if assume_yes:
        return default
    return cast(str, Prompt.ask(message, choices=choices, default=default))


def _mask_secret(value: str, *, head: int = 4, tail: int = 2) -> str:
    if len(value) <= head + tail:
        return "*" * len(value)
    return f"{value[:head]}…{value[-tail:]}"


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _open_portal(console: Console, label: str, url: str) -> None:
    try:
        console.print(f"[cyan]Opening {label}: {url}[/cyan]")
        webbrowser.open(url, new=2)
    except webbrowser.Error as exc:  # pragma: no cover - depends on OS integration
        console.print(f"[yellow]Unable to open {label}: {exc}[/yellow]")


def _run_optional_command(
    console: Console, command: list[str], description: str
) -> None:
    if not command:
        return
    if not _command_available(command[0]):
        console.print(
            f"[yellow]Skipping {description}; '{command[0]}' command not available.[/yellow]"
        )
        return
    try:
        console.print(f"[cyan]Running {description}:[/cyan] {format_command(command)}")
        run_command(command, check=True)
    except CommandExecutionError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(
            f"[yellow]{description} failed; continue setup after resolving the issue.[/yellow]"
        )


def _command_available(executable: str) -> bool:
    return bool(shutil.which(executable))


def _aws_cli_available() -> bool:
    return _command_available("aws")


__all__ = ["register", "build"]
