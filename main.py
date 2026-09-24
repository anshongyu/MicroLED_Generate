import sys

from PySide6.QtWidgets import QApplication

from microled_lightbox.ui.main_window import MainWindow


def main() -> int:
	app = QApplication(sys.argv)
	app.setApplicationName("MicroLED Lightbox Generator")
	window = MainWindow()
	window.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())

