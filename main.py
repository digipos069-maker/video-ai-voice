import sys
import os
import traceback

# Fix for DLL conflicts: Load torch before PyQt5
try:
    import torch
except ImportError:
    pass

# Fix for potential OpenMP/MKL conflicts on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from PyQt5.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow

def exception_hook(exctype, value, tb):
    """Global exception handler to log crashes."""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print("CRITICAL ERROR:", error_msg)
    with open("debug_log.txt", "a", encoding="utf-8") as f:
        f.write("\n--- CRASH REPORT ---\n")
        f.write(error_msg)
        f.write("\n--------------------\n")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
