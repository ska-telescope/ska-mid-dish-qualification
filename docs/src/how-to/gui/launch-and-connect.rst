.. role:: ps1(code)
    :language: powershell

==================
Launch and connect
==================

For most users, the recommened way to install the DiSQ GUI is with the standalone Windows installer. Launching the GUI is as simple as double-clicking the shortcut on the desktop or in the start menu.

If the `ska-mid-disq` python package is installed in a Python virtual environment, running the ``disq-gui`` command will launch the GUI included in the package:

:ps1:`(.venv) PS C:\\Users\\<user>\\Documents\\SKAO\\ska_mid_disq> disq-gui`

.. warning::
    The DiSQ GUI is an expert engineering interface. The user is expected to understand the consequences of actions performed via the GUI.

.. image:: /img/Screenshot-gui_main_view.png

Selecting the ``Connection`` menu in the top left corner will show a drop-down menu. Then clicking ``Connect to DSC...`` will bring up a dialog box for an OPC-UA server connection.

.. image:: /img/Screenshot-control_dropdown.png
.. image:: /img/Screenshot-OPCUA_server_connection_dialog.png
   
The server connection dialog window has several inputs:

1. Configuration drop-down: This menu is populated with configurations found via the :meth:`~ska_mid_disq.utils.configuration.find_config_file` method (see :doc:`DiSQ Configuration</api/configuration>`). Selecting a configuration from the available options will populate the remaining input boxes with the stored configuration and prevent further user input. To re-enable these input boxes, select the empty option on the drop-down menu.

.. image:: /img/Screenshot-OPCUA_server_connection_dialog_cetc_sim.png

2. Server Address input box: The IP address of the server to connect to.
3. Server Port input box: The port to connect to on the server. 4840 is the default port for OPC-UA TCP.
4. Server Endpoint input box: The endpoint is the address to access within the OPC-UA server.
5. Server Namespace input box: The namespace (node container) to access on the server.
6. Nodes Cache checkbox: When first connecting to a new OPC-UA server (e.g. one at a different address), DiSQ generates a cache of the nodes available. On subsequent connections, checking the box can improve the speed at which DiSQ creates the connection. To re-scan the server if any changes were made to the OPC-UA server, simply leave the `Use nodes cache` box unchecked. This feature is only recommened for users who have a considerable network latency to the server they are regularly connecting to.
   
Clicking ``OK`` will submit the details in the dialog box and the GUI will attempt to connect to the server. While connecting, the OPC-UA server banner at the top of the window will display `"Connecting... please wait"` and the status bar at the bottom will read `"Connecting to server..."`. If the connection is successful, both will state that the GUI is connected, and display some details about the connection. If the connection fails, the server banner will show `"Disconnected"` and the GUI will attempt to report the error on the status bar.

Upon successful connection, the GUI will automatically subscribe to the displayed nodes and the relevant widgets will fill with values.

.. image:: /img/Screenshot-connected_cetc.png