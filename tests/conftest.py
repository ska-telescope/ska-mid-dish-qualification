"""Tests configuration."""

from unittest.mock import MagicMock

import pytest

from disq.controller import Controller
from disq.model import Model
from disq.view import MainView


def pytest_addoption(parser: pytest.Parser):
    """Add custom pytest options for test setup."""
    parser.addoption(
        "--with-cetc-sim",
        action="store_true",
        help="A running CETC54 simulator is available to run the tests against.",
    )


@pytest.fixture(name="main_view", scope="module")
def main_view_fixture() -> MainView:
    """Fixture to setup the DiSQ application."""
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)
    return main_view


@pytest.fixture(name="disq_cetc_simulator", scope="module")
def disq_cetc_simulator_fixture(main_view: MainView) -> MainView:  # type: ignore
    """Fixture of DiSQ connected to running CETC simulator."""
    main_view.controller.connect_server(
        {
            "host": "localhost",
            "port": "4840",
            "endpoint": "/OPCUA/SimpleServer",
            "namespace": "CETC54",
            "username": "LMC",
            "password": "lmc",
        }
    )
    yield main_view
    main_view.controller.disconnect_server()
    main_view.close()


@pytest.fixture(name="disq_mock_model")
def disq_mock_model_fixture(main_view: MainView) -> MainView:
    """Fixture of DiSQ with mocks for model methods."""
    main_view.model.run_opcua_command = MagicMock(  # type: ignore
        return_value=(0, "CommandStatus", None)
    )
    return main_view
