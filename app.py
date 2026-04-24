"""
PDF 압축기 – entry point (PyQt6).

Run:
    python app.py
"""

import sys


def main():
    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PDF 압축기")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
