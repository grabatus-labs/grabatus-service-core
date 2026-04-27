# Minimal Makefile for Sphinx docs.
#
# Usage:
#   make html           build the English HTML site (warnings as errors)
#   make pt_BR          build the Portuguese (Brazilian) HTML site
#   make gettext        extract translatable strings to docs/_build/gettext
#   make update-pt_BR   update docs/locale/pt_BR/LC_MESSAGES from gettext
#   make linkcheck      verify external links resolve
#   make clean          remove docs/_build/
#
# Both ``make html`` and ``make pt_BR`` use ``-W`` so any Sphinx warning
# fails the build, matching CI behaviour.

SPHINXBUILD ?= uv run sphinx-build
SOURCEDIR   := .
BUILDDIR    := _build

.PHONY: html pt_BR gettext update-pt_BR linkcheck clean

html:
	$(SPHINXBUILD) -W -b html "$(SOURCEDIR)" "$(BUILDDIR)/html/en"

pt_BR:
	$(SPHINXBUILD) -W -b html -D language=pt_BR "$(SOURCEDIR)" "$(BUILDDIR)/html/pt_BR"

gettext:
	$(SPHINXBUILD) -b gettext "$(SOURCEDIR)" "$(BUILDDIR)/gettext"

update-pt_BR: gettext
	uv run sphinx-intl update -p "$(BUILDDIR)/gettext" -l pt_BR

linkcheck:
	$(SPHINXBUILD) -b linkcheck "$(SOURCEDIR)" "$(BUILDDIR)/linkcheck"

clean:
	rm -rf "$(BUILDDIR)"
