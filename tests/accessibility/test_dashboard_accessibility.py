"""Semantic accessibility tests for the Streamlit dashboard."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, ParamSpec, TypeVar, cast

import hotpass.dashboard as dashboard
import pandas as pd
import pytest

from tests.helpers.assertions import expect
from tests.helpers.pytest_marks import parametrize

pytest.importorskip("streamlit")
pytest.importorskip("nameparser")

P = ParamSpec("P")
R = TypeVar("R")


def accessibility_mark(func: Callable[P, R]) -> Callable[P, R]:  # noqa: UP047
    """Typed wrapper around the ``pytest.mark.accessibility`` decorator."""

    wrapped = pytest.mark.accessibility(func)
    return cast(Callable[P, R], wrapped)


@dataclass
class SidebarCall:
    """Record a sidebar widget invocation."""

    widget: str
    label: str
    kwargs: dict[str, Any] = field(default_factory=dict)


class AccessibilitySidebar:
    """Streamlit sidebar shim capturing accessibility metadata."""

    def __init__(self) -> None:
        self.calls: list[SidebarCall] = []

    def header(self, *_: Any, **__: Any) -> None:
        return None

    def text_input(self, label: str, value: str = "", **kwargs: Any) -> str:
        self.calls.append(SidebarCall("text_input", label, kwargs))
        return value

    def selectbox(self, label: str, options: list[str], **kwargs: Any) -> str:
        self.calls.append(SidebarCall("selectbox", label, kwargs))
        return options[0]

    def number_input(self, label: str, value: int = 0, **kwargs: Any) -> int:
        self.calls.append(SidebarCall("number_input", label, kwargs))
        return value


class AccessibilityStreamlit:
    """Minimal Streamlit shim focusing on accessible semantics."""

    def __init__(self) -> None:
        self.sidebar = AccessibilitySidebar()
        self._button_pressed = False
        self.button_kwargs: dict[str, Any] | None = None
        self.tabs_requested: tuple[str, ...] = ()
        self.spinner_messages: list[str] = []
        self.info_messages: list[str] = []
        self.expanders: list[str] = []

    def set_button_response(self, pressed: bool) -> None:
        self._button_pressed = pressed

    def set_page_config(self, **_: Any) -> None:  # noqa: D401 - shim
        return None

    def title(self, *_: Any, **__: Any) -> None:
        return None

    def markdown(self, message: str, **_: Any) -> None:
        if message.startswith("---"):
            return
        self.info_messages.append(message)

    def caption(self, message: str, **_: Any) -> None:
        self.info_messages.append(message)

    def tabs(self, labels: list[str]) -> tuple[AccessibilityStreamlit, ...]:
        self.tabs_requested = tuple(labels)
        return tuple(self for _ in labels)

    def columns(self, spec: list[int] | tuple[int, ...] | int) -> list[AccessibilityStreamlit]:
        if isinstance(spec, int):
            count = spec
        else:
            count = len(spec)
        return [self for _ in range(count)]

    def button(self, *_: Any, **kwargs: Any) -> bool:
        self.button_kwargs = kwargs
        return self._button_pressed

    def spinner(self, message: str, **_: Any) -> AccessibilityStreamlit:
        self.spinner_messages.append(message)
        return self

    def __enter__(self) -> AccessibilityStreamlit:  # noqa: D401 - shim
        return self

    def __exit__(self, *_: Any) -> Literal[False]:  # noqa: D401 - shim
        return False

    def header(self, *_: Any, **__: Any) -> None:
        return None

    def info(self, message: str, **_: Any) -> None:
        self.info_messages.append(message)

    def success(self, message: str, **_: Any) -> None:
        self.info_messages.append(message)

    def warning(self, *_: Any, **__: Any) -> None:
        return None

    def error(self, *_: Any, **__: Any) -> None:
        return None

    def exception(self, *_: Any, **__: Any) -> None:
        return None

    def metric(self, *_: Any, **__: Any) -> None:
        return None

    def subheader(self, *_: Any, **__: Any) -> None:
        return None

    def expander(self, label: str, **_: Any) -> AccessibilityStreamlit:
        self.expanders.append(label)
        return self

    def json(self, *_: Any, **__: Any) -> None:
        return None

    def dataframe(self, *_: Any, **__: Any) -> None:
        return None


@accessibility_mark
@parametrize("widget", ["text_input", "selectbox", "number_input"])
def test_sidebar_widgets_include_help(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    widget: str,
) -> None:
    """Sidebar widgets must provide descriptive help text for assistive tech users."""

    stub = AccessibilityStreamlit()
    monkeypatch.setattr(dashboard, "st", stub)
    monkeypatch.chdir(tmp_path)
    stub.set_button_response(False)

    dashboard.main()

    calls = [call for call in stub.sidebar.calls if call.widget == widget]
    expect(bool(calls), f"Expected at least one call to {widget}")
    for call in calls:
        help_text = call.kwargs.get("help")
        text = help_text.strip() if isinstance(help_text, str) else ""
        expect(bool(text), f"Help text missing for {call.label}")


@accessibility_mark
def test_run_button_uses_accessible_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Run button must expose accessible tap target and semantic naming."""

    stub = AccessibilityStreamlit()
    monkeypatch.setattr(dashboard, "st", stub)
    monkeypatch.chdir(tmp_path)
    stub.set_button_response(False)

    dashboard.main()

    button_kwargs = stub.button_kwargs
    if button_kwargs is None:  # pragma: no cover - defensive guard for mypy
        pytest.fail("Run button was not configured")
    assert button_kwargs is not None
    expect(button_kwargs.get("type") == "primary", "Run button should use primary styling")
    expect(
        button_kwargs.get("use_container_width") is True,
        "Run button should occupy the available width",
    )


@accessibility_mark
def test_tabs_cover_primary_journeys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tabs should align with pipeline control, execution history, and quality metrics."""

    stub = AccessibilityStreamlit()
    monkeypatch.setattr(dashboard, "st", stub)
    monkeypatch.chdir(tmp_path)
    stub.set_button_response(False)

    dashboard.main()

    expect(
        stub.tabs_requested
        == (
            "Pipeline Control",
            "Execution History",
            "Quality Metrics",
        ),
        "Dashboard tabs should match the expected journeys",
    )


@accessibility_mark
def test_spinner_announces_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Spinner must provide textual status for assistive tech."""

    stub = AccessibilityStreamlit()
    monkeypatch.setattr(dashboard, "st", stub)
    stub.set_button_response(True)
    monkeypatch.chdir(tmp_path)

    class DummyQualityReport:
        def __init__(self) -> None:
            self.expectations_passed = True
            self.invalid_records = 0

        def to_dict(self) -> dict[str, Any]:
            return {"status": "ok"}

    run_result = SimpleNamespace(
        refined=pd.DataFrame({"data_quality_score": [0.9, 0.8]}),
        quality_report=DummyQualityReport(),
    )

    monkeypatch.setattr(dashboard, "get_default_profile", lambda _: SimpleNamespace())
    monkeypatch.setattr(dashboard, "run_pipeline", lambda _: run_result)

    dashboard.main()

    expect(bool(stub.spinner_messages), "Expected spinner to announce status")
    expect(
        any("Running pipeline" in message for message in stub.spinner_messages),
        "Spinner should announce that the pipeline is running",
    )

    history_file = Path("./logs/pipeline_history.json")
    expect(history_file.exists(), "Pipeline history should be written to disk")
    data = json.loads(history_file.read_text())
    expect(bool(data), "History should contain at least one entry")
