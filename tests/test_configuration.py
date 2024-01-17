import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from disq.configuration import find_config_file, get_configurations


def test_find_config_file():
    # Test when fname_cli_option is None
    with patch("os.getenv", return_value=None):
        with pytest.raises(FileNotFoundError):
            find_config_file(None)

    # Test when fname_cli_option is a valid file
    with patch("os.getenv", return_value=None):
        assert find_config_file(__file__) == Path(__file__)


def test_get_configuration():
    # Test when fname is None
    with patch("disq.configuration.find_config_file", return_value=Path("disq.ini")):
        config = get_configurations(None)
        assert config is not None

    # Test when fname is a valid config file
    with patch("disq.configuration.find_config_file", return_value=Path("disq.ini")):
        config = get_configurations("disq.ini")
        assert config is not None

    # Test when the file exist but is not a valid configuration file
    with patch(
        "disq.configuration.find_config_file", return_value=Path(__file__)
    ), pytest.raises(configparser.Error):
        config = get_configurations(__file__)

    # Test with the test file disq.ini
    config = get_configurations("disq.ini")
    assert config is not None
    assert config["DEFAULT"]["port"] == "4840"
    assert "opcua_server.cetc54_simulator" in config.sections()
    assert "opcua_server.karoo_simulator" in config.sections()
