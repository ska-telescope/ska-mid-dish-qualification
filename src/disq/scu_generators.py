"""SteeringControlUnit (SCU) object generator methods."""

import logging

from disq import SCU, SteeringControlUnit, configuration
from disq.constants import USER_CACHE_DIR

logger = logging.getLogger("ska-mid-ds-scu")


# pylint: disable=invalid-name
def SCU_from_config(  # noqa: N802
    server_name: str,
    ini_file: str = "disq.ini",
    use_nodes_cache: bool = True,
    authority_name: str | None = None,
) -> SteeringControlUnit | None:
    """SCU object generator method.

    This method creates an SCU object based on OPC-UA server_name connection details
    found in the ini_file configuration file. It then connects the SCU object to the
    OPC-UA server and sets it up, ready to be used with the attributes and commands.

    The method also configures logging based on the log configuration file:
    "disq_logging_config.yaml".

    :return: an initialised and connected instance of the SteeringControlUnit class or
        None if the connection to the OPC-UA server failed.
    """
    configuration.configure_logging()
    sculib_args: dict = configuration.get_config_sculib_args(
        ini_file, server_name=server_name
    )
    # TODO: figure out a neat way to handle conversion of config variables from string
    if "timeout" in sculib_args:
        sculib_args["timeout"] = float(sculib_args["timeout"].strip())
    if "port" in sculib_args:
        sculib_args["port"] = int(sculib_args["port"].strip())
    try:
        scu = SCU(
            **sculib_args,
            use_nodes_cache=use_nodes_cache,
            nodes_cache_dir=USER_CACHE_DIR,
            authority_name=authority_name,
        )
    except ConnectionRefusedError:
        logger.error(
            "Failed to connect to the OPC-UA server with connection parameters: %s",
            str(sculib_args),
        )
        return None
    return scu
