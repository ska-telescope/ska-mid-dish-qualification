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

PYTHON_SWITCHES_FOR_BLACK = --force-exclude "src/disq/sculib.py|src/disq/_version.py"
PYTHON_SWITCHES_FOR_FLAKE8 = --config .flake8
PYTHON_SWITCHES_FOR_PYLINT = --rcfile .pylintrc

#######################################
# DOCS
#######################################
include .make/docs.mk
