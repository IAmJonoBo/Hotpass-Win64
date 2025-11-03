from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """Describe the permissions associated with an MCP role."""

    name: str
    description: str = ""
    allow: frozenset[str] = field(default_factory=frozenset)
    deny: frozenset[str] = field(default_factory=frozenset)
    inherits: tuple[str, ...] = ()
    allow_all: bool = False


@dataclass(slots=True)
class RolePolicy:
    """Evaluate whether a role may execute a tool."""

    roles: dict[str, RoleDefinition]
    default_role: str = "operator"
    tool_overrides: dict[str, frozenset[str]] = field(default_factory=dict)

    def is_allowed(self, role: str | None, tool_name: str) -> bool:
        """Return True when the supplied role may execute ``tool_name``."""

        role_name = role or self.default_role
        definition = self.roles.get(role_name)
        if definition is None:
            return False

        override_roles = self.tool_overrides.get(tool_name)
        if override_roles is not None and role_name not in override_roles:
            return False

        allow, deny, allow_all = self._collect_permissions(role_name, set())
        if tool_name in deny:
            return False
        if allow_all or "*" in allow:
            return True
        return tool_name in allow

    def register_tool_override(self, tool_name: str, roles: Sequence[str] | None) -> None:
        """Restrict a tool to the supplied roles."""

        if roles is None:
            self.tool_overrides.pop(tool_name, None)
            return
        filtered = [str(role).strip() for role in roles if str(role).strip()]
        self.tool_overrides[tool_name] = frozenset(filtered)

    def _collect_permissions(
        self, role_name: str, visited: set[str]
    ) -> tuple[set[str], set[str], bool]:
        if role_name in visited:
            return set(), set(), False
        visited.add(role_name)

        role = self.roles.get(role_name)
        if role is None:
            return set(), set(), False

        allow = set(role.allow)
        deny = set(role.deny)
        allow_all = role.allow_all

        for parent in role.inherits:
            parent_allow, parent_deny, parent_allow_all = self._collect_permissions(parent, visited)
            allow.update(parent_allow)
            deny.update(parent_deny)
            allow_all = allow_all or parent_allow_all

        return allow, deny, allow_all

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object], default_role: str | None = None
    ) -> RolePolicy:
        """Create a policy from a mapping payload."""

        raw_roles = payload.get("roles", {})
        if not isinstance(raw_roles, Mapping):
            raise ValueError("'roles' must be a mapping")

        roles: dict[str, RoleDefinition] = {}
        for name, definition in raw_roles.items():
            if not isinstance(name, str):
                raise ValueError("Role names must be strings")
            if not isinstance(definition, Mapping):
                raise ValueError(f"Role '{name}' must be a mapping")

            allow = frozenset(_to_iterable(definition.get("allow", ())))
            deny = frozenset(_to_iterable(definition.get("deny", ())))
            inherits = tuple(_to_iterable(definition.get("inherits", ())))
            description = str(definition.get("description", ""))
            allow_all = bool(definition.get("allow_all", False)) or "*" in allow

            roles[name] = RoleDefinition(
                name=name,
                description=description,
                allow=allow,
                deny=deny,
                inherits=inherits,
                allow_all=allow_all,
            )

        policy_default = str(payload.get("default_role", "operator"))
        if default_role is not None:
            policy_default = default_role

        if policy_default not in roles:
            # Ensure default exists even if it wasn't explicitly declared.
            roles[policy_default] = RoleDefinition(name=policy_default, allow=frozenset())

        return cls(roles=roles, default_role=policy_default)


def _to_iterable(value: object) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return (str(item) for item in value.values())
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return (str(value),)
