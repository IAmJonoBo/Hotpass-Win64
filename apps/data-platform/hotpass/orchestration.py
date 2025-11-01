"""Prefect orchestration for the Hotpass refinement pipeline.

The flow layer coordinates retries, logging, and archiving behaviour around
the core pipeline runner. When Prefect is unavailable the module exposes
lightweight no-op decorators so CLI workflows can continue operating during
unit tests or constrained deployments.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import zipfile
from collections.abc import Awaitable, Callable, Mapping, MutableSequence, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from .artifacts import create_refined_archive
from .config import get_default_profile
from .lineage import (
    build_hotpass_run_facet,
    build_output_datasets,
    create_emitter,
    discover_input_datasets,
)
from .pipeline import PipelineConfig, run_pipeline
from .telemetry.bootstrap import TelemetryBootstrapOptions, telemetry_session

if TYPE_CHECKING:  # pragma: no cover - typing aids
    from hotpass.config_schema import HotpassConfig

F = TypeVar("F", bound=Callable[..., Any])

DecoratorFactory = Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]]

_prefect_flow_decorator: DecoratorFactory | None = None
_prefect_task_decorator: DecoratorFactory | None = None
_prefect_get_run_logger: Callable[..., Any] | None = None


def _noop_prefect_decorator(*_args: Any, **_kwargs: Any) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        return func

    return decorator


try:  # pragma: no cover - verified via unit tests
    from prefect.logging import get_run_logger as prefect_get_run_logger

    from prefect import flow as prefect_flow_decorator
    from prefect import task as prefect_task_decorator
except ImportError:  # pragma: no cover - exercised in fallback tests
    PREFECT_AVAILABLE = False
else:
    PREFECT_AVAILABLE = True
    _prefect_flow_decorator = prefect_flow_decorator
    _prefect_task_decorator = prefect_task_decorator
    _prefect_get_run_logger = prefect_get_run_logger

    if os.getenv("HOTPASS_ENABLE_PREFECT_RUNTIME", "0") != "1":
        PREFECT_AVAILABLE = False
        _prefect_flow_decorator = None
        _prefect_task_decorator = None
        _prefect_get_run_logger = None


def _resolve_prefect_decorator(
    factory: DecoratorFactory | None,
) -> DecoratorFactory:
    """Return the available Prefect decorator or a no-op fallback."""

    if factory is not None:
        return factory

    def _fallback(*_args: Any, **_kwargs: Any) -> Callable[[F], F]:
        return _noop_prefect_decorator(*_args, **_kwargs)

    return _fallback


flow: DecoratorFactory = _resolve_prefect_decorator(_prefect_flow_decorator)
task: DecoratorFactory = _resolve_prefect_decorator(_prefect_task_decorator)


ConcurrencyCallable = Callable[..., AbstractAsyncContextManager[object]]

prefect_concurrency: ConcurrencyCallable | None

try:  # pragma: no cover - optional Prefect feature
    from prefect.concurrency.asyncio import concurrency as _prefect_concurrency
except Exception:  # pragma: no cover - Prefect may be unavailable in tests
    prefect_concurrency = None
else:
    prefect_concurrency = cast(ConcurrencyCallable, _prefect_concurrency)


if _prefect_get_run_logger is not None:

    def get_run_logger(*args: Any, **kwargs: Any) -> logging.Logger:
        """Proxy Prefect's logger helper while supporting the fallback stub."""

        logger_callable = _prefect_get_run_logger
        if logger_callable is None:  # pragma: no cover - defensive
            return logging.getLogger("hotpass.orchestration")

        logger_or_adapter = logger_callable(*args, **kwargs)
        if isinstance(logger_or_adapter, logging.Logger):
            return logger_or_adapter
        adapter_logger = getattr(logger_or_adapter, "logger", None)
        if isinstance(adapter_logger, logging.Logger):
            return adapter_logger
        return logging.getLogger("hotpass.orchestration")

else:

    def get_run_logger(*_args: Any, **_kwargs: Any) -> logging.Logger:
        return logging.getLogger("hotpass.orchestration")


logger = logging.getLogger(__name__)


class PipelineOrchestrationError(RuntimeError):
    """Raised when orchestration helpers encounter unrecoverable errors."""


