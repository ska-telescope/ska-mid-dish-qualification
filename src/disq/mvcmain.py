import logging

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

from disq.controller import Controller
from disq.model import Model
from disq.sculib import configure_logging
from disq.view import MainView


def main():
    load_dotenv()
    configure_logging(default_log_level=logging.DEBUG)
    app = QApplication([])
    # Create our M, V and C...
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)
    main_view.show()
    app.exec()


if __name__ == "__main__":
    main()
