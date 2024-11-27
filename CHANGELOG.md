# Changelog

## Unreleased

- Bug fixes:
    - WOM-518: Rectify static tracking offsets input range limits.
    - WOM-424: Simplified main dependencies and limited Python version to 3.10 and 3.11.

## 0.5.1

WOM-510: 
- Fixed crash when clicking 'Start' recording before configurating `DataLogger`.
- Fixed 'InterlockClearable' LED indicator in 'Commands' group.
- Correctly renamed azimuth 'CCS2' LED to 'CCW2'.
- Changed 'Slew2Abs' inputs to spin boxes as used in 'Axis' tab.
- Various minor UI tweaks for consistency.

## 0.5.0

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

## 0.4.0

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

## 0.3.0

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

## 0.2.1

- WOM-237: gui-load-track-table
- WOM-247: improve-enum-logging
- WOM-193: change-multiprocessing-to-threading
- WOM-241: easy-powershell-logging
- WOM-239: short-diff-ini-readme

## 0.2.0

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

## 0.1.1

- WOM-170: fix-mvp-release-issues

## 0.1.0

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
