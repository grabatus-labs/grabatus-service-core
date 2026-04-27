"""Sphinx configuration for grabatus-service-core."""

from __future__ import annotations

from pathlib import Path

# -- Project information --------------------------------------------------

project = "grabatus-service-core"
author = "Grabatus Engineering"
copyright = "2026, Grabatus"  # Sphinx config name
release = "0.1.0"

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_parser",
    "autoapi.extension",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # GitHub-facing README; Sphinx surfaces ADRs through ``adr_index.rst``.
    "adr/README.md",
    # Superpowers planning artefacts live under docs/ for tooling reasons
    # but are not part of the published documentation.
    "superpowers/**",
]

# -- Internationalisation -------------------------------------------------

# Default build language. CI builds the site twice: once with
# ``language = "en"`` (default) and once with ``language = "pt_BR"``.
# Translations live as Gettext .po files under ``docs/locale/``.
language = "en"
locale_dirs = ["locale/"]
gettext_compact = False

# -- HTML output ----------------------------------------------------------

html_theme = "furo"
html_title = f"{project} {release}"
html_static_path = []
templates_path = []

# -- AutoAPI configuration ------------------------------------------------

# Generate API docs from the source tree, not from the installed package,
# so docstring edits are visible without re-installing.
autoapi_type = "python"
autoapi_dirs = [str(Path(__file__).resolve().parent.parent / "src" / "grabatus_service_core")]
autoapi_root = "reference"
autoapi_keep_files = False
autoapi_add_toctree_entry = True
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_python_class_content = "both"

# -- MyST options ---------------------------------------------------------

myst_enable_extensions = [
    "deflist",
    "colon_fence",
    "tasklist",
]
myst_heading_anchors = 3

# -- Napoleon (Google/NumPy docstring rendering) --------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_use_admonition_for_examples = True

# -- Warnings as errors ---------------------------------------------------

# CI runs ``sphinx-build -W`` to fail the build on any warning. The local
# ``Makefile`` mirrors this for parity. Suppressed warnings are listed
# below so reviewers can audit each one.
suppress_warnings: list[str] = [
    # AutoAPI emits ambiguous-cross-reference warnings for TypeVars that
    # share a name across modules (e.g., ``ParamsT`` declared in both
    # ``contract.base`` and ``testing.factories``). The reference output
    # is correct in both pages; the warning is purely cosmetic.
    "ref.python",
]
