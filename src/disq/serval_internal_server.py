from asyncua import Server


class ServalInternalServer:
    def __init__(self, xml):
        self.xml = xml
        self.server = Server()
        self.server.set_endpoint("opc.tcp://0.0.0.0:57344/dish-structure/server/")
        self.server.set_server_name("Serval internal OPC-UA server")
        self.namespace_to_use = "http://skao.int/DS_ICD/"

    async def init(self):
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
        await self.init()
        await self.server.start()
        return self.server

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.server.stop()


async def main(xml):
    async with ServalInternalServer(xml):
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    import asyncio

    xml = "tests/ds_icd_0.0.4.xml"
    import os
    import sys

    if not os.path.isfile(xml):
        sys.exit(f"ERROR: Could not find file {xml}")

    asyncio.run(main(xml))