class AgentApprovalError(PipelineOrchestrationError):
    """Raised when agent requests fail policy or approval checks."""


@dataclass(frozen=True, slots=True)
class PipelineRunOptions:
    """Configuration required to execute the pipeline once."""

    config: HotpassConfig
    profile_name: str | None = None
    runner: Callable[..., Any] | None = None
    runner_kwargs: Mapping[str, Any] | None = None
    telemetry_context: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PipelineRunSummary:
    """Structured payload describing a pipeline execution."""

    success: bool
    total_records: int
    elapsed_seconds: float
    output_path: Path
    quality_report: Mapping[str, Any]
    archive_path: Path | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialise the summary for CLI and Prefect consumers."""

        payload: dict[str, Any] = {
            "success": self.success,
            "total_records": self.total_records,
            "elapsed_seconds": self.elapsed_seconds,
            "quality_report": dict(self.quality_report),
            "output_path": str(self.output_path),
        }
        if self.archive_path is not None:
            payload["archive_path"] = str(self.archive_path)
        return payload


@dataclass(frozen=True, slots=True)
class AgenticRequest:
    """Model a brokered MCP request handed to Prefect."""

    request_id: str
    agent_name: str
    role: str
    tool: str
    action: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AgentToolPolicy:
    """Allowed tools per role and auto-approval rules."""

    allowed_tools_by_role: Mapping[str, frozenset[str]]
    auto_approved_roles: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        normalised = {role: frozenset(tools) for role, tools in self.allowed_tools_by_role.items()}
        object.__setattr__(self, "allowed_tools_by_role", normalised)
        object.__setattr__(self, "auto_approved_roles", frozenset(self.auto_approved_roles))

    def is_tool_allowed(self, role: str, tool: str) -> bool:
        allowed = self.allowed_tools_by_role.get(role)
        if not allowed:
            return False
        return "*" in allowed or tool in allowed

    def requires_manual_approval(self, role: str) -> bool:
        return role not in self.auto_approved_roles


@dataclass(frozen=True, slots=True)
class AgentApprovalDecision:
    """Outcome of a manual review for an agent request."""

    approved: bool
    approver: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class AgentAuditRecord:
    """Audit trail entry produced for each agent action."""

    request_id: str
    agent_name: str
    role: str
    tool: str
    action: str
    status: str
    approved: bool
    approver: str
    timestamp: datetime
    notes: str | None = None
    result: Mapping[str, Any] | None = None


def _normalise_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(parameters, dict):
        return parameters
    return {key: parameters[key] for key in parameters}


def _pipeline_options_from_request(request: AgenticRequest) -> PipelineRunOptions:
    parameters = _normalise_parameters(request.parameters)
    pipeline_payload = parameters.get("pipeline")
    if not isinstance(pipeline_payload, Mapping):
        raise AgentApprovalError("Agent request missing pipeline configuration payload")

    payload = _normalise_parameters(pipeline_payload)
    try:
        input_dir = Path(str(payload["input_dir"]))
        output_path = Path(str(payload["output_path"]))
        profile_name = str(payload.get("profile_name", "aviation"))
    except KeyError as exc:  # pragma: no cover - defensive, asserted via tests
        raise AgentApprovalError(f"Missing pipeline parameter: {exc.args[0]}") from exc

    archive = bool(payload.get("archive", False))
    archive_dir_value = payload.get("archive_dir")
    excel_chunk_size_value = payload.get("excel_chunk_size")

    config_updates: dict[str, Any] = {
        "pipeline": {
            "input_dir": input_dir,
            "output_path": output_path,
            "archive": archive,
        }
    }

    if archive_dir_value is not None:
        config_updates["pipeline"]["dist_dir"] = Path(str(archive_dir_value))
    if excel_chunk_size_value is not None:
        config_updates["pipeline"]["excel_chunk_size"] = int(excel_chunk_size_value)

    from hotpass.config_schema import HotpassConfig

    config = HotpassConfig().merge(config_updates)

    if profile_name:
        industry = get_default_profile(profile_name)
        config = config.merge({"profile": industry.to_dict()})

    return PipelineRunOptions(
        config=config,
        profile_name=profile_name,
        telemetry_context={"hotpass.command": "agentic.run"},
    )


@task(name="evaluate-agent-request", retries=0)
def evaluate_agent_request(
    request: AgenticRequest,
    policy: AgentToolPolicy,
    approval: AgentApprovalDecision | None = None,
) -> AgentApprovalDecision:
    """Validate the agent request against the policy and manual approvals."""

    logger = get_run_logger()
    if not policy.is_tool_allowed(request.role, request.tool):
        reason = f"Role '{request.role}' is not permitted to use tool '{request.tool}'"
        _safe_log(logger, logging.WARNING, reason)
        raise AgentApprovalError(reason)

    if policy.requires_manual_approval(request.role):
        if approval is None or not approval.approved:
            reason = "Manual approval required for role"
            _safe_log(logger, logging.WARNING, reason)
            raise AgentApprovalError(reason)
        return approval

    if approval is not None:
        if not approval.approved:
            reason = approval.notes or "Manual approval denied"
            _safe_log(logger, logging.WARNING, reason)
            raise AgentApprovalError(reason)
        return approval

    auto_approver = f"policy:{request.role}"
    _safe_log(logger, logging.INFO, "Auto-approving agent request %s", request.request_id)
    return AgentApprovalDecision(
        approved=True,
        approver=auto_approver,
        notes="Auto-approved by policy",
    )


@task(name="log-agent-action", retries=0)
def log_agent_action(
    record: AgentAuditRecord,
    log_sink: MutableSequence[AgentAuditRecord] | None = None,
) -> AgentAuditRecord:
    """Persist agent audit records to a sink and Prefect logs."""

    logger = get_run_logger()
    _safe_log(
        logger,
        logging.INFO,
        "Agent %s performed %s (status=%s, approved=%s)",
        record.agent_name,
        record.action,
        record.status,
        record.approved,
    )
    if log_sink is not None:
        log_sink.append(record)
    return record


def broker_agent_run(
    request: AgenticRequest,
    policy: AgentToolPolicy,
    *,
    approval: AgentApprovalDecision | None = None,
    log_sink: MutableSequence[AgentAuditRecord] | None = None,
) -> PipelineRunSummary:
    """Broker an agent-triggered pipeline execution with approvals and logging."""

    timestamp = datetime.now(tz=UTC)
    try:
        decision = evaluate_agent_request(request=request, policy=policy, approval=approval)
    except AgentApprovalError as exc:
        log_agent_action(
            AgentAuditRecord(
                request_id=request.request_id,
                agent_name=request.agent_name,
                role=request.role,
                tool=request.tool,
                action=request.action,
                status="denied",
                approved=False,
                approver=("manual" if policy.requires_manual_approval(request.role) else "policy"),
                timestamp=timestamp,
                notes=str(exc),
            ),
            log_sink,
        )
        raise

    log_agent_action(
        AgentAuditRecord(
            request_id=request.request_id,
            agent_name=request.agent_name,
            role=request.role,
            tool=request.tool,
            action=request.action,
            status="approved",
            approved=True,
            approver=decision.approver,
            timestamp=timestamp,
            notes=decision.notes,
        ),
        log_sink,
    )

    options = _pipeline_options_from_request(request)

    try:
        summary = run_pipeline_once(options)
    except Exception as exc:  # pragma: no cover - exercised via unit tests
        log_agent_action(
            AgentAuditRecord(
                request_id=request.request_id,
                agent_name=request.agent_name,
                role=request.role,
                tool=request.tool,
                action=request.action,
                status="failed",
                approved=True,
                approver=decision.approver,
                timestamp=datetime.now(tz=UTC),
                notes=str(exc),
            ),
            log_sink,
        )
        raise

    log_agent_action(
        AgentAuditRecord(
            request_id=request.request_id,
            agent_name=request.agent_name,
            role=request.role,
            tool=request.tool,
            action=request.action,
            status="executed",
            approved=True,
            approver=decision.approver,
            timestamp=datetime.now(tz=UTC),
            result=summary.to_payload(),
        ),
        log_sink,
    )

    return summary


def _safe_log(logger_: logging.Logger, level: int, message: str, *args: Any) -> None:
    """Log a message while suppressing ValueErrors raised by closed handlers."""

    try:
        logger_.log(level, message, *args)
    except ValueError:  # pragma: no cover - depends on interpreter shutdown timing
        return None


def build_pipeline_job_name(config: PipelineConfig) -> str:
    """Construct a stable OpenLineage job name for pipeline executions."""

    profile = getattr(config, "industry_profile", None)
    profile_name = getattr(profile, "name", None)
    candidate = profile_name or config.expectation_suite_name or config.output_path.stem
    component = _sanitise_component(str(candidate)) or "refinement"
    return ".".join(("hotpass", "pipeline", component.lower()))


def _execute_pipeline(
    config: PipelineConfig,
    *,
    runner: Callable[..., Any],
    runner_kwargs: Mapping[str, Any] | None,
    archive: bool,
    archive_dir: Path | None,
) -> PipelineRunSummary:
    """Execute the pipeline runner and return a structured summary."""

    input_datasets = discover_input_datasets(config.input_dir)
    facets = build_hotpass_run_facet(
        profile=_resolve_profile_name(config),
        source_spreadsheet=_first_dataset_name(input_datasets),
        research_enabled=_research_enabled(),
    )
    emitter = create_emitter(
        build_pipeline_job_name(config),
        run_id=config.run_id,
        facets=facets,
    )
    emitter.emit_start(inputs=input_datasets)

    archive_path: Path | None = None
    try:
        start_time = time.time()
        result = runner(config, **(runner_kwargs or {}))
        elapsed = time.time() - start_time

        quality_report_dict: dict[str, Any] = {}
        success = True
        quality_report = getattr(result, "quality_report", None)
        if quality_report is not None:
            to_dict = getattr(quality_report, "to_dict", None)
            if callable(to_dict):
                quality_report_dict = cast(dict[str, Any], to_dict())
            success = bool(getattr(quality_report, "expectations_passed", True))

        if archive:
            archive_root = archive_dir or config.output_path.parent
            try:
                archive_root = Path(archive_root)
                archive_root.mkdir(parents=True, exist_ok=True)
                archive_path = create_refined_archive(
                    excel_path=config.output_path,
                    archive_dir=archive_root,
                )
            except Exception as exc:  # pragma: no cover - exercised via unit tests
                raise PipelineOrchestrationError(f"Failed to create archive: {exc}") from exc

        total_records = len(getattr(result, "refined", []))
    except Exception as exc:
        emitter.emit_fail(str(exc), outputs=build_output_datasets(config.output_path))
        raise

    summary = PipelineRunSummary(
        success=success,
        total_records=total_records,
        elapsed_seconds=elapsed,
        output_path=config.output_path,
        quality_report=quality_report_dict,
        archive_path=archive_path,
    )

    emitter.emit_complete(outputs=build_output_datasets(config.output_path, archive_path))
    return summary


def run_pipeline_once(options: PipelineRunOptions) -> PipelineRunSummary:
    """Execute the pipeline once using shared orchestration helpers."""

    config = options.config
    runner = options.runner or run_pipeline
    pipeline_config = config.to_pipeline_config()
    enhanced_config = config.to_enhanced_config()

    telemetry_options = TelemetryBootstrapOptions(
        enabled=enhanced_config.enable_observability,
        service_name=enhanced_config.telemetry_service_name,
        environment=enhanced_config.telemetry_environment,
        exporters=enhanced_config.telemetry_exporters,
        resource_attributes=enhanced_config.telemetry_attributes,
        exporter_settings=enhanced_config.telemetry_exporter_settings,
    )
    telemetry_context: dict[str, str] = {}
    if options.telemetry_context:
        for key, value in options.telemetry_context.items():
            if value is None:
                continue
            telemetry_context[str(key)] = str(value)
    telemetry_context.setdefault("hotpass.command", "prefect.run_pipeline_once")
    if options.profile_name:
        telemetry_context["hotpass.profile"] = str(options.profile_name)
    if pipeline_config.run_id:
        telemetry_context["hotpass.run_id"] = str(pipeline_config.run_id)

    runner_kwargs = dict(options.runner_kwargs or {})

    with telemetry_session(telemetry_options, additional_attributes=telemetry_context) as metrics:
        runner_name = getattr(runner, "__name__", "")
        if metrics is not None and runner_name == "run_enhanced_pipeline":
            runner_kwargs.setdefault("metrics", metrics)

        return _execute_pipeline(
            pipeline_config,
            runner=runner,
            runner_kwargs=runner_kwargs or None,
            archive=config.pipeline.archive,
            archive_dir=config.pipeline.dist_dir,
        )


@task(name="run-pipeline", retries=2, retry_delay_seconds=10)
def run_pipeline_task(
    config: PipelineConfig,
) -> dict[str, Any]:
    """Run the Hotpass pipeline as a Prefect task.

    Args:
        config: Pipeline configuration

    Returns:
        Pipeline execution results
    """
    logger = get_run_logger()
    _safe_log(logger, logging.INFO, "Running pipeline with input_dir=%s", config.input_dir)

    summary = _execute_pipeline(
        config,
        runner=run_pipeline,
        runner_kwargs=None,
        archive=False,
        archive_dir=None,
    )

    _safe_log(
        logger,
        logging.INFO,
        "Pipeline completed in %.2f seconds - %d organizations processed",
        summary.elapsed_seconds,
        summary.total_records,
    )

    payload = summary.to_payload()

    def _coerce_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return bool(value)
        return False

    payload["backfill"] = _coerce_flag(getattr(config, "backfill", False))
    payload["incremental"] = _coerce_flag(getattr(config, "incremental", False))

    since_value = getattr(config, "since", None)
    if isinstance(since_value, datetime):
        payload["since"] = since_value.isoformat()
    elif isinstance(since_value, str):
        payload["since"] = since_value

    return payload


def _lookup_nested(mapping: Mapping[str, Any] | None, keys: tuple[str, ...]) -> Any | None:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _sanitise_component(value: str) -> str:
    cleaned = value.replace("\\", "-").replace("/", "-").strip()
    return cleaned or "default"


def _resolve_profile_name(config: PipelineConfig) -> str | None:
    profile = getattr(config, "industry_profile", None)
    candidate = getattr(profile, "name", None)
    if candidate:
        return str(candidate)
    expectation = getattr(config, "expectation_suite_name", None)
    if expectation:
        return str(expectation)
    return None


def _first_dataset_name(datasets: Sequence[Any]) -> str | None:
    for dataset in datasets:
        if isinstance(dataset, Mapping):
            name = dataset.get("name")
            if name:
                return str(name)
        elif isinstance(dataset, Path):
            return str(dataset)
        else:
            candidate = str(dataset).strip()
            if candidate:
                return candidate
    return None


def _research_enabled() -> bool:
    feature = os.getenv("FEATURE_ENABLE_REMOTE_RESEARCH", "0").lower()
    allow = os.getenv("ALLOW_NETWORK_RESEARCH", "false").lower()
    truthy = {"1", "true", "yes", "on"}
    return feature in truthy and allow in truthy


def _format_archive_path(root: Path, pattern: str, run_date: date, version: str) -> Path:
    try:
        relative = pattern.format(date=run_date, version=version)
    except Exception as exc:  # pragma: no cover - formatting errors are unexpected
        msg = f"Invalid archive pattern '{pattern}': {exc}"
        raise PipelineOrchestrationError(msg) from exc
    return (root / Path(relative)).expanduser()


@task(name="rehydrate-archive", retries=2, retry_delay_seconds=5)
def rehydrate_archive_task(archive_path: Path, restore_dir: Path) -> Path:
    if not archive_path.exists():
        msg = f"Archive not found: {archive_path}"
        raise FileNotFoundError(msg)
    if restore_dir.exists():
        shutil.rmtree(restore_dir)
    restore_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zip_handle:
        zip_handle.extractall(restore_dir)
    return restore_dir


ThreadRunner = Callable[[Callable[[], PipelineRunSummary]], Awaitable[PipelineRunSummary]]


async def _run_with_prefect_concurrency(
    concurrency: ConcurrencyCallable,
    key: str,
    slots: int,
    callback: Callable[[], PipelineRunSummary],
    *,
    run_sync: ThreadRunner | None = None,
) -> PipelineRunSummary:
    """Execute the callback while holding a Prefect concurrency slot."""

    if run_sync is None:
        from anyio import to_thread

        run_sync = to_thread.run_sync

    try:
        async with concurrency(key, occupy=slots):
            result = await run_sync(callback)
            return result
    except Exception as exc:  # pragma: no cover - concurrency fallback
        _safe_log(
            logger,
            logging.WARNING,
            "Prefect concurrency unavailable for key %s (%s); running synchronously.",
            key,
            exc,
        )
        return await run_sync(callback)


def _execute_with_concurrency(
    key: str,
    slots: int,
    callback: Callable[[], PipelineRunSummary],
) -> PipelineRunSummary:
    concurrency = prefect_concurrency
    if concurrency is None or slots <= 0:
        return callback()

    try:
        import anyio
    except Exception:  # pragma: no cover - fallback when anyio missing
        return callback()

    try:
        result = anyio.run(
            _run_with_prefect_concurrency,
            concurrency,
            key,
            slots,
            callback,
        )
        return cast(PipelineRunSummary, result)
    except Exception as exc:  # pragma: no cover - execution fallback
        _safe_log(
            logger,
            logging.WARNING,
            "Failed to acquire Prefect concurrency for key %s (%s); running synchronously.",
            key,
            exc,
        )
        return callback()


def _coerce_run_date(raw: str | date) -> date:
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        msg = f"Invalid run_date value: {raw}"
        raise PipelineOrchestrationError(msg) from exc


def _coerce_since(raw: datetime | str | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        candidate = raw
    else:
        try:
            candidate = datetime.fromisoformat(str(raw))
        except ValueError as exc:
            msg = f"Invalid since value: {raw}"
            raise PipelineOrchestrationError(msg) from exc
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=UTC)
    return candidate


@flow(name="hotpass-backfill", log_prints=True, validate_parameters=False)
def backfill_pipeline_flow(
    runs: Sequence[Mapping[str, Any]] | Sequence[dict[str, Any]],
    *,
    archive_root: str,
    restore_root: str,
    archive_pattern: str = "hotpass-inputs-{date:%Y%m%d}-v{version}.zip",
    base_config: Mapping[str, Any] | None = None,
    parameters: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    concurrency_limit: int = 1,
    concurrency_key: str = "hotpass/backfill",
) -> dict[str, Any]:
    logger = get_run_logger()

    runs_normalised: list[dict[str, str]] = []
    for entry in runs:
        run_date_raw = entry.get("run_date")
        version_raw = entry.get("version")
        if run_date_raw is None or version_raw is None:
            msg = "Each run must include 'run_date' and 'version' keys"
            raise PipelineOrchestrationError(msg)
        run_date_value = _coerce_run_date(run_date_raw)
        version_value = str(version_raw)
        runs_normalised.append({"run_date": run_date_value.isoformat(), "version": version_value})

    archive_root_path = Path(archive_root)
    restore_root_path = Path(restore_root)
    restore_root_path.mkdir(parents=True, exist_ok=True)
    outputs_root = restore_root_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)

    from hotpass.config_schema import HotpassConfig

    if base_config is None:
        base_payload: Mapping[str, Any] = HotpassConfig().model_dump(mode="python")
    else:
        base_candidate: object = base_config
        if not isinstance(base_candidate, Mapping):
            msg = "base_config must be a mapping if provided"
            raise PipelineOrchestrationError(msg)
        base_payload = cast(Mapping[str, Any], base_candidate)

    total_records = 0
    total_elapsed = 0.0
    successes = 0
    run_payloads: list[dict[str, Any]] = []

    for run in runs_normalised:
        iso_date = run["run_date"]
        version = run["version"]
        run_date_value = _coerce_run_date(iso_date)
        archive_path = _format_archive_path(
            archive_root_path,
            archive_pattern,
            run_date_value,
            version,
        )
        restore_dir = restore_root_path / f"{iso_date}--{_sanitise_component(version)}"

        _safe_log(
            logger,
            logging.INFO,
            "Rehydrating archive %s to %s",
            archive_path,
            restore_dir,
        )

        try:
            extracted = rehydrate_archive_task(archive_path, restore_dir)
        except FileNotFoundError as exc:
            msg = f"Archived inputs not found for {iso_date} version {version}: {archive_path}"
            raise PipelineOrchestrationError(msg) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            msg = f"Failed to extract archive for {iso_date} version {version}: {exc}"
            raise PipelineOrchestrationError(msg) from exc

        config_model = HotpassConfig.model_validate(dict(base_payload))
        if parameters:
            config_model = config_model.merge(parameters)
        if telemetry:
            config_model = config_model.merge({"telemetry": telemetry})

        output_path = outputs_root / f"refined-{iso_date}-{_sanitise_component(version)}.xlsx"
        run_updates: dict[str, Any] = {
            "pipeline": {
                "input_dir": extracted,
                "output_path": output_path,
                "dist_dir": outputs_root,
                "backfill": True,
                "incremental": False,
                "run_id": f"backfill-{iso_date}-{_sanitise_component(version)}",
            }
        }
        if _lookup_nested(parameters, ("pipeline", "archive")) is None:
            run_updates["pipeline"]["archive"] = False
        if _lookup_nested(parameters, ("pipeline", "since")) is None:
            run_updates["pipeline"]["since"] = datetime.combine(
                run_date_value, datetime.min.time(), tzinfo=UTC
            )

        config_model = config_model.merge(run_updates)

        def _invoke(
            config_snapshot: HotpassConfig = config_model,
            *,
            run_version: str = version,
            run_date_value: str = iso_date,
        ) -> PipelineRunSummary:
            profile_name = None
            profile = getattr(config_snapshot, "profile", None)
            if profile is not None:
                profile_name = getattr(profile, "name", None)
            return run_pipeline_once(
                PipelineRunOptions(
                    config=config_snapshot,
                    profile_name=profile_name,
                    telemetry_context={
                        "hotpass.command": "prefect.backfill_flow",
                        "hotpass.flow": "hotpass-backfill",
                        "hotpass.backfill.version": run_version,
                        "hotpass.backfill.date": run_date_value,
                    },
                )
            )

        summary = _execute_with_concurrency(concurrency_key, concurrency_limit, _invoke)

        total_records += summary.total_records
        total_elapsed += summary.elapsed_seconds
        if summary.success:
            successes += 1

        run_payload = summary.to_payload()
        run_payload.update({"run_date": iso_date, "version": version})
        run_payloads.append(run_payload)

    metrics = {
        "total_runs": len(run_payloads),
        "successful_runs": successes,
        "failed_runs": len(run_payloads) - successes,
        "total_records": total_records,
        "total_elapsed_seconds": total_elapsed,
    }

    _safe_log(
        logger,
        logging.INFO,
        "Completed backfill window - %d runs, %d successes",
        metrics["total_runs"],
        metrics["successful_runs"],
    )

    return {"runs": run_payloads, "metrics": metrics}


@flow(name="hotpass-refinement-pipeline", log_prints=True, validate_parameters=False)
def refinement_pipeline_flow(
    input_dir: str = "./data",
    output_path: str = "./data/refined_data.xlsx",
    profile_name: str = "aviation",
    excel_chunk_size: int | None = None,
    archive: bool = False,
    dist_dir: str = "./dist",
    backfill: bool = False,
    incremental: bool = False,
    since: datetime | str | None = None,
    telemetry_enabled: bool | None = None,
    telemetry_exporters: Sequence[str] | None = None,
    telemetry_service_name: str | None = None,
    telemetry_environment: str | None = None,
    telemetry_resource_attributes: Mapping[str, str] | None = None,
    telemetry_otlp_endpoint: str | None = None,
    telemetry_otlp_metrics_endpoint: str | None = None,
    telemetry_otlp_headers: Mapping[str, str] | None = None,
    telemetry_otlp_insecure: bool | None = None,
    telemetry_otlp_timeout: float | None = None,
) -> dict[str, Any]:
    """Main Hotpass refinement pipeline as a Prefect flow.

    Args:
        input_dir: Directory containing input Excel files
        output_path: Path for the output refined workbook
        profile_name: Name of the industry profile to use
        excel_chunk_size: Optional chunk size for Excel reading
        archive: Whether to create a packaged archive
        dist_dir: Directory for archive output

    Returns:
        Pipeline execution results dictionary
    """
    logger = get_run_logger()
    _safe_log(
        logger,
        logging.INFO,
        "Starting Hotpass refinement pipeline (profile=%s, backfill=%s, incremental=%s, since=%s)",
        profile_name,
        backfill,
        incremental,
        since,
    )

    from hotpass.config_schema import HotpassConfig

    resolved_since = _coerce_since(since)

    run_id = None
    flow_run_name = None
    scheduled_start_time = None
    try:
        from prefect.runtime import flow_run

        run_id = getattr(flow_run, "id", None)
        flow_run_name = getattr(flow_run, "name", None)
        scheduled_start_time = getattr(flow_run, "expected_start_time", None)
        _safe_log(
            logger,
            logging.DEBUG,
            "Prefect runtime resolved (run_id=%s, name=%s, scheduled=%s)",
            run_id,
            flow_run_name,
            scheduled_start_time,
        )
    except Exception:  # pragma: no cover - runtime availability only
        pass

    config_updates: dict[str, Any] = {
        "pipeline": {
            "input_dir": Path(input_dir),
            "output_path": Path(output_path),
            "archive": archive,
            "dist_dir": Path(dist_dir),
            "backfill": bool(backfill),
            "incremental": bool(incremental),
        }
    }
    telemetry_updates: dict[str, Any] = {}
    if resolved_since is not None:
        config_updates["pipeline"]["since"] = resolved_since
    if run_id:
        config_updates["pipeline"]["run_id"] = run_id
    if flow_run_name:
        config_updates.setdefault("orchestrator", {})["run_name_template"] = flow_run_name

    if excel_chunk_size is not None:
        config_updates["pipeline"]["excel_chunk_size"] = int(excel_chunk_size)

    if telemetry_enabled is not None:
        telemetry_updates["enabled"] = bool(telemetry_enabled)
    if telemetry_exporters:
        telemetry_updates["exporters"] = tuple(telemetry_exporters)
    if telemetry_service_name:
        telemetry_updates["service_name"] = telemetry_service_name
    if telemetry_environment:
        telemetry_updates["environment"] = telemetry_environment
    if telemetry_resource_attributes:
        telemetry_updates["resource_attributes"] = dict(telemetry_resource_attributes)
    if telemetry_otlp_endpoint:
        telemetry_updates["otlp_endpoint"] = telemetry_otlp_endpoint
    if telemetry_otlp_metrics_endpoint:
        telemetry_updates["otlp_metrics_endpoint"] = telemetry_otlp_metrics_endpoint
    if telemetry_otlp_headers:
        telemetry_updates["otlp_headers"] = dict(telemetry_otlp_headers)
    if telemetry_otlp_insecure is not None:
        telemetry_updates["otlp_insecure"] = bool(telemetry_otlp_insecure)
    if telemetry_otlp_timeout is not None:
        telemetry_updates["otlp_timeout"] = float(telemetry_otlp_timeout)

    if telemetry_updates:
        config_updates["telemetry"] = telemetry_updates

    config = HotpassConfig().merge(config_updates)
    profile = get_default_profile(profile_name)

    profile_payload: Mapping[str, Any] | None = None
    model_dump = getattr(profile, "model_dump", None)
    if callable(model_dump):
        candidate = model_dump()
        if isinstance(candidate, Mapping):
            profile_payload = candidate
    if profile_payload is None and hasattr(profile, "to_dict"):
        candidate = profile.to_dict()
        if isinstance(candidate, Mapping):
            profile_payload = candidate
    if profile_payload is None and isinstance(profile, Mapping):
        profile_payload = profile

    if profile_payload is not None:
        config = config.merge({"profile": profile_payload})

    telemetry_context = {
        "hotpass.command": "prefect.refinement_flow",
        "hotpass.flow": "hotpass-refinement-pipeline",
    }
    if run_id:
        telemetry_context["prefect.flow_run_id"] = str(run_id)
    if flow_run_name:
        telemetry_context["prefect.flow_run_name"] = str(flow_run_name)
    if scheduled_start_time is not None:
        telemetry_context["prefect.scheduled_start"] = str(scheduled_start_time)

    summary = run_pipeline_once(
        PipelineRunOptions(
            config=config,
            profile_name=profile_name,
            telemetry_context=telemetry_context,
        )
    )

    payload = summary.to_payload()
    if run_id:
        payload["run_id"] = run_id
    if resolved_since is not None:
        payload["since"] = resolved_since.isoformat()
    payload["backfill"] = bool(backfill)
    payload["incremental"] = bool(incremental)

    _safe_log(
        logger,
        logging.INFO,
        "Pipeline flow completed - Status: %s",
        "SUCCESS" if summary.success else "VALIDATION_FAILED",
    )

    return payload
