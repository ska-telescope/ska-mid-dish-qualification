"""Tests of the GUI."""

from time import sleep

import pytest
from PyQt6 import QtWidgets

from ska_mid_disq import Command
from ska_mid_disq.view import MainView


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
        # ALWAYS NEEDED:
        disq_fixture.controller.command_take_authority("LMC")
        # The following setup is only needed if running tests individually for debugging
        # disq_fixture.controller.command_stow(False)
        # disq_fixture.controller.command_activate("AzEl")
        # disq_fixture.controller.command_activate("Fi")
    yield disq_fixture
    # Stop any running slews and release authority after test (also done if test failed)
    if with_cetc_simulator or with_plc:
        # The following setup is only needed if running tests individually for debugging
        # disq_fixture.controller.command_stop("AzEl")
        # disq_fixture.controller.command_stop("Fi")
        sleep(0.5)


def set_combobox_to_string(combo_box: QtWidgets.QComboBox, string: str) -> bool:
    """Set QComboBox to string if the option exists."""
    for index in range(combo_box.count()):
        item_text = combo_box.itemText(index)
        if item_text == string:
            combo_box.setCurrentIndex(index)
            return True  # String found and set successfully
    return False  # String not found in combobox options


slew2abs_input_widgets = [
    "spinbox_slew_simul_azim_position",
    "spinbox_slew_simul_elev_position",
    "spinbox_slew_simul_azim_velocity",
    "spinbox_slew_simul_elev_velocity",
]
slew_azimuth_input_widgets = [
    "spinbox_slew_only_azimuth_position",
    "spinbox_slew_only_azimuth_velocity",
]
slew_elevation_input_widgets = [
    "spinbox_slew_only_elevation_position",
    "spinbox_slew_only_elevation_velocity",
]
slew_indexer_input_widgets = [
    "spinbox_slew_only_indexer_position",
    "spinbox_slew_only_indexer_velocity",
]

pointing_model_setup_input_widgets = [
    "button_static_point_model_toggle",
    "button_tilt_correction_toggle",
    "button_temp_correction_toggle",
    "combo_static_point_model_band_input",
]
static_pointing_params_input_widgets = [
    "combo_static_point_model_band_input",
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
set_time_source_input_widgets = [
    "combobox_time_source",
    "line_edit_ntp_source_addr",
]
set_power_mode_input_widgets = [
    "button_power_mode_low",
    "spinbox_power_lim_kw",
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
            "set_time_source_clicked",
            None,
            "Time_cds.Commands.SetTimeSource",
            ("NTP", "196.10.54.57"),
            set_time_source_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "set_power_mode_clicked",
            None,
            "Management.Commands.SetPowerMode",
            (False, 20.0),
            set_power_mode_input_widgets,
            ("CommandActivated", 9),
            # ("CommandRejected", 2),  # CETC simulator v4.3
        ),
        (
            "unstow_button_clicked",
            None,
            "Management.Commands.Stow",
            (False,),
            None,
            ("CommandActivated", 9),
        ),
        (
            "activate_button_clicked",
            "Az",
            "Management.Commands.Activate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "activate_button_clicked",
            "El",
            "Management.Commands.Activate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "activate_button_clicked",
            "Fi",
            "Management.Commands.Activate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "activate_button_clicked",
            "AzEl",
            "Management.Commands.Activate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandRejected", 2),  # CETC simulator v4.1
        ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (10.0, 20.0, 0.5, 0.3),
            slew2abs_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "stop_button_clicked",
            "AzEl",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (-10.0, 15.0, 0.5, 0.3),
            slew2abs_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "stop_button_clicked",
            "AzEl",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
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
            "stop_button_clicked",
            "Az",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
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
            "El",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "slew_button_clicked",
            "Fi",
            "Management.Commands.Slew2AbsSingleAx",
            (10.0, 1.0),
            slew_indexer_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "stop_button_clicked",
            "Fi",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "take_authority_button_clicked",
            None,
            "CommandArbiter.Commands.TakeAuth",
            ("EGUI",),
            ["combobox_authority"],
            ("SCU already has command authority with user EGUI", -1),
        ),
        # TODO: The interactions of this slot is complex, so cannot test 'ON' values
        # here in this test - a custom test is needed.
        # (
        #     "pointing_correction_setup_button_clicked",
        #     None,
        #     "Pointing.Commands.PmCorrOnOff",
        #     (False, "Off", False, "Band_1"),
        #     pointing_model_setup_input_widgets,
        #     ("CommandDone", 10),  # TODO: Weird behaviour with CETC simulator
        # ),
        (
            "apply_static_pointing_parameters",
            None,
            "Pointing.Commands.StaticPmSetup",
            ("Optical",) + (0.0,) * 18,
            static_pointing_params_input_widgets,
            ("CommandDone", 10),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandActivated", 9),  # CETC simulator v4.1
        ),
        (
            "apply_static_pointing_offsets",
            None,
            "Tracking.Commands.TrackLoadStaticOff",
            (10.0, -10.0),
            static_pointing_offset_input_widgets,
            ("CommandActivated", 9),
        ),
        (
            "apply_ambtemp_correction_parameters",
            None,
            "Pointing.Commands.AmbTempCorrSetup",
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
            ambtemp_correction_input_widgets,
            ("CommandDone", 10),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandActivated", 9),  # CETC simulator v4.1
        ),
        (
            "deactivate_button_clicked",
            "Az",
            "Management.Commands.DeActivate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "deactivate_button_clicked",
            "El",
            "Management.Commands.DeActivate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "deactivate_button_clicked",
            "Fi",
            "Management.Commands.DeActivate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "deactivate_button_clicked",
            "AzEl",
            "Management.Commands.DeActivate",
            None,
            None,
            ("CommandActivated", 9),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandRejected", 2),  # CETC simulator v4.1 - already deactivated
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
        (
            "stop_button_clicked",
            "Fi",
            "Management.Commands.Stop",
            None,
            None,
            ("CommandRejected", 2),  # PLC at MID-ITF response as of 9 Oct 2024
            # ("CommandDone", 10),  # CETC simulator v4.1
        ),
        (
            "stow_button_clicked",
            None,
            "Management.Commands.Stow",
            (True,),
            None,
            ("CommandActivated", 9),
        ),
        (
            "release_authority_button_clicked",
            None,
            "CommandArbiter.Commands.ReleaseAuth",
            None,
            None,
            ("CommandDone", 10),
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
) -> None:
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
        if command == "Management.Commands.Stow":
            attr_name = "Safety.Status.StowPinStatus"
            # For Unstow, wait for Retracted(1); for Stow, wait for Deployed(3)
            expected = 1 if input_values == (False,) else 3
            count = 0
            # pylint: disable=protected-access
            while disq_app.model._scu.attributes[attr_name].value != (  # type: ignore
                expected
            ):
                assert count != 90, (
                    "Stow/Unstow timeout - command potentially failed? StowPinStatus = "
                    f"{disq_app.model._scu.attributes[attr_name].value}"  # type: ignore
                )
                count += 1
                sleep(1)
    else:
        # Verify the mock command method was called with the correct arguments
        disq_app.model.run_opcua_command.assert_called_with(  # type: ignore
            Command(command), *cmd_args
        )
