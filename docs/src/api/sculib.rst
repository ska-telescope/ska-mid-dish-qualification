============================================
SKA-Mid Dish Structure Steering Control Unit
============================================

Steering Control Unit (SCU) for a SKA-Mid Dish Structure Controller OPC UA server.

This module contains an OPC UA client class that simplifies connecting to a server and
calling methods on it, reading or writing attributes.

How to use SCU
--------------

The simplest way to initialise a :class:`~ska_mid_disq.SteeringControlUnit`, is to use the :meth:`~ska_mid_disq.SCU`
object generator method. It creates an instance, connects to the server, and can also
take command authority immediately. Provided here are some of the defaults which can be
overwritten by specifying the named parameter:

.. code-block:: python

    from ska_mid_disq import SCU
    scu = SCU(
        host="localhost",
        port=4840,
        endpoint="",
        namespace="",
        timeout=10.0,
        authority_name="LMC", # Default is None - then take_authority() must be used.
    )
    # Do things with the scu instance..
    scu.disconnect_and_cleanup()

Altenatively the :class:`~ska_mid_disq.SteeringControlUnit` class can be used directly as a context
manager without calling the teardown method explicitly:

.. code-block:: python

    from ska_mid_disq import SteeringControlUnit
    with SteeringControlUnit(host="localhost") as scu:
        scu.take_authority("LMC")

Finally, the third and most complete option to initialise and connect a
:class:`~ska_mid_disq.SteeringControlUnit`, is to use the :meth:`~ska_mid_disq.SCU_from_config` object 
generator method, which will:

- Read the server address/port/namespace from the configuration file.
- Configure logging.
- Create (and return) the :class:`~ska_mid_disq.SteeringControlUnit` object.
- Connect to the server.
- Take authority if requested.

.. code-block:: python

    from ska_mid_disq import SCU_from_config
    scu = SCU_from_config("CETC54 simulator", authority_name="LMC")
    # Do things with the scu instance..
    scu.disconnect_and_cleanup()

All nodes under the *Server* tree, including the *PLC_PRG* tree, are stored in the :attr:`~ska_mid_disq.SteeringControlUnit.nodes` dictionary. 
The keys are the full node names, the values are the Node objects. The full names of all nodes can be retrieved with:

.. code-block:: python

    scu.get_node_list()

Every value in :attr:`~ska_mid_disq.SteeringControlUnit.nodes` exposes the full OPC UA functionality for a node.
Note: When accessing nodes directly, it is mandatory to await any calls:

.. code-block:: python

    node = scu.nodes["PLC_PRG"]
    node_name = (await node.read_display_name()).Text

The command methods that are below the *Server* node's hierarchy can be accessed through
the :attr:`~ska_mid_disq.SteeringControlUnit.commands` dictionary:

.. code-block:: python

    scu.get_command_list()

When you want to call a command, please check the ICD for the parameters that the
commands expects. Checking for the correctness of the parameters is not done here
in the SCU class, but in the PLC's OPC UA server. Once the parameters are in order,
calling a command is really simple:

.. code-block:: python

    result = scu.commands["COMMAND_NAME"](YOUR_PARAMETERS)

You can also use the :class:`~ska_mid_disq.Command` enum, as well as the helper method for 
converting types from the OPC UA server to the correct base integer type:

.. code-block:: python

    from ska_mid_disq import Command
    axis = scu.convert_enum_to_int("AxisSelectType", "Az")
    result = scu.commands[Command.ACTIVATE.value](axis)

For instance, command the PLC to slew to a new position:

.. code-block:: python

    az = 182.0; el = 21.8; az_v = 1.2; el_v = 2.1
    code, msg, _ = scu.commands[Command.SLEW2ABS_AZ_EL.value](az, el, az_v, el_v)

The OPC UA server also provides read-writeable and read-only :attr:`~ska_mid_disq.SteeringControlUnit.attributes`. 
An attribute's value can easily be read:

.. code-block:: python

    scu.attributes["Azimuth.p_Set"].value

If an attribute is writable, then a simple assignment does the trick:


.. code-block:: python

    scu.attributes["Azimuth.p_Set"].value = 1.2345

In case an attribute is not writeable, the OPC UA server will report an error:

`*** Exception caught: User does not have permission to perform the requested operation.
(BadUserAccessDenied)`

How to use SCU with a weather station
-------------------------------------

The :class:`~ska_mid_disq.SCUWeatherStation` class is a subclass of :class:`~ska_mid_disq.SteeringControlUnit` that provides additional functionality for reading weather station sensor data.

Simular to the :meth:`~ska_mid_disq.SCU_from_config` method, the :meth:`~ska_mid_disq.SCUWeatherStation_from_config` object generator method can be used to initialise and connect a :class:`~ska_mid_disq.SCUWeatherStation` object. However, connecting to a weather station must be done manually after the SCU object is initialised:

.. code-block:: python

    from ska_mid_disq import SCUWeatherStation_from_config
    scu = SCUWeatherStation_from_config("CETC54 simulator", authority_name="LMC")
    scu.connect_weather_station("/path/to/config/yaml", "localhost", 502)

Once successfully connected to a weather station, a list of its available sensors can be retrieved with :meth:`~ska_mid_disq.SCUWeatherStation.list_weather_station_sensors`, and their values read with the :attr:`~ska_mid_disq.SteeringControlUnit.attributes` dictionary: 

.. code-block:: python

    temperature = scu.attributes["weather.station.temperature"].value

.. Include the publicly exposed functions and classes as in src/ska_mid_disq/__init_.py

SteeringControlUnit classes
---------------------------

.. autoclass:: ska_mid_disq.SteeringControlUnit
   :members:

.. autoclass:: ska_mid_disq.SCUWeatherStation
   :members:

SCU generator methods
---------------------

.. autofunction:: ska_mid_disq.SCU

.. autofunction:: ska_mid_disq.SCU_from_config

.. autofunction:: ska_mid_disq.SCUWeatherStation_from_config

Enum classes
------------

.. autoclass:: ska_mid_disq.Command
   :members:
   :undoc-members:

.. autoclass:: ska_mid_disq.ResultCode
   :members:
   :undoc-members: