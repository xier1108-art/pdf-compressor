"""
PDF 압축기 – entry point.

Run:
    python app.py

Or double-click run.bat
"""

import sys


def main():
    # Try to use tkinterdnd2 for drag-and-drop support
    has_dnd = False
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        has_dnd = True
    except Exception:
        import tkinter as tk
        root = tk.Tk()

    from ui.main_window import MainWindow
    MainWindow(root, has_dnd=has_dnd)
    root.mainloop()


if __name__ == "__main__":
    main()
