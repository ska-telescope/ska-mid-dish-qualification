import asyncio
import logging
import pprint
import threading

import asyncua

from disq import configuration, sculib


def run_event_loop(
    event_loop: asyncio.AbstractEventLoop,
    thread_started_event: threading.Event,
) -> None:
    # The self.event_loop needs to be stored here. Otherwise asyncio
    # complains that it has the wrong type when scheduling a coroutine.
    # Sigh.
    """
    Run the event loop using the specified event loop and thread started event.

    :param event_loop: The asyncio event loop to run.
    :type event_loop: asyncio.AbstractEventLoop
    :param thread_started_event: The threading event signaling that the thread has
        started.
    :type thread_started_event: threading.Event
    """
    asyncio.set_event_loop(event_loop)
    thread_started_event.set()  # Signal that the event loop thread has started
    event_loop.run_forever()


def _create_and_start_asyncio_event_loop() -> None:
    """
    Create and start an asyncio event loop in a separate thread.

    This function creates a new asyncio event loop, starts it in a separate thread,
    and waits for the thread to start.
    """
    event_loop = asyncio.new_event_loop()
    thread_started_event = threading.Event()
    event_loop_thread = threading.Thread(
        target=run_event_loop,
        args=(event_loop, thread_started_event),
        name="asyncio event loop for sculib instance 2sandbox",
        daemon=True,
    )
    event_loop_thread.start()
    thread_started_event.wait(5.0)  # Wait for the event loop thread to start
    return event_loop


