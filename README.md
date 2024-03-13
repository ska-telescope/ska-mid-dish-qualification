# Dish Structure Qualification (DiSQ)

This repository: `ska-mid-dish-qualification` contain the source code for the Dish Structure Qualification software, known as "DiSQ" in everyday terminology. 

## Description
DiSQ enables engineers and scientists to control and qualify observatory dish structures for the SKAO MID telescope. The dish structures will be delivered with a PLC based control system which provides an OPC-UA interface for external control and monitoring. The DiSQ software communicates with the PLC via this interface and provides the users with:

* A GUI application for easy control and monitoring of key features.
* A Python API intended for performing complex operations such as tracking for verification of the dish structure, intended to be used in Jupyter notebooks.
* A data logger built in to both of the two above interfaces to allow recording of engineering parameters published from the PLC.

## Installation
This is a python software package which can be installed with the ubiquitous `pip` tool.

Python >= 3.11 is required for this software package. Python package dependencies are installed automatically during the following installation steps.

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

```
pip install -e .[dev]
```

Developers can also build a distributable package wheel using the [`build`](https://pypa-build.readthedocs.io/en/stable/) module. It is recommended to do this in a completely fresh clone and fresh virtualenv:

```
git clone git@gitlab.com:ska-telescope/ska-mid-dish-qualification.git
cd ska-mid-dish-qualification
python3 -m venv venv
source venv/bin/activate
python3 -m pip install build
python3 -m build --wheel
```

The resulting `.whl` package can be found in the `dist/` direcotory and be installed with `pip install <packagename>.whl`

## Usage
The DiSQ software is intended to be used either as a ready-made GUI application or for more advanced users as a library in Jupyter notebooks. See the examples directory for, well, examples.

After `pip` installing the package (see above) the GUI can be launched with the `disq-gui` command.

Installing the package will also make the server validator available with `disq-validate-server`. The expected usage is as follows:
```shell
disq-validate-server -x <xml file> -f <configuration file> -c <config>
disq-validate-server -x <xml file> -c <config>
```
Where the -x argument is an xml file used to generate a "good" OPCUA server to compare against, -f is a .ini configuration file containing server configurations, and -c is the specific configuration within that file. The -f flag can be omitted and the script will attempt to use the system default configurations.

The server validator can also be used with just the -i flag:
```shell
disq-validate-server -i <configuration file>
disq-validate-server -i
```
The -i flag will list the available configs in the given configuration file. If used without an argument the script will attempt to list the available configs in the system default configurations. For more information on configuration files see the Configuration section below.

Finally the `disq-validate-server` has a -h flag to output information about its options.


### Configuration
A configuration file named `ska-mid-disq.ini` can be used to specify a list of servers and their parameters. The user can then select the specific server to connect to from a drop-down menu widget and save having to type in all the server parameters.

The GUI application will search for the configuration file in the following order:
* First the current working directory (CWD) is searched for a `ska-mid-disq.ini` file.
* Then the environment variable `DISQ_CONFIG` is scanned for the existence of a file (any filename)
* Finally the users data directory is scanned for a `ska-mid-disq.ini` file
  * This is cross-platform compatible using [platformdirs](https://pypi.org/project/platformdirs/). On Linux `~/.local/share/ska_mid_dish_qualification/`

### Application Logs
DiSQ uses Python logging to log and output or record debug/info/warning/error messages. The logging comes pre-configured in `src/ska_mid_dish_qualification/default_logging_config.py` but this default configuration can be overridden by a custom configuration if a file named `disq_logging_config.yaml` is found in the current working directory (CWD) when starting the app. 

To tweak the default configuration, for example to switch to debug level, simply copy and rename the default logging config and make the required modifications to the copy:

```shell
cp src/ska_mid_dish_qualification/default_logging_config.py disq_logging_config.yaml
```

### Powershell Logs
There is a small powershell script in the repository root directory named log.ps1. Intended to be used as:
```shell
.\log.ps1 <git command>
```
to easily create logs of git commands run in a Windows powershell.
WARNING: This will only work with commands that output to the terminal. Commands that open a text editor will not behave correctly.

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
