=========
Authority
=========

Once connected, the dish stucture controller PLCs will allow nodes to be subscribed to, so functionality such as the displayed values and using the :code:`Recording` section can be used immediately. However, most buttons on the GUI are linked to OPCUA commands, which require the session to have "authority".

.. warning::
    Only one connection can have authority at a time. Taking authority with an equal to or greater priority than an existing session will supersede the existing connection. The GUI will display the current authority if any, but when there are multiple connections of the same priority level it is not possible to know which connection has authority without sending a command (although it will be the most recent client to take authority).

To take authority as the engineering GUI, select the :code:`EGUI` option from the drop-down in the :code:`Authority Status` section and click the :code:`Take Authority` button.

.. image:: /img/Screenshot-take_authority.png
   
The status bar at the bottom of the window will show the command and its response (the history of commands can be seen in the :code:`Logs` tab). If the command was successful (e.g. CommandDone, CommandActivated), the :code:`Current Auth` box will update to show the current authority is the EGUI.
   
To change authority, first release any held authority with the :code:`Release Authority` button. The GUI will automatically release authority when closed.