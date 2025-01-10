import os
import sys
from pynput.mouse import Listener as MouseListener
from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget, QListWidget, QLabel, QListWidgetItem, QSplitter
from PyQt6.QtWidgets import QMenu, QPushButton, QHBoxLayout, QDialog, QMessageBox
from PyQt6.QtCore import Qt, QSize, QPoint, QEvent, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction, QCursor
from datetime import datetime
import pyscreenshot as ImageGrab
from PIL import Image, ImageDraw, ImageOps
import wave
import pyaudiowpatch as pyaudio
from pathlib import Path
from UIAuto import get_element_under_cursor

APP_PATH = os.getcwd()
SHOT_PATH = os.path.join(APP_PATH, "shots")
AUDIO_PATH = os.path.join(APP_PATH, "audio")
if not os.path.exists(SHOT_PATH):
    os.makedirs(SHOT_PATH)
if not os.path.exists(AUDIO_PATH):
    os.makedirs(AUDIO_PATH)
CURSOR_ICON_PATH = os.path.join(APP_PATH, "cursor.png")
MIC_USABLE = False

MIC_RATE = 16000
MIC_CHANNELS = 1
MIC_DEVICE_INDEX = 2

def detect_mic():
    global MIC_RATE, MIC_CHANNELS, MIC_DEVICE_INDEX, MIC_USABLE
    try:
        p = pyaudio.PyAudio()
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_microphone = p.get_device_info_by_index(wasapi_info["defaultInputDevice"])    
        print(f"Recording microphone audio from: ({default_microphone['index']}) {default_microphone['name']}")
        print(f"==========Channels, Rate===: ({default_microphone['maxInputChannels']}) {default_microphone['defaultSampleRate']}")
        MIC_RATE = int(default_microphone["defaultSampleRate"])
        MIC_CHANNELS = default_microphone["maxInputChannels"]
        MIC_DEVICE_INDEX = default_microphone["index"]
        MIC_USABLE = True
    except OSError:
        print("No Audio Device.")

class AudioRecorder(QThread):
    recording_done = pyqtSignal(str)  # Signal to notify when recording is complete

    def __init__(self, mic_rate=MIC_RATE, mic_channels=MIC_CHANNELS, mic_device_index=MIC_DEVICE_INDEX, audio_name = None, parent=None):
        super().__init__(parent)
        self.mic_rate = mic_rate
        self.mic_channels = mic_channels
        self.mic_device_index = mic_device_index
        self.is_recording = False
        self.audio_name = audio_name  # Pass the path from outside

    def run(self):
        """Start recording audio."""
        self.is_recording = True
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=self.mic_channels,
            rate=self.mic_rate,
            input=True,
            input_device_index=self.mic_device_index,
            frames_per_buffer=1024,
        )

        frames = []
        while self.is_recording:
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)

        # Stop and save the recording
        stream.stop_stream()
        stream.close()
        audio.terminate()

        # Save to a WAV file
        if self.audio_name is None:
            self.audio_name = datetime.now().strftime('%Y%m%d%H%M%S')
        audio_path = os.path.join(AUDIO_PATH, f"{self.audio_name}.wav")
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(self.mic_channels)
            wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.mic_rate)
            wf.writeframes(b''.join(frames))

        # Emit the signal with the file path
        self.recording_done.emit(audio_path)

    def stop(self):
        """Stop recording audio."""
        self.is_recording = False

class GlobalMouseListener(QThread):
    mouse_clicked = pyqtSignal(int, int)
    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        with MouseListener(on_click=self.on_click) as listener:
            while self.running:
                pass
            listener.stop()

    def on_click(self, x, y, button, pressed):
        if pressed:  # When mouse button is pressed
            self.mouse_clicked.emit(x, y)

    def stop(self):
        """Stop the listener."""
        self.running = False

