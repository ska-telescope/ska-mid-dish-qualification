import asyncio
import asyncua
import typing


class treeViewer:
    node_tree = {}

    def __init__(self, server):
        self.server = "opc.tcp://" + server
        print("self.server =", self.server)
        self.client = asyncua.client.client.Client(url=self.server)

    async def _get_name_ns_id(self, node: asyncua.common.node.Node):
        """Return the display name and ns_id string of a node."""
        name = await node.read_display_name()
        node_ns_string = "ns=" + str(node.nodeid.NamespaceIndex)
        if isinstance(node.nodeid.Identifier, int):
            child_ns_id_string = node_ns_string + ";i=" + str(node.nodeid.Identifier)
        elif isinstance(node.nodeid.Identifier, str):
            child_ns_id_string = node_ns_string + ";s=" + node.nodeid.Identifier
        else:
            print(
                "ERROR: Id is not an int or string for ns",
                node.nodeid.NamespaceIndex,
                "id",
                node.nodeid.Identifier,
            )

        return (name.Text, child_ns_id_string)

    async def read_server(self, start_node: str = None):
        """Read the node tree for the server into self.node_tree starting from
        start_node or the server root node if start_node is None."""
        await self.client.connect()

        if start_node is not None:
            node = self.client.get_node(start_node)
        else:
            node = self.client.get_root_node()

        name, ns_id = await self._get_name_ns_id(node)
        self.node_tree[(name, ns_id)] = await self._node_children_recursive_search(
            ns_id
        )

        await self.client.disconnect()

    async def _node_children_recursive_search(self, node_id: str):
        """Recursively generate name-ns_id tuple to child nodes dictionaries."""
        node = self.client.get_node(node_id)
        children = await node.get_children()
        children_dict = {}

        for child in children:
            child_name, child_ns_id = await self._get_name_ns_id(child)
            children_dict[
                (child_name, child_ns_id)
            ] = await self._node_children_recursive_search(child_ns_id)

        return children_dict

    def generate_html(self, file_name: str):
        """Generate a HTML file called file_name with a collapsible structure from
        the node tree dict self.node_tree. Not very interesting unless read_server is
        run first."""
        with open(file_name, "w") as file:
            file.write(" <!DOCTYPE html>\n")
            file.write("<html>\n")
            file.write("<head>\n")
            file.write("<title>OPCUA Server Node Tree</title>\n")
            file.write("<style>\n")
            file.write("ul, #treeUL {\n")
            file.write("  list-style-type: none;\n")
            file.write("}\n")

            file.write("#treeUL {\n")
            file.write("  margin: 0;\n")
            file.write("  padding: 0;\n")
            file.write("}\n")

            file.write(".caret {\n")
            file.write("  cursor: pointer;\n")
            file.write("  -webkit-user-select: none; /* Safari 3.1+ */\n")
            file.write("  -moz-user-select: none; /* Firefox 2+ */\n")
            file.write("  -ms-user-select: none; /* IE 10+ */\n")
            file.write("  user-select: none;\n")
            file.write("}\n")

            file.write(".caret::before {\n")
            file.write('  content: "\\25B6";\n')
            file.write("  color: black;\n")
            file.write("  display: inline-block;\n")
            file.write("  margin-right: 6px;\n")
            file.write("}\n")

            file.write(".caret-down::before {\n")
            file.write("  -ms-transform: rotate(90deg); /* IE 9 */\n")
            file.write("  -webkit-transform: rotate(90deg); /* Safari */'\n")
            file.write("  transform: rotate(90deg);  \n")
            file.write("}\n")

            file.write(".nested {\n")
            file.write("  display: none;\n")
            file.write("}\n")

            file.write(".active {\n")
            file.write("  display: block;\n")
            file.write("}\n")
            file.write("</style>\n")
            file.write("</head>\n")
            file.write("<body>\n")

            file.write("<h1>OPCUA Server Node Tree for " + self.server + "</h1>\n")
            file.write(
                '<button type="button" onclick="expand_collapse_all()">Expand/Collapse All (only works properly if page was not interacted with since load)</button>\n'
            )
            file.write('<ul id="treeUL">\n')
            self._html_tree_recursive(self.node_tree, file)
            file.write("</ul>\n")

            file.write("<script>\n")
            file.write('var toggler = document.getElementsByClassName("caret");\n')
            file.write("var i;\n")

            file.write("for (i = 0; i < toggler.length; i++) {\n")
            file.write('  toggler[i].addEventListener("click", function() {\n')
            file.write(
                '    this.parentElement.querySelector(".nested").classList.toggle("active");\n'
            )
            file.write('    this.classList.toggle("caret-down");\n')
            file.write("  });\n")
            file.write("}\n")
            file.write("function expand_collapse_all() {\n")
            file.write('  var els = document.getElementsByClassName("caret");\n')
            file.write("  var i;\n")

            file.write("  for (i = 0; i < toggler.length; i++) {\n")
            file.write(
                '    toggler[i].parentElement.querySelector(".nested").classList.toggle("active");\n'
            )
            file.write('    toggler[i].classList.toggle("caret-down");\n')
            file.write("  }\n")
            file.write("}\n")
            file.write("</script>\n")

            file.write("</body>\n")
            file.write("</html> \n")

    def _html_tree_recursive(self, tree_dict: dict, file: typing.TextIO):
        """Recursively populate HTML treeUL."""
        for node, children in tree_dict.items():
            if children:
                file.write(
                    '<li><span class="caret">'
                    + node[0]
                    + ", ID: "
                    + str(node[1])
                    + "</span>\n"
                )
                file.write('<ul class="nested">\n')
                self._html_tree_recursive(children, file)
                file.write("</ul>\n")
                file.write("</li>\n")
            else:
                file.write("<li>" + node[0] + ", ID: " + str(node[1]) + "</li>\n")


if __name__ == "__main__":
    viewer = treeViewer(
        "0.0.0.0:4840" + "/OPCUA/SimpleServer"
    )  # "/OPCUA/SimpleServer" for the CETC (prosys) server
    # viewer = treeViewer("0.0.0.0:4840")
    asyncio.run(viewer.read_server("ns=0;i=23470"))
    viewer.generate_html("test_node_tree.html")
