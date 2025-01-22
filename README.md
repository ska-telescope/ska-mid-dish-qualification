# SKA-Mid Dish Structure Qualification (DiSQ)

This repository contains the source code for the Dish Structure Qualification software, known as "DiSQ" in everyday terminology. 

## Description
DiSQ enables engineers and scientists to control and qualify observatory dish structures for the SKA-Mid telescope. The dish structures will be delivered with a PLC based control system which provides an OPC-UA interface for external control and monitoring. The DiSQ software communicates with the PLC via this interface and provides the users with:

* A GUI application for easy control and monitoring of key features.
* A Python API intended for performing complex operations such as tracking for verification of the dish structure, intended to be used in Jupyter notebooks.
* A data logger built in to both of the two above interfaces to allow recording of engineering parameters published from the PLC.

## Installation
This is a python software package which can be installed with the ubiquitous `pip` tool.

Python >= 3.10 is required for this software package. Python package dependencies are installed automatically during the following installation steps.

The recommendation is to use a [virtualenv](https://docs.python.org/3/library/venv.html):
```
python3 -m venv .venv/
source .venv/bin/activate
```

### For users
Users can easily install the latest development build directly from the project's package registry: 
```
pip install ska-mid-disq --index-url https://gitlab.com/api/v4/projects/47618837/packages/pypi/simple --extra-index-url https://artefact.skao.int/repository/pypi-all/simple
```

In other words, users should not keep a git clone and pull from main anymore to get the latest changes,
just python and pip needs to be installed. Installing the pre-built package is recommemded 
because it will display an accurate version number containing the relevant short commit hash, 
such as  `0.4.0+dev.c68862160`. This helps the developers when providing support.
To check the currently installed version, use `pip show ska-mid-disq`.

Users can also install the latest stable release from the SKAO central artefact repository: 
```
pip install ska-mid-disq --index-url https://artefact.skao.int/repository/pypi-all/simple
```

Alternatively, if given a packaged wheel (`.whl`) from the developers: `pip install <package-name-version>.whl`

If you want to install a newer build in an existing evironment, you might need to first 
uninstall the existing version using `pip uninstall ska-mid-disq`. This should only be necessary
if the currently installed version is a recent development build based on the same 
tagged release as the one you are trying to install. 

### For developers
Assuming you have your ssh keys setup in gitlab and access to the repo, first clone the repo:
```
git clone --recurse-submodules git@gitlab.com:ska-telescope/ska-mid-disq.git
```

Then install as an ["editable" development installation](https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs):
```
pip install -e .[dev]
```

#### How to develop the [Steering Control Unit](https://gitlab.com/ska-telescope/ska-mid-dish-steering-control) simultaneously with DiSQ

To make code changes to the SCU package in your local virtualenv, you need a clone of its repo installed as an editable package. First clone the repo in the same directory where this one is on your machine, and create a new development branch:
```
git clone --recurse-submodules git@gitlab.com:ska-telescope/ska-mid-dish-steering-control.git
```

Then within your existing DiSQ venv, install the local working copy of SCU as an editable package:
```
pip install -e ../ska-mid-dish-steering-control
```

Now you can develop `ska-mid-dish-steering-control` as a separate project in a editor while using the working changes in the DiSQ project.

If you want to revert your virtualenv to use the version of `ska-mid-dish-steering-control` as defined in the `pyproject.toml`:
```
pip install -e .[dev] --upgrade
```

#### Building a distributable
Developers can also build a distributable package wheel using `make python-build`, which uses the [`build`](https://pypa-build.readthedocs.io/en/stable/) module in a temporary isolated virtualenv.

The resulting `.whl` package can be found in the `dist/` directory and be installed with `pip install <packagename>.whl`

#### Running in WSL2
In order to run the DiSQ software from a Linux distro without a GUI, like WSL2 Ubuntu, the following packages will need to be installed:
```
apt-get install libxkbcommon-x11-0 libgl1 libegl1 libwayland-client0 libwayland-server0 libxcb1 libxcb-xkb1 -y
```

## Usage
The DiSQ software is intended to be used either as a ready-made GUI application or for more advanced users as a library in Jupyter notebooks. See the examples directory for, well, examples.

After `pip` installing the package (see above) the GUI can be launched with the `disq-gui` command.

Installing the package will also make the server validator available with `disq-validate-server`. The expected usage is as follows:
```
disq-validate-server -x <xml file> -f <configuration file> -c <config> -o <output file>
disq-validate-server -x <xml file> -c <config> -o <output file>
```
Where the -x argument is an xml file used to generate a "good" OPCUA server to compare against, -f is a .ini configuration file containing server configurations, -c is the specific configuration within that file, and -o is the name of a file to write the output to (WARNING: The file specified by -o will be overwritten). The -f flag can be omitted and the script will attempt to use the system default configurations. It is recommended to open the output file in a text editor that can scroll horizontally (such as VSCode) as the output lines for the actual/expected nodes line up to make it easier to spot the differences.

The server validator can also be used with just the -i flag:
```
disq-validate-server -i <configuration file>
disq-validate-server -i
```
The -i flag will list the available configs in the given configuration file. If used without an argument the script will attempt to list the available configs in the system default configurations. For more information on configuration files see the Configuration section below.

Finally the `disq-validate-server` has a -h flag to output information about its options.


### Configuration
A configuration file named `disq.ini` can be used to specify a list of servers and their parameters. The user can then select the specific server to connect to from a drop-down menu widget and save having to type in all the server parameters.

The GUI application will search for the configuration file in the following order:
* First the current working directory (CWD) is searched for a `disq.ini` file.
* Then the environment variable `DISQ_CONFIG` is scanned for the existence of a file (any filename)
* Finally the users data directory is scanned for a `disq.ini` file. This is cross-platform compatible using [platformdirs](https://pypi.org/project/platformdirs/):
  * Windows: /Users/your-username/AppData/Local/SKAO/disq
  * Ubuntu: /home/your-username/.config/disq
  * MacOS: /Users/your-username/Library/Application Support/disq

An example `disq.ini` file is provided in the root directory of the source distribution of this repo.

### Application Logs
DiSQ uses Python logging to log and output or record debug/info/warning/error messages. The logging comes pre-configured in `src/ska_mid_disq/default_logging_config.yaml` but this default configuration can be overridden by a custom configuration if a file named `disq_logging_config.yaml` is found in the current working directory (CWD) when starting the app. 

To tweak the default configuration, for example to switch to debug level, simply copy and rename the default logging config and make the required modifications to the copy:
```
cp src/ska_mid_disq/default_logging_config.yaml disq_logging_config.yaml
```

### Powershell Logs
There is a small powershell script in the repository root directory named log.ps1. Intended to be used as:
```
.\log.ps1 <git command>
```
to easily create logs of git commands run in a Windows powershell.
WARNING: This will only work with commands that output to the terminal. Commands that open a text editor will not behave correctly.

## Testing
At the time of writing, manual exploratory testing of the GUI application is done against the latest CETC54 simulator, which lags behind the current ICD version.

### Regression tests
Some regression tests with limited coverage are run as part of the CI/CD pipeline. If you have a development installation, these test should always be run locally with `make python-test` before pushing any commits.

In order to run the GUI and `DataLogger` tests locally, you need the latest CETC simulator image (named 'simulator' and tagged with a version number) already built in your local docker image registry from [ska-te-dish-structure-simulator](https://gitlab.com/ska-telescope/ska-te-dish-structure-simulator). The ``make python-test`` target should always be used, as it executes a pre- and post-target to start and stop the container. If you want to run only some tests, you need to use:
```
make python-test PYTHON_TEST_FILE=tests/test_commands.py::test_opcua_command_slot_function
```

To run the tests (only some will be) against the PLC at the Mid-ITF, use the defined custom pytest option:
```
make python-test PYTHON_VARS_AFTER_PYTEST=--with-plc
```

## Authors and acknowledgment
SKAO Team Wombat is developing this project:

* Thomas Juerges
* Oliver Skivington
* Ulrik Pedersen
* Jarrett Engelbrecht

## License
Copyright 2020 SARAO - see LICENSE file for details.
Copyright 2023 SARAO and SKA Observatory

## Project status
This project is in development.
