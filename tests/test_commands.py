"""Tests of the GUI."""

import os
from time import sleep

import pytest
from PySide6 import QtWidgets

from ska_mid_disq.view import MainView


# pylint: disable=unused-argument
@pytest.fixture(name="disq_app", scope="module")
def disq_app_fixture(qapp, request: pytest.FixtureRequest) -> MainView:  # type: ignore
    """Fixture to setup the qtbot with the DiSQ application."""
    # Switch the MainView between two fixtures defined in conftest.py
    with_plc = request.config.getoption("--with-plc")
    if with_plc:
        disq_fixture: MainView = request.getfixturevalue("disq_mid_itf_plc")
    else:
        disq_fixture = request.getfixturevalue("disq_cetc_simulator")
    if os.getenv("CI_JOB_ID") is None:
        disq_fixture.win.show()
    return disq_fixture


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
    "button_power_mode_group",
    "spinbox_power_lim_kw",
]
start_tracking_input_widgets = [
    "combobox_track_start_interpol_type",
    "button_start_track_group",
    "line_edit_start_track_at",
]
set_on_source_threshold_input_widgets = [
    "spinbox_source_threshold_radius",
    "spinbox_source_threshold_period",
]


# pylint: disable=too-many-arguments,too-many-branches,too-many-locals
@pytest.mark.parametrize(
    (
        "slot_function",
        "slot_argument",
        "command",
        "input_values",
        "input_widgets",
        "expected_response",  # Only checked if fixture is connected to an OPC UA server
        # 1st tuple is expected response for CETC sim ^4.4 and 2nd tuple is for PLC
    ),
    [
        (
            "set_time_source_clicked",
            None,
            "Time_cds.Commands.SetTimeSource",
            ("NTP", "196.10.54.57"),
            set_time_source_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "set_power_mode_clicked",
            None,
            "Management.Commands.SetPowerMode",
            (True, 10.0),
            set_power_mode_input_widgets,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "set_power_mode_clicked",
            None,
            "Management.Commands.SetPowerMode",
            (False, 20.0),
            set_power_mode_input_widgets,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "set_on_source_threshold_clicked",
            None,
            "Management.Commands.SetOnSourceThreshold",
            (20.0, 10.0),
            set_on_source_threshold_input_widgets,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "activate_button_clicked",
            "Az",
            "Management.Commands.Activate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "activate_button_clicked",
            "El",
            "Management.Commands.Activate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "activate_button_clicked",
            "Fi",
            "Management.Commands.Activate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "deactivate_button_clicked",
            "AzEl",
            "Management.Commands.DeActivate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "activate_button_clicked",
            "AzEl",
            "Management.Commands.Activate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "start_tracking_clicked",
            None,
            "Tracking.Commands.TrackStart",
            ("Spline", True),
            start_tracking_input_widgets,
            (("CommandRejected", 2), ("CommandActivated", 9)),  # TODO: CETC sim?
        ),
        (
            "start_tracking_clicked",
            None,
            "Tracking.Commands.TrackStart",
            ("Newton", False, "5.0"),
            start_tracking_input_widgets,
            (("CommandRejected", 2), ("CommandActivated", 9)),  # TODO: CETC sim?
        ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (10.0, 20.0, 0.5, 0.3),
            slew2abs_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "AzEl",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "slew2abs_button_clicked",
            None,
            "Management.Commands.Slew2AbsAzEl",
            (-10.0, 15.0, 0.5, 0.3),
            slew2abs_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "AzEl",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "slew_button_clicked",
            "Az",
            "Management.Commands.Slew2AbsSingleAx",
            (10.0, 1.0),
            slew_azimuth_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "Az",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "slew_button_clicked",
            "El",
            "Management.Commands.Slew2AbsSingleAx",
            (20.0, 1.0),
            slew_elevation_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "El",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "slew_button_clicked",
            "Fi",
            "Management.Commands.Slew2AbsSingleAx",
            (10.0, 1.0),
            slew_indexer_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "Fi",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "take_authority_button_clicked",
            None,
            "CommandArbiter.Commands.TakeAuth",
            ("EGUI",),
            ["combobox_authority"],
            (("CommandDone", 10), ("CommandDone", 10)),
        ),
        # TODO: The interactions of this slot is complex, so cannot test 'ON' values
        # here in this test - a custom test is needed.
        (
            "pointing_correction_setup_button_clicked",
            None,
            "Pointing.Commands.PmCorrOnOff",
            (False, "Off", False, "Band_1"),
            pointing_model_setup_input_widgets,
            (("CommandRejected", 2), ("CommandDone", 10)),  # TODO: CETC sim?
        ),
        (
            "apply_static_pointing_parameters",
            None,
            "Pointing.Commands.StaticPmSetup",
            ("Optical",) + (0.0,) * 18,
            static_pointing_params_input_widgets,
            (("CommandDone", 10), ("CommandDone", 10)),
        ),
        (
            "apply_static_pointing_offsets",
            None,
            "Tracking.Commands.TrackLoadStaticOff",
            (10.0, -10.0),
            static_pointing_offset_input_widgets,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "apply_ambtemp_correction_parameters",
            None,
            "Pointing.Commands.AmbTempCorrSetup",
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
            ambtemp_correction_input_widgets,
            (("CommandActivated", 9), ("CommandDone", 10)),
        ),
        # (
        #     "deactivate_button_clicked",
        #     "Az",
        #     "Management.Commands.DeActivate",
        #     None,
        #     None,
        #     (("CommandDone", 10), ("CommandActivated", 9)),
        # ),
        (
            "deactivate_button_clicked",
            "El",
            "Management.Commands.DeActivate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "deactivate_button_clicked",
            "Fi",
            "Management.Commands.DeActivate",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "move2band_button_clicked",
            "Optical",
            "Management.Commands.Move2Band",
            None,
            None,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "move2band_button_clicked",
            "Band_1",
            "Management.Commands.Move2Band",
            None,
            None,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "stop_button_clicked",
            "Fi",
            "Management.Commands.Stop",
            None,
            None,
            (("CommandDone", 10), ("CommandActivated", 9)),
        ),
        (
            "stow_button_clicked",
            None,
            "Management.Commands.Stow",
            (True,),
            None,
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "unstow_button_clicked",
            None,
            "Management.Commands.Stow",
            (False,),
            None,
            # CETC sim does not startup stowed, so unstow is rejected.
            (("CommandActivated", 9), ("CommandActivated", 9)),
        ),
        (
            "release_authority_button_clicked",
            None,
            "CommandArbiter.Commands.ReleaseAuth",
            None,
            None,
            (("CommandDone", 10), ("CommandDone", 10)),
        ),
    ],
)
# pylint: disable=too-many-positional-arguments
def test_opcua_command_slot_function(
    disq_app: MainView,
    slot_function: str,
    slot_argument: str | bool | None,
    command: str,
    input_values: tuple | None,
    input_widgets: list[str] | None,
    expected_response: tuple[tuple[str, int], tuple[str, int]],
    request: pytest.FixtureRequest,
) -> None:
    """Test the successful sending and response of OPC UA commands."""
    sleep(1)
    if input_values is not None:
        # Setup the input widgets with valid values
        if input_widgets is not None:
            for widget_name, value in zip(input_widgets, input_values):
                try:
                    widget = getattr(disq_app, widget_name)
                except AttributeError:
                    widget = getattr(disq_app.win, widget_name)
                if isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QtWidgets.QComboBox):
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

    # Verify the command status bar was updated (ignoring single quote characters)
    assert f"Command: {command}{tuple(cmd_args)}".replace(
        "'", ""
    ) in disq_app.cmd_status_label.text().replace("'", "")

    # Check for expected response from the OPC UA server
    with_plc = request.config.getoption("--with-plc")
    response = expected_response[1] if with_plc else expected_response[0]
    assert (
        f"Response: {response[0]} [{response[1]}]" in disq_app.cmd_status_label.text()
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
            assert count != 60, (
                "Stow/Unstow timeout - command potentially failed? StowPinStatus = "
                f"{disq_app.model._scu.attributes[attr_name].value}"  # type: ignore
            )
            count += 1
            sleep(1)
