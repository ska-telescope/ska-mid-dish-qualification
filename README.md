# Dish Structure Qualification (DiSQ)

This repository: `ska-mid-dish-qualification` contain the source code for the Dish Structure Qualification software, known as "DiSQ" in everyday terminology. 

## Description
DiSQ enables engineers and scientists to control and qualify observatory dish structures for the SKAO MID telescope. The dish structures will be delivered with a PLC based control system which provides an OPC-UA interface for external control and monitoring. The DiSQ software communicates with the PLC via this interface and provides the users with:

* A GUI application for easy control and monitoring of key features.
* A Python API intended for performing complex operations such as tracking for verification of the dish structure, intended to be used in Jupyter notebooks.
* A data logger built in to both of the two above interfaces to allow recording of engineering parameters published from the PLC.

## Installation
This is a python software package which can be installed with the ubiquitous `pip` tool.

Python >= 3.10 is required for this software package. Python package dependencies are installed automatically during the following installation steps.

The recommendation is to use a [virtualenv](https://docs.python.org/3/library/venv.html):
```
python -m venv .venv/
source .venv/bin/activate
```

### For users:
Non-developing users can easily install the software directly from the repository: `pip install https://gitlab.com/ska-telescope/ska-mid-dish-qualification.git`

Or to install a specific `<VERSION>` use: `pip install https://gitlab.com/ska-telescope/ska-mid-dish-qualification.git@<VERSION>`

Alternatively, if given a packaged wheel (`.whl`) from the developers: `pip install <package-name-version>.whl`

### For developers
Assuming you have your ssh keys setup in gitlab and access to the repo, first clone the repo:

```git clone git@gitlab.com:ska-telescope/ska-mid-dish-qualification.git```

Then install as an ["editable" development installation](https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs):

```pip install -e .[dev]```

Developers can also build a distributable package wheel using the [`build`](https://pypa-build.readthedocs.io/en/stable/) module:

```python -m build --wheel```

The resulting `.whl` package can be found in the `dist/` direcotory and be installed with `pip install <packagename>.whl`

## Usage
The DiSQ software is intended to be used either as a ready-made GUI application or for more advanced users as a library in Jupyter notebooks. See the examples directory for, well, examples.

## Authors and acknowledgment
SKAO Team Wombat is developing this project:

* Thomas Juerges
* Oliver Skivington
* Ulrik Pedersen

## License
Copyright 2020 SKA Observatory - see LICENSE file for details.

## Project status
This project is in development.
