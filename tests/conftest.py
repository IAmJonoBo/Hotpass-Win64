from __future__ import annotations

import os
import warnings
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from marshmallow.warnings import ChangedInMarshmallow4Warning

from tests.helpers.fixtures import fixture

pytest_plugins = ["tests.fixtures.lineage"]

QUALITY_GATE_FILES = {
    Path("tests/cli/test_quality_gates.py"),
}

QUALITY_GATE_DIRS = {
    Path("tests/automation"),
    Path("tests/contracts"),
    Path("tests/enrichment"),
    Path("tests/geospatial"),
    Path("tests/mcp"),
    Path("tests/pipeline"),
    Path("tests/research"),
    Path("tests/quality"),
}

SLOW_DIRS = {
    Path("tests/data_sources"),
    Path("tests/observability"),
    Path("tests/ml"),
}


def _install_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        category=ChangedInMarshmallow4Warning,
        message=(
            "`Number` field should not be instantiated. "
            "Use `Integer`, `Float`, or `Decimal` instead."
        ),
    )
    warnings.filterwarnings(
        "ignore",
        category=pytest.PytestUnraisableExceptionWarning,
    )
    warnings.filterwarnings(
        "ignore",
        category=ResourceWarning,
        message="Implicitly cleaning up <TemporaryDirectory",
    )


_install_warning_filters()


def pytest_configure(config: pytest.Config) -> None:
    _install_warning_filters()
    config.addinivalue_line(
        "markers",
        "bandwidth(name): classify test runtime footprint (smoke|full|quality_gate|slow)",
    )
    config.addinivalue_line("markers", "smoke: smoke-tier fast checks")
    config.addinivalue_line("markers", "full: comprehensive default checks")


@fixture(autouse=True)
def _fail_fast_for_mutmut() -> None:
    if os.environ.get("MUTANT_UNDER_TEST") == "fail":
        pytest.fail("mutmut forced failure sentinel", pytrace=False)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        bandwidth_marks = list(item.iter_markers(name="bandwidth"))
        if bandwidth_marks:
            bucket = bandwidth_marks[-1].args[0]
        else:
            abs_path = Path(item.fspath).resolve()
            try:
                rel_path = abs_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = abs_path
            if rel_path in QUALITY_GATE_FILES or any(
                rel_path.is_relative_to(dir_path) for dir_path in QUALITY_GATE_DIRS
            ):
                bucket = "quality_gate"
            elif any(rel_path.is_relative_to(dir_path) for dir_path in SLOW_DIRS):
                bucket = "slow"
            else:
                bucket = "full"
            item.add_marker(pytest.mark.bandwidth(bucket))

        if bucket == "smoke":
            item.add_marker("smoke")
        elif bucket == "full":
            item.add_marker("full")
        elif bucket == "quality_gate":
            item.add_marker("quality_gate")
        elif bucket == "slow":
            item.add_marker("slow")


@dataclass(slots=True)
class MultiWorkbookBundle:
    """Fixture payload describing a synthetic multi-workbook bundle."""

    input_dir: Path
    archive_root: Path
    archive_path: Path
    run_date: str
    version: str
    pattern: str
    workbook_names: tuple[str, ...]


@fixture()
def multi_workbook_bundle(tmp_path: Path) -> MultiWorkbookBundle:
    """Create a multi-workbook bundle along with an archived copy."""

    bundle_dir = tmp_path / "multi_workbook_bundle"
    workbook_paths = _build_sample_workbooks(bundle_dir)

    archive_root = tmp_path / "archives"
    archive_root.mkdir(parents=True, exist_ok=True)

    pattern = "hotpass-inputs-{date:%Y%m%d}-v{version}.zip"
    run_date = date(2025, 11, 1)
    version = "v2025.11"
    archive_name = pattern.format(date=run_date, version=version)
    archive_path = archive_root / archive_name

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for workbook in workbook_paths:
            archive.write(workbook, arcname=workbook.name)

    return MultiWorkbookBundle(
        input_dir=bundle_dir,
        archive_root=archive_root,
        archive_path=archive_path,
        run_date=run_date.isoformat(),
        version=version,
        pattern=pattern,
        workbook_names=tuple(path.name for path in workbook_paths),
    )


