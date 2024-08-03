import sys
from PyQt6.QtWidgets import QApplication
from app import App

def main():
    app = QApplication(sys.argv)
    window = DroneDetectionApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()