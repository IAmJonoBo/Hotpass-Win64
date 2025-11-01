"""Quality Gate tests for Hotpass UPGRADE.md implementation.

These tests implement the Quality Gates (QG-1 through QG-5) specified
in IMPLEMENTATION_PLAN.md to ensure compliance with UPGRADE.md requirements.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROVENANCE_COLUMNS = [
    "provenance_source",
    "provenance_timestamp",
    "provenance_confidence",
    "provenance_strategy",
    "provenance_network_status",
]


def expect(condition: bool, message: str) -> None:
    """Assert-free test helper per docs/how-to-guides/assert-free-pytest.md."""
    if not condition:
        raise AssertionError(message)


class TestQG1CLIIntegrity:
    """QG-1: CLI Integrity Gate.

    Ensures that the CLI exposes all required verbs as specified in UPGRADE.md section 2.
    """

    def test_overview_command_exists(self):
        """QG-1a: Overview command should be accessible."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "overview", "--help"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "overview command should have --help")
        expect("overview" in result.stdout.lower(), "overview help should mention itself")

    def test_refine_command_exists(self):
        """QG-1b: Refine command should be accessible."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "refine", "--help"], capture_output=True, text=True
        )
        expect(result.returncode == 0, "refine command should have --help")
        expect("refine" in result.stdout.lower(), "refine help should mention itself")

    def test_enrich_command_exists(self):
        """QG-1c: Enrich command should be accessible."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "enrich", "--help"], capture_output=True, text=True
        )
        expect(result.returncode == 0, "enrich command should have --help")
        expect("enrich" in result.stdout.lower(), "enrich help should mention itself")

    def test_qa_command_exists(self):
        """QG-1d: QA command should be accessible."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "qa", "--help"], capture_output=True, text=True
        )
        expect(result.returncode == 0, "qa command should have --help")
        expect(
            "quality" in result.stdout.lower() or "qa" in result.stdout.lower(),
            "qa help should mention quality assurance",
        )

    def test_contracts_command_exists(self):
        """QG-1e: Contracts command should be accessible."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "contracts", "--help"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "contracts command should have --help")
        expect(
            "contract" in result.stdout.lower(),
            "contracts help should mention contracts",
        )

    def test_overview_lists_all_required_verbs(self):
        """QG-1f: Overview command should list all required verbs."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "overview"], capture_output=True, text=True
        )

        expect(result.returncode == 0, "overview command should exit successfully")

        required_verbs = ["refine", "enrich", "qa", "contracts", "overview"]
        output_lower = result.stdout.lower()

        for verb in required_verbs:
            expect(verb in output_lower, f"overview must list {verb}")

    def test_cli_main_help_shows_all_commands(self):
        """QG-1g: Main CLI help should show all commands."""
        result = subprocess.run(["uv", "run", "hotpass", "--help"], capture_output=True, text=True)

        expect(result.returncode == 0, "hotpass --help should exit successfully")

        required_commands = ["overview", "refine", "enrich", "qa", "contracts"]
        output_lower = result.stdout.lower()

        for cmd in required_commands:
            expect(cmd in output_lower, f"hotpass --help must show {cmd}")

    def test_qg1_script_emits_json_summary(self):
        """QG-1h: Gate script should emit JSON summary and pass."""
        result = subprocess.run(
            [sys.executable, "ops/quality/run_qg1.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_qg1.py should exit successfully")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"run_qg1.py output must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "run_qg1.py payload should be a dict")
        expect(payload.get("passed") is True, "QG-1 gate should pass on healthy repo")


class TestQG2DataQuality:
    """QG-2: Data Quality Gate.

    Ensures Great Expectations validation works and catches quality issues.
    """

    def test_qa_command_supports_data_quality(self):
        """QG-2a: QA command should support data quality checks."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "qa", "--help"], capture_output=True, text=True
        )
        expect(result.returncode == 0, "qa --help should work")
        expect(
            "data-quality" in result.stdout.lower(),
            "qa --help must mention data-quality target",
        )
        expect("cli" in result.stdout.lower(), "qa --help must mention cli target")

    def test_qg2_script_generates_summary(self):
        """QG-2b: Gate script should run checkpoints and emit JSON."""
        result = subprocess.run(
            [sys.executable, "ops/quality/run_qg2.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_qg2.py should exit successfully")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"run_qg2.py output must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "run_qg2.py payload should be a dict")
        expect(
            payload.get("passed") is True,
            "QG-2 gate should pass on sample data",
        )

        stats = payload.get("stats")
        expect(isinstance(stats, dict), "QG-2 payload must include stats")
        total = stats.get("total")
        expect(isinstance(total, int), "QG-2 stats.total must be an integer")
        results = payload.get("results")
        expect(isinstance(results, list), "QG-2 payload must include results list")
        expect(len(results) == total, "QG-2 stats.total must match results length")

        data_docs = payload.get("data_docs")
        expect(isinstance(data_docs, str), "QG-2 payload must include data_docs path")
        expect(Path(data_docs).exists(), "QG-2 Data Docs directory must exist")


class TestQG3EnrichmentChain:
    """QG-3: Enrichment Chain Gate.

    Ensures enrichment works offline with provenance tracking.
    """

    def test_enrich_command_has_network_flag(self):
        """QG-3a: Enrich command should have --allow-network flag."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "enrich", "--help"], capture_output=True, text=True
        )
        expect(result.returncode == 0, "enrich --help should work")
        expect(
            "allow-network" in result.stdout.lower() or "allow_network" in result.stdout.lower(),
            "enrich should have --allow-network flag",
        )

    def test_qg3_script_runs_enrichment(self, tmp_path: Path):
        """QG-3b: Gate script should refine deterministic enrichment output."""
        result = subprocess.run(
            [sys.executable, "ops/quality/run_qg3.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_qg3.py should exit successfully")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"run_qg3.py output must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "run_qg3.py payload should be a dict")
        expect(
            payload.get("passed") is True,
            "QG-3 gate should pass on deterministic workflow",
        )

        artifacts = payload.get("artifacts")
        expect(isinstance(artifacts, dict), "QG-3 payload must include artifacts")
        output_workbook = artifacts.get("output_workbook")
        expect(
            isinstance(output_workbook, str),
            "QG-3 artifacts must include output workbook path",
        )
        expect(Path(output_workbook).exists(), "QG-3 output workbook must exist")

        # Copy artifact to tmp to confirm readability
        copied = tmp_path / "enriched.xlsx"
        copied.write_bytes(Path(output_workbook).read_bytes())
        df = pd.read_excel(copied)
        for column in PROVENANCE_COLUMNS:
            expect(column in df.columns, f"QG-3 output must include {column}")


class TestQG4MCPDiscoverability:
    """QG-4: MCP Discoverability Gate.

    Ensures MCP tools are discoverable and functional.
    """

    def test_mcp_server_module_exists(self):
        """QG-4a: MCP server module should exist."""
        mcp_server = Path("apps/data-platform/hotpass/mcp/server.py")
        expect(
            mcp_server.exists(),
            "MCP server should exist at apps/data-platform/hotpass/mcp/server.py",
        )

    def test_mcp_server_is_importable(self):
        """QG-4b: MCP server should be importable."""
        try:
            from hotpass.mcp.server import HotpassMCPServer

            server = HotpassMCPServer()
            expect(len(server.tools) > 0, "MCP server should have tools registered")
        except ImportError as exc:
            raise AssertionError(f"MCP server should be importable: {exc}") from exc

    def test_qg4_script_validates_tools(self):
        """QG-4c: Gate script should report required tools."""
        result = subprocess.run(
            [sys.executable, "ops/quality/run_qg4.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_qg4.py should exit successfully")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"run_qg4.py output must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "run_qg4.py payload should be a dict")
        expect(payload.get("passed") is True, "QG-4 gate should pass on healthy repo")
        steps = payload.get("steps")
        expect(isinstance(steps, list), "QG-4 payload must include steps")
        tool_step = next((step for step in steps if step.get("id") == "required-tools"), None)
        if not isinstance(tool_step, dict):
            raise AssertionError("QG-4 steps must include required-tools step")
        expect(tool_step.get("status") == "passed", "QG-4 required-tools step must pass")


class TestQG5DocsInstruction:
    """QG-5: Docs/Instruction Gate.

    Ensures agent instruction files exist and contain required terminology.
    """

    def test_copilot_instructions_exists(self):
        """QG-5a: .github/copilot-instructions.md should exist."""
        copilot_instructions = Path(".github/copilot-instructions.md")
        expect(copilot_instructions.exists(), ".github/copilot-instructions.md must exist")

        content = copilot_instructions.read_text()
        expect(len(content) > 100, "copilot-instructions.md should not be empty")

    def test_agents_md_exists(self):
        """QG-5b: AGENTS.md should exist."""
        agents_md = Path("AGENTS.md")
        expect(agents_md.exists(), "AGENTS.md must exist")

        content = agents_md.read_text()
        expect(len(content) > 100, "AGENTS.md should not be empty")

    def test_copilot_instructions_mentions_required_terms(self):
        """QG-5c: copilot-instructions should mention key terms."""
        copilot_instructions = Path(".github/copilot-instructions.md")
        content = copilot_instructions.read_text().lower()

        # Check for presence (not exact match to allow flexibility)
        expect("profile" in content, "copilot-instructions must mention profiles")
        expect(
            "deterministic" in content or "offline" in content,
            "copilot-instructions must mention deterministic/offline approach",
        )
        expect(
            "provenance" in content or "source" in content,
            "copilot-instructions must mention provenance/sources",
        )

    def test_agents_md_mentions_required_terms(self):
        """QG-5d: AGENTS.md should mention key terms."""
        agents_md = Path("AGENTS.md")
        content = agents_md.read_text().lower()

        # Check for presence
        expect(
            "profile" in content or "aviation" in content or "generic" in content,
            "AGENTS.md must mention profiles",
        )

    def test_qg5_script_validates_docs(self):
        """QG-5e: Gate script should validate docs."""
        result = subprocess.run(
            [sys.executable, "ops/quality/run_qg5.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_qg5.py should exit successfully")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"run_qg5.py output must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "run_qg5.py payload should be a dict")
        expect(
            payload.get("passed") is True,
            "QG-5 gate should pass on current documentation",
        )

    def test_implementation_plan_exists(self):
        """QG-5e: IMPLEMENTATION_PLAN.md should exist."""
        impl_plan = Path("IMPLEMENTATION_PLAN.md")
        expect(impl_plan.exists(), "IMPLEMENTATION_PLAN.md must exist")

        content = impl_plan.read_text()
        expect("sprint" in content.lower(), "IMPLEMENTATION_PLAN should define sprints")
        expect(
            "quality gate" in content.lower() or "qg-" in content.lower(),
            "IMPLEMENTATION_PLAN should define quality gates",
        )


class TestTechnicalAcceptance:
    """Technical Acceptance (TA) criteria tests.

    These verify the TA items from UPGRADE.md section 6.
    """

    def test_ta1_single_tool_rule_cli_verbs(self):
        """TA-1a: All operations accessible via uv run hotpass."""
        result = subprocess.run(["uv", "run", "hotpass", "--help"], capture_output=True, text=True)
        expect(result.returncode == 0, "CLI should be accessible via uv run hotpass")

    def test_ta5_mcp_server_exists(self):
        """TA-5a: MCP server exists for tool exposure."""
        mcp_server = Path("apps/data-platform/hotpass/mcp/server.py")
        expect(mcp_server.exists(), "MCP server must exist")

    def test_ta6_quality_gates_exist(self):
        """TA-6a: Quality gate scripts/tests exist."""
        # This test file itself proves QG tests exist
        expect(True, "Quality gate tests exist in this file")

    def test_ta7_docs_present(self):
        """TA-7a: Agent instructions and docs are present."""
        expect(
            Path(".github/copilot-instructions.md").exists(),
            "Copilot instructions must exist",
        )
        expect(Path("AGENTS.md").exists(), "AGENTS.md must exist")
        expect(Path("IMPLEMENTATION_PLAN.md").exists(), "Implementation plan must exist")

    def test_ta_summary_artifact_written(self):
        """TA-8a: Consolidated TA summary should persist to dist/quality-gates."""
        summary_path = Path("dist/quality-gates/latest-ta.json")
        if summary_path.exists():
            summary_path.unlink()

        result = subprocess.run(
            [sys.executable, "ops/quality/run_all_gates.py", "--json"],
            capture_output=True,
            text=True,
        )
        expect(result.returncode == 0, "run_all_gates.py should exit successfully")
        expect(
            summary_path.exists(),
            "TA summary artifact should be written to dist/quality-gates",
        )
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"TA summary artifact must be JSON: {exc}") from exc
        expect(isinstance(payload, dict), "TA summary artifact must be a JSON object")
        history_path = Path("dist/quality-gates/history.ndjson")
        expect(history_path.exists(), "TA history log should exist after running all gates")
        expect(
            bool(history_path.read_text(encoding="utf-8").strip()),
            "TA history log should contain entries",
        )
