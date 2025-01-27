"""Tests of the configuration file."""

import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from ska_mid_disq.utils.configuration import find_config_file, get_configurations


def test_find_config_file():
    # Test when fname_cli_option is None
    """
    Test function for finding a configuration file.

    This function tests the behavior of the find_config_file function under different
    scenarios.

    :param None: Testing scenario where environment variable is not set.
    :type None: None
    :param __file__: Testing scenario where a valid file path is provided as input.
    :type __file__: str
    :raises FileNotFoundError: If the environment variable is not set.
    """
    with patch("os.getenv", return_value=None):
        with pytest.raises(FileNotFoundError):
            find_config_file(None)

    # Test when fname_cli_option is a valid file
    with patch("os.getenv", return_value=None):
        assert find_config_file(__file__) == Path(__file__)


def test_get_configuration():
    # Test when fname is None
    """
    Test the get_configurations function.

    This function tests the get_configurations function by mocking the find_config_file
    function and checking the output configuration file.

    :raises: AssertionError: If any of the test cases fail.
    """
    with patch(
        "ska_mid_disq.utils.configuration.find_config_file",
        return_value=Path("disq.ini"),
    ):
        config = get_configurations(None)
        assert config is not None

    # Test when fname is a valid config file
    with patch(
        "ska_mid_disq.utils.configuration.find_config_file",
        return_value=Path("disq.ini"),
    ):
        config = get_configurations("disq.ini")
        assert config is not None

    # Test when the file exist but is not a valid configuration file
    with (
        patch(
            "ska_mid_disq.utils.configuration.find_config_file",
            return_value=Path(__file__),
        ),
        pytest.raises(configparser.Error),
    ):
        config = get_configurations(__file__)

    # Test with the test file disq.ini
    config = get_configurations("disq.ini")
    assert config is not None
    assert config["DEFAULT"]["port"] == "4840"
    assert "opcua_server.CETC54 simulator" in config.sections()
