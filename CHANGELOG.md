# Changelog

## Unreleased

- Non-breaking changes:
    - WOM-308: Update slew velocity input boxes with maximum allowed value on startup.
    - WOM-332: Removed loading/use of environment variables from .env file.
    - WOM-414: Try using exception.add_note() in SCU for python 3.11.

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
