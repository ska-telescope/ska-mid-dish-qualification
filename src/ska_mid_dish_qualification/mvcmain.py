import logging

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

from ska_mid_dish_qualification.controller import Controller
from ska_mid_dish_qualification.model import Model
from ska_mid_dish_qualification.sculib import configure_logging
from ska_mid_dish_qualification.view import MainView


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
