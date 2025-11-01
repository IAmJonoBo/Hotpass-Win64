# noqa: E402
"""Dashboard helper behaviour tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from tests.helpers.fixtures import fixture

_STREAMLIT_MODULE = cast(Any, ModuleType("streamlit"))
_STREAMLIT_MODULE.sidebar = SimpleNamespace(
    header=lambda *args, **kwargs: None,
    text_input=lambda *args, **kwargs: "",
    button=lambda *args, **kwargs: False,
)
_STREAMLIT_MODULE.session_state = {}
_STREAMLIT_MODULE.success = lambda *args, **kwargs: None
_STREAMLIT_MODULE.error = lambda *args, **kwargs: None
_STREAMLIT_MODULE.warning = lambda *args, **kwargs: None
sys.modules.setdefault("streamlit", _STREAMLIT_MODULE)

from hotpass import dashboard  # noqa: E402
from hotpass.dashboard import (
    ALLOWED_ROOTS_ENV,  # noqa: E402
    AUTH_PASSWORD_ENV,
    AUTH_STATE_KEY,
    _ensure_path_within_allowlist,
    _load_allowed_roots,
    _require_authentication,
    _validate_input_directory,
    _validate_output_path,
    load_pipeline_history,
    save_pipeline_run,
)

from tests.helpers.assertions import expect  # noqa: E402


def _dashboard_streamlit() -> Any:
    """Return the Streamlit module exposed by the dashboard with ``Any`` typing."""

    return cast(Any, dashboard.st)


class _SidebarStub:
    def __init__(self, *, password: str, button: bool) -> None:
        self._password = password
        self._button = button
        self.header_called = False

    def header(self, *_args: Any, **_kwargs: Any) -> None:
        self.header_called = True

    def text_input(self, *_args: Any, **_kwargs: Any) -> str:
        return self._password

    def button(self, *_args: Any, **_kwargs: Any) -> bool:
        return self._button


class _StreamlitStub:
    def __init__(self, sidebar: _SidebarStub) -> None:
        self.sidebar = sidebar
        self.session_state: dict[str, Any] = {}
        self.success_messages: list[str] = []
        self.error_messages: list[str] = []
        self.warnings: list[str] = []

    def success(self, message: str) -> None:
        self.success_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


@fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [ALLOWED_ROOTS_ENV, AUTH_PASSWORD_ENV]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        dashboard,
        "st",
        _StreamlitStub(_SidebarStub(password="", button=False)),
        raising=False,
    )


def test_load_allowed_roots_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ALLOWED_ROOTS_ENV, raising=False)
    roots = _load_allowed_roots()
    expect(len(roots) == 3, "Default allowlist should expose three directories")
    expect(str(roots[0]).endswith("data"), "Default entry should include data directory")


def test_load_allowed_roots_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidate = os.pathsep.join([str(tmp_path / "one"), str(tmp_path / "two")])
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, candidate)
    roots = _load_allowed_roots()
    expect(
        {root.name for root in roots} == {"one", "two"},
        "Environment entries should be honoured",
    )


def test_ensure_path_within_allowlist_rejects_outside(tmp_path: Path) -> None:
    allowed = [tmp_path / "inside"]
    allowed[0].mkdir()
    outside = tmp_path / "outside" / "data.csv"
    outside.parent.mkdir()

    _ensure_path_within_allowlist(allowed[0] / "file.txt", allowed, description="input")

    try:
        _ensure_path_within_allowlist(outside, allowed, description="output")
    except ValueError as exc:
        expect("outside" in str(exc), "Error should mention offending path")
    else:  # pragma: no cover - defensive guard
        raise AssertionError("ValueError expected for disallowed paths")


def test_validate_directory_helpers_return_resolved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = [tmp_path]
    resolved = _validate_input_directory(tmp_path, allowed)
    expect(resolved == tmp_path, "Input directory should resolve as-is")

    output_file = tmp_path / "results" / "out.xlsx"
    output_file.parent.mkdir()
    resolved_output = _validate_output_path(output_file, allowed)
    expect(resolved_output == output_file, "Output path should resolve and pass validation")

    with pytest.raises(ValueError):
        _validate_output_path(tmp_path.parent / "out.xlsx", allowed)


def test_require_authentication_without_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AUTH_PASSWORD_ENV, raising=False)
    cast(dict[str, Any], _dashboard_streamlit().session_state).clear()
    expect(_require_authentication(), "No password configured should allow access")


def test_require_authentication_with_session_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(AUTH_PASSWORD_ENV, "secret")
    cast(dict[str, Any], _dashboard_streamlit().session_state)[AUTH_STATE_KEY] = True
    expect(_require_authentication(), "Existing session flag should bypass prompt")


def test_require_authentication_success_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    sidebar = _SidebarStub(password="secret", button=True)
    stub = _StreamlitStub(sidebar)
    monkeypatch.setenv(AUTH_PASSWORD_ENV, "secret")
    monkeypatch.setattr(dashboard, "st", stub)

    allowed = _require_authentication()

    expect(allowed, "Correct password should unlock dashboard")
    expect(bool(stub.success_messages), "Success message should be emitted on unlock")
    expect(
        stub.session_state[AUTH_STATE_KEY] is True,
        "Session flag should be set after unlock",
    )


def test_load_and_save_pipeline_history(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    initial = load_pipeline_history(history_file)
    expect(initial == [], "Missing history file should return empty list")

    save_pipeline_run(history_file, {"status": "ok"})
    save_pipeline_run(history_file, {"status": "retry"})

    loaded = load_pipeline_history(history_file)
    expect(len(loaded) == 2, "History should append successive runs")
    expect(loaded[0]["status"] == "ok", "Entries should persist in order")


def test_load_pipeline_history_handles_invalid_structure(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps({"not": "a list"}))

    loaded = load_pipeline_history(history_file)
    expect(loaded == [], "Non-list history should coerce to empty list")
