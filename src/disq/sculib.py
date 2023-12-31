#Feed Indexer tests [316-000000-043]

#Author: P.P.A. Kotze
#Date: 1/9/2020
#Version:
#0.1 Initial
#0.2 Update after feedback and correction from HN email dated 1/8/2020
#0.3 Rework scu_get and scu_put to simplify
#0.4 attempt more generic scu_put with either jason payload or simple params, remove payload from feedback function
#0.5 create scu_lib
#0.6 1/10/2020 added load track tables and start table tracking also as debug added 'field' command for old scu
#HN: 13/05/2021 Changed the way file name is defined by defining a start time
##: 07/10/2021 Added new "save_session14" where file time is no longer added to the file name in this library, but expected to be passed as part of "filename" string argument from calling script.
# 2023-08-31, Thomas Juerges Refactored the basic access mechanics for an OPC UA server.

import asyncio
import enum
import logging
import logging.config
import os
import queue
import sys
import threading
import time
from importlib import resources
from pathlib import Path
from typing import Any, Union

import asyncua
import cryptography
import yaml

logger = logging.getLogger('sculib')

def configure_logging(default_log_level: int = logging.INFO) -> None:
    if os.path.exists("disq_logging_config.yaml"):
        disq_log_config_file: resources.Traversable | str = "disq_logging_config.yaml"
    else:
        disq_log_config_file = resources.files(__package__) / "default_logging_config.yaml"
    config = None
    if os.path.exists(disq_log_config_file):
        with open(disq_log_config_file, "rt") as f:
            try:
                config = yaml.safe_load(f.read())
            except Exception as e:
                print(e)
                print(f"WARNING: Unable to read logging configuration file {disq_log_config_file}")
    else:
        print(f"WARNING: Logging configuration file {disq_log_config_file} not found")

    if config is None:
        print("Reverting to basic logging config at level:{default_log_level}")
        logging.basicConfig(level = default_log_level)
    else:
        logging.config.dictConfig(config)


#define some preselected sensors for recording into a logfile
hn_feed_indexer_sensors=[
'acu.time.act_time_source',
'acu.time.internal_time',
'acu.time.external_ptp',
'acu.general_management_and_controller.state',
'acu.general_management_and_controller.feed_indexer_pos',
'acu.azimuth.state',
'acu.azimuth.p_set',
'acu.azimuth.p_act',
'acu.azimuth.v_act',
'acu.elevation.state',
'acu.elevation.p_set',
'acu.elevation.p_act',
'acu.elevation.v_act',
'acu.feed_indexer.state',
'acu.feed_indexer.p_set',
'acu.feed_indexer.p_shape',
'acu.feed_indexer.p_act',
'acu.feed_indexer.v_shape',
'acu.feed_indexer.v_act',
'acu.feed_indexer.motor_1.actual_velocity',
'acu.feed_indexer.motor_2.actual_velocity',
'acu.feed_indexer.motor_1.actual_torque',
'acu.feed_indexer.motor_2.actual_torque',
'acu.general_management_and_controller.act_power_consum',
'acu.general_management_and_controller.power_factor',
'acu.general_management_and_controller.voltage_phase_1',
'acu.general_management_and_controller.voltage_phase_2',
'acu.general_management_and_controller.voltage_phase_3',
'acu.general_management_and_controller.current_phase_1',
'acu.general_management_and_controller.current_phase_2',
'acu.general_management_and_controller.current_phase_3'
]

# OPC UA equivalent for the above listed hh_feed_indexer_sensors
# NOTE: These attributes/sensros are currently missing:
# *** general_management_and_controller.state
# *** time.act_time_source
# *** time.internal_time
# *** time.external_ptp
# Helper code that I used:
# lower = {}
# for i in scu.attributes.keys():
#     lower = i.tolower()
#     lower[lower] = i
# s = "hn_opcua_feed_indexer_sensors = ["
# for i in sculib.feed_indexer_sensors:
#     name = i.replace('acu.', '')
#     name = name.replace('feed_indexer', 'feedindexer')
#     a = None
#     try:
#         u = lower[name]
#         s += f"\n'{u}',"
#     except KeyError as e:
#         print(f'*** {name}')
# s += f"\n]"
# print(f'{s}')
# s = "hn_opcua_tilt_sensors = ["
# for i in sculib.hn_tilt_sensors:
#     name = i.replace('acu.', '')
#     name = name.replace('feed_indexer', 'feedindexer')
#     a = None
#     try:
#         u = lower[name]
#         s += f"\n'{u}',"
#     except KeyError as e:
#         print(f'*** {name}')
# s += f"\n]"
# print(f'{s}')
hn_opcua_feed_indexer_sensors = [
'Azimuth.AxisState',
'Azimuth.p_Set',
'Azimuth.p_Act',
'Azimuth.v_Act',
'Elevation.AxisState',
'Elevation.p_Set',
'Elevation.p_Act',
'Elevation.v_Act',
'FeedIndexer.AxisState',
'FeedIndexer.MotorOne.mActTorq',
'FeedIndexer.MotorOne.mActVelocity',
'FeedIndexer.MotorTwo.mActTorq',
'FeedIndexer.MotorTwo.mActVelocity',
'FeedIndexer.p_Set',
'FeedIndexer.p_Shape',
'FeedIndexer.p_Act',
'FeedIndexer.v_Shape',
'FeedIndexer.v_Act',
'Management.ManagementStatus.FiPos',
'Management.ManagementStatus.PowerStatus.ActPwrCnsm',
'Management.ManagementStatus.PowerStatus.CurrentPh1',
'Management.ManagementStatus.PowerStatus.CurrentPh2',
'Management.ManagementStatus.PowerStatus.CurrentPh3',
'Management.ManagementStatus.PowerStatus.PowerFactor',
'Management.ManagementStatus.PowerStatus.VoltagePh1',
'Management.ManagementStatus.PowerStatus.VoltagePh2',
'Management.ManagementStatus.PowerStatus.VoltagePh3',
'Time.DscTime'
]

