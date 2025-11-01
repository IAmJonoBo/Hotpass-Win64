"""SACAA registry adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import (
    BaseRegistryAdapter,
    RegistryResponse,
    RegistryTransportError,
    clean_text,
    normalise_address,
    normalise_date,
    normalise_officer,
)


class SACAARegistryAdapter(BaseRegistryAdapter):
    """Adapter for the South African Civil Aviation Authority operator registry."""

    registry = "sacaa"
    default_base_url = "https://api.sacaa.co.za/operators"
    _query_param = "query"

    def __init__(self, *, query_param: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if query_param:
            self._query_param = query_param
        elif "query_param" in self.extra_params:
            self._query_param = str(self.extra_params.pop("query_param"))

    def lookup(self, organization: str) -> RegistryResponse:
        params = {self._query_param: organization, **self.extra_params}
        response = self._request(self.base_url, params=params)
        meta = {**self._base_meta(), "status_code": response.status_code}
        body = self._json(response)
        status = response.status_code
        if status is not None and status >= 500:
            raise RegistryTransportError(f"{self.registry.upper()} service error ({status})")

        data = _extract_data(body)
        if not data:
            errors = [
                {
                    "code": "not_found" if status == 404 else "no_results",
                    "message": body.get("message")
                    or f"{organization} not found in {self.registry.upper()} registry",
                }
            ]
            return RegistryResponse(
                registry=self.registry,
                organization=organization,
                success=False,
                status_code=status,
                payload=None,
                errors=errors,
                raw=body,
                meta=meta,
            )

        payload = _normalise_entry(data)
        if isinstance(body.get("meta"), Mapping):
            meta["provider_meta"] = dict(body["meta"])
        return RegistryResponse(
            registry=self.registry,
            organization=organization,
            success=True,
            status_code=status,
            payload=payload,
            errors=[],
            raw=dict(data),
            meta=meta,
        )


def _extract_data(body: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = body.get("data")
    if isinstance(data, Mapping):
        return data
    if isinstance(data, list):
        for item in data:
            if isinstance(item, Mapping):
                return item
    return None


def _normalise_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    addresses = []
    for item in entry.get("addresses", []) or []:
        if isinstance(item, Mapping):
            address = normalise_address(item, kind=clean_text(item.get("type")))
            if address:
                addresses.append(address)

    contacts_payload: dict[str, Any] = {}
    contacts_source = entry.get("contacts")
    if isinstance(contacts_source, Mapping):
        contacts_payload = dict(contacts_source)
    contacts = {
        "email": clean_text(contacts_payload.get("email")),
        "phone": clean_text(contacts_payload.get("phone")),
        "fax": clean_text(contacts_payload.get("fax")),
    }

    responsible = entry.get("responsible_persons")
    if not isinstance(responsible, list):
        responsible = []
    officers: list[dict[str, Any]] = []
    for item in responsible:
        if not isinstance(item, Mapping):
            continue
        officer = normalise_officer(item)
        if officer:
            officers.append(officer)

    return {
        "registration_number": clean_text(
            entry.get("air_operator_certificate") or entry.get("certificate_number")
        ),
        "registered_name": clean_text(entry.get("legal_name")),
        "trading_name": clean_text(entry.get("trading_name")),
        "entity_type": clean_text(entry.get("operator_type") or "air_operator"),
        "status": clean_text(entry.get("status")),
        "status_effective": normalise_date(entry.get("issue_date")),
        "expiry_date": normalise_date(entry.get("expiry_date")),
        "addresses": addresses,
        "contacts": contacts,
        "officers": officers,
        "extra": {
            "aircraft": (
                entry.get("aircraft") if isinstance(entry.get("aircraft"), list) else None
            ),
        },
    }


__all__ = ["SACAARegistryAdapter"]
