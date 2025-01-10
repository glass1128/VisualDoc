import os
import sys
from pynput.mouse import Listener as MouseListener
from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget, QListWidget, QLabel, QListWidgetItem, QSplitter
from PyQt6.QtWidgets import QMenu, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QSize, QPoint, QEvent, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction, QCursor
from datetime import datetime
import pyscreenshot as ImageGrab

app_path = os.getcwd()
shot_path = os.path.join(app_path, "shots")
if not os.path.exists(shot_path):
    os.makedirs(shot_path)

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Initialize and configure UI elements
        self.setWindowTitle("VisualDoc")
        self.setGeometry(100, 100, 800, 600)
        
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
        self.load_images(shot_path)

        # Add widgets to top splitter
        top_splitter.addWidget(self.image_list)
        top_splitter.addWidget(self.image_preview)
        top_splitter.setSizes([200, 600])

        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.toggle_mouse_listener)

        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.btn_start)
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
            open_action = QAction("Open", self)
            delete_action = QAction("Delete", self)

            # Connect actions
            open_action.triggered.connect(lambda: self.open_image(item.text()))
            delete_action.triggered.connect(lambda: self.delete_image(item))

            context_menu.addAction(open_action)
            context_menu.addAction(delete_action)
            context_menu.exec(self.image_list.mapToGlobal(position))

    def open_image(self, filename: str):
        """Open the selected image (placeholder for actual functionality)."""
        print(f"Open image: {filename}")

    def delete_image(self, item: QListWidgetItem):
        """Delete the selected image from the list."""
        self.image_list.takeItem(self.image_list.row(item))
        print(f"Deleted image: {item.text()}")

    def display_image(self, item: QListWidgetItem):
        """Display the selected image in the preview area."""
        filename = item.text()
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
        """Take a screenshot and print the mouse position."""
        # screen = QApplication.primaryScreen()
        # screenshot = screen.grabWindow(0)  # Capture the entire screen

        # Take screenshot of the entire screen using pyscreenshot
        screenshot = ImageGrab.grab()  # Capture the entire screen
        screenshot_path = os.path.join(shot_path, f"{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        screenshot.save(screenshot_path, "PNG")  # Save the screenshot

        print(f"Mouse clicked at: {mouse_pos_x}, {mouse_pos_y}")
        print(f"Screenshots saved.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())