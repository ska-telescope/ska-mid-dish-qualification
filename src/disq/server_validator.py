import argparse
import os
import sys
import asyncua
import yaml
import asyncio
import multiprocessing as mp
import pprint
from difflib import SequenceMatcher
from disq import sculib
from disq.serval_internal_server import ServalInternalServer


class Serval:
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
        self.internal_server_started_barrier = mp.Barrier(2)
        self.fuzzy_threshold = 0.85
        self.include_namespace = False
        if include_namespace:
            self.in_args = "0:InputArguments"
            self.out_args = "0:OutputArguments"
        else:
            self.in_args = "InputArguments"
            self.out_args = "OutputArguments"

    async def _run_internal_server(self, xml_file: str):
        async with ServalInternalServer(xml_file):
            self.internal_server_started_barrier.wait()
            while True:
                await asyncio.sleep(1)

    def _run_internal_server_wrap(self, xml_file):
        asyncio.run(self._run_internal_server(xml_file))

    def _read_node_name(self, node: asyncua.Node) -> asyncua.ua.uatypes.QualifiedName:
        return asyncio.run_coroutine_threadsafe(
            node.read_browse_name(), self.event_loop
        ).result()

    def _get_node_info(self, node: asyncua.Node) -> tuple:
        name = self._read_node_name(node)
        node_class = asyncio.run_coroutine_threadsafe(
            node.read_node_class(), self.event_loop
        ).result()
        children = asyncio.run_coroutine_threadsafe(
            node.get_children(), self.event_loop
        ).result()

        return (name, node_class, children)

    def _get_param_type_tuple(self, node_id: asyncua.ua.uatypes.NodeId) -> tuple:
        param_type = self.server.get_attribute_data_type(node_id)
        if param_type == "Enumeration":
            return (param_type, ",".join(self.server.get_enum_strings(node_id)))

        return (param_type,)

    def _get_method_info(self, node: asyncua.Node) -> dict:
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
        try:
            data_type = self.server.get_attribute_data_type(sculib_path)
        except:
            return ("Node name error",)
        if data_type == "Enumeration":
            return (data_type, ",".join(self.server.get_enum_strings(sculib_path)))

        return (data_type,)

    def _fill_tree_recursive(self, node: asyncua.Node, ancestors: list[str]) -> dict:
        node_dict = {}
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

    def _scan_opcua_server(
        self, host: str, port: str, endpoint: str, namespace: str
    ) -> dict:
        # Use sculib for encryption and getting PLC_PRG node.
        self.server = sculib.scu(
            host=host, port=port, endpoint=endpoint, namespace=namespace
        )
        self.event_loop = self.server.event_loop
        # Fill tree dict for server
        server_tree = self._fill_tree_recursive(self.server.plc_prg, [])

        self.server.disconnect()
        return server_tree

    def _args_match(self, actual_args: dict, expected_args: dict) -> bool:
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
        diff_tree = {}
        for node, node_info in expected.items():
            if node in actual:
                current_diff = {}
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
                        except:
                            current_diff["type_match"] = False
                        else:
                            current_diff["type_match"] = (
                                actual[node]["data_type"] == node_info["data_type"]
                            )

                    # check num and name of children
                    to_fuzzy = []
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

    def _print_method_args_mismatch_string(
        self, indent: str, args_string: str, expected_info: dict, actual_info: dict
    ):
        alignment = " " * (len(args_string) + 4)
        expected_params = [
            (name, data_type) for name, data_type in expected_info[args_string].items()
        ]
        actual_params = [
            (name, data_type) for name, data_type in actual_info[args_string].items()
        ]
        print(
            f"""  {indent}{args_string}: Expected: {expected_params},
{alignment}{indent}  actual: {actual_params}"""
        )

    def print_diff(
        self,
        actual: dict,
        expected: dict,
        diff: dict,
        level: int,
        verbose: bool = False,
    ):
        indent = " " * len("  Children: ") * level
        for node, node_info in expected.items():
            if node in actual:
                print(f"{indent}>{node}")
                if node == self.in_args:
                    if diff[node]["diff"]["params_match"]:
                        if verbose:
                            print(f"  {indent}method_params: Match")
                    else:
                        self._print_method_args_mismatch_string(
                            indent, "method_params", node_info, actual[node]
                        )

                elif node == self.out_args:
                    if diff[node]["diff"]["return_match"]:
                        if verbose:
                            print(f"  {indent}method_return: Match")
                    else:
                        self._print_method_args_mismatch_string(
                            indent, "method_return", node_info, actual[node]
                        )

                else:
                    if diff[node]["diff"]["class_match"]:
                        if verbose:
                            print(f"  {indent}node_class: Match")
                    else:
                        print(
                            f"  {indent}node_class: Expected: {node_info['node_class']}, actual: {actual[node]['node_class']}"
                        )

                    if node_info["node_class"] == "Variable":
                        if diff[node]["diff"]["type_match"]:
                            if verbose:
                                print(f"  {indent}data_type: Match")
                        else:
                            try:
                                actual_type = actual[node]["data_type"]
                            except:
                                actual_type = "None"

                            print(
                                f"  {indent}data_type: Expected: {node_info['data_type']}, actual: {actual_type}"
                            )

                    if len(node_info["children"]) > 0:
                        if diff[node]["diff"]["children_match"]:
                            if verbose:
                                print(f"  {indent}children: Match")
                            else:
                                print(f"  {indent}children:")
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

                            print(f"  {indent}children: {children_match}")

                    self.print_diff(
                        actual[node]["children"],
                        node_info["children"],
                        diff[node]["children"],
                        level + 1,
                        verbose=verbose,
                    )

    def validate(self, xml_file: str, server_config: str) -> (bool, dict, dict, dict):
        print(f"Using xml file: {xml_file}, and config file: {server_config}")
        # First build tree of correct server
        internal_server_process = mp.Process(
            target=self._run_internal_server_wrap,
            args=[xml_file],
            name="Internal server process",
        )
        internal_server_process.start()
        self.internal_server_started_barrier.wait()
        expected_tree = self._scan_opcua_server(
            "127.0.0.1", "57344", "/dish-structure/server/", "http://skao.int/DS_ICD/"
        )
        internal_server_process.terminate()
        internal_server_process.join()

        # Second build tree of dubious server
        with open(server_config, "r") as f:
            try:
                config = yaml.safe_load(f.read())
            except Exception as e:
                print(e)
                sys.exit(
                    f"ERROR: Unable to parse server configuration file {server_config}."
                )

        actual_tree = self._scan_opcua_server(
            config["connection"]["address"],
            config["connection"]["port"],
            config["connection"]["endpoint"],
            config["connection"]["namespace"],
        )
        # Third compare the two

        diff_tree = self._compare(actual_tree, expected_tree)
        if actual_tree == expected_tree:
            return (True, actual_tree, expected_tree, diff_tree)

        return (False, actual_tree, expected_tree, diff_tree)


def main():
    parser = argparse.ArgumentParser(
        prog="Dish Structure Server Validator",
        description="Validates an OPCUA server against an XML.",
    )
    parser.add_argument(
        "-x",
        "--xml",
        help="XML file to validate against.",
        required=True,
        nargs=1,
        dest="xml",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="YAML file specifying OPCUA server configuration.",
        required=True,
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
    args = parser.parse_args()
    xml = args.xml[0]
    config = args.config[0]
    verbose = args.verbose
    if not os.path.isfile(xml):
        sys.exit(f"ERROR: Could not find file {xml}")

    if not os.path.isfile(config):
        sys.exit(f"ERROR: Could not find file {config}")

    validator = Serval()
    valid, actual, expected, diff = validator.validate(xml, config)
    if valid:
        print("The servers match! No significant differences found.")
    else:
        print("The servers do not match! Printing diff...")
        validator.print_diff(actual, expected, diff, 0, verbose=verbose)


if __name__ == "__main__":
    main()
