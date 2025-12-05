from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtWidgets

from pyside_ui.mcp_client import MCPClient
from pyside_ui.simulated_runs import SimulationRunLoader


class MCPDesktop(QtWidgets.QMainWindow):
    """Lightweight desktop harness for Hotpass MCP flows."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotpass MCP Desktop")
        self.resize(900, 700)

        self.client = MCPClient()
        self.simulations = SimulationRunLoader()

        self._refine_input = QtWidgets.QLineEdit(str(Path("data/e2e")))
        self._refine_output = QtWidgets.QLineEdit("dist/pyside-ui/refined-simulated.xlsx")
        self._refine_profile = QtWidgets.QComboBox()
        self._refine_profile.addItems(["generic", "aviation"])
        self._refine_archive = QtWidgets.QCheckBox("Archive outputs")

        self._enrich_input = QtWidgets.QLineEdit("dist/pyside-ui/refined-simulated.xlsx")
        self._enrich_output = QtWidgets.QLineEdit("dist/pyside-ui/enriched-simulated.xlsx")
        self._enrich_profile = QtWidgets.QComboBox()
        self._enrich_profile.addItems(["generic", "aviation"])
        self._enrich_allow_network = QtWidgets.QCheckBox("Allow network enrichment")

        self._qa_target = QtWidgets.QComboBox()
        self._qa_target.addItems(["all", "fitness", "profiles", "docs", "ta", "contracts"])

        self._output = QtWidgets.QPlainTextEdit()
        self._output.setReadOnly(True)

        self._tool_list = QtWidgets.QListWidget()

        self._build_layout()
        self._refresh_tools()

    def _build_layout(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(QtWidgets.QLabel("Refine, enrich, or QA data through the MCP server. Use simulations when you need a quick dry run."))

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_refine_tab(), "Refine")
        tabs.addTab(self._build_enrich_tab(), "Enrich")
        tabs.addTab(self._build_qa_tab(), "QA")
        layout.addWidget(tabs)

        catalog = QtWidgets.QGroupBox("Visible MCP tools")
        catalog_layout = QtWidgets.QVBoxLayout()
        refresh = QtWidgets.QPushButton("Refresh tool list")
        refresh.clicked.connect(self._refresh_tools)
        catalog_layout.addWidget(refresh)
        catalog_layout.addWidget(self._tool_list)
        catalog.setLayout(catalog_layout)
        layout.addWidget(catalog)

        output_box = QtWidgets.QGroupBox("MCP output / simulation log")
        output_layout = QtWidgets.QVBoxLayout()
        output_layout.addWidget(self._output)
        output_box.setLayout(output_layout)
        layout.addWidget(output_box)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_refine_tab(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout()

        form.addRow("Input directory", self._refine_input)
        form.addRow("Output path", self._refine_output)
        form.addRow("Profile", self._refine_profile)
        form.addRow(self._refine_archive)

        call_button = QtWidgets.QPushButton("Call MCP refine")
        call_button.clicked.connect(self._call_refine)
        simulate_button = QtWidgets.QPushButton("Simulate refine")
        simulate_button.clicked.connect(lambda: self._simulate("refine"))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(call_button)
        row.addWidget(simulate_button)
        form.addRow(row)

        container.setLayout(form)
        return container

    def _build_enrich_tab(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout()

        form.addRow("Input file", self._enrich_input)
        form.addRow("Output path", self._enrich_output)
        form.addRow("Profile", self._enrich_profile)
        form.addRow(self._enrich_allow_network)

        call_button = QtWidgets.QPushButton("Call MCP enrich")
        call_button.clicked.connect(self._call_enrich)
        simulate_button = QtWidgets.QPushButton("Simulate enrich")
        simulate_button.clicked.connect(lambda: self._simulate("enrich"))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(call_button)
        row.addWidget(simulate_button)
        form.addRow(row)

        container.setLayout(form)
        return container

    def _build_qa_tab(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout()

        form.addRow("Target", self._qa_target)

        call_button = QtWidgets.QPushButton("Call MCP QA")
        call_button.clicked.connect(self._call_qa)
        simulate_button = QtWidgets.QPushButton("Simulate QA")
        simulate_button.clicked.connect(lambda: self._simulate("qa"))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(call_button)
        row.addWidget(simulate_button)
        form.addRow(row)

        container.setLayout(form)
        return container

    def _call_refine(self) -> None:
        args = {
            "input_path": self._refine_input.text(),
            "output_path": self._refine_output.text(),
            "profile": self._refine_profile.currentText(),
            "archive": self._refine_archive.isChecked(),
        }
        self._call_tool("hotpass.refine", args)

    def _call_enrich(self) -> None:
        args = {
            "input_path": self._enrich_input.text(),
            "output_path": self._enrich_output.text(),
            "profile": self._enrich_profile.currentText(),
            "allow_network": self._enrich_allow_network.isChecked(),
        }
        self._call_tool("hotpass.enrich", args)

    def _call_qa(self) -> None:
        args = {"target": self._qa_target.currentText()}
        self._call_tool("hotpass.qa", args)

    def _call_tool(self, tool: str, args: dict[str, str | bool]) -> None:
        self._output.appendPlainText(f"Calling {tool} with {args}\n")
        result = self.client.call_tool(tool, args)
        if result.success:
            formatted = json.dumps(result.payload, indent=2)
            self._output.appendPlainText(formatted)
        else:
            self._output.appendPlainText(f"Error: {result.error or 'Unknown MCP error'}")
        self._output.appendPlainText("\n")

    def _simulate(self, name: str) -> None:
        if name not in self.simulations.available():
            self._output.appendPlainText(f"Simulation '{name}' not found under {self.simulations.data_dir}\n")
            return

        run = self.simulations.load(name)
        payload = {
            "tool": run.tool,
            "description": run.description,
            "arguments": run.arguments,
            "result": run.result,
        }
        self._output.appendPlainText(f"Simulation: {run.name}\n")
        self._output.appendPlainText(json.dumps(payload, indent=2))
        self._output.appendPlainText("\n")

    def _refresh_tools(self) -> None:
        self._tool_list.clear()
        for tool in self.client.list_tools():
            name = tool.get("name", "")
            description = tool.get("description", "")
            self._tool_list.addItem(f"{name} — {description}")


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MCPDesktop()
    window.show()
    app.exec()
