"""DiSQ GUI main."""

import argparse
import logging
import platform
import signal
import sys
from types import TracebackType
from typing import Type

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QMainWindow

from ska_mid_disq import __version__
from ska_mid_disq.constants import XML_UI_PATH
from ska_mid_disq.model import Model
from ska_mid_disq.utils.configuration import configure_logging
from ska_mid_disq.view import Controller, LimitedDisplaySpinBox, MainView, ToggleSwitch

logger = logging.getLogger("gui.main")


def main():
    """
    Entry point for the application.

    Configures logging, creates the application and necessary components, displays the
    main view, and starts the event loop.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", help="Server from config file to connect to.")
    parser.add_argument(
        "-c",
        "--cache",
        action="store_true",
        help="Include this flag to use the node cache.",
    )
    args = parser.parse_args()
    configure_logging(default_log_level=logging.DEBUG)

    # Set the required attributes before creating the application instance
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication([])

    # Load the UI from the XML .ui file
    loader = QUiLoader()
    loader.registerCustomWidget(LimitedDisplaySpinBox)
    loader.registerCustomWidget(ToggleSwitch)
    main_window: QMainWindow = loader.load(XML_UI_PATH)  # type: ignore

    # Create our M, V and C...
    model = Model()
    controller = Controller(model)
    main_view = MainView(
        main_window, model, controller, server=args.server, cache=args.cache
    )

    # Connect the aboutToQuit signal to the model's disconnect method
    app.instance().aboutToQuit.connect(model.disconnect_server)

    # Catch unhandled exceptions
    def _exception_hook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        logger.exception(
            "Unhandled %s exception caught with hook:",
            exc_type.__qualname__,
        )
        app.aboutToQuit.disconnect()  # Disconnect the signal to prevent recursion
        app.quit()
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _exception_hook

    # Signal handling
    def _signal_handler(signum, frame):  # pylint: disable=unused-argument
        logger.info(
            "Signal '%s' received from OS. Cleaning up and exiting...",
            signal.Signals(signum).name,
        )
        app.quit()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTSTP, _signal_handler)  # Not supported by Windows
        signal.signal(signal.SIGQUIT, _signal_handler)  # Not supported by Windows

    # Let the python interpreter run periodically to catch Unix signals
    timer = QTimer()
    timer.start(1000)
    timer.timeout.connect(lambda: None)

    main_view.show()
    logger.info(f"Successfully initialised DiSQ GUI v{__version__}")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
