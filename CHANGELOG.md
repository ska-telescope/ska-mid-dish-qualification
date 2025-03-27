# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added 
- WOM-561: Added `SCUWeatherStation_from_config()` object generator method to API, to allow monitoring of a weather station while interfacing with a dish using scripts.

### Changed
- WOM-634: The DiSQ Sphinx docs is bundled with the Windows installer for offline viewing, and is opened in the `Help` menu of the GUI. The application logs directory can also be opened from the `Help` menu for easy access when needed for debugging.
- WOM-694: Update for changes to ``SCU.subscribe()`` method in ska-mid-dish-steering-control 0.6.0:

  - The ``period`` argument has been renamed to ``publishing_interval`` to match OPC-UA nomenclature, and no longer has a default value.
  - The client now requests that samples are buffered on the server (at its default rate). All samples are then received concurrently at the set publishing interval. 
  - The 'MinSupportedSampleRate' value of the server is read to set an appropriate queue size for sample buffering. 
  - The new optional ``buffer_samples`` argument can be explicitly set to ``False`` to revert to the original behaviour of only receiving the latest sample at the publishing interval. 
  - If the new optional argument ``trigger_on_change`` is set to ``False``, the subscription will trigger on timestamps - i.e. notifications will always be received at the ``publishing_interval``. This is useful for attributes that are not expected to change frequently, but need to be read at a high rate.

### Fixed
- WOM-695: Update exception handling of ``Model.connect_server()`` method, and log message of unhandled exceptions hook with type and traceback.

### Documentation
- WOM-560, WOM-561: Reorganised the DiSQ GUI user guide, updated existing pages with screenshots of v1.0.0 in Windows 11, and added the `Pointing correction` and `Weather station` pages. 

## 1.0.0 - 2025-02-17

### Added
- WOM-593, WOM-625: Can open a generic window for any available command on the PLC to enter inputs and execute it. Available under the 'Expert options' menu and intended as a debugging tool.
- WOM-619: Axes' position input spin boxes are updated with the actual value after connecting to a server and after an axis movement has stopped, but not during movement.
- WOM-626: Show PLC's 'System.DisplayedDiagnosis' variable on the main window.

### Changed
- WOM-556, WOM-557: Refactored GUI to use PySide6 instead of PyQt6, as PySide6 is the official Python bindings maintained by the Qt project. Using the latest PySide 6.8 now also allows installing the package with Python 3.12.
- WOM-621: Reorganised package source and unexposed `configuration` module.

### Fixed
- WOM-623: Weather station widgets and disconnect menu action are disabled after disconnecting from DSC.

## 0.6.0 - 2025-01-23

### Added
- WOM-454, WOM-578, WOM-579, WOM-580, WOM-609: Integrated the Weather Monitoring System into DiSQ on the 'Weather' tab.
- WOM-543: Added a global option to enable or disable min/max limits on all inputs.
- WOM-576: Add an 'Attribute' menu to display all attributes as graphs or logs in their own window.
- WOM-591: Display the current and end index of the loaded track table in the 'Track' tab.
- WOM-607: Add 'Set On Source Threshold' command to 'Track' tab.

### Changed
- WOM-577: Move `DataLogger` output file structure creation to thread.

### Fixed
- WOM-597: Check that the path in the track table file input field is a real file and not a directory to prevent an error message when pressing 'Load Track Table File'.
- WOM-611: Axes' position input spin boxes are not constantly updated to the actual or set value anymore. 

## 0.5.2 - 2024-12-17

### Added
- WOM-542: Added buttons to server connection dialog window to save/delete configs.

### Fixed
- WOM-518: Rectify static tracking offsets input range limits.
- WOM-424: Simplified main dependencies and limited Python version to 3.10 and 3.11.

## 0.5.1 - 2024-11-11

### Fixed
WOM-510: 
- Fixed crash when clicking 'Start' recording before configurating `DataLogger`.
- Fixed 'InterlockClearable' LED indicator in 'Commands' group.
- Correctly renamed azimuth 'CCS2' LED to 'CCW2'.
- Changed 'Slew2Abs' inputs to spin boxes as used in 'Axis' tab.
- Various minor UI tweaks for consistency.

## 0.5.0 - 2024-11-07

- API changes:
    - WOM-402: Removed `parameter_commands`, `server`, `server_nodes`, `server_attributes` and `server_commands` properties.
    - WOM-453: Made many class variables and methods of SCU private.
    - WOM-482: Renamed the python package to `ska-mid-disq` and the data logger class to `DataLogger` to differentiate it from python's built-in `Logger` class.
