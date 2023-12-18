import argparse
import os
import sys
import yaml
import xml.etree.ElementTree as ET
import xml.etree
import asyncua
import re
from disq import sculib


class Serval:
    def __init__(self):
        self.config = None
        self.xml = None
        self.missing = []
        self.extra = []
        self.plc_prg_string = "1:PLC_PRG"

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

    def _get_children_from_xml_element_recursive(self, element: ET.Element):
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
                children[child_ele] = {
                    "browse_name": self._get_browse_name_from_xml_element(child_ele),
                    "children": self._get_children_from_xml_element_recursive(
                        child_ele
                    ),
                }

        return children

    def validate(self, xml_file: str, server_config: str):
        print(f"Using xml file: {xml_file}, and config file: {server_config}")
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
        #        "children": self._get_children_from_xml_element_recursive(plc_prg),
        #    }
        # }
        # sculib does not include plc_prg in nodes
        self.xml_tree = self._get_children_from_xml_element_recursive(plc_prg)
        # extras for development
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
        # print(self.xml_tree)

        self.hll = sculib.scu(
            host=self.config["connection"]["address"],
            port=self.config["connection"]["port"],
            endpoint=self.config["connection"]["endpoint"],
            namespace=self.config["connection"]["namespace"],
        )
        # print(self.hll.nodes)
        for input_node in self.xml_tree:
            self._check_sculib_against_xml_recursive(self.xml_tree[input_node], "")

        print("OPCUA Server is missing the following nodes:")
        for node in self.missing:
            print(node)

    def _check_sculib_against_xml_recursive(self, entry, path):
        name = path + entry["browse_name"].split(":")[1]
        if name in self.hll.nodes:
            print(f"found node for {name}")
            for child in entry["children"]:
                self._check_sculib_against_xml_recursive(
                    entry["children"][child], name + "."
                )
        else:
            self.missing.append(name)
            self._walk_xml_tree_missing_recursive(entry["children"], name + ".")

    def _walk_xml_tree_missing_recursive(self, children, path):
        for child in children:
            name = path + children[child]["browse_name"].split(":")[1]
            self.missing.append(name)
            self._walk_xml_tree_missing_recursive(
                children[child]["children"], name + "."
            )


if __name__ == "__main__":
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
