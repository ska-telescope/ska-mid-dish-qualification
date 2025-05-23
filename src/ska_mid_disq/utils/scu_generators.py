"""SteeringControlUnit (SCU) object generator methods."""

import logging

from ska_mid_disq import SCU, SCUWeatherStation, SteeringControlUnit

from .configuration import configure_logging, get_config_sculib_args

logger = logging.getLogger("ska-mid-ds-scu")


# pylint: disable=invalid-name
def SCU_from_config(  # noqa: N802
    server_name: str,
    ini_file: str = "disq.ini",
    use_nodes_cache: bool = True,
    authority_name: str | None = None,
) -> SteeringControlUnit | None:
    """
    SCU object generator method.

    This method creates an SCU object based on OPC-UA server_name connection details
    found in the ini_file configuration file. It then connects the SCU object to the
    OPC-UA server and sets it up, ready to be used with the attributes and commands.

    The method also configures logging based on the log configuration file:
    "disq_logging_config.yaml".

    :param server_name: the name of the OPC-UA server to connect to.
    :param ini_file: the name of the configuration file to read the connection details
        from, defaults to "disq.ini".
    :param use_nodes_cache: a flag to indicate whether to use the nodes cache, defaults
        to True.
    :param authority_name: optional user name to take authority as when connecting to
        the DSC, defaults to None.
    :return: an initialised and connected instance of the SteeringControlUnit class or
        None if the connection to the OPC-UA server failed.
    """
    configure_logging()
    sculib_args: dict = get_config_sculib_args(ini_file, server_name=server_name)
    # TODO: figure out a neat way to handle conversion of config variables from string
    if "timeout" in sculib_args:
        sculib_args["timeout"] = float(sculib_args["timeout"].strip())
    if "port" in sculib_args:
        sculib_args["port"] = int(sculib_args["port"].strip())
    try:
        scu = SCU(
            **sculib_args,
            use_nodes_cache=use_nodes_cache,
            authority_name=authority_name,
        )
    except ConnectionRefusedError:
        logger.error(
            "Failed to connect to the OPC-UA server with connection parameters: %s",
            str(sculib_args),
        )
        return None
    return scu


# pylint: disable=invalid-name
def SCUWeatherStation_from_config(  # noqa: N802
    server_name: str,
    ini_file: str = "disq.ini",
    authority_name: str | None = None,
) -> SCUWeatherStation | None:
    """
    SCUWeatherStation object generator method.

    This method creates an SCUWeatherStation object based on OPC-UA server_name
    connection details found in the ini_file configuration file. It then connects the
    SCUWeatherStation object to the OPC-UA server and sets it up, ready to be used with
    the attributes and commands.

    The method also configures logging based on the log configuration file:
    "disq_logging_config.yaml".

    :param server_name: the name of the OPC-UA server to connect to.
    :param ini_file: the name of the configuration file to read the connection details
        from, defaults to "disq.ini".
    :param authority_name: optional user name to take authority as when connecting to
        the DSC, defaults to None.
    :return: an initialised and connected instance of the SCUWeatherStation class or
        None if the connection to the OPC-UA server failed.
    """  # noqa: D403
    configure_logging()
    sculib_args: dict = get_config_sculib_args(ini_file, server_name=server_name)
    # TODO: figure out a neat way to handle conversion of config variables from string
    if "timeout" in sculib_args:
        sculib_args["timeout"] = float(sculib_args["timeout"].strip())
    if "port" in sculib_args:
        sculib_args["port"] = int(sculib_args["port"].strip())
    try:
        scu = SCUWeatherStation(
            **sculib_args,
        )
        scu.connect_and_setup()
        if authority_name is not None:
            scu.take_authority(authority_name)
        return scu
    except ConnectionRefusedError:
        logger.error(
            "Failed to connect to the OPC-UA server with connection parameters: %s",
            str(sculib_args),
        )
        return None
