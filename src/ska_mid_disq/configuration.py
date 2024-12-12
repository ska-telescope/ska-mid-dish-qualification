"""
DiSQ configuration utilities.

This module contains functions for finding and reading the DiSQ configuration file, and
other global tasks such as configuring the python loggers.

The DiSQ server configuration file is a standard .ini file that can be parsed with the
configparser module.

Example configuration file `disq.ini`:

.. literalinclude:: ../../../disq.ini
"""

import datetime
import logging
import os
from configparser import ConfigParser
from importlib import resources
from logging.config import dictConfig
from pathlib import Path

import yaml  # type: ignore

from .constants import USER_CONFIG_DIR

# The default configuration file name to search for
_DEFAULT_CONFIG_FILENAME = "disq.ini"


def find_config_file(config_filename: str | None = None) -> Path:
    """
    Finds the configuration file named "disq.ini" and returns a ``Path`` pointing to it.

    The configuration file can be specified in three ways:

    1. By providing the file path as a command line option.
    2. By setting the ``DISQ_CONFIG`` environment variable to the file path.
    3. If neither of the above are provided, the function will look for the file in the
       user's data directory. The path for each OS:

       - Windows: /Users/your-username/AppData/Local/SKAO/disq
       - Ubuntu: /home/your-username/.config/disq
       - MacOS: /Users/your-username/Library/Application Support/disq

    :param config_filename: The name and path to a configuration file.
        If provided, it will be checked first. Defaults to None.
    :return: The path to the configuration file.
    :raises FileNotFoundError: If the configuration file is not found.
    """
    # Check if the CLI option was provided
    if config_filename is not None:
        fname_cli_option_path = Path(config_filename)
        logging.debug("Checking CLI option: %s", {fname_cli_option_path})
        if fname_cli_option_path.exists():
            return fname_cli_option_path

    # Check if the environment variable was set
    fname_env_var = os.getenv("DISQ_CONFIG")
    if fname_env_var is not None:
        fname_env_var_path = Path(fname_env_var)
        logging.debug(
            "Checking environment variable: %s=%s", "DISQ_CONFIG", {fname_env_var_path}
        )
        if fname_env_var_path.exists():
            return fname_env_var_path

    # Locate the user data directory
    fname_user_file = USER_CONFIG_DIR / _DEFAULT_CONFIG_FILENAME
    logging.debug("Checking user data directory: %s", {fname_user_file})
    if fname_user_file.exists():
        return fname_user_file

    # If we get here, the configuration file was not found
    raise FileNotFoundError(
        "Could not find the configuration file. "
        "Please set the DISQ_CONFIG environment variable or "
        "pass the configuration file path as a command line argument."
    )


def get_configurations(config_filename: str | None = None) -> ConfigParser:
    """
    Reads the configuration file and returns a ``ConfigParser`` object with the data.

    :param config_filename: The name of the configuration file. If None, the default
        configuration file is used.
    :return: A ConfigParser object.
    """
    # Find the configuration file
    config_file_path = find_config_file(config_filename)

    # Read the configuration file
    config = ConfigParser()
    config.read(config_file_path)

    return config


def get_config_sculib_args(
    config_filename: str | None = None, server_name: str = "DEFAULT"
) -> dict[str, str]:
    """
    Reads the configuration file and returns a dictionary of SCU library arguments.

    :param config_filename: (str, optional) The name of the configuration file. If None,
        the default configuration file is used.
    :param server_name: (str, optional) The name of the server to read from the
        configuration file. Defaults to "DEFAULT" which just picks the first server
        listed in the .ini file.
    :return: A dictionary containing the SCU library arguments, including the host,
        port, endpoint, and namespace.
    :raises FileNotFoundError: If the specified configuration file is not found.
    :raises KeyError: If specified server name is not found in the configuration file.
    :raises ValueError: If server port is not an integer.
    """
    config = get_configurations(config_filename)
    if server_name == "DEFAULT":
        server_name = config.sections()[0]
    else:
        server_name = f"opcua_server.{server_name}"
    server_config: dict[str, str] = dict(config[server_name])

    # Try to cast port to integer to validate input
    try:
        int(server_config["port"])
    except ValueError as e:
        logging.exception(
            "Specified port in config is not valid: %s", server_config["port"]
        )
        raise e
    # Every controller MUST have a host and port to be able to establish a connection
    sculib_args = {
        "host": server_config["host"],
        "port": server_config["port"],
    }
    # The remaining args are optional so we add them if defined in config
    # (PLC controller does not have these defined)
    optional_args = ["endpoint", "namespace", "username", "password", "use_nodes_cache"]
    for arg in optional_args:
        if arg in server_config:
            sculib_args[arg] = server_config[arg]
    logging.debug("SCU library args: %s", sculib_args)
    return sculib_args


def get_config_server_list(config_filename: str | None = None) -> list[str]:
    """
    Reads the configuration file and returns a list of server names.

    :param config_filename: The name of the configuration file. If None, the default
        configuration file is used.
    :return: A list containing the server names.
    """
    config = get_configurations(config_filename)
    server_list = [server.split(".")[1] for server in config.sections()]
    return server_list


def configure_logging(default_log_level: int = logging.INFO) -> None:
    """
    Configure logging settings based on a YAML configuration file.

    :param default_log_level: The default logging level to use if no configuration file
        is found. Defaults to logging.INFO.
    :raises ValueError: If an error occurs while configuring logging from the file.
    """
    disq_log_config_file = Path("disq_logging_config.yaml")
    if disq_log_config_file.exists() is False:
        disq_log_config_file = Path(
            resources.files(__package__) / "default_logging_config.yaml"  # type: ignore
        )
    config = None
    if disq_log_config_file.exists():
        with open(disq_log_config_file, "rt", encoding="UTF-8") as f:
            try:
                config = yaml.safe_load(f.read())
            except yaml.YAMLError as e:
                print(f"{type(e).__name__}: '{e}'")
                print(
                    "WARNING: Unable to read logging configuration file "
                    f"{disq_log_config_file}"
                )
        try:
            at_time = datetime.time.fromisoformat(
                config["handlers"]["file_handler"]["atTime"]
            )
            config["handlers"]["file_handler"]["atTime"] = at_time
        except KeyError as e:
            print(f"WARNING: {e} not found in logging configuration for file_handler")
    else:
        print(f"WARNING: Logging configuration file {disq_log_config_file} not found")

    if config is None:
        print(f"Reverting to basic logging config at level:{default_log_level}")
        logging.basicConfig(level=default_log_level)
    else:
        Path("logs").mkdir(parents=True, exist_ok=True)
        try:
            dictConfig(config)
        except ValueError as e:
            print(f"{type(e).__name__}: '{e}'")
            print(
                "WARNING: Caught exception. Unable to configure logging from file "
                f"{disq_log_config_file}. Reverting to logging to the console "
                "(basicConfig)."
            )
            logging.basicConfig(level=default_log_level)
