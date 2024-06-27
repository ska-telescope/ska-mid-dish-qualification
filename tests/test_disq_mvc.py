"""Tests of the GUI."""

import time

import pytest
from PyQt6 import QtWidgets

from disq.view import MainView


@pytest.fixture(name="disq_app")
def disq_app_fixture(qtbot, request: pytest.FixtureRequest) -> MainView:  # type: ignore
    """Fixture to setup the qtbot with the DiSQ application."""
    # Switch the MainView between two fixtures defined in conftest.py
    with_cetc_simulator = request.config.getoption("--with-cetc-sim")
    with_plc = request.config.getoption("--with-plc")
    if with_cetc_simulator:
        disq_fixture: MainView = request.getfixturevalue("disq_cetc_simulator")
    elif with_plc:
        disq_fixture = request.getfixturevalue("disq_mid_itf_plc")
    else:
        disq_fixture = request.getfixturevalue("disq_mock_model")
    qtbot.addWidget(disq_fixture)
    # Setup simulator/PLC before running test
    if with_cetc_simulator or with_plc:
        disq_fixture.controller.command_take_authority("EGUI")
        disq_fixture.controller.command_stow(False)
        disq_fixture.controller.command_activate("AzEl")
        disq_fixture.controller.command_activate("Fi")
    yield disq_fixture
    # Stop any running slews and release authority after test (also done if test failed)
    if with_cetc_simulator or with_plc:
        disq_fixture.controller.command_stop("AzEl")
        disq_fixture.controller.command_stop("Fi")
        disq_fixture.controller.command_release_authority()
        time.sleep(0.05)


def set_combobox_to_string(combo_box: QtWidgets.QComboBox, string: str) -> bool:
    """Set QComboBox to string if the option exists."""
    for index in range(combo_box.count()):
        item_text = combo_box.itemText(index)
        if item_text == string:
            combo_box.setCurrentIndex(index)
            return True  # String found and set successfully
    return False  # String not found in combobox options


slew2abs_input_widgets = [
    "line_edit_slew_simul_azim_position",
    "line_edit_slew_simul_elev_position",
    "line_edit_slew_simul_azim_velocity",
    "line_edit_slew_simul_elev_velocity",
]
slew_azimuth_input_widgets = [
    "line_edit_slew_only_azimuth_position",
    "line_edit_slew_only_azimuth_velocity",
]
slew_elevation_input_widgets = [
    "line_edit_slew_only_elevation_position",
    "line_edit_slew_only_elevation_velocity",
]

pointing_model_setup_input_widgets = [
    "button_group_static_point_model",
    "button_group_tilt_correction",
    "button_group_temp_correction",
    "combo_static_point_model_band",
]
static_pointing_params_input_widgets = [
    "combo_static_point_model_band",
    "spinbox_ia",
    "spinbox_ca",
    "spinbox_npae",
    "spinbox_an",
    "spinbox_an0",
    "spinbox_aw",
    "spinbox_aw0",
    "spinbox_acec",
    "spinbox_aces",
    "spinbox_aba",
    "spinbox_abphi",
    "spinbox_ie",
    "spinbox_ecec",
    "spinbox_eces",
    "spinbox_hece4",
    "spinbox_hese4",
    "spinbox_hece8",
    "spinbox_hese8",
]
static_pointing_offset_input_widgets = [
    "spinbox_offset_xelev",
    "spinbox_offset_elev",
]
ambtemp_correction_input_widgets = [
    "spinbox_ambtempfiltdt",
    "spinbox_ambtempparam1",
    "spinbox_ambtempparam2",
    "spinbox_ambtempparam3",
    "spinbox_ambtempparam4",
    "spinbox_ambtempparam5",
    "spinbox_ambtempparam6",
]


