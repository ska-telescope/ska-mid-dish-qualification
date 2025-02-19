=================
Command authority
=================

Once connected, the dish stucture controller PLC will allow nodes to be subscribed to, so attribute values will be displayed and functionality such as the data recorder can be used immediately. However, most buttons on the GUI are linked to OPC-UA commands, which require the session to have "authority" with a given user.

.. warning::
    Only one connection can have authority at a time. Taking authority with an equal to or greater user level than an existing session will supersede the existing connection. The GUI will display the current user, if any, but when there are multiple connections of the same user, it is not possible to know which connection has authority without sending a command (although it will be the most recent client to take authority).

To take authority as the engineering GUI, select the `EGUI` option from the drop-down in the `Command Authority` box and click the ``Take Authority`` button.

.. image:: /img/Screenshot-take_authority.png
   
The status bar at the bottom of the window will show the command and its response (the history of commands can be seen in the `Logs` tab). If the command was successful (e.g. CommandDone, CommandActivated), the `Current user` display will update to show `EGUI`.
   
To change authority, first release any held authority with the ``Release Authority`` button. The GUI will automatically release authority when closed.