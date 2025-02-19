=======
Slewing
=======

To perform a slew to an absolute position, first connect and take authority. Then, if the PLC is showing that the stow pin is deployed (top right corner), click the ``Un-Stow`` button in the `Dish Control` box. It may also be necessary to first activate the axis using the ``Activate`` buttons in the `Dish Control` box or `Axis` tab.

.. image:: /img/Screenshot-slew_az_el.png

Once the axes are activated (`Standstill` state), a joint azimuth and elevation slew can be commanded in the `Slew to Absolute Position` box, or each single axis can be commanded in the `Axis` tab. Enter the desired position and slew velocity in the respective boxes, and click one of the ``Slew2Abs`` buttons.

.. image:: /img/Screenshot-axis_tab.png