"""
This module contains functions for finding and reading the configuration file for the
application. The configuration file is a standard .ini file that can be parsed with
the configparser module.

Example configuration file `disq.ini`:

    [DEFAULT]
    port = 4840
    subscription_period_ms = 100

    [opcua_server.cetc54_simulator]
    host = 127.0.0.1
    endpoint = /OPCUA/SimpleServer
    namespace = CETC54
    auth_user = LMC

    [opcua_server.karoo_simulator]
    host = 127.0.0.1
    endpoint = /dish-structure/server/
    namespace = http://skao.int/DS_ICD/

Functions:
    find_config_file(config_filename: str | None = None) -> Path:
        Finds the configuration file named "disq.ini" and returns its path as a Path
        object. The configuration file can be specified in three ways:
            1. By providing the file path as a command line option.
            2. By setting the DISQ_CONFIG environment variable to the file path.
            3. If neither of the above are provided, the function will look for the
            file in the user's data directory.
        If the configuration file is not found, a FileNotFoundError is raised.

    get_configuration(config_filename: str | None = None) -> configparser.ConfigParser:
        Reads the configuration file and returns a ConfigParser object containing the
        configuration data.

    get_config_sculib_args(config_filename, server_name) -> dict[str, str]:
        Convenience function: Reads the configuration file and returns a dictionary of
        SCU library arguments.
"""

import configparser
import logging
import os
from pathlib import Path

import platformdirs

# The default configuration file name to search for
_DEFAULT_CONFIG_FILENAME = "disq.ini"


def find_config_file(config_filename: str | None = None) -> Path:
    """
    Finds the configuration file named "disq.ini"

    The logic for finding the configuration file is as follows in mermaid diagram
    syntax:

    mermaid:
        graph TD
            A[Start] --> B{CLI option provided?}
            B -->|No| E
            B -->|yes| C[Read CLI option]
            C --> D{File found?}
            D -->|Yes| RET[Return file path]
            D -->|No| E[Read environment variable]
            E --> F{env variable set\nAND File found?}
            F -->|Yes| RET
            F -->|No| G[Locate user data dir]
            G --> H{File found?}
            H -->|Yes| RET
            H -->|No| ERR[Raise exception]

    Args:
        config_filename (str, optional): The name and path to a configuration file.
            If provided, it will be checked first. Defaults to None.

    Returns:
        Path: The path to the configuration file.

    Raises:
        FileNotFoundError: If the configuration file is not found.

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
    fname_user_dir = Path(
        platformdirs.user_config_dir(appauthor="SKAO", appname="disq")
    )
    fname_user_file = fname_user_dir / _DEFAULT_CONFIG_FILENAME
    logging.debug("Checking user data directory: %s", {fname_user_file})
    if fname_user_file.exists():
        return fname_user_file

    # If we get here, the configuration file was not found
    raise FileNotFoundError(
        "Could not find the configuration file. "
        "Please set the DISQ_CONFIG environment variable or "
        "pass the configuration file path as a command line argument."
    )


def get_configurations(config_filename: str | None = None) -> configparser.ConfigParser:
    """
    Reads the configuration file and returns a ConfigParser object.

    Args:
        config_filename (str, optional): The name of the configuration file.
            If None, the default configuration file is used.

    Returns:
        configparser.ConfigParser: A ConfigParser object.
    """
    # Find the configuration file
    config_file_path = find_config_file(config_filename)

    # Read the configuration file
    config = configparser.ConfigParser()
    config.read(config_file_path)

    return config


def get_config_sculib_args(
    config_filename: str | None = None, server_name: str = "DEFAULT"
) -> dict[str, str | int]:
    """
    Reads the configuration file and returns a dictionary of SCU library arguments.

    Args:
        config_filename (str, optional): The name of the configuration file. If None,
            the default configuration file is used.
        server_name (str, optional): The name of the server to read from the
            configuration file. Defaults to "DEFAULT" which just picks the first server
            listed in the .ini file.

    Returns:
        dict[str, str | int]: A dictionary containing the SCU library arguments,
        including the host, port, endpoint, and namespace.

    Raises:
        FileNotFoundError: If the specified configuration file is not found.
        KeyError: If the specified server name is not found in the configuration file.
    """
    config: configparser.ConfigParser = get_configurations(config_filename)
    if server_name == "DEFAULT":
        server_name = config.sections()[0]
    else:
        server_name = f"opcua_server.{server_name}"
    server_config: dict[str, str] = dict(config[server_name])

    # Every controller MUST have a host and port to be able to establish a connection
    sculib_args: dict[str, str | int] = {
        "host": str(server_config["host"]),
        "port": int(server_config["port"]),
    }
    # The remaining args are optional so we add them if defined in config (PLC controller does not have these defined)
    optional_args = ["endpoint", "namespace", "username", "password"]
    for arg in optional_args:
        if arg in server_config:
            sculib_args[arg] = str(server_config[arg])
    logging.debug("SCU library args: %s", sculib_args)
    return sculib_args


def get_config_server_list(config_filename: str | None = None) -> list[str]:
    """
    Reads the configuration file and returns a list of server names.

    Args:
        config_filename (str, optional): The name of the configuration file. If None,
            the default configuration file is used.

    Returns:
        list[str]: A list containing the server names.
    """
    config: configparser.ConfigParser = get_configurations(config_filename)
    server_list = [server.split(".")[1] for server in config.sections()]
    return server_list