- Non-breaking changes:
    - WOM-332: Removed loading/use of environment variables from .env file.
    - WOM-308: Updated slew velocity input boxes with maximum allowed value on startup.
    - WOM-414: Try using `exception.add_note()` in SCU for python 3.11.
    - WOM-450: Moved `configure_logging()` to configuration module.
    - WOM-418: Updated mock test server to version 2 of ICD.
    - WOM-478: Display package version in GUI's main window title.
    - WOM-408: Added status indicators for aggregated warnings and errors in main window.
    - WOM-471: Swopped sculib with ska-mid-dish-steering-control package and updated dependencies (asyncua 1.1.5).
    - WOM-479: Update `DataLogger` to use newer SCU enum methods.
    - WOM-480: Added more allowed OPCUA types to data logger.
    - WOM-446: Added set power mode and power status attributes to the power tab.
    - WOM-447: Added 'Reset Axis Errors' buttons to the axis tab that clears latched errors of the servos.
    - WOM-401: Changed the individual axis position & velocity widgets to spinboxes with range limits that can be enabled/disabled with a button.
    - WOM-464: Added time info and 'Set Time Source' in track tab, and also indicator of time source and synced status in main window.
    - WOM-496: Update DataLogger subscription times to be from server time.
    - WOM-257: Update the GUI recording interface. Change the configure dialog to have a check box and a configurable period per node. Load/Save configurations. Other small changes.
    - WOM-445: Completely reworked and fixed the point tab's functionality.
    - WOM-474: Moved server connection into pop-up window. Added 'Control' and 'Help' menus with 'About' window, and various GUI display/layout improvements.
    - WOM-476: Add track status tr_TimeRemaining and OnSourceDev to track tab
- Bug fixes:
    - WOM-235: Fixed track table get details string list index out of range.
    - WOM-428: Various small bugs in GUI and other GUI improvements.
    - WOM-427: Prevent DiSQ crashing when resetting the PLC it's connected to.

## 0.4.0 - 2024-08-27

- Breaking changes for version 2 of ICD (WOM-334, WOM-335, WOM-392, WOM-399, WOM-235):
    - Updated commands to handle session ID.
    - Changed commands' arguments from enumerated types to integer types.
    - Updated Track Table loading to work as per ICD v2 (works with PLC as CETC sim Track Table does not work)
    - SCU disconnects from incompatible CETC simulator versions and informs user with log and GUI status message - only v3.2.3. and up is compatible.
- Non-breaking changes (WOM-352, WOM-383, WOM-371, WOM-390, WOM-392, WOM-396, WOM-397, WOM-405, WOM-406):
    - Data logger reads all Management.NamePlate children and adds the values as attributes to the root of the created HDF5 file.
    - SCU caches node IDs to JSON file after scanning server, which significantly speeds-up subsequent reconnects to the same server.
    - SCU automatically releases command authority when disconnecting from server.
    - GUI gracefully quits with unhandled exceptions or Unix signals.
    - Handle write-error exception in SCU lib.
    - Handle missing call_method exception in SCU lib.
    - Handle connection timeout exception in SCU lib.
    - Handle unexpected closed connection in SCU lib.
    - Replaced all command strings with Command Enum and result codes with ResultCode Enum classes.
    - Refactored and cleaned-up SCU functions.
    - Data logger's wait_for_completion() has been squashed into stop() and local datetime is converted to timezone aware timestamp before writing to file.

## 0.3.0 - 2024-05-29

- WOM-223: DiSQ: GUI Tooltips
- WOM-353: DiSQ GUI throws exception in logging message
- WOM-346: Add DS sim as fixture for Logger tests to run against
- WOM-341: Display selected FI band and set tab order of widgets
- WOM-339: Add pytest-qt GUI tests in CI job
- WOM-333: Fix server validator script crash
- WOM-256: DiSQ GUI layout improvements
- WOM-260: Add static pointing model tab in GUI
- WOM-337: Fix hdf5_to_csv offset naive datetime
- WOM-330: Sphinx docstrings and linting
- WOM-259: Add individual axes control to Axis tab in GUI
- WOM-323: Enable configuration of username and password
- WOM-236: Fix GUI crash on connection error
- WOM-275: Extend sculib
- WOM-237: Minor corrections to opc-ua parameter name on GUI
- WOM-281: Add make module, sphinx docs and update pipeline
- WOM-277: Server validator printt to file
- WOM-321: Change unsubscribe to delete
- WOM-306: Change CSV output to use commas
- WOM-269: Fix reconnect button
- WOM-267: Fix node name error
- WOM-262: Fix abs_azel typo

## 0.2.1 - 2024-02-05

- WOM-237: gui-load-track-table
- WOM-247: improve-enum-logging
- WOM-193: change-multiprocessing-to-threading
- WOM-241: easy-powershell-logging
- WOM-239: short-diff-ini-readme

## 0.2.0 - 2024-01-17

- WOM-189: hot-fix
- WOM-238: log-to-files
- WOM-232: gui-take-command-authority
- WOM-189: add-load-tracktable-file
- WOM-188: config-file
- WOM-194: display-data-in-graph
- WOM-193: dish-server-validation-script
- WOM-187: fix-ui-crash-bug
- WOM-231: fix-sculib-start-thread-racecondition
- WOM-190: add-ci-build-release
- WOM-171: fix-poetry-in-mvp

## 0.1.1 - 2023-11-29

- WOM-170: fix-mvp-release-issues

## 0.1.0 - 2023-11-29

- WOM-127: method-conversion
- WOM-130: gui-match-wireframe
- WOM-169: wheel
- WOM-152: use-types-in-datalog
- WOM-166: python-logger
- WOM-154: test-logger
- WOM-152: get-types-and-enumerations
- WOM-121: hdf5-to-csv-converter
- WOM-158: sculib-in-gui
- WOM-115: log-to-hdf5-file
- WOM-160: remove-qasync-workaround
- WOM-153: linting
- WOM-117: add-pyqt-gui-prototype-code
- WOM-116: disq-component-interfaces
- WOM-117: python-package-structure
- WOM-98: change-scu-access-mechanics-to-opc-us
- WOM-95: Add existing SKAMPI quali scripts
