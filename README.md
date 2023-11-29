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

Developers can also build a distributable package wheel using the [`build`](https://pypa-build.readthedocs.io/en/stable/) module. It is recommended to do this in a completely fresh clone and fresh virtualenv:

```
git clone git@gitlab.com:ska-telescope/ska-mid-dish-qualification.git
python3 -m venv venv
source venv/bin/activate
python3 -m pip install build
python3 -m build --wheel
```

The resulting `.whl` package can be found in the `dist/` direcotory and be installed with `pip install <packagename>.whl`

## Usage
The DiSQ software is intended to be used either as a ready-made GUI application or for more advanced users as a library in Jupyter notebooks. See the examples directory for, well, examples.

### Environment
The following environment variables can be used to modify default parameter values. The recommended way to manage these configurations are to drop a `.env` file in the current working directory. The default settings can be modified.

For the "Karoo" simulator, running on your local host (127.0.0.1) use:

```ini
DISQ_OPCUA_SERVER_ADDRESS=127.0.0.1
DISQ_OPCUA_SERVER_NAMESPACE=http://skao.int/DS_ICD/
DISQ_OPCUA_SERVER_ENDPOINT=/dish-structure/server/
DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS=100
```

For the "CETC" simulator, running on your local host (127.0.0.1) use:

```ini
DISQ_OPCUA_SERVER_ADDRESS=127.0.0.1
DISQ_OPCUA_SERVER_NAMESPACE=CETC54
DISQ_OPCUA_SERVER_ENDPOINT=/OPCUA/SimpleServer
DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS=100
```

### Application Logs
DiSQ uses Python logging to log and output or record debug/info/warning/error messages. The logging comes pre-configured in `src/disq/default_logging_config.py` but this default configuration can be overridden by a custom configuration if a file named `disq_logging_config.yaml` is found in the current working directory (CWD) when starting the app. 

To tweak the default configuration, for example to switch to debug level, simply copy and rename the default logging config and make the required modifications to the copy:

```shell
cp src/disq/default_logging_config.py disq_logging_config.yaml
```

## Authors and acknowledgment
SKAO Team Wombat is developing this project:

* Thomas Juerges
* Oliver Skivington
* Ulrik Pedersen

## License
Copyright 2020 SARAO - see LICENSE file for details.
Copyright 2023 SARAO and SKA Observatory

## Project status
This project is in development.
