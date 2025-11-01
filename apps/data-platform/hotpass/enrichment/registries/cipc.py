"""CIPC registry adapter."""

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


class CIPCRegistryAdapter(BaseRegistryAdapter):
    """Adapter for the Companies and Intellectual Property Commission."""

    registry = "cipc"
    default_base_url = "https://api.cipc.gov.za/v1/companies"
    _search_param = "search"

    def __init__(self, *, search_param: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if search_param:
            self._search_param = search_param
        elif "search_param" in self.extra_params:
            self._search_param = str(self.extra_params.pop("search_param"))

    def lookup(self, organization: str) -> RegistryResponse:
        params = {self._search_param: organization, **self.extra_params}
        response = self._request(self.base_url, params=params)
        meta = {**self._base_meta(), "status_code": response.status_code}
        body = self._json(response)

        status = response.status_code
        if status is not None and status >= 500:
            raise RegistryTransportError(f"{self.registry.upper()} service error ({status})")

        results = _extract_results(body)
        if not results:
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

        entry = results[0]
        payload = _normalise_entry(entry)
        meta.update(
            {
                "result_count": len(results),
                "search_param": self._search_param,
            }
        )
        return RegistryResponse(
            registry=self.registry,
            organization=organization,
            success=True,
            status_code=status,
            payload=payload,
            errors=[],
            raw=dict(entry),
            meta=meta,
        )


def _extract_results(body: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    results = body.get("results") or body.get("data")
    if isinstance(results, Mapping):
        return [results]
    if isinstance(results, list):
        return [item for item in results if isinstance(item, Mapping)]
    return []


def _normalise_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    addresses = []
    registered_address = normalise_address(
        entry.get("registered_address"),
        kind="registered",
    )
    if registered_address:
        addresses.append(registered_address)
    postal_address = normalise_address(
        entry.get("postal_address"),
        kind="postal",
    )
    if postal_address:
        addresses.append(postal_address)

    directors = entry.get("directors", [])
    if not isinstance(directors, list):
        directors = []
    officers: list[dict[str, Any]] = []
    for record in directors:
        if not isinstance(record, Mapping):
            continue
        officer = normalise_officer(record)
        if officer:
            officers.append(officer)

    return {
        "registration_number": clean_text(
            entry.get("enterprise_number") or entry.get("registration_number")
        ),
        "registered_name": clean_text(entry.get("enterprise_name") or entry.get("name")),
        "entity_type": clean_text(entry.get("enterprise_type") or entry.get("entity_type")),
        "status": clean_text(entry.get("status")),
        "status_effective": normalise_date(
            entry.get("status_date") or entry.get("status_effective_date")
        ),
        "incorporation_date": normalise_date(entry.get("registration_date")),
        "business_start_date": normalise_date(entry.get("business_start_date")),
        "addresses": addresses,
        "contacts": {
            "email": clean_text(entry.get("email")),
            "phone": clean_text(entry.get("phone")),
        },
        "officers": officers,
        "extra": {
            "financial_year_end": normalise_date(entry.get("financial_year_end")),
            "last_updated": entry.get("last_updated") or entry.get("last_update"),
        },
    }


__all__ = ["CIPCRegistryAdapter"]
