"""Profile loading and validation for the unified Hotpass CLI."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hotpass.config_schema import HotpassConfig
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

yaml: Any | None
try:  # pragma: no cover - optional dependency for YAML profiles
    import yaml
except Exception:  # pragma: no cover - fallback when PyYAML missing
    yaml = None


class ProfileNotFoundError(FileNotFoundError):
    """Raised when a profile cannot be located in configured search paths."""


class ProfileValidationError(ValueError):
    """Raised when a profile file fails schema validation."""


class ProfileIntentError(ProfileValidationError):
    """Raised when sensitive features are enabled without an explicit intent."""


class FeatureFlags(BaseModel):
    """Feature toggles that map to optional Hotpass capabilities."""

    entity_resolution: bool = False
    enrichment: bool = False
    geospatial: bool = False
    compliance: bool = False
    observability: bool = False
    dashboards: bool = False


class OrchestratorPreset(BaseModel):
    """Declarative orchestrator configuration mapping to Prefect presets."""

    deployment: str | None = None
    work_pool: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CLIProfile(BaseModel):
    """Validated representation of a CLI configuration profile."""

    name: str
    summary: str | None = None
    expectation_suite: str | None = None
    country_code: str | None = None
    industry_profile: str | None = None
    qa_mode: str | None = Field(default=None, pattern=r"^(default|strict|relaxed)$")
    log_format: str | None = Field(default=None, pattern=r"^(json|rich)$")
    observability: bool | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    config_files: list[Path] = Field(default_factory=list)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    orchestrator: OrchestratorPreset | None = None
    declared_intent: list[str] = Field(default_factory=list, alias="intent")
    path: Path | None = Field(default=None, exclude=True)

    @field_validator("config_files", mode="before")
    @classmethod
    def _coerce_paths(cls, values: Iterable[str | Path] | None) -> list[Path]:
        if not values:
            return []
        return [Path(value) for value in values]

    @model_validator(mode="after")
    def _ensure_intent(self) -> CLIProfile:
        if (self.features.enrichment or self.features.compliance) and not self.declared_intent:
            raise ProfileIntentError(
                "Profiles enabling enrichment or compliance must declare intent statements "
                "via the 'intent' field."
            )
        return self

    def apply(self, options: dict[str, Any]) -> dict[str, Any]:
        """Apply profile defaults to a mutable options dictionary."""

        merged = dict(options)
        if self.expectation_suite is not None:
            merged["expectation_suite_name"] = self.expectation_suite
        if self.country_code is not None:
            merged["country_code"] = self.country_code
        if self.log_format is not None:
            merged["log_format"] = self.log_format
        if self.qa_mode is not None:
            merged["qa_mode"] = self.qa_mode
        if self.observability is not None:
            merged["observability"] = self.observability
        merged.update(self.options)
        return merged

    def resolved_config_files(self) -> list[Path]:
        """Return config file paths resolved relative to the profile location."""

        if not self.config_files:
            return []
        resolved: list[Path] = []
        if self.path is None:
            base_dir = None
        else:
            base_dir = self.path.parent
        for candidate in self.config_files:
            candidate_path = Path(candidate)
            if not candidate_path.is_absolute() and base_dir is not None:
                candidate_path = (base_dir / candidate_path).resolve()
            elif not candidate_path.is_absolute():
                candidate_path = candidate_path.resolve()
            resolved.append(candidate_path)
        return resolved

    def feature_payload(self) -> dict[str, bool]:
        """Expose feature toggles as a plain dictionary for downstream consumers."""

        return self.features.model_dump()

    def apply_to_config(self, config: HotpassConfig) -> HotpassConfig:
        """Merge profile-defined defaults into a canonical configuration object."""

        pipeline_updates: dict[str, Any] = {}
        if self.expectation_suite is not None:
            pipeline_updates["expectation_suite"] = self.expectation_suite
        if self.country_code is not None:
            pipeline_updates["country_code"] = self.country_code
        if self.log_format is not None:
            pipeline_updates["log_format"] = self.log_format
        if self.qa_mode is not None:
            pipeline_updates["qa_mode"] = self.qa_mode
        if self.observability is not None:
            pipeline_updates["observability"] = self.observability

        updates: dict[str, Any] = {}
        if pipeline_updates:
            updates["pipeline"] = pipeline_updates
        if self.features is not None:
            updates["features"] = self.features.model_dump()

        if updates:
            config = config.merge(updates)
        return config


DEFAULT_PROFILE_DIRS: tuple[Path, ...] = (
    Path(__file__).resolve().parent / "profiles",
    Path.cwd() / "profiles",
    Path.cwd() / "config" / "profiles",
)


def load_profile(
    identifier: str | Path,
    *,
    search_paths: Iterable[Path] | None = None,
) -> CLIProfile:
    """Load and validate a CLI profile."""

    candidate_paths: list[Path] = []
    if isinstance(identifier, Path):
        candidate_paths.append(identifier)
    else:
        potential = Path(identifier)
        if potential.suffix:
            candidate_paths.append(potential)
        else:
            directories = list(search_paths or []) + list(DEFAULT_PROFILE_DIRS)
            for directory in directories:
                for extension in (".toml", ".tml", ".yaml", ".yml"):
                    candidate_paths.append(directory / f"{identifier}{extension}")

        for path in candidate_paths:
            if not path.exists():
                continue
            payload = _load_profile_payload(path)
            try:
                profile = CLIProfile.model_validate(payload)
            except ValidationError as exc:  # pragma: no cover - exercised in tests
                for error in exc.errors():
                    maybe = error.get("ctx", {}).get("error")
                    if isinstance(maybe, ProfileIntentError):
                        raise ProfileIntentError(str(maybe)) from exc
                raise ProfileValidationError(str(exc)) from exc
            if not profile.name:
                profile = profile.model_copy(update={"name": path.stem})
            profile = profile.model_copy(update={"path": path})
            return profile

    msg = f"Profile '{identifier}' could not be found"
    raise ProfileNotFoundError(msg)


def _load_profile_payload(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".toml", ".tml"}:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        if yaml is None:  # pragma: no cover - guard when PyYAML missing
            msg = "PyYAML is required to load YAML profiles"
            raise ProfileValidationError(msg)
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            msg = f"YAML profile must define a mapping: {path}"
            raise ProfileValidationError(msg)
        return loaded
    msg = f"Unsupported profile format: {path}"
    raise ProfileValidationError(msg)


__all__ = [
    "CLIProfile",
    "FeatureFlags",
    "OrchestratorPreset",
    "ProfileIntentError",
    "ProfileNotFoundError",
    "ProfileValidationError",
    "DEFAULT_PROFILE_DIRS",
    "load_profile",
]
