"""Internal server for the OPC UA server validator system."""

from asyncua import Server
from asyncua.common.node import Node


class SerValInternalServer:
    """
    A class representing an internal server for the OPC UA server validator system.

    :param xml: The XML configuration file for the internal server.
    :type xml: str
    """

    def __init__(self, xml: str):
        """
        Initialize the class with XML data and set the OPC-UA server details.

        :param xml: The XML data to be used.
        :type xml: str
        """
        self.xml = xml
        self.server = Server()
        self.server.set_endpoint("opc.tcp://0.0.0.0:57344/dish-structure/server/")
        self.server.set_server_name("OPCUAServerValidator internal server")
        self.namespace_to_use = "http://skao.int/DS_ICD/"
        self.idx: int
        self.plc_prg: Node

    async def init(self):
        """
        Initialize the object.

        This method will initialize the server, import XML data, get the namespace
        index, and set the PLC program node.
        """
        await self.server.init()
        await self.server.import_xml(self.xml)
        self.idx = await self.server.get_namespace_index(uri=self.namespace_to_use)
        self.plc_prg = await self.server.nodes.root.get_child(
            [
                "0:Objects",
                f"{self.idx}:Logic",
                f"{self.idx}:Application",
                f"{self.idx}:PLC_PRG",
            ]
        )

    async def __aenter__(self):
        """
        Asynchronously enter a context manager.

        This method initializes the instance and starts the server asynchronously.

        :return: The server instance.
        :rtype: Server
        :raises: Any exceptions that occur during initialization or server start.
        """
        await self.init()
        await self.server.start()
        return self.server

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the asynchronous context manager.

        :param exc_type: The type of the exception raised, if any.
        :param exc_val: The exception value raised, if any.
        :param exc_tb: The traceback of the exception raised, if any.
        """
        await self.server.stop()


async def main(xml: str):
    """
    Asynchronous function to run a SerValInternalServer.

    :param xml: XML configuration for the server.
    :type xml: str
    """
    async with SerValInternalServer(xml):
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    import asyncio

    XML = "tests/ds_icd_0.0.4.xml"
    import os
    import sys

    if not os.path.isfile(XML):
        sys.exit(f"ERROR: Could not find file {XML}")

    asyncio.run(main(XML))