def _build_sample_workbooks(target_dir: Path) -> tuple[Path, ...]:
    target_dir.mkdir(parents=True, exist_ok=True)

    reachout_org = pd.DataFrame(
        {
            "Organisation Name": ["Aero School", "Heli Ops"],
            "ID": [1, 2],
            "Reachout Date": ["March 10, 2025", "2025-01-20"],
            "Recent_Touch_Ind": ["Y", "N"],
            "Area": ["Gauteng", "Western Cape"],
            "Distance": [0, 1200],
            "Type": ["Flight School", "Helicopter"],
            "Website": ["www.aero.example", ""],
            "Address": ["Hangar 1", "Cape Town Intl"],
            "Planes": ["Sling 2", "Robinson R44"],
            "Description Type": ["Fixed-wing", "Rotary"],
            "Notes": ["Follow up", ""],
            "Open Questions": ["Need pricing", ""],
        }
    )
    reachout_contacts = pd.DataFrame(
        {
            "ID": [1, 1, 2],
            "Organisation Name": ["Aero School", "Aero School", "Heli Ops"],
            "Reachout Date": ["2025-01-15", "2025-01-15", "2025-01-20"],
            "Firstname": ["Jane", "Ops", "Kelly"],
            "Surname": ["Doe", "Team", "Nguyen"],
            "Position": ["Head of Training", "Operations", "Chief Pilot"],
            "Phone": ["082 123 4567", "0829991111", "021 555 0000"],
            "WhatsApp": ["0821234567", "", "0215550000"],
            "Email": [
                "JANE.DOE@AERO.EXAMPLE",
                "ops@aero.example",
                "kelly@heliops.example",
            ],
            "Invalid": ["", "", ""],
            "Unnamed: 10": ["Validated", "Validated", "Validated"],
        }
    )

    reachout_path = target_dir / "Reachout Database.xlsx"
    with pd.ExcelWriter(reachout_path) as writer:
        reachout_org.to_excel(writer, sheet_name="Organisation", index=False)
        reachout_contacts.to_excel(writer, sheet_name="Contact Info", index=False)

    company_cat = pd.DataFrame(
        {
            "C_ID": [10, 11],
            "Company": ["Aero School", "Heli Ops"],
            "QuickNooks_Name": ["Aero School QB", "Heli Ops QB"],
            "Last_Order_Date": ["2024-11-01", ""],
            "Category": ["Flight School", "Helicopter"],
            "Strat": ["Core", "Expansion"],
            "Priority": ["High", "Medium"],
            "Status": ["Active", "Prospect"],
            "LoadDate": ["05/02/2025", "2025/02/18"],
            "Checked": ["2024-11-05", "2024-11-05"],
            "Website": ["https://aero.example", ""],
        }
    )
    company_contacts = pd.DataFrame(
        {
            "C_ID": [10, 11],
            "Company": ["Aero School", "Heli Ops"],
            "Status": ["Active", "Prospect"],
            "FirstName": ["John", "Kelly"],
            "Surname": ["Smith", "Nguyen"],
            "Position": ["Operations", "Chief Pilot"],
            "Cellnumber": ["+27 82 999 1111", "0215550000"],
            "Email": ["ops@aero.example", "kelly@heliops.example"],
            "Landline": ["0111110000", "0215550001"],
        }
    )
    company_addresses = pd.DataFrame(
        {
            "C_ID": [10, 11],
            "Company": ["Aero School", "Heli Ops"],
            "Type": ["Head", "Head"],
            "Airport": ["FALA", "FACT"],
            "Unnamed: 4": ["Hangar Complex", "Cape Town Intl"],
        }
    )
    capture_sheet = pd.DataFrame(
        {
            "Unnamed: 0": [""],
            "School": ["Heli Ops"],
            "Contact person (role)": ["Kelly Nguyen (Chief Pilot)"],
            "Phone": ["021 555 0000"],
            "Email": ["kelly@heliops.example"],
            "Addresses": ["Cape Town"],
            "Planes": ["Robinson R44"],
            "Website": [""],
            "Description": ["Helicopter operations"],
            "Type": ["Helicopter"],
        }
    )

    contact_path = target_dir / "Contact Database.xlsx"
    with pd.ExcelWriter(contact_path) as writer:
        company_cat.to_excel(writer, sheet_name="Company_Cat", index=False)
        company_contacts.to_excel(writer, sheet_name="Company_Contacts", index=False)
        company_addresses.to_excel(writer, sheet_name="Company_Addresses", index=False)
        capture_sheet.to_excel(writer, sheet_name="10-10-25 Capture", index=False)

    sacaa_cleaned = pd.DataFrame(
        {
            "Name of Organisation": ["Aero School", "Heli Ops"],
            "Province": ["Gauteng", "Western Cape"],
            "Status": ["Active", "Active"],
            "Website URL": ["https://aero.example", ""],
            "Contact Person": ["Jane Doe", "Kelly Nguyen"],
            "Contact Number": ["0821234567", "0215550000"],
            "Contact Email Address": [
                "jane.doe@aero.example",
                "kelly@heliops.example; ops@heliops.example",
            ],
        }
    )

    sacaa_path = target_dir / "SACAA Flight Schools - Refined copy__CLEANED.xlsx"
    with pd.ExcelWriter(sacaa_path) as writer:
        sacaa_cleaned.to_excel(writer, sheet_name="Cleaned", index=False)

    return (reachout_path, contact_path, sacaa_path)


@fixture()
def sample_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    _build_sample_workbooks(data_dir)
    return data_dir