class ScreenshotWorker(QThread):
    screenshot_done = pyqtSignal(str)  # Signal to notify when screenshot is complete

    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.mouse_pos_x = x
        self.mouse_pos_y = y

    def run(self):
        """Take a screenshot and print the mouse position."""
        # screen = QApplication.primaryScreen()
        # screenshot = screen.grabWindow(0)  # Capture the entire screen

        # Take screenshot of the entire screen using pyscreenshot
        print(datetime.now().strftime('%Y%m%d%H%M%S'))
        screenshot = ImageGrab.grab()  # Capture the entire screen
        cursor_icon = Image.open(CURSOR_ICON_PATH).convert("RGBA")

        # Resize the cursor icon if needed
        cursor_icon_size = 90  # Desired cursor size
        cursor_icon = cursor_icon.resize((cursor_icon_size, cursor_icon_size), Image.Resampling.LANCZOS)
        screenshot.paste(cursor_icon, (self.mouse_pos_x, self.mouse_pos_y), cursor_icon)

        screenshot_path = os.path.join(SHOT_PATH, f"{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        screenshot.save(screenshot_path, "PNG")  # Save the screenshot
        print(datetime.now().strftime('%Y%m%d%H%M%S'))

        # Emit the signal with the screenshot path
        self.screenshot_done.emit(screenshot_path)

class LoadingScreen(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loading")
        self.setFixedSize(200, 100)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        # Center the dialog
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Add a label
        layout = QVBoxLayout(self)
        self.label = QLabel("Processing...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        # Optional: Add a progress bar or spinner here

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_name = ""
        self.initUI()

    def initUI(self):
        # Initialize and configure UI elements
        self.setWindowTitle("VisualDoc")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon('icon.png'))
        
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.image_list = QListWidget()
        self.image_list.setViewMode(QListWidget.ViewMode.IconMode)
        # self.image_list.setIconSize(QPixmap(100, 100).size())  # Thumbnail size
        self.image_list.setSpacing(10)
        self.image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.image_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_list.resizeEvent = self.adjust_thumbnail_sizes
        self.image_list.customContextMenuRequested.connect(self.show_context_menu)
        self.image_list.itemClicked.connect(self.display_image)

        # Top-right: Image display area
        self.image_preview = QLabel("No Image Selected")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px solid black; background-color: white;")
        self.image_preview.resizeEvent = self.update_preview_image

        self.image_thumbnails = []
        self.current_image = None
        self.load_images(SHOT_PATH)

        # Add widgets to top splitter
        top_splitter.addWidget(self.image_list)
        top_splitter.addWidget(self.image_preview)
        top_splitter.setSizes([200, 600])

        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.toggle_mouse_listener)
        self.btn_record = QPushButton("Record")
        self.btn_record.clicked.connect(self.toggle_record_listener)

        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.btn_start)
        bottom_layout.addWidget(self.btn_record)
        bottom_widget.setLayout(bottom_layout)

        # Add top splitter and bottom widget to main splitter
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([400, 50])  # Initial sizes

        # Set central widget
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(main_splitter)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Install global event filter
        # self.installEventFilter(self)

        self.listener = None
        self.loading_screen = None
        self.audio_recorder = None

    def toggle_mouse_listener(self):
        """Start or stop the global mouse listener based on button state."""
        if self.btn_start.text() == "Start":
            # Start the listener
            self.listener = GlobalMouseListener()
            self.listener.mouse_clicked.connect(self.take_screenshot)
            self.listener.start()
            self.btn_start.setText("End")
        else:
            # Stop the listener
            if self.listener:
                self.listener.stop()
                self.listener.quit()
                self.listener.wait()
                self.listener = None
            self.btn_start.setText("Start")

    def toggle_record_listener(self):
        """Start or stop the global mouse listener based on button state."""
        global MIC_USABLE
        if self.btn_record.text() == "Record":
            if not MIC_USABLE:
                mic_alert = QMessageBox.information(
                    self,
                    "Information",
                    "No input devices found.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
                return
            if self.selected_name == "":
                select_shot_alert = QMessageBox.information(
                    self,
                    "Information",
                    "Select screenshot.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
                return

            # Start the listener
            if not self.audio_recorder:
                self.audio_recorder = AudioRecorder()
                self.audio_recorder.recording_done.connect(self.on_audio_recording_done)
            self.audio_recorder.audio_name = self.selected_name
            self.audio_recorder.start()
            print("Audio recording started.")
            self.btn_record.setText("Stop")
        else:
            # Stop the listener
            if self.audio_recorder and self.audio_recorder.is_recording:
                self.audio_recorder.stop()
                self.audio_recorder.wait()
                print("Audio recording stopped.")
            self.btn_record.setText("Record")

    def on_audio_recording_done(self, audio_path):
        """Handle post-recording actions."""
        print(f"Audio recording saved at: {audio_path}")
        self.audio_recorder = None

    def load_images(self, folder_path):
        """Load image thumbnails into the list widget."""
        supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')  # Supported image formats
        if not os.path.exists(folder_path):
            print(f"Error: Folder {folder_path} does not exist.")
            return

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(supported_formats):
                file_path = os.path.join(folder_path, filename)
                pixmap = QPixmap(file_path)
                self.image_thumbnails.append((filename, pixmap))  # Store original pixmap for resizing

        # Initial load
        self.adjust_thumbnail_sizes()

    def adjust_thumbnail_sizes(self, event=None):
        """Adjust thumbnail sizes dynamically to fit one image per row with filename below."""
        if self.image_list.width() == 0 or len(self.image_thumbnails) == 0:
            return

        list_width = self.image_list.width()
        image_height = list_width // 2  # Image height proportional to list width
        text_height = 30  # Fixed height for the filename
        thumbnail_size = QSize(list_width - 20, image_height)

        self.image_list.clear()  # Clear current items
        for filename, pixmap in self.image_thumbnails:
            resized_pixmap = pixmap.scaled(thumbnail_size, Qt.AspectRatioMode.KeepAspectRatio)
            icon = QIcon(resized_pixmap)
            item = QListWidgetItem(icon, filename)
            item.setSizeHint(QSize(list_width, image_height + text_height))  # Space for image and text
            self.image_list.addItem(item)

        self.image_list.setIconSize(thumbnail_size)
        self.image_list.setGridSize(QSize(list_width, image_height + text_height + 10))

    def show_context_menu(self, position: QPoint):
        """Display a context menu when right-clicking on an item."""
        item = self.image_list.itemAt(position)
        if item is not None:
            context_menu = QMenu(self)
            delete_action = QAction("Delete", self)

            # Connect actions
            delete_action.triggered.connect(lambda: self.delete_image(item))

            context_menu.addAction(delete_action)
            context_menu.exec(self.image_list.mapToGlobal(position))

    def delete_image(self, item: QListWidgetItem):
        """Delete the selected image from the list."""
        self.image_list.takeItem(self.image_list.row(item))
        item_path = os.path.join(SHOT_PATH, item.text())
        if os.path.exists(item_path):
            os.remove(item_path)
        print(f"Deleted image: {item.text()}")

    def display_image(self, item: QListWidgetItem):
        """Display the selected image in the preview area."""
        filename = item.text()
        self.selected_name = Path(filename).stem
        for file, pixmap in self.image_thumbnails:
            if file == filename:
                self.current_image = pixmap
                self.update_preview_image()  # Update preview immediately
                break

    def update_preview_image(self, event=None):
        """Update the image preview based on the available width of the image_preview widget."""
        if self.current_image:
            preview_width = self.image_preview.width()
            # Resize the image to fit the width while maintaining aspect ratio
            resized_pixmap = self.current_image.scaled(
                preview_width, int(preview_width * self.current_image.height() / self.current_image.width()),
                Qt.AspectRatioMode.KeepAspectRatio
            )
            self.image_preview.setPixmap(resized_pixmap)

    # def eventFilter(self, obj, event):
    #     """Override eventFilter to capture global mouse click events."""
    #     if event.type() == QEvent.Type.MouseButtonPress:
    #         if event.button() == Qt.MouseButton.LeftButton:  # If left mouse button is clicked
    #             self.take_screenshot(event.globalPosition())
    #     return super().eventFilter(obj, event)

    def take_screenshot(self, mouse_pos_x, mouse_pos_y):
        """Handle the screenshot logic in a separate thread."""
        if self.isActiveWindow():
            print("Main window is focused, ignoring the click.")
            return

        self.loading_screen = LoadingScreen()
        self.loading_screen.show()

        # element_info = get_element_under_cursor()
        # if element_info:
        #     print(f"Clicked Element: {element_info}")

        self.screenshot_worker = ScreenshotWorker(mouse_pos_x, mouse_pos_y)
        self.screenshot_worker.screenshot_done.connect(self.on_screenshot_done)
        self.screenshot_worker.start()

    def on_screenshot_done(self, screenshot_path):
        """Handle post-screenshot actions."""
        print(f"Screenshot saved at: {screenshot_path}")
        if self.loading_screen:
            self.loading_screen.close()
        self.load_images(SHOT_PATH)  # Reload the image list from the screenshot folder

if __name__ == "__main__":
    app = QApplication(sys.argv)
    detect_mic()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())