#hn_tilt_sensors is equivalent to "Servo performance"
hn_tilt_sensors=[
'acu.time.act_time_source',
'acu.time.internal_time',
'acu.time.external_ptp',
'acu.general_management_and_controller.state',
'acu.general_management_and_controller.feed_indexer_pos',
'acu.azimuth.state',
'acu.azimuth.p_set',
'acu.azimuth.p_act',
'acu.azimuth.v_act',
'acu.elevation.state',
'acu.elevation.p_set',
'acu.elevation.p_act',
'acu.elevation.v_act',
'acu.general_management_and_controller.act_power_consum',
'acu.general_management_and_controller.power_factor',
'acu.general_management_and_controller.voltage_phase_1',
'acu.general_management_and_controller.voltage_phase_2',
'acu.general_management_and_controller.voltage_phase_3',
'acu.general_management_and_controller.current_phase_1',
'acu.general_management_and_controller.current_phase_2',
'acu.general_management_and_controller.current_phase_3',
'acu.pointing.act_amb_temp_1',
'acu.pointing.act_amb_temp_2',
'acu.pointing.act_amb_temp_3',
'acu.general_management_and_controller.temp_air_inlet_psc',
'acu.general_management_and_controller.temp_air_outlet_psc',
'acu.pointing.incl_signal_x_raw',
'acu.pointing.incl_signal_x_deg',
'acu.pointing.incl_signal_x_filtered',
'acu.pointing.incl_signal_x_corrected',
'acu.pointing.incl_signal_y_raw',
'acu.pointing.incl_signal_y_deg',
'acu.pointing.incl_signal_y_filtered',
'acu.pointing.incl_signal_y_corrected',
'acu.pointing.incl_temp',
'acu.pointing.incl_corr_val_az',
'acu.pointing.incl_corr_val_el'
]

hn_opcua_tilt_sensors = [
'Azimuth.AxisState',
'Azimuth.p_Set',
'Azimuth.p_Act',
'Azimuth.v_Act',
'Elevation.AxisState',
'Elevation.p_Set',
'Elevation.p_Act',
'Elevation.v_Act',
'Management.ManagementStatus.FiPos',
'Management.ManagementStatus.PowerStatus.ActPwrCnsm',
'Management.ManagementStatus.PowerStatus.CurrentPh1',
'Management.ManagementStatus.PowerStatus.CurrentPh2',
'Management.ManagementStatus.PowerStatus.CurrentPh3',
'Management.ManagementStatus.PowerStatus.PowerFactor',
'Management.ManagementStatus.PowerStatus.VoltagePh1',
'Management.ManagementStatus.PowerStatus.VoltagePh2',
'Management.ManagementStatus.PowerStatus.VoltagePh3',
'Management.ManagementStatus.TempHumidStatus.TempPSC_Inlet',
'Management.ManagementStatus.TempHumidStatus.TempPSC_Outlet',
'Pointing.ActAmbTemp_East',
'Pointing.ActAmbTemp_South',
'Pointing.ActAmbTemp_West',
'Pointing.TiltCorrVal_Az',
'Pointing.TiltCorrVal_El',
'Pointing.TiltTemp_One',
'Pointing.TiltXArcsec_One',
'Pointing.TiltXArcsec_Two',
'Pointing.TiltXFilt_One',
'Pointing.TiltXFilt_Two',
'Pointing.TiltXRaw_One',
'Pointing.TiltXRaw_Two',
'Pointing.TiltXTemp_Two',
'Pointing.TiltYArcsec_One',
'Pointing.TiltYArcsec_Two',
'Pointing.TiltYFilt_One',
'Pointing.TiltYFilt_Two',
'Pointing.TiltYRaw_One',
'Pointing.TiltYRaw_Two',
'Time.DscTime'
]

async def handle_exception(e: Exception) -> None:
    logger.exception(f'*** Exception caught: {e}')


def create_command_function(node: asyncua.Node, event_loop: asyncio.AbstractEventLoop):
    call = asyncio.run_coroutine_threadsafe(node.get_parent(), event_loop).result().call_method
    id = f'{node.nodeid.NamespaceIndex}:{asyncio.run_coroutine_threadsafe(node.read_display_name(), event_loop).result().Text}'
    def fn(*args) -> Any:
        try:
            return_code = asyncio.run_coroutine_threadsafe(call(id, *args), event_loop).result()
            return_msg:str = ""
            if hasattr(asyncua.ua, 'CmdResponseType') and return_code is not None:
                # The asyncua library has a CmdResponseType enum ONLY if the opcua server implements the type
                return_msg = asyncua.ua.CmdResponseType(return_code).name
            else:
                return_msg = str(return_code)
        except Exception as e:
            e.add_note(f'Command: {id} args: {args}')
            asyncio.run_coroutine_threadsafe(handle_exception(e), event_loop)
            return_code = -1
            return_msg = str(e)
        return return_code, return_msg
    return fn

