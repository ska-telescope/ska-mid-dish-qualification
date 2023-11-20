from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

from disq.controller import Controller
from disq.model import Model
from disq.view import MainView


def main():
    load_dotenv()
    app = QApplication([])
    # Create our M, V and C...
    model = Model()
    controller = Controller(model)
    main_view = MainView(model, controller)
    main_view.show()
    app.exec()


if __name__ == "__main__":
    main()
