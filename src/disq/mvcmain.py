import asyncio
from dotenv import load_dotenv
import functools
import qasync
from qasync import QApplication
import sys

from disq.view import MainView
from disq.model import Model
from disq.controller import Controller


async def async_main():
    def close_future(future, loop):
        print("close_future")
        loop.call_later(10, future.cancel)
        future.cancel()

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    future = asyncio.Future()

    load_dotenv()

    app = QApplication.instance()
    if hasattr(app, "aboutToQuit"):
        getattr(app, "aboutToQuit").connect(
            functools.partial(close_future, future, loop)
        )

    # Create our M, V and C...
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)
    main_view.show()

    try:
        await future
    except asyncio.exceptions.CancelledError:
        print("Quitting")

    return True


if __name__ == "__main__":
    qasync.run(async_main())