# pylint: disable=too-many-arguments,too-many-branches
@pytest.mark.parametrize(
    (
        "slot_function",
        "slot_argument",
        "command",
        "input_values",
        "input_widgets",
        "expected_response",  # Only checked if fixture is connected to an OPC UA server
    ),
    [
        (
            "activate_button_clicked",
            "AzEl",
            "Management.Commands.Activate",
            None,
            None,
            ("CommandAborted", 2),
        ),
        (
            "deactivate_button_clicked",
            "AzEl",
            "Management.Commands.DeActivate",
            None,
            None,
            ("CommandDone", 10),
        ),
        (
            "unstow_button_clicked",
            None,
            "Management.Commands.Stow",
            (False,),
            None,
            ("CommandAborted", 2),
        ),
        # TODO: Weird behaviour with v3.1 CETC simulator
        # (
        #     "stow_button_clicked",
        #     None,
        #     "Management.Commands.Stow",
        #     (True,),
        #     None,
        #     ("CommandActivated", 9),
        # ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (10.0, 20.0, 0.5, 0.3),
            slew2abs_input_widgets,
            ("CommandActivated", 9),  # TODO: Weird behaviour with v3.1 CETC simulator
        ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (-10.0, 15.0, 0.5, 0.3),
            slew2abs_input_widgets,
            ("CommandActivated", 9),  # TODO: Weird behaviour with v3.1 CETC simulator
        ),
        (
            "slew_button_clicked",
            "Az",
            "Management.Commands.Slew2AbsSingleAx",
            (10.0, 1.0),
            slew_azimuth_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "slew_button_clicked",
            "El",
            "Management.Commands.Slew2AbsSingleAx",
            (20.0, 1.0),
            slew_elevation_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "stop_button_clicked",
            "AzEl",
            "Management.Commands.Stop",
            None,
            None,
            None,
        ),
        (
            "take_authority_button_clicked",
            None,
            "CommandArbiter.Commands.TakeAuth",
            ("LMC",),
            ["combobox_authority"],
            ("DiSQ already has command authority with user 3", -1),
        ),
        (
            "release_authority_button_clicked",
            None,
            "CommandArbiter.Commands.ReleaseAuth",
            None,
            None,
            ("CommandDone", 10),
        ),
        (
            "move2band_button_clicked",
            "Band_2",
            "Management.Commands.Move2Band",
            None,
            None,
            ("CommandActivated", 9),
        ),
        (
            "move2band_button_clicked",
            "Optical",
            "Management.Commands.Move2Band",
            None,
            None,
            ("CommandActivated", 9),
        ),
        # TODO: The interactions of this slot is complex, so cannot test 'ON' values
        # here in this test - a custom test is needed.
        (
            "pointing_model_button_clicked",
            None,
            "Pointing.Commands.PmCorrOnOff",
            (False, "Off", False, "Band_1"),
            pointing_model_setup_input_widgets,
            ("CommandDone", 10),  # TODO: Weird behaviour with v3.1 CETC simulator
        ),
        (
            "static_pointing_parameter_changed",
            None,
            "Pointing.Commands.StaticPmSetup",
            ("Band_1",) + (0.0,) * 18,
            static_pointing_params_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "static_pointing_offset_changed",
            None,
            "Tracking.Commands.TrackLoadStaticOff",
            (10.0, -10.0),
            static_pointing_offset_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "ambtemp_correction_parameter_changed",
            None,
            "Pointing.Commands.AmbTempCorrSetup",
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
            ambtemp_correction_input_widgets,
            ("CommandActivated", 9),
        ),
    ],
)
def test_opcua_command_slot_function(
    disq_app: MainView,
    slot_function: str,
    slot_argument: str | bool | None,
    command: str,
    input_values: tuple | None,
    input_widgets: list[str] | None,
    expected_response: tuple[str, int] | None,
):
    """Test the successful sending and response of OPC UA commands."""
    # Check whether test fixture is connected to an OPC UA server
    opcua_server: bool = disq_app.controller.is_server_connected()

    if input_values is not None:
        # Setup the input widgets with valid values
        if input_widgets is not None:
            for widget_name, value in zip(input_widgets, input_values):
                widget = getattr(disq_app, widget_name)
                if isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QtWidgets.QComboBox):
                    if not opcua_server:
                        widget.addItem(value)
                    assert set_combobox_to_string(widget, value)
                elif isinstance(widget, QtWidgets.QButtonGroup) and isinstance(
                    value, bool
                ):
                    widget.button(int(value)).setChecked(True)
        # Create a list of the command arguments
        cmd_args = [*input_values]
    else:
        cmd_args = []

    # Simulate the slot function signal
    if slot_argument is None:
        getattr(disq_app, slot_function)()
    else:
        getattr(disq_app, slot_function)(slot_argument)
        cmd_args.insert(0, slot_argument)

    # Verify the command status bar was updated
    assert f"Command: {command}{tuple(cmd_args)}" in disq_app.cmd_status_label.text()

    if opcua_server:
        # Check for expected response from the OPC UA server
        if expected_response is not None:
            assert (
                f"Response: {expected_response[0]} [{expected_response[1]}]"
                in disq_app.cmd_status_label.text()
            )
    else:
        # Verify the mock command method was called with the correct arguments
        disq_app.model.run_opcua_command.assert_called_once_with(command, *cmd_args)
