#
# Project makefile for SKA-Mid dish qualification software. 
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.

PROJECT = DiSQ

include .make/base.mk
# include .make/raw.mk

# -include PrivateRules.mak

#######################################
# PYTHON
#######################################
include .make/python.mk

PYTHON_LINE_LENGTH = 88
PYTHON_LINT_TARGET = tests/ src/

PYTHON_SWITCHES_FOR_BLACK = --force-exclude "src/disq/_version.py"
PYTHON_SWITCHES_FOR_FLAKE8 = --config .flake8
PYTHON_SWITCHES_FOR_PYLINT = --rcfile .pylintrc

python-post-lint: # TODO: fix issues with excluded files
	$(PYTHON_RUNNER) mypy --exclude "sculib.py|ds_opcua_server_mock.py" src/ tests/

#######################################
# DOCS
#######################################
include .make/docs.mk

DOCS_SPHINXOPTS = -Q