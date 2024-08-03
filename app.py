import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QSlider,
    QWidget,
    QPushButton,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QSoundEffect
from hackrf import *
from scipy.signal import welch

# Constants for signal analysis
FREQUENCY = 2.4e9  # 2.4 GHz for common drone frequency
SAMPLE_RATE = 10e6  # 10 MHz
BUFFER_SIZE = 8192  # Buffer size for HackRF data
THRESHOLD_POWER = -50  # Power threshold for drone detection in dB
SWEEP_REFRESH_RATE = 30  # Refresh rate in Hz

# Define frequency range for sliders
FREQ_MIN = 1e9  # Minimum frequency in Hz (1 GHz)
FREQ_MAX = 10e9  # Maximum frequency in Hz (10 GHz)
FREQ_SCALE = (FREQ_MAX - FREQ_MIN) / 1000  # Slider range scaling

hrf = HackRF()

class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Drone Detection System")
        self.setGeometry(100, 100, 800, 600)

        # PyQtGraph setup for real-time spectrum visualization
        self.graph_widget = pg.PlotWidget()
        self.graph_widget.setBackground("black")
        self.graph_widget.setYRange(-120, 0)
        self.graph_widget.setLabel("left", "Amplitude", units="dB")
        self.graph_widget.setLabel("bottom", "Frequency", units="Hz")
        self.spectrum_line = self.graph_widget.plot(
            [], [], pen=pg.mkPen("w", width=2)
        )

        # Frequency Range Sliders
        self.freq_min_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.freq_max_slider = QSlider(Qt.Orientation.Horizontal, self)

        self.freq_min = FREQUENCY
        self.freq_max = FREQ_MAX

        self.freq_min_slider.setMinimum(0)
        self.freq_min_slider.setMaximum(1000)  # Slider range
        self.freq_min_slider.setValue(int((FREQUENCY - FREQ_MIN) / FREQ_SCALE))  # Default min frequency 1 GHz below center
        self.freq_min_slider.valueChanged.connect(self.on_freq_min_change)

        self.freq_max_slider.setMinimum(0)
        self.freq_max_slider.setMaximum(1000)  # Slider range
        self.freq_max_slider.setValue(int((FREQUENCY + 1e9 - FREQ_MIN) / FREQ_SCALE))  # Default max frequency 1 GHz above center
        self.freq_max_slider.valueChanged.connect(self.on_freq_max_change)

        # Power Level Slider
        self.slider_label = QLabel("Power Level Threshold: 0 dB", self)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setMinimum(-120)
        self.slider.setMaximum(0)
        self.slider.setValue(THRESHOLD_POWER)
        self.slider.valueChanged.connect(self.on_slider_change)

        # Drone Status Label
        self.drone_status_label = QLabel("Drone Status: Not Detected", self)
        self.drone_status_label.setStyleSheet("color: green; font-size: 30pt")

        # Manual Check Button
        self.alert_button = QPushButton("Check for Drone", self)
        self.alert_button.clicked.connect(self.check_for_drone)

        # Sound Alert for Drone Detection
        self.sound_alert = QSoundEffect()
        self.sound_alert.setSource(QUrl.fromLocalFile("alert.wav"))
        self.sound_alert.setVolume(0.3)

        # HackRF Device Initialization
        self.hackrf = hrf
        self.hackrf.sample_rate = SAMPLE_RATE
        self.hackrf.center_freq = FREQUENCY
        self.hackrf.lna_gain = 40  # Low Noise Amplifier gain
        self.hackrf.vga_gain = 20  # Variable Gain Amplifier gain

        # Timer for Real-Time Updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_spectrum)
        self.timer.start(int(1000 / SWEEP_REFRESH_RATE))  # Update interval in ms

        # Logo Setup
        self.logo_label = QLabel(self)
        self.logo_pixmap = QPixmap("assets/logo.png")  # Update this with the path to your logo
        self.logo_pixmap = self.logo_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio)  # Resize the logo
        self.logo_label.setPixmap(self.logo_pixmap)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title Setup
        self.title_label = QLabel("Yiur Title", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 24pt; font-weight: bold; color: white;")

        # Layout Setup
        layout = QVBoxLayout()
        layout.addWidget(self.logo_label)  # Add logo to the layout
        layout.addWidget(self.title_label)  # Add title below the logo
        layout.addWidget(QLabel("Frequency Min (GHz):"))
        layout.addWidget(self.freq_min_slider)
        layout.addWidget(QLabel("Frequency Max (GHz):"))
        layout.addWidget(self.freq_max_slider)
        layout.addWidget(self.slider_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.graph_widget)
        layout.addWidget(self.drone_status_label)
        layout.addWidget(self.alert_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def check_bandwidth(self):
        """Check the bandwidth of the signal and determine if a drone is detected."""
        power_level = self.slider.value()
        max_power = self.analyze_signal()

        if max_power > power_level:
            self.drone_detected()
        else:
            self.drone_not_detected()

    def drone_detected(self):
        """Handle drone detection."""
        self.drone_status_label.setText("Drone Status: Detected!")
        self.drone_status_label.setStyleSheet("color: blue; font-size:30pt;")
        if not self.sound_alert.isPlaying():
            self.sound_alert.play()  # Play the alert sound if not already playing

    def drone_not_detected(self):
        """Handle the case when no drone is detected."""
        self.drone_status_label.setText("Drone Status: Not Detected")
        self.drone_status_label.setStyleSheet("color: green; font-size:30pt;")
        # Stop the alert sound if it is playing
        if self.sound_alert.isPlaying():
            self.sound_alert.stop()

    def on_freq_min_change(self, value):
        """Handle frequency min slider value change."""
        min_freq = FREQ_MIN + value * FREQ_SCALE
        # Update your frequency range based on min_freq
        self.hackrf.center_freq = (self.hackrf.center_freq + min_freq) / 2

    def on_freq_max_change(self, value):
        """Handle frequency max slider value change."""
        max_freq = FREQ_MIN + value * FREQ_SCALE
        # Update your frequency range based on max_freq
        self.hackrf.center_freq = (self.hackrf.center_freq + max_freq) / 2

    def on_slider_change(self, value):
        """Handle slider value change."""
        self.slider_label.setText(f"Power Level Threshold: {value} dB")
        self.check_bandwidth()

    def check_for_drone(self):
        """Manually check for a drone."""
        self.check_bandwidth()

    def update_spectrum(self):
        """Update the spectrum plot with real-time data."""
        samples = self.hackrf.read_samples(BUFFER_SIZE)
        if samples is not None:
            freqs, power = self.compute_spectrum(samples)
            self.spectrum_line.setData(freqs, power)
            self.check_bandwidth()

    def compute_spectrum(self, samples):
        """Compute the frequency spectrum of the signal."""
        if np.iscomplexobj(samples):
            # Compute power spectrum for real and imaginary parts separately
            freqs, power_real = welch(
                np.real(samples), SAMPLE_RATE, nperseg=BUFFER_SIZE, scaling="spectrum"
            )
            _, power_imag = welch(
                np.imag(samples), SAMPLE_RATE, nperseg=BUFFER_SIZE, scaling="spectrum"
            )
            power = power_real + power_imag  # Combine power
            power = 10 * np.log10(power / 2)  # Convert to dB
        else:
            freqs, power = welch(
                samples, SAMPLE_RATE, nperseg=BUFFER_SIZE, scaling="spectrum"
            )
            power = 10 * np.log10(power)  # Convert to dB

        # Only keep positive frequencies
        positive_freqs = freqs[freqs >= 0]
        positive_power = power[freqs >= 0]
        
        return positive_freqs, positive_power

    def analyze_signal(self):
        """Analyze the signal to determine the max power level."""
        samples = self.hackrf.read_samples(BUFFER_SIZE)
        if samples is not None:
            _, power = self.compute_spectrum(samples)
            max_power = np.max(power)
            return max_power
        return -np.inf

    def closeEvent(self, event):
        """Clean up HackRF device on close."""
        self.hackrf.close()
        event.accept()