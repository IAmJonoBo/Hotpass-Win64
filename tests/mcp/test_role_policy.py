import pytest

from hotpass.mcp.access import RoleDefinition, RolePolicy


def test_role_policy_allows_default_roles():
    payload = {
        "roles": {
            "admin": {"allow": ["*"]},
            "reader": {"allow": ["hotpass.qa"]},
        },
        "default_role": "reader",
    }
    policy = RolePolicy.from_payload(payload)
    assert policy.is_allowed(None, "hotpass.qa") is True
    assert policy.is_allowed("admin", "hotpass.refine") is True
    assert policy.is_allowed("reader", "hotpass.refine") is False


def test_role_policy_overrides_and_roles():
    policy = RolePolicy.from_payload({"roles": {"operator": {"allow": ["hotpass.refine"]}}})
    policy.register_tool_override("hotpass.refine", ("operator",))
    policy.register_tool_override("hotpass.qa", ("observer",))
    assert policy.is_allowed("operator", "hotpass.refine") is True
    assert policy.is_allowed("observer", "hotpass.refine") is False

    new_role = RoleDefinition(name="observer", allow=frozenset({"hotpass.qa"}))
    policy.roles[new_role.name] = new_role
    assert policy.is_allowed("observer", "hotpass.qa") is True


def test_role_policy_invalid_payload_raises():
    with pytest.raises(ValueError):
        RolePolicy.from_payload({"roles": []})
