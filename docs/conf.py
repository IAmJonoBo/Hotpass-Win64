"""Sphinx configuration for the Hotpass documentation."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

project = "Hotpass"
author = "Hotpass Team"
release = "0.2.0"
copyright = f"{datetime.now():%Y}, {author}"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]

autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = True

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
    "substitution",
]

myst_heading_anchors = 3
myst_substitutions = {
    "project_name": project,
    "last_updated": datetime.now(UTC).strftime("%Y-%m-%d"),
}

nitpicky = True

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "furo"
html_static_path = ["_static"]

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

linkcheck_ignore = [
    r"https://github.com/IAmJonoBo/Hotpass/issues/.*",
    r"https://developers.google.com/style",
    r"https://diataxis.fr/",
    r"https://docs.astral.sh/uv/getting-started/installation/",
    r"https://greatexpectations.io/",
    r"https://github.com/GoogleCloudPlatform/fourkeys",
    r"https://docs.sigstore.dev/.*",
    r"https://cyclonedx.org/.*",
    r"https://docs.structurizr.com/.*",
    r"https://mutmut.readthedocs.io/.*",
    r"https://www.w3.org/.*",
    r"https://docs.streamlit.io/.*",
    r"https://queue.acm.org/.*",
]
linkcheck_timeout = 10