def create_rw_attribute(node: asyncua.Node, event_loop: asyncio.AbstractEventLoop):
    class opc_ua_rw_attribute:
        @property
        def value(self) -> Any:
            try:
                return asyncio.run_coroutine_threadsafe(node.get_value(), event_loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(handle_exception(e), event_loop)
        @value.setter
        def value(self, _value: Any) -> None:
            try:
                asyncio.run_coroutine_threadsafe(node.set_value(_value), event_loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(handle_exception(e), event_loop)
    return opc_ua_rw_attribute()

def create_ro_attribute(node: asyncua.Node, event_loop: asyncio.AbstractEventLoop):
    class opc_ua_ro_attribute:
        @property
        def value(self) -> Any:
            try:
                return asyncio.run_coroutine_threadsafe(node.get_value(), event_loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(handle_exception(e), event_loop)
    return opc_ua_ro_attribute()

class SubscriptionHandler:
    def __init__(self, subscription_queue: queue.Queue, nodes: dict) -> None:
        self.subscription_queue = subscription_queue
        self.nodes = nodes
    def datachange_notification(self, node: asyncua.Node, value: Any, data: asyncua.ua.DataChangeNotification) -> None:
        """
        Callback for an asyncua subscription.
        This method will be called when an asyncua.Client receives a data change
        message from an OPC UA server.
        """
        name = self.nodes[node]
        source_timestamp = data.monitored_item.Value.SourceTimestamp
        server_timestamp = data.monitored_item.Value.ServerTimestamp.timestamp()
        value_for_queue = {'name': name, 'node': node, 'value': value, 'source_timestamp': source_timestamp, 'server_timestamp': server_timestamp, 'data': data}
        self.subscription_queue.put(value_for_queue, block = True, timeout = 0.1)

class scu:
    """
    Small ibrary that eases the pain when connecting to an OPC UA server and calling methods on it, reading or writing attributes.
    HOW TO
    ------
    # Import the library:
    import sculib
    # Instantiate an scu object. I provide here the defaults which can be
    # overwritten by specifying the named parameter.
    scu = sculib.scu(host = 'localhost', port = 4840, endpoint = '', namespace = 'http://skao.int/DS_ICD/', timeout = 10.0)
    # Done.

    # All nodes from and including the PLC_PRG node are stored in the nodes dictionary:
    scu.get_node_list()

    # You will notice that the keys in the nodes dictionary map the hierarchy
    # in the OPC UA server to a "dotted" notation. If, for example, in the
    # PLC_PRG node hierarchy a node "PLC_PRG -> Management -> Slew2AbsAzEl"
    # exists, the then key for this node will be "Management.Slew2AbsAzEl".

    # Therefore nodes can easily be accessed by their hierarchical name.
    node = scu.nodes['Tracking.TrackStatus.tr_initOk']

    # Every value in the dictionary exposes the full OPC UA functionality for a
    # node.
    # NOTE: When accessing nodes directly, it is mandatory to await any calls.
    node_name = (await (node.read_display_name()).Text

    #
    # The methods that are below the PLC_PRG node's hierarchy can be accessed
    # through the commands dictionary:
    scu.get_command_list()

    # Again, each command has a name that is directly mapped from the location
    # of the command in the hierarchy below the PLC_PRG node.
    # When you want to call a command, please check the ICD for the parameters
    # that the commands expects. Checking for the correctness of the parameters
    # is not done here in sculib but in the PLC's OPC UA server.
    # Once the parameters are in order, calling a command is really simple:
    result = scu.commands['COMMAND_NAME'](YOUR_PARAMETERS)

    # For instance, command the PLC to slew to a new position:
    az = 182.0; el = 21.8; az_v = 1.2; el_v = 2.1
    result_code, result_msg = scu.commands['Management.Slew2AbsAzEl'](az, el, az_v, el_v)

    # The OPC UA server also provides read-writeable and read-only variables,
    # commonly called in OPC UA "attributes". An attribute's value can easily
    # be read:
    scu.attributes['Azimuth.p_Set'].value

    # If an attribute is writable, then a simple assignment does the trick:
    scu.attributes['Azimuth.p_Set'].value = 1.2345

    # In case an attribute is not writeable, the OPC UA server will report an
    # error:
    scu.attributes['Azimuth.p_Set'].value = 10

    *** Exception caught
    "User does not have permission to perform the requested operation."(BadUserAccessDenied)
    """
    def __init__(self, host: str = 'localhost', port: int = 4840,
                 endpoint: str = '/OPCUA/SimpleServer',
                 namespace: str = 'CETC54',
                 timeout: float = 10.0,
                 eventloop: asyncio.AbstractEventLoop = None,
                 debug: bool = False) -> None:
        logger.info('Initialising sculib')
        self.init_called = False
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.namespace = namespace
        self.timeout = timeout
        self.event_loop_thread = None
        self.subscription_handler = None
        self.subscriptions = {}
        self.subscription_queue = queue.Queue()
        if eventloop is None:
            self.create_and_start_asyncio_event_loop()
        else:
            self.event_loop = eventloop
        logger.info(f"Event loop: {self.event_loop}")
        try:
            self.connection = self.connect(self.host, self.port, self.endpoint, self.timeout, encryption = True)
        except:
            try:
                self.connection = self.connect(self.host, self.port, self.endpoint, self.timeout, encryption = False)
            except Exception as e:
                e.add_note('Cannot connect to the OPC UA server. Please '
                             'check the connection parameters that were '
                             'passed to instantiate the sculib!')
                raise e
        logger.info('Populating nodes dicts from server. This will take about 10s...')
        self.populate_node_dicts()
        self.debug = debug
        self.init_called = True
        logger.info('Initialising sculib done.')

    def __del__(self) -> None:
        self.unsubscribe_all()
        self.disconnect()
        if self.event_loop_thread is not None:
            # Signal the event loop thread to stop.
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            # Join the event loop thread once it is done processing tasks.
            self.event_loop_thread.join()

    def run_event_loop(self, event_loop: asyncio.AbstractEventLoop, thread_started_event: threading.Event) -> None:
        # The self.event_loop needs to be stored here. Otherwise asyncio
        # complains that it has the wrong type when scheduling a coroutine.
        # Sigh.
        self.event_loop = event_loop
        asyncio.set_event_loop(event_loop)
        thread_started_event.set()  # Signal that the event loop thread has started
        event_loop.run_forever()

    def create_and_start_asyncio_event_loop(self) -> None:
        event_loop = asyncio.new_event_loop()
        thread_started_event = threading.Event()
        self.event_loop_thread = threading.Thread(target = self.run_event_loop, args = (event_loop, thread_started_event), name = f'asyncio event loop for sculib instance {self.__class__.__name__}', daemon = True,)
        self.event_loop_thread.start()
        thread_started_event.wait(5.0)  # Wait for the event loop thread to start

    def set_up_encryption(self, connection, user: str, pw: str) -> None:
        # this is generated if it does not exist
        opcua_client_key = Path(resources.files(__package__) / "certs/key.pem")
         # this is generated if it does not exist
        opcua_client_cert = Path(resources.files(__package__) / "certs/cert.der")
        # get from simulator/PKI/private/SimpleServer_2048.der in tarball
        opcua_server_cert = Path(resources.files(__package__) / "certs/SimpleServer_2048.der")
        connection.set_user(user)
        connection.set_password(pw)
        from asyncua.crypto.cert_gen import setup_self_signed_certificate
        from asyncua.crypto.security_policies import SecurityPolicyBasic256
        from asyncua.ua import MessageSecurityMode
        from cryptography.x509.oid import ExtendedKeyUsageOID
        client_app_uri = "urn:freeopcua:client"
        _ = asyncio.run_coroutine_threadsafe(setup_self_signed_certificate(
            key_file=opcua_client_key,
            cert_file=opcua_client_cert,
            app_uri=client_app_uri,
            host_name="localhost",
            cert_use=[ExtendedKeyUsageOID.CLIENT_AUTH],
            subject_attrs={
                "countryName": "ZA",
                "stateOrProvinceName": "Western Cape",
                "localityName": "Cape Town",
                "organizationName": "SKAO",
                },
            ), self.event_loop).result()
        _ = asyncio.run_coroutine_threadsafe(connection.set_security(
            SecurityPolicyBasic256,
            certificate=str(opcua_client_cert),
            private_key=str(opcua_client_key),
            server_certificate=str(opcua_server_cert),
            mode=MessageSecurityMode.Sign), self.event_loop).result()

    def connect(self, host: str, port: int, endpoint: str, timeout: float, encryption: bool = True) -> None:
        opc_ua_server = f'opc.tcp://{host}:{port}{endpoint}'
        logger.info(f"Connecting to: {opc_ua_server}")
        connection = asyncua.Client(opc_ua_server, timeout)
        if encryption:
            self.set_up_encryption(connection, "LMC", "lmc")
        _ = asyncio.run_coroutine_threadsafe(connection.connect(), self.event_loop).result()
        self.opc_ua_server = opc_ua_server
        try:
            _ = asyncio.run_coroutine_threadsafe(connection.load_data_type_definitions(), self.event_loop).result()
        except:
            # The CETC simulator V1 returns a faulty DscCmdAuthorityEnumType,
            # where the entry for 3 has no name.
            pass
        try:
            self.ns_idx = asyncio.run_coroutine_threadsafe(connection.get_namespace_index(self.namespace), self.event_loop).result()
        except ValueError as e:
            namespaces = None
            try:
                namespaces = asyncio.run_coroutine_threadsafe(connection.get_namespace_array(), self.event_loop).result()
            except:
                pass
            try:
                self.disconnect(connection)
            except:
                pass
            message = f'*** Exception caught while trying to access the requested namespace "{self.namespace}" on the OPC UA server. Will NOT continue with the normal operation but list the available namespaces here for future reference:\n{namespaces}'
            logger.error(message)
            e.add_note(message)
            raise e
        return connection

    def disconnect(self, connection = None) -> None:
        if connection is None:
            connection = self.connection
            self.connection = None
        if connection is not None:
            _ = asyncio.run_coroutine_threadsafe(connection.disconnect(), self.event_loop).result()

    def connection_reset(self) -> None:
        self.disconnect()
        self.connect()

    def populate_node_dicts(self) -> None:
        # Create three dicts:
        # nodes, attributes, commands
        # nodes: Contains the entire uasync.Node-tree from and including
        #   the 'PLC_PRG' node.
        # attributes: Contains the attributes in the uasync.Node-tree from
        #   the 'PLC_PRG' node on. The values are callables that return the
        #   current value.
        # {Key = Name as in the node hierarchy, value = the uasync.Node}
        # commands: Contains all callable methods in the uasync.Node-tree
        #   from the 'PLC_PRG' node on. The values are callables which
        #   just require the expected parameters.
        plc_prg = asyncio.run_coroutine_threadsafe(self.connection.nodes.objects.get_child([f'{self.ns_idx}:Logic', f'{self.ns_idx}:Application', f'{self.ns_idx}:PLC_PRG']), self.event_loop).result()
        nodes, attributes, commands = self.get_sub_nodes(plc_prg)
        # Small fix for the key of the top level node 'PLC_PRG'.
        plc_prg = nodes.pop('')
        nodes.update({'PLC_PRG': plc_prg})
        # Now store the three dicts as members.
        self.nodes = nodes
        self.nodes_reversed = {v: k for k, v in nodes.items()}
        self.attributes = attributes
        self.attributes_reversed = {v: k for k, v in attributes.items()}
        self.commands = commands
        self.commands_reversed = {v: k for k, v in commands.items()}

    def generate_full_node_name(self, node: asyncua.Node, node_name_separator: str = '.', stop_at_node_name: str = 'PLC_PRG') -> str:
        nodes = asyncio.run_coroutine_threadsafe(node.get_path(), self.event_loop).result()
        nodes.reverse()
        node_name = ''
        for parent_node in nodes:
            parent_node_name = f'{asyncio.run_coroutine_threadsafe(parent_node.read_display_name(), self.event_loop).result().Text}'
            if parent_node_name == stop_at_node_name:
                break
            else:
                node_name = f'{parent_node_name}{node_name_separator}{node_name}'
        return node_name.strip('.')

    def get_sub_nodes(self, node: asyncua.Node, node_name_separator: str = '.') -> (dict, dict, dict):
        nodes = {}
        attributes = {}
        commands = {}
        node_name = self.generate_full_node_name(node)
        # Do not add the InputArgument and OutputArgument nodes.
        if node_name.endswith('.InputArguments', node_name.rfind('.')) is True or node_name.endswith('.OutputArguments', node_name.rfind('.')) is True:
            return nodes, attributes, commands
        else:
            nodes[node_name] = node
        node_class = asyncio.run_coroutine_threadsafe(node.read_node_class(), self.event_loop).result().value
        # node_class = 1: Normal node with children
        # node_class = 2: Attribute
        # node_class = 4: Method
        if node_class == 1:
            children = asyncio.run_coroutine_threadsafe(node.get_children(), self.event_loop).result()
            child_nodes = {}
            for child in children:
                child_nodes, child_attributes, child_commands = self.get_sub_nodes(child)
                nodes.update(child_nodes)
                attributes.update(child_attributes)
                commands.update(child_commands)
        elif node_class == 2:
            # An attribute. Add it to the attributes dict.
            # attributes[node_name] = node.get_value
            #
            # Check if RO or RW and call the respective creator functions.
            # if node.figure_out_if_RW_or_RO is RW:
            attributes[node_name] = create_rw_attribute(node, self.event_loop)
            #else:
            # attributes[node_name] = create_ro_attribute(node, self.event_loop)
        elif node_class == 4:
            # A command. Add it to the commands dict.
            commands[node_name] = create_command_function(node, self.event_loop)
        return nodes, attributes, commands

    def get_node_list(self) -> None:
        info = ''
        for key in self.nodes.keys():
            info += f'{key}\n'
        logger.debug(info)
        return list(self.nodes.keys())
    def get_command_list(self) -> None:
        info = ''
        for key in self.commands.keys():
            info += f'{key}\n'
        logger.debug(info)
        return list(self.commands.keys())
    def get_attribute_list(self) -> None:
        info = ''
        for key in self.attributes.keys():
            info += f'{key}\n'
        logger.debug(info)
        return list(self.attributes.keys())

    def get_attribute_data_type(self, attribute: str) -> str:
        """
        Get the data type for the given node. Returns "Boolean"/"Double"/"Enumeration",
        for the respective types or "Unknown" for a not yet known type.
        """
        node = self.nodes[attribute]
        dt_id = asyncio.run_coroutine_threadsafe(node.read_data_type(), self.event_loop).result()
        dt_node = self.connection.get_node(dt_id)
        dt_node_info = asyncio.run_coroutine_threadsafe(dt_node.read_browse_name(), self.event_loop).result()
        dt_name = dt_node_info.Name
        if dt_name == "Boolean" or dt_name == "Double":
            return dt_name

        # load_data_type_definitions() called in connect() adds new classes to the asyncua.ua module.
        if dt_name in dir(asyncua.ua):
            if issubclass(getattr(asyncua.ua, dt_name), enum.Enum):
                return "Enumeration"

        return "Unknown"

    def get_enum_strings(self, enum_node: str) -> list[str]:
        """
        Get a list of enumeration strings where the index of the list matches the enum value.
        enum_node MUST be the name of an Enumeration type node (see get_attribute_data_type()).
        """
        node = self.nodes[enum_node]
        dt_id = asyncio.run_coroutine_threadsafe(node.read_data_type(), self.event_loop).result()
        dt_node = self.connection.get_node(dt_id)
        dt_node_def = asyncio.run_coroutine_threadsafe(dt_node.read_data_type_definition(), self.event_loop).result()

        return [Field.Name if Field.Value == index else logger.error("Enum fields out of order") for index, Field in enumerate(dt_node_def.Fields)]

    def subscribe(self, attributes: Union[str, list[str]] = hn_opcua_tilt_sensors, period: int = 100, data_queue: queue.Queue = None) -> int:
        if data_queue is None:
            data_queue = self.subscription_queue
        subscription_handler = SubscriptionHandler(data_queue, self.nodes_reversed)
        if not isinstance(attributes, list):
            attributes = [attributes,]
        nodes = []
        invalid_attributes = []
        for attribute in attributes:
            if attribute in self.nodes:
                nodes.append(self.nodes[attribute])
            else:
                invalid_attributes.append(attribute)
        if len(invalid_attributes) > 0:
            logger.warning(f'The following OPC-UA attributes not found in nodes '
                           f'dict and not subscribed for event updates: {invalid_attributes}')
        subscription = asyncio.run_coroutine_threadsafe(self.connection.create_subscription(period, subscription_handler), self.event_loop).result()
        handle = asyncio.run_coroutine_threadsafe(subscription.subscribe_data_change(nodes), self.event_loop).result()
        id = time.monotonic_ns()
        self.subscriptions[id] = {'handle': handle, 'nodes': nodes, 'subscription': subscription}
        return id

    def unsubscribe(self, id: int) -> None:
        subscription = self.subscriptions.pop(id)
        _ = asyncio.run_coroutine_threadsafe(subscription['subscription'].unsubscribe(subscription['handle']), self.event_loop).result()

    def unsubscribe_all(self) -> None:
        while len(self.subscriptions) > 0:
            id, subscription = self.subscriptions.popitem()
            _ = asyncio.run_coroutine_threadsafe(subscription['subscription'].unsubscribe(subscription['handle']), self.event_loop).result()

    def get_subscription_values(self) -> list[dict]:
        values = []
        while not self.subscription_queue.empty():
            values.append(self.subscription_queue.get(block = False, timeout = 0.1))
        return values

    #Direct SCU webapi functions based on urllib PUT/GET
    def feedback(self, r):
        logger.error('Not implemented because this function is not needed.')
        return
        if self.debug == True:
            logger.info('***Feedback:', r.request.url, r.request.body)
            logger.info(r.reason, r.status_code)
            logger.info("***Text returned:")
            logger.info(r.text)
        elif r.status_code != 200:
            logger.info('***Feedback:', r.request.url, r.request.body)
            logger.info(r.reason, r.status_code)
            logger.info("***Text returned:")
            logger.info(r.text)
            #logger.info(r.reason, r.status_code)
            #logger.info()

    #	def scu_get(device, params = {}, r_ip = self.ip, r_port = port):
    def scu_get(self, device, params = {}):
        logger.error('Not implemented because this function is not needed.')
        return
        '''This is a generic GET command into http: scu port + folder
        with params=payload'''
        URL = 'http://' + self.ip + ':' + self.port + device
        r = requests.get(url = URL, params = params)
        self.feedback(r)
        return(r)

    def scu_put(self, device, payload = {}, params = {}, data=''):
        logger.error('Not implemented because this function is not needed.')
        return
        '''This is a generic PUT command into http: scu port + folder
        with json=payload'''
        URL = 'http://' + self.ip + ':' + self.port + device
        r = requests.put(url = URL, json = payload, params = params, data = data)
        self.feedback(r)
        return(r)

    def scu_delete(self, device, payload = {}, params = {}):
        logger.error('Not implemented because this function is not needed.')
        return
        '''This is a generic DELETE command into http: scu port + folder
        with params=payload'''
        URL = 'http://' + self.ip + ':' + self.port + device
        r = requests.delete(url = URL, json = payload, params = params)
        self.feedback(r)
        return(r)

    #SIMPLE PUTS

    #command authority
    def command_authority(self, action: bool = None, username: str = ""):
        if action not in authority:
            logger.error('command_authority requires the action to be Get or Release!')
            return
        if len(username) <= 0:
            logger.error('command_authority command requires a user as second parameter!')
            return
        #1 get #2 release
        logger.info('command authority: ', action)
        authority={'Get': True, 'Release': False}
        return self.commands['CommandArbiter.TakeReleaseAuth'](authority[action], username)

    #commands to DMC state - dish management controller
    def interlock_acknowledge_dmc(self):
        logger.info('acknowledge dmc')
        return self.commands['Safety.InterlockAck']()

    def reset_dmc(self, axis: int = None):
        logger.info('reset dmc')
        if axis is None:
            logger.error('reset_dmc requires an axis as parameter! Try one '
                         'of these values: 0=AZ, 1=EL, 2=FI, 3=AZ&EL')
        return self.commands['Management.Reset'](axis)

    def activate_dmc(self, axis: int = None):
        logger.info('activate dmc')
        if axis is None:
            logger.error('activate_dmc requires now an axis as parameter! '
                         'Try one of these values: 0=AZ, 1=EL, 2=FI, 3=AZ&EL')
            return
        return self.commands['Management.Activate'](axis)

    def deactivate_dmc(self, axis: int = None):
        logger.info('deactivate dmc')
        if axis is None:
            logger.error('deactivate_dmc requires now an axis as parameter! '
                         'Try one of these values: 0=AZ, 1=EL, 2=FI, 3=AZ&EL')
            return
        return self.commands['Management.DeActivate'](axis)

    def move_to_band(self, position):
        bands = {'Band 1': 1, 'Band 2': 2, 'Band 3': 3, 'Band 4': 4, 'Band 5a': 5, 'Band 5b': 6, 'Band 5c': 7}
        logger.info('move to band:', position)
        if not(isinstance(position, str)):
            return self.commands['Management.Move2Band'](position)
        else:
            return self.commands['Management.Move2Band'](bands[position])

    def abs_azel(self, az_angle, el_angle, az_velocity: float = None, el_velocity: float = None):
        if az_velocity is None or el_velocity is None:
            logger.error('abs_azel requires now the velocities for az and el '
                         'as third and fourth parameters!')
            return
        logger.info(f'abs az: {az_angle:.4f} el: {el_angle:.4f}, az velocity: {az_velocity:.4f}, el velocity: {el_velocity:.4f}')
        return self.commands['Management.Slew2AbsAzEl'](az_angle, el_angle, az_veloxity, el_velocity)

    #commands to ACU
    def activate_az(self):
        logger.info('activate azimuth')
        return self.activate_dmc(0)

    def deactivate_az(self):
        logger.info('deactivate azimuth')
        return self.deactivate_dmc(0)

    def activate_el(self):
        logger.info('activate elevation')
        return self.activate_dmc(1)

    def deactivate_el(self):
        logger.info('deactivate elevation')
        return self.deactivate_dmc(1)

    def activate_fi(self):
        logger.info('activate feed indexer')
        return self.activate_dmc(2)

    def deactivate_fi(self):
        logger.info('deactivate feed indexer')
        return self.deactivate_dmc(2)

    def abs_azimuth(self, az_angle, az_vel):
        logger.info(f'abs az: {az_angle:.4f} vel: {az_vel:.4f}')
        return self.commands['Management.Slew2AbsSingleAx'](0, az_angle, az_vel)

    def abs_elevation(self, el_angle, el_vel):
        logger.info(f'abs el: {el_angle:.4f} vel: {el_vel:.4f}')
        return self.commands['Management.Slew2AbsSingleAx'](1, el_angle, el_vel)

    def abs_feed_indexer(self, fi_angle, fi_vel):
        logger.info(f'abs fi: {fi_angle:.4f} vel: {fi_vel:.4f}')
        return self.commands['Management.Slew2AbsSingleAx'](2, fi_angle, fi_vel)

    def load_static_offset(self, az_offset, el_offset):
        logger.info(f'offset az: {az_offset:.4f} el: {el_offset:.4f}')
        return self.commands['Tracking.TrackLoadStaticOff'](az_offset, el_offset)

    def load_program_track(self, load_type, entries, t=[0]*5000, az=[0]*5000, el=[0]*5000):
        logger.info(load_type)

        # unused
        # LOAD_TYPES = {
        #     'LOAD_NEW' : 0,
        #     'LOAD_ADD' : 1,
        #     'LOAD_RESET' : 2}

        # unused
        #table selector - to tidy for future use
        # ptrackA = 11
        # TABLE_SELECTOR =  {
        #     'pTrackA' : 11,
        #     'pTrackB' : 12,
        #     'oTrackA' : 21,
        #     'oTrackB' : 22}

        # unused
        #funny thing is SCU wants 50 entries, even for LOAD RESET! or if you send less then you have to pad the table
        # if entries != 50:
        #     padding = 50 - entries
        #     t  += [0] * padding
        #     az += [0] * padding
        #     el += [0] * padding

        table = ""
        for index in range(len(t)):
            row = f'{index:03d}:{t[index]},{az[index]},{el[index]};\n'
            table.append(row)
        logging.debug(f'Track table that will be sent to DS:{table}')
        byte_string = table.encode()
        return self.commands['Tracking.TrackLoadTable'](load_type, entries, byte_string)

    def start_program_track(self, start_time, start_restart_or_stop: bool = True):
        # unused
        # ptrackA = 11
        #interpol_modes
        # NEWTON = 0
        # SPLINE = 1
        #start_track_modes
        # AZ_EL = 1
        # RA_DEC = 2
        # RA_DEC_SC = 3  #shortcut
        return self.commands['Tracking.TrackStart'](1, start_time, start_restart_or_stop)

    def acu_ska_track(self, number_of_entries: int = None, BODY: bytes = None):
        logger.info('acu ska track')
        if number_of_entries is None:
            logger.error('acu_ska_track requires now as first parameter the '
                         'number of entries!')
            return
        self.commands['Tracking.TrackLoadTable'](0, number_of_entries, BODY)

    def acu_ska_track_stoploadingtable(self):
        logger.error('Not implemented because the function '
                     '"stopLoadingTable" is not supported by the OPC UA '
                     'server.')
        return
        # self.scu_put('/acuska/stopLoadingTable')

    def format_tt_line(self, t, az,  el, capture_flag: int = 1,
                       parallactic_angle: float = 0.0):
        '''something will provide a time, az and el as minimum
        time must alread be absolute time desired in mjd format
        assumption is capture flag and parallactic angle will not be used'''
        f_str = f'{t:.12f} {az:.6f} {el:.6f} {capture_flag:.0f} ' \
            '{parallactic_angle:.6f}\n'
        return f_str

    def format_body(self, t, az, el):
        body = ''
        for i in range(len(t)):
            body += self.format_tt_line(t[i], az[i], el[i])
        return body

    #status get functions goes here

    def status_Value(self, sensor):
        return self.attributes[sensor].value

    def status_finalValue(self, sensor):
        logger.error('Not implemented because the function '
                     '"finalValue" is not supported by the OPC UA '
                     'server.')
        return
        # return self.status_Value(sensor)
        # r = self.scu_get('/devices/statusValue',
        #       {'path': sensor})
        # data = r.json()['finalValue']
        #logger.info('finalValue: ', data)
        # return data

    def commandMessageFields(self, commandPath):
        logger.error('Not implemented because the function '
                     '"commandMessageFields" is not supported by the OPC UA '
                     'server.')
        return
        # r = self.scu_get('/devices/commandMessageFields',
        #       {'path': commandPath})
        # return r

    def statusMessageField(self, statusPath):
        logger.error('Not implemented because the function '
                     '"statusMessageFields" is not supported by the OPC UA '
                     'server.')
        return
        # r = self.scu_get('/devices/statusMessageFields',
        #       {'deviceName': statusPath})
        # return r

    #ppak added 1/10/2020 as debug for onsite SCU version
    #but only info about sensor, value itself is murky?
    def field(self, sensor):
        logger.error('Not implemented because the function "field" is not '
                     'supported by the OPC UA server.')
        return
        #old field method still used on site
        r = self.scu_get('/devices/field',
              {'path': sensor})
        #data = r.json()['value']
        data = r.json()
        return data

    #logger functions goes here

    def create_logger(self, config_name, sensor_list):
        '''
        PUT create a config for logging
        Usage:
        create_logger('HN_INDEX_TEST', hn_feed_indexer_sensors)
        or
        create_logger('HN_TILT_TEST', hn_tilt_sensors)
        '''
        logger.info('create logger')
        r = self.scu_put('/datalogging/config',
              {'name': config_name,
               'paths': sensor_list})
        return r

    '''unusual does not take json but params'''
    def start_logger(self, filename):
        logger.info('start logger: ', filename)
        r = self.scu_put('/datalogging/start',
              params='configName=' + filename)
        return r

    def stop_logger(self):
        logger.info('stop logger')
        r = self.scu_put('/datalogging/stop')
        return r

    def logger_state(self):
#        logger.info('logger state ')
        r = self.scu_get('/datalogging/currentState')
        #logger.info(r.json()['state'])
        return r.json()['state']

    def logger_configs(self):
        logger.info('logger configs ')
        r = self.scu_get('/datalogging/configs')
        return r

    def last_session(self):
        '''
        GET last session
        '''
        logger.info('Last sessions ')
        r = self.scu_get('/datalogging/lastSession')
        session = (r.json()['uuid'])
        return session

    def logger_sessions(self):
        '''
        GET all sessions
        '''
        logger.info('logger sessions ')
        r = self.scu_get('/datalogging/sessions')
        return r

    def session_query(self, id):
        '''
        GET specific session only - specified by id number
        Usage:
        session_query('16')
        '''
        logger.info('logger sessioN query id ')
        r = self.scu_get('/datalogging/session',
             {'id': id})
        return r

    def session_delete(self, id):
        '''
        DELETE specific session only - specified by id number
        Not working - returns response 500
        Usage:
        session_delete('16')
        '''
        logger.info('delete session ')
        r = self.scu_delete('/datalogging/session',
             params= 'id='+id)
        return r

    def session_rename(self, id, new_name):
        '''
        RENAME specific session only - specified by id number and new session name
        Not working
        Works in browser display only, reverts when browser refreshed!
        Usage:
        session_rename('16','koos')
        '''
        logger.info('rename session ')
        r = self.scu_put('/datalogging/session',
             params = {'id': id,
                'name' : new_name})
        return r


    def export_session(self, id, interval_ms=1000):
        '''
        EXPORT specific session - by id and with interval
        output r.text could be directed to be saved to file
        Usage:
        export_session('16',1000)
        or export_session('16',1000).text
        '''
        logger.info('export session ')
        r = self.scu_get('/datalogging/exportSession',
             params = {'id': id,
                'interval_ms' : interval_ms})
        return r

    #sorted_sessions not working yet

    def sorted_sessions(self, isDescending = 'True', startValue = '1', endValue = '25', sortBy = 'Name', filterType='indexSpan'):
        logger.info('sorted sessions')
        r = self.scu_get('/datalogging/sortedSessions',
             {'isDescending': isDescending,
              'startValue': startValue,
              'endValue': endValue,
              'filterType': filterType, #STRING - indexSpan|timeSpan,
              'sortBy': sortBy})
        return r

    #get latest session
    def save_session(self, filename, interval_ms=1000, session = 'last'):
        '''
        Save session data as CSV after EXPORTing it
        Default interval is 1s
        Default is last recorded session
        if specified no error checking to see if it exists
        Usage:
        export_session('16',1000)
        or export_session('16',1000).text
        '''
        from pathlib import Path
        logger.info('Attempt export and save of session: {} at rate {:.0f} ms'.format(session, interval_ms))
        if session == 'last':
            #get all logger sessions, may be many
            r = self.logger_sessions()
            #[-1] for end of list, and ['uuid'] to get id of last session in list
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info('Session id: {} '.format(session))
        file_time = str(int(time.time()))
        file_name = str(filename + '_' + file_time + '.csv')
        file_path = Path.cwd()  / 'output' / file_name
        logger.info('Log file location:', file_path)
        f = open(file_path, 'a+')
        f.write(file_txt)
        f.close()

    #get latest session ADDED BY HENK FOR BETTER FILE NAMING FOR THE OPTICAL TESTS (USING "START" AS TIMESTAMP)
    def save_session13(self, filename, start, interval_ms=1000, session = 'last'):
        '''
        Save session data as CSV after EXPORTing it
        Default interval is 1s
        Default is last recorded session
        if specified no error checking to see if it exists
        Usage:
        export_session('16',1000)
        or export_session('16',1000).text
        '''
        from pathlib import Path
        logger.info('Attempt export and save of session: {} at rate {:.0f} ms'.format(session, interval_ms))
        if session == 'last':
            #get all logger sessions, may be many
            r = self.logger_sessions()
            #[-1] for end of list, and ['uuid'] to get id of last session in list
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info('Session id: {} '.format(session))
##        file_time = str(int(time.time()))
        file_time = str(int(start))
        file_name = str(filename + '_' + file_time + '.csv')
        file_path = Path.cwd()  / 'output' / file_name
        logger.info('Log file location:', file_path)
        f = open(file_path, 'a+')
        f.write(file_txt)
        f.close()

    def save_session14(self, filename, interval_ms=1000, session = 'last'):
        '''
        Save session data as CSV after EXPORTing it
        Default interval is 1s
        Default is last recorded session
        if specified no error checking to see if it exists
        Usage:
        export_session('16',1000)
        or export_session('16',1000).text
        '''
        from pathlib import Path
        logger.info('Attempt export and save of session: {} at rate {:.0f} ms'.format(session, interval_ms))
        if session == 'last':
            #get all logger sessions, may be many
            r = self.logger_sessions()
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info('Session id: {} '.format(session))
        file_name = str(filename + '.csv')
        file_path = Path.cwd()  / 'output' / file_name
        logger.info('Log file location:', file_path)
        f = open(file_path, 'a+')
        f.write(file_txt)
        f.close()

    #Simplified one line commands particular to test section being peformed

    #wait seconds, wait value, wait finalValue
    def wait_duration(self, seconds):
        logger.info(f'  wait for {seconds:.1f}s', end="")
        time.sleep(seconds)
        logger.info(' done *')

    def wait_value(self, sensor, value):
        logger.info(f'wait until sensor: {sensor} == value {value}')
        while self.attributes[sensor].value != value:
            time.sleep(1)
        logger.info(f' {sensor} done *')

    def wait_finalValue(self, sensor, value):
        logger.info(f'wait until sensor: {sensor} == value {value}')
        while status_finalValue(sensor) != value:
            time.sleep(1)
        logger.info(f' {sensor} done *')

    #Simplified track table functions


if __name__ == '__main__':
   logger.info("main")
