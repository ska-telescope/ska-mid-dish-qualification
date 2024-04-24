"""Tests of the GUI."""

from unittest.mock import MagicMock

import pytest

from disq.controller import Controller
from disq.model import Model
from disq.view import MainView


@pytest.fixture(name="app")
def app_fixture(qtbot) -> MainView:
    """Fixture to setup the application."""
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)
    qtbot.addWidget(main_view)
    return main_view


def test_slew2abs_button_clicked_positive_position(app):
    """Test the successful execution of slew2abs_button_clicked."""
    # Setup the text inputs with valid float strings
    app.line_edit_slew_simul_azim_position.setText("10")
    app.line_edit_slew_simul_elev_position.setText("20")
    app.line_edit_slew_simul_azim_velocity.setText("0.5")
    app.line_edit_slew_simul_elev_velocity.setText("0.3")

    # Mock the controller's methods
    app.controller.command_slew2abs_azim_elev = MagicMock()
    app.controller.emit_ui_status_message = MagicMock()

    # Simulate the button click
    app.slew2abs_button_clicked()

    # Verify that the controller's method was called with the correct arguments
    app.controller.command_slew2abs_azim_elev.assert_called_once_with(10, 20, 0.5, 0.3)
    app.controller.emit_ui_status_message.assert_not_called()


def test_slew2abs_button_clicked_negative_position(app):
    """Testing the behavior when the button is clicked with negative values."""
    # Setup the text inputs with negative position values
    app.line_edit_slew_simul_azim_position.setText("-10")
    app.line_edit_slew_simul_elev_position.setText("-20")
    app.line_edit_slew_simul_azim_velocity.setText("0.5")
    app.line_edit_slew_simul_elev_velocity.setText("0.3")

    # Mock the controller's methods
    app.controller.command_slew2abs_azim_elev = MagicMock()
    app.controller.emit_ui_status_message = MagicMock()

    # Simulate the button click
    app.slew2abs_button_clicked()

    # Verify that the controller's method was called with the correct arguments
    app.controller.command_slew2abs_azim_elev.assert_called_once_with(
        -10, -20, 0.5, 0.3
    )
    app.controller.emit_ui_status_message.assert_not_called()


def test_slew2abs_button_clicked_invalid_inputs(app):
    """Test the error handling in slew2abs_button_clicked when inputs are invalid."""
    # Setup the text inputs with non-convertible strings
    app.line_edit_slew_simul_azim_position.setText("a")
    app.line_edit_slew_simul_elev_position.setText("b")
    app.line_edit_slew_simul_azim_velocity.setText("c")
    app.line_edit_slew_simul_elev_velocity.setText("d")

    # Mock the controller's methods
    app.controller.command_slew2abs_azim_elev = MagicMock()
    app.controller.emit_ui_status_message = MagicMock()

    # Simulate the button click
    app.slew2abs_button_clicked()

    # Verify that the error message was emitted
    app.controller.emit_ui_status_message.assert_called_once()
    assert (
        "invalid arguments"
        in app.controller.emit_ui_status_message.call_args[0][1].lower()
    )
    app.controller.command_slew2abs_azim_elev.assert_not_called()


def test_slew2abs_button_clicked_empty_inputs(app):
    """Test the error handling in slew2abs_button_clicked when inputs are empty."""
    # Setup the text inputs with empty strings
    app.line_edit_slew_simul_azim_position.setText("")
    app.line_edit_slew_simul_elev_position.setText("")
    app.line_edit_slew_simul_azim_velocity.setText("")
    app.line_edit_slew_simul_elev_velocity.setText("")

    # Mock the controller's methods
    app.controller.command_slew2abs_azim_elev = MagicMock()
    app.controller.emit_ui_status_message = MagicMock()

    # Simulate the button click
    app.slew2abs_button_clicked()

    # Verify that the error message was emitted
    app.controller.emit_ui_status_message.assert_called_once()
    assert (
        "invalid arguments"
        in app.controller.emit_ui_status_message.call_args[0][1].lower()
    )
    app.controller.command_slew2abs_azim_elev.assert_not_called()
