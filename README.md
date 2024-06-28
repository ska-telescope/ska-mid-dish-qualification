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
python3 -m venv .venv/
source .venv/bin/activate
```

### For users
Non-developing users can easily install the latest build directly from the project's package registry: 

```
pip install DiSQ --index-url https://gitlab.com/api/v4/projects/47618837/packages/pypi/simple
```

Or to install a specific release `<VERSION>`: 

```
pip install DiSQ==<VERSION> --index-url https://artefact.skao.int/repository/pypi-all/simple
```

Alternatively, if given a packaged wheel (`.whl`) from the developers: `pip install <package-name-version>.whl`

### For developers
Assuming you have your ssh keys setup in gitlab and access to the repo, first clone the repo:

```git clone git@gitlab.com:ska-telescope/ska-mid-dish-qualification.git```

Then install as an ["editable" development installation](https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs):

```pip install -e .[dev]```

Developers can also build a distributable package wheel using the [`build`](https://pypa-build.readthedocs.io/en/stable/) module. It is recommended to do this in a completely fresh clone and fresh virtualenv:

```
git clone git@gitlab.com:ska-telescope/ska-mid-dish-qualification.git
cd ska-mid-dish-qualification
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install build
python3 -m build --wheel
```

The resulting `.whl` package can be found in the `dist/` direcotory and be installed with `pip install <packagename>.whl`

In order to run the DiSQ software from a Linux distro without a GUI, like WSL2 Ubuntu, the following packages will need to be installed:

```apt-get install libxkbcommon-x11-0 libgl1 libegl1 libwayland-client0 libwayland-server0 libxcb1 libxcb-xkb1 -y```

## Usage
The DiSQ software is intended to be used either as a ready-made GUI application or for more advanced users as a library in Jupyter notebooks. See the examples directory for, well, examples.

After `pip` installing the package (see above) the GUI can be launched with the `disq-gui` command.

Installing the package will also make the server validator available with `disq-validate-server`. The expected usage is as follows:
```shell
disq-validate-server -x <xml file> -f <configuration file> -c <config> -o <output file>
disq-validate-server -x <xml file> -c <config> -o <output file>
```
Where the -x argument is an xml file used to generate a "good" OPCUA server to compare against, -f is a .ini configuration file containing server configurations, -c is the specific configuration within that file, and -o is the name of a file to write the output to (WARNING: The file specified by -o will be overwritten). The -f flag can be omitted and the script will attempt to use the system default configurations. It is recommended to open the output file in a text editor that can scroll horizontally (such as VSCode) as the output lines for the actual/expected nodes line up to make it easier to spot the differences.

The server validator can also be used with just the -i flag:
```shell
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
* Finally the users data directory is scanned for a `disq.ini` file
  * This is cross-platform compatible using [platformdirs](https://pypi.org/project/platformdirs/). On Linux `~/.local/share/disq/`

An example `disq.ini` file is provided in the root directory of the source distribution of this repo.

### Application Logs
DiSQ uses Python logging to log and output or record debug/info/warning/error messages. The logging comes pre-configured in `src/disq/default_logging_config.yaml` but this default configuration can be overridden by a custom configuration if a file named `disq_logging_config.yaml` is found in the current working directory (CWD) when starting the app. 

To tweak the default configuration, for example to switch to debug level, simply copy and rename the default logging config and make the required modifications to the copy:

```shell
cp src/disq/default_logging_config.yaml disq_logging_config.yaml
```

### Powershell Logs
There is a small powershell script in the repository root directory named log.ps1. Intended to be used as:
```shell
.\log.ps1 <git command>
```
to easily create logs of git commands run in a Windows powershell.
WARNING: This will only work with commands that output to the terminal. Commands that open a text editor will not behave correctly.

## Testing

At the time of writing, manual exploratory testing of the GUI application is done against the latest CETC54 simulator, which lags behind the current ICD version.

### Regression tests

Some regression tests with limited coverage are run as part of the CI/CD pipeline. If you have a development installation, these test should always be run locally with `make python-test` before pushing any commits.

The GUI tests mock the `model.run_opcua_command` method, so no simulator is involved other than the basic `DSSimulatorOPCUAServer` for the Logger's tests. This is what is done in the CI job.

Additionally, if you have the CETC simulator running on your local machine, the GUI tests can be run against it using:

    make python-test PYTHON_VARS_AFTER_PYTEST=--with-cetc-sim

`--with-cetc-sim` is a custom pytest argument. When using it, nothing is mocked, and the GUI and SCU library is more thoroughly tested against whatever version of the ICD the simulator is using.

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
