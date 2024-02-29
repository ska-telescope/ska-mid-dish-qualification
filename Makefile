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
PYTHON_LINT_TARGET = src/ tests/

#######################################
# DOCS
#######################################
include .make/docs.mk
