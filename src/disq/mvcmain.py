"""DiSQ GUI main."""

import logging
import platform
import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from disq.controller import Controller
from disq.model import Model
from disq.sculib import configure_logging
from disq.view import MainView

logger = logging.getLogger("gui.main")


def main():
    """
    Entry point for the application.

    Configures logging, creates the application and necessary components, displays the
    main view, and starts the event loop.
    """
    configure_logging(default_log_level=logging.DEBUG)
    app = QApplication([])
    # Create our M, V and C...
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)

    # Connect the aboutToQuit signal to the model's disconnect method
    app.instance().aboutToQuit.connect(model.disconnect)

    # Catch unhandled exceptions
    def _exception_hook(exc_type, exc_value, exc_traceback):
        logger.error(
            "Unhandled exception caught with hook. Cleaning up and quitting..."
        )
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
