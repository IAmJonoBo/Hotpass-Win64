"""Helpers for computing pipeline quality indicators."""

from __future__ import annotations

from collections.abc import Mapping


def summarise_quality(row: Mapping[str, str | None]) -> dict[str, object]:
    """Compute quality score indicators for a refined pipeline row."""

    checks = {
        "contact_email": bool(row.get("contact_primary_email")),
        "contact_phone": bool(row.get("contact_primary_phone")),
        "website": bool(row.get("website")),
        "province": bool(row.get("province")),
        "address": bool(row.get("address_primary")),
    }
    score = sum(1 for flag in checks.values() if flag) / max(len(checks), 1)
    missing_flags = [f"missing_{key}" for key, ok in checks.items() if not ok]
    return {
        "score": round(score, 2),
        "flags": ";".join(missing_flags) if missing_flags else "none",
    }


__all__ = ["summarise_quality"]
