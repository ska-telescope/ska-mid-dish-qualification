#
# Project makefile for SKA-Mid dish qualification software. 
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.

PROJECT = ska-mid-dish-qualification

include .make/base.mk
# include .make/raw.mk

# -include PrivateRules.mak

#######################################
# PYTHON
#######################################
include .make/python.mk

PYTHON_LINE_LENGTH = 88
# PYTHON_LINT_TARGET = tests/
# linting source has way too many problems to fix right now
PYTHON_LINT_TARGET = tests/ src/

PYTHON_SWITCHES_FOR_BLACK = --force-exclude "src/ska_mid_dish_qualification/sculib.py"
PYTHON_SWITCHES_FOR_FLAKE8 = --config .flake8
PYTHON_SWITCHES_FOR_PYLINT = --rcfile .pylintrc

#######################################
# DOCS
#######################################
include .make/docs.mk
