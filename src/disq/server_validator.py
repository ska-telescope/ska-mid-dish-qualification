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

import pickle


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

    def __init__(self):
        self.config = None
        self.xml = None
        self.sculib_like = {}
        self.missing = []
        self.extra = []
        self.plc_prg_string = "1:PLC_PRG"
        self.internal_server_started_barrier = mp.Barrier(2)
        self.fuzzy_threshold = 0.1
        self.short_print = False
        self.spaces_per_indent = 4

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
        for param in params:
            args[param.Name] = self._get_param_type_tuple(param.DataType)

        return args

    def _read_data_type_tuple(self, sculib_path: str) -> tuple:
        type = self.server.get_attribute_data_type(sculib_path)
        if type == "Enumeration":
            return (type, ",".join(self.server.get_enum_strings(sculib_path)))

        return (type,)

    def _fill_tree_recursive(self, node: asyncua.Node, ancestors: list[str]) -> dict:
        node_dict = {}
        # Fill node info
        name, node_class, node_children = self._get_node_info(node)
        short_name = name.Name
        ns_name = f"{name.NamespaceIndex}:{short_name}"
        node_dict[ns_name] = {
            "node_class": self.opcua_node_class_names[node_class],
        }
        ancestors.append(name.Name)
        if node_class == 2:
            if short_name == "InputArguments":
                node_dict[ns_name]["method_params"] = self._get_method_info(node)
            elif short_name == "OutputArguments":
                node_dict[ns_name]["method_return"] = self._get_method_info(node)
            else:
                sculib_ancestors = ancestors[1:]  # No "PLC_PRG" in sculib paths
                sculib_path = ".".join(sculib_ancestors)
                data_type = self._read_data_type_tuple(sculib_path)
                node_dict[ns_name]["data_type"] = data_type

        # Create hierarchical structure
        children = {}
        for child in node_children:
            children.update(self._fill_tree_recursive(child, ancestors[:]))

        node_dict[ns_name]["children"] = children

        return node_dict

    def _scan_opcua_server(
        self, host: str, port: str, endpoint: str, namespace: str
    ) -> dict:
        return {}
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
        for param, type in expected_args.items():
            if param not in actual_args:
                ret = False
                break

            if actual_args[param] != type:
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
                    print(sibling)
                    possible.append(sibling)

            possibles.append({expected: possible})

        print("possibles =", possibles)
        return possibles

    def _compare(self, actual: dict, expected: dict) -> dict:
        diff_tree = {}
        for node, node_info in expected.items():
            if node in actual:
                current_diff = {}
                node_children = {}
                if node == "0:InputArguments":
                    current_diff["params_match"] = self._args_match(
                        actual[node]["method_params"], node_info["method_params"]
                    )
                elif node == "0:OutputArguments":
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

    def _print_full_diff(self, actual: dict, expected: dict, diff: dict, level: int):
        indent = " " * self.spaces_per_indent * level
        for node, node_info in expected.items():
            print(f"{indent}{node}")
            if node == "0:InputArguments":
                if diff[node]["diff"]["params_match"]:
                    params_match = "Match"
                else:
                    expected_params = [
                        (name, type) for name, type in node_info["method_params"]
                    ]
                    actual_params = [
                        (name, type) for name, type in actual[node]["method_params"]
                    ]
                    params_match = (
                        f"Expected: {expected_params}, actual: {actual_params}"
                    )

                print(f"  {indent}method_params: {params_match}")
            elif node == "0:OutputArguments":
                if diff[node]["diff"]["return_match"]:
                    return_match = "Match"
                else:
                    expected_return = [
                        (name, type) for name, type in node_info["method_return"]
                    ]
                    actual_return = [
                        (name, type) for name, type in actual[node]["method_return"]
                    ]
                    return_match = (
                        f"Expected: {expected_return}, actual: {actual_return}"
                    )

                print(f"  {indent}method_return: {return_match}")
            else:
                if diff[node]["diff"]["class_match"]:
                    class_match = "Match"
                else:
                    class_match = f"Expected: {node_info['node_class']}, actual: {actual[node]['node_class']}"

                print(f"  {indent}node_class: {class_match}")
                if node_info["node_class"] == "Variable":
                    if diff[node]["diff"]["type_match"]:
                        type_match = "Match"
                    else:
                        type_match = f"Expected: {node_info['data_type']}, actual: {actual[node]['data_type']}"

                    print(f"  {indent}data_type: {type_match}")

                if diff[node]["diff"]["children_match"]:
                    children_match = "Match"
                else:
                    expected_children = [name for name in node_info["children"].keys()]
                    actual_children = [name for name in actual[node]["children"].keys()]
                    if len(diff[node]["diff"]["fuzzy"]) > 0:
                        fuzzy_children = [
                            fuzzy for fuzzy in diff[node]["diff"]["fuzzy"]
                        ]
                        children_match = f"Expected: {expected_children}, actual: {actual_children}. Possible matches: {fuzzy_children}"
                    else:
                        children_match = (
                            f"Expected: {expected_children}, actual: {actual_children}"
                        )

                print(f"  {indent}children: {children_match}")
                self._print_full_diff(
                    actual[node]["children"],
                    node_info["children"],
                    diff[node]["children"],
                    level + 1,
                )

    def validate(self, xml_file: str, server_config: str):
        print(f"Using xml file: {xml_file}, and config file: {server_config}")
        # First build tree of correct server
        internal_server_process = mp.Process(
            target=self._run_internal_server_wrap,
            args=[xml_file],
            name="Internal server process",
        )
        # internal_server_process.start()
        # self.internal_server_started_barrier.wait()
        correct_tree = self._scan_opcua_server(
            "127.0.0.1", "57344", "/dish-structure/server/", "http://skao.int/DS_ICD/"
        )
        # internal_server_process.terminate()
        # internal_server_process.join()

        # Second build tree of dubious server
        with open(server_config, "r") as f:
            try:
                config = yaml.safe_load(f.read())
            except Exception as e:
                print(e)
                sys.exit(
                    f"ERROR: Unable to parse server configuration file {server_config}."
                )

        dubious_tree = self._scan_opcua_server(
            config["connection"]["address"],
            config["connection"]["port"],
            config["connection"]["endpoint"],
            config["connection"]["namespace"],
        )
        # Third compare the two

        # with open("xml_4_tree.pkl", "wb") as f:
        # pickle.dump(correct_tree, f)
        # with open("xml_4_mock_tree.pkl", "wb") as f:
        # pickle.dump(dubious_tree, f)

        if dubious_tree == correct_tree:
            print("The servers match! No significant differences found.")
            # return

        with open("xml_4_tree.pkl", "rb") as f:
            correct_tree = pickle.load(f)
        with open("xml_4_mock_tree.pkl", "rb") as f:
            dubious_tree = pickle.load(f)

        # diff_tree = self._compare(dubious_tree, correct_tree)
        diff_tree = self._compare(correct_tree, dubious_tree)
        self.short_print = False
        if self.short_print:
            pprint.pprint(diff_tree, sort_dicts=False)
        else:
            self._print_full_diff(dubious_tree, correct_tree, diff_tree, 0)
        # delme_print(diff_tree, correct_tree, dubious_tree)


def delme_print(diff, cor, dub):
    print(">>>>>Diff<<<<<")
    pprint.pprint(diff, sort_dicts=False)
    print(">>>>>Correct<<<<<")
    pprint.pprint(cor, sort_dicts=False)
    print(">>>>>Dubious<<<<<")
    pprint.pprint(dub, sort_dicts=False)


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
    args = parser.parse_args()
    xml = args.xml[0]
    config = args.config[0]
    if not os.path.isfile(xml):
        sys.exit(f"ERROR: Could not find file {xml}")

    if not os.path.isfile(config):
        sys.exit(f"ERROR: Could not find file {config}")

    validator = Serval()
    validator.validate(xml, config)


if __name__ == "__main__":
    main()
