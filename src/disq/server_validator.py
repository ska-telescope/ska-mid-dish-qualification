import argparse
import os
import re
import sys
import xml.etree
import xml.etree.ElementTree as ET

import asyncua
import yaml

import asyncio
import multiprocessing as mp
import pprint
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

    def __init__(self):
        self.config = None
        self.xml = None
        self.sculib_like = {}
        self.missing = []
        self.extra = []
        self.plc_prg_string = "1:PLC_PRG"
        self.internal_server_started_barrier = mp.Barrier(2)

    def _get_browse_name_from_xml_element(self, element: ET.Element):
        browse_name = None
        if "BrowseName" in element.attrib:
            browse_name = element.attrib["BrowseName"]

        return browse_name

    def _get_element_from_node_string(self, node_string: str):
        for ele in self.xml.iter():
            if "NodeId" in ele.attrib:
                if ele.attrib["NodeId"] == node_string:
                    return ele

        return None

    def _get_children_from_xml_element_recursive(self, element: ET.Element, path):
        children_node_strings = []

        for ele in element.iter():
            if ele.tag == self.xmlns + "Reference":
                if "ReferenceType" in ele.attrib:
                    if ele.attrib["ReferenceType"] == "HasComponent":
                        if (
                            "IsForward" not in ele.attrib
                            or ele.attrib["IsForward"] == "true"
                        ):
                            children_node_strings.append(ele.text)

        children = {}
        for child_string in children_node_strings:
            child_ele = self._get_element_from_node_string(child_string)
            if child_ele is not None:
                name = self._get_browse_name_from_xml_element(child_ele)
                name_stripped = name.split(":")[1]
                children[child_ele] = {
                    "browse_name": name,
                    "children": self._get_children_from_xml_element_recursive(
                        child_ele, path + name_stripped + "."
                    ),
                }
                self.sculib_like[path + name_stripped] = None

        return children

    def _walk_xml_tree_missing_recursive(self, children, path):
        for child in children:
            name = path + children[child]["browse_name"].split(":")[1]
            self.missing.append(name)
            self._walk_xml_tree_missing_recursive(
                children[child]["children"], name + "."
            )

    def _check_sculib_against_xml_recursive(self, entry, path):
        name = path + entry["browse_name"].split(":")[1]
        if name in self.hll.nodes:
            for child in entry["children"]:
                self._check_sculib_against_xml_recursive(
                    entry["children"][child], name + "."
                )
        else:
            self.missing.append(name)
            self._walk_xml_tree_missing_recursive(entry["children"], name + ".")

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
            "object_type": node_class,
            # "method_params": None,
            # "method_return": None,
        }
        ancestors.append(name.Name)
        if node_class == 2:
            if short_name != "InputArguments" and short_name != "OutputArguments":
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
        # Use sculib for encryption and getting PLC_PRG node.
        self.server = sculib.scu(
            host=host, port=port, endpoint=endpoint, namespace=namespace
        )
        self.event_loop = self.server.event_loop
        # Fill tree dict for server
        server_tree = self._fill_tree_recursive(self.server.plc_prg, [])

        self.server.disconnect()
        return server_tree

    def validate(self, xml_file: str, server_config: str):
        print(f"Using xml file: {xml_file}, and config file: {server_config}")
        # First build tree of correct server
        internal_server_process = mp.Process(
            target=self._run_internal_server_wrap,
            args=[xml_file],
            name="Internal server process",
        )
        internal_server_process.start()
        self.internal_server_started_barrier.wait()
        correct_tree = self._scan_opcua_server(
            # "127.0.0.1", "57344", "/dish-structure/server/", "http://skao.int/DS_ICD/"
            "127.0.0.1",
            "4840",
            "/dish-structure/server/",
            "http://skao.int/DS_ICD/",
        )
        internal_server_process.terminate()

        pprint.pprint(correct_tree, sort_dicts=False)
        internal_server_process.join()
        return

        # Second build tree of dubious server
        # Third compare the two
        with open(server_config, "r") as f:
            try:
                self.config = yaml.safe_load(f.read())
            except Exception as e:
                print(e)
                sys.exit(
                    f"ERROR: Unable to parse server configuration file {server_config}."
                )

        print(self.config)
        self.xml = ET.parse(xml_file)
        root = self.xml.getroot()
        self.xmlns = re.split("(^.*})", root.tag)[1]
        plc_prg = None
        # Find the PLC_PRG node in the xml
        for element in root.iter():
            if "BrowseName" in element.attrib:
                if element.attrib["BrowseName"] == self.plc_prg_string:
                    plc_prg = element

        if plc_prg is None:
            sys.exit(f"ERROR: Could not find PLC_PRG node in input XML")

        # Recursively build input tree from xml
        # self.xml_tree = {
        #    plc_prg: {
        #        "browse_name": self._get_browse_name_from_xml_element(plc_prg),
        #        "children": self._get_children_from_xml_element_recursive(plc_prg, ""),
        #    }
        # }
        # sculib does not include plc_prg in nodes
        self.xml_tree = self._get_children_from_xml_element_recursive(plc_prg, "")
        self.sculib_like["PLC_PRG"] = None
        # extras for testing during development <
        """
        axis_select_type = None
        for element in root.iter():
            if "BrowseName" in element.attrib:
                if element.attrib["BrowseName"] == "1:AxisSelectType":
                    axis_select_type = element
        self.xml_tree.update(
            {
                root: {
                    "browse_name": "1:test1",
                    "children": {
                        root: {
                            "browse_name": "1:test2",
                            "children": {
                                axis_select_type: {
                                    "browse_name": "1:test3",
                                    "children": {},
                                }
                            },
                        }
                    },
                },
                axis_select_type: {
                    "browse_name": "1:axis1",
                    "children": {
                        root: {"browse_name": "1:axis1.1", "children": {}},
                        axis_select_type: {"browse_name": "1:axis1.2", "children": {}},
                    },
                },
            }
        )
        """
        # >
        # print(self.xml_tree)

        self.hll = sculib.scu(
            host=self.config["connection"]["address"],
            port=self.config["connection"]["port"],
            endpoint=self.config["connection"]["endpoint"],
            namespace=self.config["connection"]["namespace"],
        )
        # print(self.hll.nodes)
        # Find missing nodes
        for input_node in self.xml_tree:
            self._check_sculib_against_xml_recursive(self.xml_tree[input_node], "")

        print("OPCUA Server is missing the following nodes under the PLC_PRG node:")
        for node in self.missing:
            print(node)

        # Find extra nodes
        for node in self.hll.nodes:
            if node not in self.sculib_like:
                self.extra.append(node)

        print("OPCUA Server has the following extra nodes under the PLC_PRG node:")
        for node in self.extra:
            print(node)


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
