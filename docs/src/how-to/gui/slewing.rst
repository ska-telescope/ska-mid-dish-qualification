=======
Slewing
=======

To perform a slew to an absolute position, first connect and take authority (see above). Then, if the PLC is showing that the stow pin is deployed (top right corner), click the :code:`Un-Stow` button in the :code:`Commands` section. It may also be necessary to first activate the axis (using the :code:`Activate` buttons in the :code:`Commands` section or :code:`Axis` tab.

.. image:: /img/Screenshot-slew_az_el.png
.. image:: /img/Screenshot-axis_tab.png

Once the axis are ready, a joint azimuth and elevation slew can be commanded via the :code:`Slew` section or each single axis can be commanded in the :code:`Axis` tab. Enter the desired position and slew velocity in the respective boxes, and click one of the :code:`Slew2Abs` buttons.