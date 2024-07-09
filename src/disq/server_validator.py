"""Server ICD validator."""

import argparse
import asyncio
import os
import sys
import threading
from difflib import SequenceMatcher
from typing import Any

from asyncua import Node, ua

from disq import configuration, sculib
from disq.serval_internal_server import SerValInternalServer


# pylint: disable=too-many-instance-attributes
class OPCUAServerValidator:
    """
    A class representing an OPC UA server validator and its functionalities.

    :param include_namespace: Flag to indicate whether to include namespace in node
        names. Default is False.
    :type include_namespace: bool
    """

    opcua_node_class_names = {
        0: "Unspecified",
        1: "Object",
        2: "Variable",
        4: "Method",
        8: "ObjectType",
        16: "VariableType",
        32: "ReferenceType",
        64: "DataType",
        128: "View",
    }
    opcua_attribute_ids = {
        "NodeId": 1,
        "NodeClass": 2,
        "BrowseName": 3,
        "DisplayName": 4,
        "Description": 5,
        "WriteMask": 6,
        "UserWriteMask": 7,
        "IsAbstract": 8,
        "Symmetric": 9,
        "InverseName": 10,
        "ContainsNoLoops": 11,
        "EventNotifier": 12,
        "Value": 13,
        "DataType": 14,
        "ValueRank": 15,
        "ArrayDimensions": 16,
        "AccessLevel": 17,
        "UserAccessLevel": 18,
        "MinimumSamplingInterval": 19,
        "Historizing": 20,
        "Executable": 21,
        "UserExecutable": 22,
        "DataTypeDefinition": 23,
        "RolePermissions": 24,
        "UserRolePermissions": 25,
        "AccessRestrictions": 26,
        "AccessLevelEx": 27,
    }

    def __init__(self, include_namespace: bool = False):
        """
        Initialize a new instance of a class.

        :param include_namespace: A boolean indicating whether to include namespace in
            arguments (default is False).
        :type include_namespace: bool

        :variables:
            - internal_server_started_barrier: Barrier to synchronize internal server
                start.
            - internal_server_stop: Event to signal stop of internal server.
            - fuzzy_threshold: A float representing the fuzzy threshold value.
            - include_namespace: A boolean indicating whether namespace is included in
                arguments.
            - in_args: Input arguments with or without namespace based on
                include_namespace value.
            - out_args: Output arguments with or without namespace based on
                include_namespace value.
        """
        self.internal_server_started_barrier = threading.Barrier(2)
        self.internal_server_stop = threading.Event()
        self.fuzzy_threshold = 0.85
        self.include_namespace = False
        if include_namespace:
            self.in_args = "0:InputArguments"
            self.out_args = "0:OutputArguments"
        else:
            self.in_args = "InputArguments"
            self.out_args = "OutputArguments"
        self.server: sculib.SCU
        self.event_loop: asyncio.AbstractEventLoop

    async def _run_internal_server(self, xml_file: str):
        """
        Run an internal server using the specified XML file.

        :param xml_file: The path to the XML file for configuring the internal server.
        :type xml_file: str
        """
        async with SerValInternalServer(xml_file):
            self.internal_server_started_barrier.wait()
            while not self.internal_server_stop.is_set():
                await asyncio.sleep(1)

    def _run_internal_server_wrap(self, xml_file):
        """
        Run the internal server using asyncio to process an XML file.

        :param xml_file: The XML file to be processed.
        :type xml_file: str
        :raises: Any exceptions that may occur during the internal server execution.
        """
        asyncio.run(self._run_internal_server(xml_file))

    def _read_node_name(self, node: Node) -> ua.uatypes.QualifiedName:
        """
        Read the browse name of a given Node.

        :param node: The Node whose browse name is to be read.
        :type node: asyncua.Node
        :return: The QualifiedName object representing the browse name of the Node.
        :rtype: asyncua.ua.uatypes.QualifiedName
        """
        return asyncio.run_coroutine_threadsafe(
            node.read_browse_name(), self.event_loop
        ).result()

    def _get_node_info(
        self, node: Node
    ) -> tuple[ua.uatypes.QualifiedName, ua.NodeClass, list[Node]]:
        """
        Get information about a Node in the OPC UA server.

        :param node: The Node object to retrieve information from.
        :type node: asyncua.Node
        :return: A tuple containing the name, class, and children of the input Node.
        :rtype: tuple
        """
        name = self._read_node_name(node)
        node_class = asyncio.run_coroutine_threadsafe(
            node.read_node_class(), self.event_loop
        ).result()
        children = asyncio.run_coroutine_threadsafe(
            node.get_children(), self.event_loop
        ).result()

        return (name, node_class, children)

    def _get_param_type_tuple(self, node_id: ua.uatypes.NodeId) -> tuple:
        """
        Get the parameter type tuple for a given NodeId.

        :param node_id: The NodeId of the parameter.
        :type node_id: asyncua.ua.uatypes.NodeId
        :return: A tuple containing the parameter type and additional information if the
            type is 'Enumeration'.
        :rtype: tuple
        """
        param_type = self.server.get_attribute_data_type(node_id)
        if param_type == "Enumeration":
            return (param_type, ",".join(self.server.get_enum_strings(node_id)))

        return (param_type,)

    def _get_method_info(self, node: Node) -> dict:
        """
        Get information about the method associated with a Node.

        :param node: The Node object representing the method.
        :type node: asyncua.Node
        :return: A dictionary containing information about the method parameters.
        :rtype: dict
        """
        params = (
            asyncio.run_coroutine_threadsafe(
                node.read_attribute(self.opcua_attribute_ids["Value"]), self.event_loop
            )
            .result()
            .Value.Value
        )
        args = {}
        if params is not None:
            for param in params:
                args[param.Name] = self._get_param_type_tuple(param.DataType)

        return args

    def _read_data_type_tuple(self, sculib_path: str) -> tuple:
        """
        Read and return the data type information of a node in SCULib.

        The tuple can have one or two elements:
        - If an error occurs while retrieving the data type, a tuple with a single
        element 'Node name error' is returned.
        - If the data type is an Enumeration, a tuple with two elements is returned:
        The data type as the first element, and a comma-separated string of enum strings
        as the second element.
        - Otherwise, a tuple with the data type as the only element is returned.

        :param sculib_path: The path of the node in SCULib.
        :type sculib_path: str

        :return: A tuple containing the data type information.
        :rtype: tuple
        """
        try:
            data_type = self.server.get_attribute_data_type(sculib_path)
        except Exception:  # pylint: disable=broad-exception-caught
            return ("Node name error",)
        if data_type == "Enumeration":
            return (data_type, ",".join(self.server.get_enum_strings(sculib_path)))

        return (data_type,)

    def _fill_tree_recursive(self, node: Node, ancestors: list[str]) -> dict:
        """
        Fill a dictionary representing the OPC UA nodes starting from a given node.

        :param node: The starting node to traverse.
        :type node: asyncua.Node
        :param ancestors: List of ancestor node names.
        :type ancestors: list[str]
        :return: A dictionary representing the OPC UA nodes starting from the given node
        :rtype: dict
        """
        node_dict: dict[str, Any] = {}
        # Fill node info
        name, node_class, node_children = self._get_node_info(node)
        short_name = name.Name
        if self.include_namespace:
            name = f"{name.NamespaceIndex}:{short_name}"
        else:
            name = short_name
        node_dict[name] = {
            "node_class": self.opcua_node_class_names[node_class],
        }
        ancestors.append(short_name)
        if node_class == 2:
            if name == self.in_args:
                node_dict[name]["method_params"] = self._get_method_info(node)
            elif name == self.out_args:
                node_dict[name]["method_return"] = self._get_method_info(node)
            else:
                sculib_ancestors = ancestors[1:]  # No "PLC_PRG" in sculib paths
                sculib_path = ".".join(sculib_ancestors)
                data_type = self._read_data_type_tuple(sculib_path)
                node_dict[name]["data_type"] = data_type

        # Create hierarchical structure
        children = {}
        for child in node_children:
            children.update(self._fill_tree_recursive(child, ancestors[:]))

        node_dict[name]["children"] = children

        return node_dict

    # pylint: disable=too-many-arguments
    def _scan_opcua_server(
        self,
        host: str,
        port: str,
        endpoint: str,
        namespace: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        # Use sculib for encryption and getting PLC_PRG node.
        """
        Scan an OPC UA server and retrieve the server tree.

        :param host: The IP address or hostname of the OPC UA server.
        :type host: str
        :param port: The port number of the OPC UA server.
        :type port: str
        :param endpoint: The endpoint of the OPC UA server.
        :type endpoint: str
        :param namespace: The namespace of the OPC UA server.
        :type namespace: str
        :param username: The username of the OPC UA server.
        :type username: str
        :param password: The password of the OPC UA server.
        :type password: str
        :return: A dictionary representing the server tree.
        :rtype: dict
        """
        self.server = sculib.SCU(
            host, int(port), endpoint, namespace, username, password
        )
        self.event_loop = self.server.event_loop
        # Fill tree dict for server
        server_tree = self._fill_tree_recursive(self.server.plc_prg, [])

        self.server.disconnect()
        return server_tree

    def _args_match(self, actual_args: dict, expected_args: dict) -> bool:
        """
        Check if the actual arguments match the expected arguments.

        :param actual_args: A dictionary containing the actual arguments.
        :type actual_args: dict
        :param expected_args: A dictionary containing the expected arguments.
        :type expected_args: dict
        :return: True if the actual arguments match the expected arguments, False
            otherwise.
        :rtype: bool
        """
        ret = True
        for param, data_type in expected_args.items():
            if param not in actual_args:
                ret = False
                break

            if actual_args[param] != data_type:
                ret = False
                break

        return ret

    def _node_children_match(
        self, actual_children: dict, expected_children: dict, to_fuzzy: list
    ) -> bool:
        """
        Check if the children nodes of a node match the expected children.

        :param actual_children: A dictionary of actual children nodes.
        :type actual_children: dict
        :param expected_children: A dictionary of expected children nodes.
        :type expected_children: dict
        :param to_fuzzy: A list to store nodes that need to be matched fuzzily.
        :type to_fuzzy: list
        :return: True if the children nodes match, False otherwise.
        :rtype: bool
        """
        ret = True
        for child in actual_children:
            if child not in expected_children:
                # Server under test has extra nodes
                ret = False

        for child in expected_children:
            if child not in actual_children:
                # Server under test missing nodes
                ret = False
                to_fuzzy.append(child)

        return ret

    def _fuzzy_match(self, actual_siblings: dict, to_fuzzy: list) -> list:
        """
        Perform a fuzzy matching between expected values and actual siblings.

        :param actual_siblings: A dictionary containing actual sibling values.
        :type actual_siblings: dict
        :param to_fuzzy: A list of values to be fuzzy matched against actual siblings.
        :type to_fuzzy: list
        :return: A list of dictionaries where keys are expected values and values are
            possible matches.
        :rtype: list
        """
        possibles = []
        for expected in to_fuzzy:
            possible = []
            for sibling in actual_siblings.keys():
                ratio = SequenceMatcher(a=expected, b=sibling).ratio()
                if ratio > self.fuzzy_threshold:
                    possible.append(sibling)

            possibles.append({expected: possible})

        return possibles

    def _compare(self, actual: dict, expected: dict) -> dict:
        """
        Compare two dictionaries representing nested data structures.

        :param actual: The actual dictionary representing the current state.
        :type actual: dict
        :param expected: The expected dictionary representing the desired state.
        :type expected: dict
        :return: A dictionary representing the differences between the actual and
            expected dictionaries.
        :rtype: dict
        """
        diff_tree = {}
        for node, node_info in expected.items():
            if node in actual:
                current_diff: dict[str, list | bool] = {}
                node_children = {}
                if node == self.in_args:
                    current_diff["params_match"] = self._args_match(
                        actual[node]["method_params"], node_info["method_params"]
                    )
                elif node == self.out_args:
                    current_diff["return_match"] = self._args_match(
                        actual[node]["method_return"], node_info["method_return"]
                    )
                else:
                    # check node class matches
                    current_diff["class_match"] = (
                        actual[node]["node_class"] == node_info["node_class"]
                    )
                    # check data type matches if it is of variable type
                    if node_info["node_class"] == "Variable":
                        try:
                            _ = actual[node]["data_type"]
                        except Exception:  # pylint: disable=broad-exception-caught
                            current_diff["type_match"] = False
                        else:
                            current_diff["type_match"] = (
                                actual[node]["data_type"] == node_info["data_type"]
                            )

                    # check num and name of children
                    to_fuzzy: list = []
                    current_diff["children_match"] = self._node_children_match(
                        actual[node]["children"], node_info["children"], to_fuzzy
                    )
                    if len(to_fuzzy) > 0:
                        current_diff["fuzzy"] = self._fuzzy_match(
                            actual[node]["children"], to_fuzzy
                        )

                    # recurse children
                    node_children = self._compare(
                        actual[node]["children"], node_info["children"]
                    )

                diff_tree[node] = {"diff": current_diff, "children": node_children}

        return diff_tree

    def _print(self, string: str, output_file: str | None = None):
        """
        Print a string either to the console or to a file.

        :param string: The string to be printed.
        :type string: str
        :param output_file: The file to which the string should be printed. If None,
            string is printed to the console.
        :type output_file: str or None
        :raises FileNotFoundError: If the specified output file does not exist.
        """
        if output_file is None:
            print(string)
        else:
            with open(output_file, "a", encoding="UTF-8") as f:
                print(string, file=f)

    # pylint: disable=too-many-arguments,unnecessary-comprehension
    def _print_method_args_mismatch_string(
        self,
        indent: str,
        args_string: str,
        expected_info: dict,
        actual_info: dict,
        output_file: str | None = None,
    ):
        """
        Print a formatted string comparing expected and actual method arguments.

        :param indent: String used for indentation.
        :type indent: str
        :param args_string: String representation of method arguments.
        :type args_string: str
        :param expected_info: Dictionary containing expected method arguments
            information.
        :type expected_info: dict
        :param actual_info: Dictionary containing actual method arguments information.
        :type actual_info: dict
        :param output_file: Optional file to write the output to.
        :type output_file: str or None
        """
        alignment = " " * (len(args_string) + 4)
        expected_params = [
            (name, data_type) for name, data_type in expected_info[args_string].items()
        ]
        actual_params = [
            (name, data_type) for name, data_type in actual_info[args_string].items()
        ]
        self._print(
            f"  {indent}{args_string}: Expected: {expected_params},"
            f"{alignment}{indent}  actual: {actual_params}",
            output_file,
        )

    # TODO: Consider refactoring for more readable code, remove below disabled rules
    # pylint: disable=too-many-branches,unnecessary-comprehension
    # pylint: disable=too-many-arguments,too-many-locals, too-many-nested-blocks
    def print_diff(
        self,
        actual: dict,
        expected: dict,
        diff: dict,
        level: int,
        verbose: bool = False,
        output_file: str | None = None,
    ):
        """
        Print the differences between actual and expected dictionaries.

        :param actual: The actual dictionary to compare.
        :type actual: dict
        :param expected: The expected dictionary to compare.
        :type expected: dict
        :param diff: The differences dictionary between actual and expected.
        :type diff: dict
        :param level: The current level of recursion.
        :type level: int
        :param verbose: Whether to include verbose output.
        :type verbose: bool, optional
        :param output_file: The file to output the results to.
        :type output_file: str, optional
        """
        indent = " " * len("  Children: ") * level
        for node, node_info in expected.items():
            if node in actual:
                self._print(f"{indent}>{node}", output_file)
                if node == self.in_args:
                    if diff[node]["diff"]["params_match"]:
                        if verbose:
                            self._print(f"  {indent}method_params: Match", output_file)
                    else:
                        self._print_method_args_mismatch_string(
                            indent,
                            "method_params",
                            node_info,
                            actual[node],
                            output_file,
                        )

                elif node == self.out_args:
                    if diff[node]["diff"]["return_match"]:
                        if verbose:
                            self._print(f"  {indent}method_return: Match", output_file)
                    else:
                        self._print_method_args_mismatch_string(
                            indent,
                            "method_return",
                            node_info,
                            actual[node],
                            output_file,
                        )

                else:
                    if diff[node]["diff"]["class_match"]:
                        if verbose:
                            self._print(f"  {indent}node_class: Match", output_file)
                    else:
                        self._print(
                            f"  {indent}node_class: Expected: {node_info['node_class']}"
                            f", actual: {actual[node]['node_class']}",
                            output_file,
                        )

                    if node_info["node_class"] == "Variable":
                        if diff[node]["diff"]["type_match"]:
                            if verbose:
                                self._print(f"  {indent}data_type: Match", output_file)
                        else:
                            try:
                                actual_type = actual[node]["data_type"]
                            except Exception:  # pylint: disable=broad-exception-caught
                                actual_type = "None"

                            self._print(
                                f"  {indent}data_type: Expected: "
                                f"{node_info['data_type']}, actual: {actual_type}",
                                output_file,
                            )

                    if len(node_info["children"]) > 0:
                        if diff[node]["diff"]["children_match"]:
                            if verbose:
                                self._print(f"  {indent}children: Match", output_file)
                            else:
                                self._print(f"  {indent}children:", output_file)
                        else:
                            children_indent = " " * len("  children: ")
                            expected_children = [
                                name for name in node_info["children"].keys()
                            ]
                            actual_children = [
                                name for name in actual[node]["children"].keys()
                            ]
                            if "fuzzy" in diff[node]["diff"]:
                                fuzzy_children = [
                                    fuzzy for fuzzy in diff[node]["diff"]["fuzzy"]
                                ]
                                children_match = f"""Expected: {expected_children},
{children_indent}{indent}  actual: {actual_children}.
{children_indent}{indent}Possible matches: {fuzzy_children}"""
                            else:
                                children_match = f"""Expected: {expected_children},
{children_indent}{indent}  actual: {actual_children}"""

                            self._print(
                                f"  {indent}children: {children_match}", output_file
                            )

                    self.print_diff(
                        actual[node]["children"],
                        node_info["children"],
                        diff[node]["children"],
                        level + 1,
                        verbose=verbose,
                        output_file=output_file,
                    )

    def validate(
        self, xml_file: str, server_file: str, server_config: str
    ) -> tuple[bool, dict, dict, dict]:
        """
        Validate the configuration of an OPC UA server.

        Using provided XML, server file, and server configuration.

        :param xml_file: The path to the XML file.
        :type xml_file: str
        :param server_file: The path to the server file.
        :type server_file: str
        :param server_config: The server configuration.
        :type server_config: str
        :return: A tuple containing a boolean indicating if the validation was
            successful, actual_tree, expected_tree, and diff_tree.
        :rtype: tuple
        :raises: No explicit exceptions raised, but may encounter exceptions related to
            configuration or server operations.
        """
        if server_file is None:
            print(
                f"Using xml file: {xml_file}, and config: {server_config} from "
                "default configuration."
            )
        else:
            print(
                f"Using xml file: {xml_file}, and config: {server_config} from "
                f"{server_file}"
            )

        # First build tree of dubious server
        server_args = configuration.get_config_sculib_args(server_file, server_config)
        if "endpoint" in server_args and "namespace" in server_args:
            if "username" in server_args and "password" in server_args:
                actual_tree = self._scan_opcua_server(
                    server_args["host"],
                    server_args["port"],
                    server_args["endpoint"],
                    server_args["namespace"],
                    server_args["username"],
                    server_args["password"],
                )
            else:
                actual_tree = self._scan_opcua_server(
                    server_args["host"],
                    server_args["port"],
                    server_args["endpoint"],
                    server_args["namespace"],
                )
        else:
            # First physical controller does not have an endpoint or namespace
            actual_tree = self._scan_opcua_server(
                server_args["host"],
                server_args["port"],
                "",
                "",
            )

        # Second build tree of correct server
        self.internal_server_stop.clear()
        internal_server_process = threading.Thread(
            target=self._run_internal_server_wrap,
            args=[xml_file],
            name="Internal Server Thread",
        )
        internal_server_process.start()
        self.internal_server_started_barrier.wait()
        expected_tree = self._scan_opcua_server(
            "127.0.0.1", "57344", "/dish-structure/server/", "http://skao.int/DS_ICD/"
        )
        self.internal_server_stop.set()

        # Third compare the two
        diff_tree = self._compare(actual_tree, expected_tree)
        if actual_tree == expected_tree:
            return (True, actual_tree, expected_tree, diff_tree)

        return (False, actual_tree, expected_tree, diff_tree)


# pylint: disable=too-many-branches
def main():
    """
    Validate an OPCUA server against an XML file.

    :param ini: Print the server configurations available in the given .ini file or in
        the default configuration if used with no argument. (optional)
    :type ini: str
    :param xml: XML file to validate against.
    :type xml: str
    :param config_file: .ini file containing OPCUA server configurations. If this option
        is not specified the script will attempt to find a default configuration.
        (optional)
    :type config_file: str
    :param config: Server within config_file specifying OPCUA server configuration.
    :type config: str
    :param verbose: The default output only reports the node tree and when the relevant
        information on the server does not match the input XML. Use this option to also
        report when the node info does match. (optional)
    :type verbose: bool
    :param output_file: Write the diff (if any) to the specified output file. If the
        file exists it will be overwritten if there is a diff. (optional)
    :type output_file: str
    :raises FileNotFoundError: If a file is not found.
    """
    parser = argparse.ArgumentParser(
        prog="Dish Structure Server Validator",
        description="Validates an OPCUA server against an XML.",
    )
    parser.add_argument(
        "-i",
        "--ini",
        help=(
            "Print the server configurations available in the given .ini file"
            " or in the default configuration if used with no argument."
        ),
        required=False,
        nargs="?",
        const=" ",
        dest="ini",
    )
    parser.add_argument(
        "-x",
        "--xml",
        help="XML file to validate against.",
        required="--ini" not in sys.argv and "-i" not in sys.argv,
        nargs=1,
        dest="xml",
    )
    parser.add_argument(
        "-f",
        "--config_file",
        help=(
            ".ini file containing OPCUA server configurations. If this option "
            "is not specified the script will attempt to find a default configuration."
        ),
        required=False,
        nargs=1,
        dest="config_file",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Server within config_file specifying OPCUA server configuration.",
        required="--ini" not in sys.argv and "-i" not in sys.argv,
        nargs=1,
        dest="config",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help=(
            "The default output only reports the node tree and when the "
            "relevant information on the server does not match the input XML. "
            "Use this option to also report when the node info does match."
        ),
        required=False,
        action="store_true",
        dest="verbose",
    )
    parser.add_argument(
        "-o",
        help=(
            "Write the diff (if any) to the specified output file. If the "
            "file exists it will be overwritten if there is a diff."
        ),
        required=False,
        nargs=1,
        dest="output_file",
    )
    args = parser.parse_args()
    if args.ini:
        try:
            if args.ini == " ":
                args.ini = None

            configurations = configuration.get_config_server_list(args.ini)
        except FileNotFoundError as e:
            print(e)
        else:
            print("Server configurations available in default configuration:")
            for server_config in configurations:
                print(server_config)
        return

    xml = args.xml[0]
    if "-f" not in sys.argv and "--config" not in sys.argv:
        config_file = None
    else:
        config_file = args.config_file[0]

    try:
        configuration.get_config_server_list(config_file)
    except FileNotFoundError as e:
        print(e)
        return

    config = args.config[0]
    verbose = args.verbose
    output_file = None
    if "-o" in sys.argv:
        output_file = args.output_file[0]

    if not os.path.isfile(xml):
        sys.exit(f"ERROR: Could not find file {xml}")

    validator = OPCUAServerValidator()
    valid, actual, expected, diff = validator.validate(xml, config_file, config)
    if valid:
        print("The servers match! No significant differences found.")
    else:
        if output_file is None:
            print("The servers do not match! Printing diff...")
            validator.print_diff(actual, expected, diff, 0, verbose=verbose)
        else:
            print(f"The servers do not match! Writing diff to {output_file}...")
            # Clear output file. pylint: disable=consider-using-with
            open(output_file, "w", encoding="UTF-8").close()
            validator.print_diff(
                actual, expected, diff, 0, verbose=verbose, output_file=output_file
            )


if __name__ == "__main__":
    main()