def main():
    tab_ob = sculib.TrackTable()
    tab_ob.store_from_csv(
        "/home/oskiv/ska-mid-dish-qualification/tests/resources/input_files/track_tables/spiral.csv"
    )
    # pprint.pprint(tab_ob.get_next_points(5, tai_offset=10))
    # pprint.pprint(tab_ob.get_next_points(10))
    # print(tab_ob.sent_index)
    port = 4840
    host = "10.165.3.41"
    endpoint = ""
    namespace = 2
    """
    host = "127.0.0.1"
    endpoint = "OPCUA/SimpleServer"
    namespace = "CETC54"
    """
    server_url = f"opc.tcp://{host}:{port}/{endpoint}"
    client = asyncua.Client(server_url)
    event_loop = _create_and_start_asyncio_event_loop()
    _ = asyncio.run_coroutine_threadsafe(client.connect(), event_loop).result()
    def_result = asyncio.run_coroutine_threadsafe(
        client.load_data_type_definitions(), event_loop
    ).result()
    # print("def_result: %s", def_result)
    """
    import inspect

    for name, obj in inspect.getmembers(asyncua.ua):
        if inspect.isclass(obj):
            print(obj)

    return
    """

    take_auth_node = client.get_node(
        nodeid="ns=2;s=Application.PLC_PRG.CommandArbiter.Commands.TakeAuth"
    )
    print("take_auth_node: ", take_auth_node)
    print("take_auth_node type: ", type(take_auth_node))
    call = take_auth_node.call_method
    call_args = asyncua.ua.UInt16(
        3
    )  # 1 = LMC, 2 = HHP, 3 = EGUI, 4 = Tester (sim only)
    auth_res = asyncio.run_coroutine_threadsafe(
        call(take_auth_node, call_args), event_loop
    ).result()
    """
            code, msg, vals = self.commands[Command.TAKE_AUTH.value](
                ua.UInt16(user_int)
            )
            if code == 10:  # CommandDone
                self._user = user_int
                self._session_id = ua.UInt16(vals[0])
                """
    print("auth_res:", auth_res)
    authority = auth_res[1]
    toffset_node = client.get_node(
        "ns=2;s=Application.PLC_PRG.Time_cds.Status.TAIoffset"
    )
    toffset_res = asyncio.run_coroutine_threadsafe(
        toffset_node.get_value(), event_loop
    ).result()
    print("toffset_res:", toffset_res)
    """
    times = [1, 2]
    tai_o = [time + 1000 + toffset_res for time in times]
    # tai = [asyncua.ua.Double(time) for time in tai_o]
    tai = asyncua.ua.ua_binary.pack_uatype_array(
        asyncua.ua.uatypes.VariantType(11), tai_o
    )
    azi_o = [45.0, 45.0]
    # azi = [asyncua.ua.Double(position) for position in azi_o]
    azi = asyncua.ua.ua_binary.pack_uatype_array(
        asyncua.ua.uatypes.VariantType(11), azi_o
    )
    ele_o = [45.0, 45.0]
    # ele = [asyncua.ua.Double(position) for position in ele_o]
    ele = asyncua.ua.ua_binary.pack_uatype_array(
        asyncua.ua.uatypes.VariantType(11), ele_o
    )
    """
    """
    load_children = asyncio.run_coroutine_threadsafe(
        load_node.get_children(), event_loop
    ).result()
    # print("load_children =", load_children)
    for child in load_children:
        child_name = asyncio.run_coroutine_threadsafe(
            child.read_browse_name(), event_loop
        ).result()
        # print("child_name:", child_name)

        find_type = asyncio.run_coroutine_threadsafe(
            child.read_value(),
            event_loop,
        ).result()
        # print("****************", find_type)
    """
    """
    print(">>>>>>>>>>>>>>>>", vars(asyncua.ua.uatypes.Variant()))
    # print(">>>>>>>>>>>>>>>>", asyncua.ua.uatypes.VariantType[11])
    print(">>>>>>>>>>>>>>>>", asyncua.ua.uatypes.VariantType["Double"])
    tai = asyncua.ua.uatypes.Variant(
        Value=tai_p,
        VariantType=asyncua.ua.uatypes.VariantType["Double"],
        Dimensions=[2],
    )
    azi = asyncua.ua.uatypes.Variant(
        Value=azi_p,
        VariantType=asyncua.ua.uatypes.VariantType["Double"],
        Dimensions=[2],
    )
    ele = asyncua.ua.uatypes.Variant(
        Value=ele_p,
        VariantType=asyncua.ua.uatypes.VariantType["Double"],
        Dimensions=[2],
    )
    """
    pt_end_node = client.get_node(
        "ns=2;s=Application.PLC_PRG.Tracking.TableStatus.act_pt_end_index"
    )
    pt_act_node = client.get_node(
        "ns=2;s=Application.PLC_PRG.Tracking.TableStatus.act_pt_act_index"
    )
    load_node = client.get_node(
        "ns=2;s=Application.PLC_PRG.Tracking.Commands.TrackLoadTable"
    )
    load_call = load_node.call_method
    result = 10
    num = 1
    mode = 1
    while result in (10, 9) and num > 0:
        num, tai, azi, ele = tab_ob.get_next_points(1000, toffset_res + 1000)
        print("num:", num)
        if num == 0:
            break
        print("First tai:", tai[0])
        if num < 1000:
            padding = [0] * (1000 - num)
            tai.extend(padding)
            azi.extend(padding)
            ele.extend(padding)

        print("Loading with mode:", mode)
        load_args = [
            asyncua.ua.UInt16(authority),
            asyncua.ua.UInt16(mode),  # 0 append, 1 new, 2 reset (TBD)
            asyncua.ua.UInt16(num),
            tai,
            azi,
            ele,
            # [asyncua.ua.Double(time) for time in tai],
            # [asyncua.ua.Double(deg) for deg in azi],
            # [asyncua.ua.Double(deg) for deg in ele],
        ]
        mode = 0
        load_res = asyncio.run_coroutine_threadsafe(
            load_call(load_node, *load_args), event_loop
        ).result()
        print("load_res =", load_res, "]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]")
        pt_end_res = asyncio.run_coroutine_threadsafe(
            pt_end_node.get_value(), event_loop
        ).result()
        pt_act_res = asyncio.run_coroutine_threadsafe(
            pt_act_node.get_value(), event_loop
        ).result()
        print(
            "act_pt_end_index - act_pt_act_index = number of points on PLC.",
            pt_end_res,
            "-",
            pt_act_res,
            "-1 =",
            abs(pt_end_res - pt_act_res) - 1,
        )
        result = load_res
    # 'Tracking.Commands.TrackLoadStaticOff',
    # 'Tracking.Commands.TrackLoadTable',
    # 'Tracking.Commands.TrackStart',
    # 'Tracking.Commands.TrackStartPoly'


if __name__ == "__main__":
    main()
