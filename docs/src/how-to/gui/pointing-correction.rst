===================
Pointing correction
===================

The static pointing model (SPM) for each band, static tracking offset, tilt correction and temperature correction can be set in the pointing tab shown below. 

.. image:: /img/Screenshot-point_tab.png

The SPM and corrections can each be toggled on and off independently by clicking on the respective toggle buttons, but the buttons themselves also indicate the current configured state on the DSC. In other words, if it cannot be enabled for some reason, the button's state will not change.

Static pointing model
---------------------

The SPM can only be active for one band at a time. The desired band must be selected from the drop-down list under the `Input` column before turning it on with the toggle button. When a band is selected, the input fields for the coefficients are always updated with the current values on the DSC.

The SPM coefficients can be entered manually in the `Input` column or imported from a JSON file. Once entered or imported, the coefficients are only set after clicking on the ``Apply`` button at the bottom of the `Input` column. To switch the SPM to another band when it is already turned on, first select the desired band, enter new coefficients if required, and click on the ``Apply`` button.

The `Display` column is used to see the current coefficients on the DSC of a band selected in the drop-down list. The current values for the band can then be saved to a JSON file by clicking on the ``Export...`` button. A dialog will open with a suggested filename which includes the selected band.

.. image:: /img/Screenshot-point_export.png

A previously saved JSON file can then be loaded again with the ``Import...`` button. A JSON file is validated when imported and an error message will be displayed if it does not match the schema. 

Abbreviated example of an exported JSON configuration file for a band's SPM:
    
.. code-block:: json

    {
        "interface": "https://schema.skao.int/ska-mid-dish-gpm/1.2",
        "antenna": "SKA063",
        "coefficients": {
            "IA": {
            "value": 1.0
            },
            "CA": {
            "value": 2.0
            },
            "NPAE": {
            "value": 3.0
            },
            //...
        }
    }

Static tracking offset and corrections
--------------------------------------

The static tracking offset, tilt correction and ambient temperature correction parameters can only be entered manually in their respective inputs fields, and are also set by clicking on the ``Apply`` button in each group's box. The input fields are updated with the current values on the DSC whenever they change.

There are two independent tilt meters that can be used for tilt correction by clicking on the toggle button right of the ``OFF``\/``ON`` button. The tilt meter toggle button will display either ``TM1`` or ``TM2`` to indicate which one is currently selected. 