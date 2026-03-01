import sys
import cv2
import numpy as np
import os

# 添加当前目录和backend目录到系统路径
sys.path.append(".")
sys.path.append("../backend")
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSlider,
    QRadioButton,
    QToolButton,
    QCheckBox,
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QPainterPath, QIcon, QBrush
from PyQt5.QtCore import QTimer, Qt, QSize, pyqtSlot, QRectF

# 从 surround_view 导入必要的类
from surround_view import CaptureThread, CameraProcessingThread
from surround_view import FisheyeCameraModel, BirdView
from surround_view import MultiBufferManager, ProjectedImageBuffer
import surround_view.param_settings as settings


class VideoLabel(QLabel):
    """A custom QLabel to draw camera feed and overlays."""

    def __init__(self, parent=None, stretch_to_fill=False):
        super().__init__(parent)
        self.pixmap = None
        self.stretch_to_fill = stretch_to_fill
        self.pen = QPen(Qt.yellow, 3, Qt.SolidLine)
        self.pen.setCosmetic(True)
        # State for drawing auxiliary path
        self.draw_path_enabled = False
        self.steering_angle = 0
        self.car_direction = "front"

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()  # Trigger a repaint

    def set_path_drawing(self, enabled, steering_angle=0, car_direction="front"):
        self.draw_path_enabled = enabled
        self.steering_angle = steering_angle
        self.car_direction = car_direction
        self.update()

    def _calculate_dynamic_path(self, W, H):
        # This logic was moved from MainWindow
        svg_h = H * 0.6
        svg_y_offset = H * 0.4

        path = QPainterPath()

        bottom_y = svg_h
        top_y = svg_h * 0.15

        bottom_sep = W * 0.25
        p0l_x, p0r_x = W / 2 - bottom_sep, W / 2 + bottom_sep

        top_sep_straight = W * 0.08
        p2l_x_straight, p2r_x_straight = (
            W / 2 - top_sep_straight,
            W / 2 + top_sep_straight,
        )

        steering_factor = self.steering_angle / 45.0
        if self.car_direction == "back":
            steering_factor = -steering_factor

        top_shift = steering_factor * (W * 0.35)
        p2l_x, p2r_x = p2l_x_straight + top_shift, p2r_x_straight + top_shift

        control_point_y = svg_h * 0.55
        curvature_amount = steering_factor * (W * 0.25)

        p1l_x = (p0l_x + p2l_x) / 2 - curvature_amount
        p1r_x = (p0r_x + p2r_x) / 2 - curvature_amount

        # The Y coordinates are relative to the pixmap, so no initial offset is needed
        path.moveTo(p0l_x, bottom_y + svg_y_offset)
        path.quadTo(p1l_x, control_point_y + svg_y_offset, p2l_x, top_y + svg_y_offset)

        path.moveTo(p0r_x, bottom_y + svg_y_offset)
        path.quadTo(p1r_x, control_point_y + svg_y_offset, p2r_x, top_y + svg_y_offset)

        return path

    def _draw_static_path(self, painter, W, H):
        # Define pens for different colors, with slightly thicker lines
        green_pen = QPen(Qt.green, 3, Qt.SolidLine)
        yellow_pen = QPen(Qt.yellow, 3, Qt.SolidLine)
        red_pen = QPen(Qt.red, 3, Qt.SolidLine)

        # Define trapezoid geometry for a correct perspective effect
        # Top is further away (narrower), bottom is closer (wider)
        top_y = H * 0.45
        bottom_y = H - 1  # Stick to the bottom of the pixmap
        top_w = W * 0.4
        bottom_w = W * 0.9

        p_tl_x = (W - top_w) / 2
        p_tr_x = (W + top_w) / 2
        p_bl_x = (W - bottom_w) / 2
        p_br_x = (W + bottom_w) / 2

        # Points for the outer trapezoid
        p_tl = (p_tl_x, top_y)
        p_tr = (p_tr_x, top_y)
        p_bl = (p_bl_x, bottom_y)
        p_br = (p_br_x, bottom_y)

        # Draw top green line
        painter.setPen(green_pen)
        painter.drawLine(int(p_tl[0]), int(p_tl[1]), int(p_tr[0]), int(p_tr[1]))

        # Function to interpolate points on the straight side lines for a given y
        def get_x(y, is_left):
            p1, p2 = (p_tl, p_bl) if is_left else (p_tr, p_br)
            if p1[1] == p2[1]:
                return p1[0]
            # Linear interpolation
            return p1[0] + (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1])

        # Draw horizontal yellow lines
        painter.setPen(yellow_pen)
        for i in range(1, 3):
            y = top_y + i * (bottom_y - top_y) / 3
            xl = get_x(y, True)
            xr = get_x(y, False)
            painter.drawLine(int(xl), int(y), int(xr), int(y))

        # Draw side lines with color split
        # Split point for color change from yellow to red
        y_split = top_y + (bottom_y - top_y) * 0.6

        xl_split = get_x(y_split, True)
        xr_split = get_x(y_split, False)

        # Yellow part of side lines
        painter.setPen(yellow_pen)
        painter.drawLine(int(p_tl[0]), int(p_tl[1]), int(xl_split), int(y_split))
        painter.drawLine(int(p_tr[0]), int(p_tr[1]), int(xr_split), int(y_split))

        # Red part of side lines
        painter.setPen(red_pen)
        painter.drawLine(int(xl_split), int(y_split), int(p_bl[0]), int(p_bl[1]))
        painter.drawLine(int(xr_split), int(y_split), int(p_br[0]), int(p_br[1]))

    def paintEvent(self, event):
        if not self.pixmap:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Scale pixmap to fit the label, either stretching or keeping aspect ratio
        scale_mode = (
            Qt.IgnoreAspectRatio if self.stretch_to_fill else Qt.KeepAspectRatio
        )
        scaled_pixmap = self.pixmap.scaled(
            self.size(), scale_mode, Qt.SmoothTransformation
        )

        # Define the path for the rounded rectangle, matching the pixmap's rectangle
        path = QPainterPath()
        path.addRoundedRect(QRectF(scaled_pixmap.rect()), 15.0, 15.0)

        # Center the drawing area in the label
        point = self.rect().center() - scaled_pixmap.rect().center()

        # Save painter state, translate to the centered position
        painter.save()
        painter.translate(point)

        # Use the pixmap as a brush to fill the rounded rectangle path
        brush = QBrush(scaled_pixmap)
        painter.setPen(Qt.NoPen)  # No border for the video frame
        painter.fillPath(path, brush)

        # Restore painter state to draw overlays from the label's origin
        painter.restore()

        if self.draw_path_enabled:
            painter.save()
            # Translate the painter again to align with the displayed pixmap for drawing paths
            painter.translate(point)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw static path if in reverse mode
            if self.car_direction == "back":
                self._draw_static_path(
                    painter, scaled_pixmap.width(), scaled_pixmap.height()
                )

            # Calculate and draw dynamic path
            path = self._calculate_dynamic_path(
                scaled_pixmap.width(), scaled_pixmap.height()
            )
            painter.setPen(self.pen)
            painter.drawPath(path)

            painter.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AVM 360° GUI System")
        self.setGeometry(100, 100, 1600, 900)

        # --- State ---
        self.steering_angle = 0
        self.car_direction = "front"  # 'front' or 'back'
        self.right_view_mode = "front"  # 'front' or 'rear'
        self.raw_frames = {}  # Cache for raw frames from cameras

        # --- Distortion Controls ---
        self.distortion_k1 = 0.0
        self.distortion_k2 = 0.0
        self.distortion_p1 = 0.0
        self.distortion_p2 = 0.0

        # --- UI Components ---
        self.main_video_label = VideoLabel(self)  # Top-right view
        self.avm_video_label = VideoLabel(self)  # Left view (bird's eye)
        self.left_video_label = VideoLabel(
            self, stretch_to_fill=True
        )  # Bottom-right, left part
        self.right_video_label = VideoLabel(
            self, stretch_to_fill=True
        )  # Bottom-right, right part

        # --- Create Image Buttons instead of Radio Buttons ---
        self.up_button = QPushButton()
        self.down_button = QPushButton()
        up_icon = QIcon(os.path.join("images", "up.png"))
        down_icon = QIcon(os.path.join("images", "down.png"))
        self.up_button.setIcon(up_icon)
        self.down_button.setIcon(down_icon)
        self.up_button.setIconSize(QSize(40, 40))
        self.down_button.setIconSize(QSize(40, 40))
        self.up_button.setFixedSize(QSize(50, 50))
        self.down_button.setFixedSize(QSize(50, 50))
        self.up_button.setStyleSheet(
            "QPushButton {border: none; background-color: transparent;}"
        )
        self.down_button.setStyleSheet(
            "QPushButton {border: none; background-color: transparent;}"
        )
        self.up_button.setCheckable(True)
        self.down_button.setCheckable(True)

        # Buttons for top-right view selection
        self.front_view_button = QPushButton("前视")
        self.rear_view_button = QPushButton("后视")
        self.front_view_button.setCheckable(True)
        self.rear_view_button.setCheckable(True)
        self.front_view_button.setChecked(True)  # Default to front view

        self.steering_slider = QSlider(Qt.Horizontal)
        self.steering_value_label = QLabel("0°")

        # Checkboxes for view enhancements
        self.gains_checkbox = QCheckBox("亮度均衡")
        self.balance_checkbox = QCheckBox("色彩校正")

        # --- Car image for stitched view ---
        # The car image is now handled by the stitcher, so we remove the UI part here.

        # --- Layout ---
        self.setup_layout()

        # --- Connections ---
        self.steering_slider.valueChanged.connect(self.update_steering_angle)
        self.up_button.clicked.connect(self.on_direction_change)
        self.down_button.clicked.connect(self.on_direction_change)
        self.front_view_button.clicked.connect(self.on_view_change)
        self.rear_view_button.clicked.connect(self.on_view_change)
        self.gains_checkbox.stateChanged.connect(self.on_enhancement_change)
        self.balance_checkbox.stateChanged.connect(self.on_enhancement_change)

        # --- Timer for frame updates ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frames)

        # --- Surround View Setup ---
        self.setup_surround_view()

        self.up_button.setChecked(True)
        self.on_direction_change()  # Set initial direction
        # Start the timer for UI updates
        self.timer.start(16)  # ~60 fps

    def setup_surround_view(self):
        yamls_dir = os.path.join(os.getcwd(), "yaml")
        self.camera_ids = [3, 1, 4, 2]
        flip_methods = [0, 0, 0, 0]
        names = settings.camera_names
        cameras_files = [os.path.join(yamls_dir, name + ".yaml") for name in names]
        camera_models = [
            FisheyeCameraModel(camera_file, name)
            for camera_file, name in zip(cameras_files, names)
        ]

        self.capture_tds = [
            CaptureThread(camera_id, flip_method, use_gst=False)
            for camera_id, flip_method in zip(self.camera_ids, flip_methods)
        ]
        self.capture_buffer_manager = MultiBufferManager()
        for td in self.capture_tds:
            self.capture_buffer_manager.bind_thread(td, buffer_size=8)
            if td.connect_camera():
                td.new_frame.connect(self.update_raw_frame)
                td.start()

        proc_buffer_manager = ProjectedImageBuffer()
        self.process_tds = [
            CameraProcessingThread(self.capture_buffer_manager, camera_id, camera_model)
            for camera_id, camera_model in zip(self.camera_ids, camera_models)
        ]
        for td in self.process_tds:
            proc_buffer_manager.bind_thread(td)
            td.start()

        self.birdview = BirdView(
            proc_buffer_manager, camera_ids_in_order=self.camera_ids
        )
        self.birdview.load_weights_and_masks("./weights.png", "./masks.png")
        # Initialize enhancement flags
        self.birdview.use_gains = False
        self.birdview.use_balance = False
        self.birdview.start()

    def setup_layout(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.setStyleSheet("background-color: #1D2A3D; color: white;")

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 15, 20, 15)
        root_layout.setSpacing(15)

        # --- Top Header Bar ---
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)

        # Left: Battery
        battery_label = QLabel("○ 80% 电池电量")
        battery_label.setStyleSheet(
            "font-size: 14px; color: #00DFFF; font-weight: bold;"
        )
        top_bar_layout.addWidget(battery_label, 0, Qt.AlignLeft)
        top_bar_layout.addStretch()

        # Center: Gears
        gear_container = QWidget()
        gear_layout = QHBoxLayout(gear_container)
        gear_layout.setSpacing(10)
        gears = {
            "P": "transparent",
            "R": "transparent",
            "N": "transparent",
            "D": "#00DFFF",
        }
        for g, color in gears.items():
            gear_label = QLabel(g)
            is_selected = color != "transparent"
            text_color = "black" if is_selected else "white"
            style = f"""
                color: {text_color};
                background-color: {color};
                border-radius: 13px;
                padding: 5px;
                font-weight: bold;
                min-width: 26px; max-width: 26px;
                min-height: 26px; max-height: 26px;
            """
            gear_label.setStyleSheet(style)
            gear_label.setAlignment(Qt.AlignCenter)
            gear_layout.addWidget(gear_label)
        top_bar_layout.addWidget(gear_container, 0, Qt.AlignCenter)
        top_bar_layout.addStretch()

        # Right: Indicators
        indicators_layout = QHBoxLayout()
        safety_belt_label = QLabel("⊗ 安全带")
        safety_belt_label.setStyleSheet(
            "color: #E85349; font-size: 14px; font-weight: bold;"
        )
        near_light_label = QLabel("💡 近光灯")
        near_light_label.setStyleSheet(
            "color: #00DFFF; font-size: 14px; font-weight: bold;"
        )
        indicators_layout.addWidget(safety_belt_label)
        indicators_layout.addSpacing(20)
        indicators_layout.addWidget(near_light_label)
        top_bar_layout.addLayout(indicators_layout)

        # --- Main content panel ---
        main_panel = QWidget()
        main_layout = QHBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # Container style for video panels
        container_style = (
            "background-color: #111829; border: 1px solid #009FFF; border-radius: 20px;"
        )

        # --- Block 1: Left Panel (AVM Bird's Eye View) ---
        avm_container = QWidget()
        avm_container.setStyleSheet(container_style)
        avm_layout = QVBoxLayout(avm_container)
        avm_layout.setContentsMargins(2, 2, 2, 2)
        avm_layout.addWidget(self.avm_video_label)
        main_layout.addWidget(avm_container, 2)

        # --- Right Super-Panel ---
        right_super_panel = QWidget()
        right_super_layout = QVBoxLayout(right_super_panel)
        right_super_layout.setContentsMargins(0, 0, 0, 0)
        right_super_layout.setSpacing(15)
        main_layout.addWidget(right_super_panel, 3)

        # --- Block 2: Top-Right (Main Camera View) ---
        top_right_container = QWidget()
        top_right_container.setStyleSheet(container_style)
        top_right_layout = QGridLayout(top_right_container)
        top_right_layout.setContentsMargins(2, 2, 2, 2)
        top_right_layout.addWidget(self.main_video_label, 0, 0, 1, 1)

        view_button_layout = QVBoxLayout()
        view_button_layout.setSpacing(0)
        view_button_style = """
            QPushButton {
                background-color: rgba(0, 0, 0, 150);
                color: white;
                border: 1px solid #555;
                padding: 20px;
                font-size: 22px;
                min-width: 100px;
            }
            QPushButton:checked {
                background-color: #5294e2;
            }
        """
        self.front_view_button.setStyleSheet(view_button_style)
        self.rear_view_button.setStyleSheet(view_button_style)
        view_button_layout.addWidget(self.front_view_button)
        view_button_layout.addWidget(self.rear_view_button)
        view_button_layout.addStretch()
        top_right_layout.addLayout(view_button_layout, 0, 0, Qt.AlignTop | Qt.AlignLeft)
        right_super_layout.addWidget(top_right_container, 3)

        # --- Bottom-Right Panel ---
        bottom_right_panel = QWidget()
        bottom_right_layout = QHBoxLayout(bottom_right_panel)
        bottom_right_layout.setContentsMargins(0, 0, 0, 0)
        bottom_right_layout.setSpacing(15)
        right_super_layout.addWidget(bottom_right_panel, 2)

        # --- Block 3: Left Camera ---
        left_video_container = QWidget()
        left_video_container.setStyleSheet(container_style)
        left_video_layout = QVBoxLayout(left_video_container)
        left_video_layout.setContentsMargins(2, 2, 2, 2)
        left_video_layout.addWidget(self.left_video_label)
        bottom_right_layout.addWidget(left_video_container, 1)

        # --- Block 4: Controls ---
        controls_container = QWidget()
        controls_container.setStyleSheet(
            "background-color: #2E2E2E; border-radius: 10px;"
        )
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(5, 10, 5, 10)
        controls_layout.setSpacing(5)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.up_button, 0, Qt.AlignCenter)
        self.steering_slider.setFixedWidth(120)
        self.steering_slider.setRange(-45, 45)
        self.steering_slider.setValue(0)
        slider_style = """
            QSlider::groove:horizontal { border: 1px solid #bbb; background: white; height: 10px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #5294e2; border: 1px solid #5294e2; width: 18px; margin: -4px 0; border-radius: 8px; }
        """
        self.steering_slider.setStyleSheet(slider_style)
        controls_layout.addWidget(self.steering_slider, 0, Qt.AlignCenter)
        self.steering_value_label.setAlignment(Qt.AlignCenter)
        controls_layout.addWidget(self.steering_value_label, 0, Qt.AlignCenter)
        controls_layout.addWidget(self.down_button, 0, Qt.AlignCenter)
        controls_layout.addStretch(1)
        bottom_right_layout.addWidget(controls_container, 0)

        # --- Block 5: Right Camera ---
        right_video_container = QWidget()
        right_video_container.setStyleSheet(container_style)
        right_video_layout = QVBoxLayout(right_video_container)
        right_video_layout.setContentsMargins(2, 2, 2, 2)
        right_video_layout.addWidget(self.right_video_label)
        bottom_right_layout.addWidget(right_video_container, 1)

        # --- Bottom Control Bar ---
        bottom_bar = QWidget()
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(0, 10, 0, 0)
        bottom_bar_layout.setSpacing(45)
        bottom_bar_layout.setAlignment(Qt.AlignCenter)

        functions = [
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_ComputerIcon")
                ),
                "空调",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_DriveNetIcon")
                ),
                "座椅",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_MediaPlay")
                ),
                "音乐",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_DirHomeIcon")
                ),
                "导航",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_FileDialogDetailedView")
                ),
                "设置",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_DesktopIcon")
                ),
                "驾驶模式",
            ),
            (
                self.style().standardIcon(
                    getattr(QApplication.style(), "SP_MessageBoxInformation")
                ),
                "电话",
            ),
        ]
        button_style = """
            QToolButton { border: none; color: white; background-color: transparent; }
            QToolButton:pressed { background-color: #2E2E2E; }
        """
        for icon, text in functions:
            button = QToolButton()
            if text == "音乐":
                button.setStyleSheet(
                    "QToolButton { border: none; color: #00DFFF; background-color: #111829; border-radius: 24px; padding: 10px; }"
                )
            else:
                button.setStyleSheet(button_style)
            button.setIcon(icon)
            button.setText(text)
            button.setIconSize(QSize(32, 32))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            bottom_bar_layout.addWidget(button)

        # Add checkboxes for view enhancements
        bottom_bar_layout.addSpacing(60)
        checkbox_style = "QCheckBox { font-size: 16px; spacing: 5px; color: white; } QCheckBox::indicator { width: 20px; height: 20px; }"
        self.gains_checkbox.setStyleSheet(checkbox_style)
        self.balance_checkbox.setStyleSheet(checkbox_style)
        bottom_bar_layout.addWidget(self.gains_checkbox)
        bottom_bar_layout.addWidget(self.balance_checkbox)

        # Add all main widgets to root layout
        root_layout.addWidget(top_bar)
        root_layout.addWidget(main_panel)
        root_layout.addWidget(bottom_bar)

        root_layout.setStretch(0, 0)
        root_layout.setStretch(1, 1)
        root_layout.setStretch(2, 0)

    def update_steering_angle(self, value):
        self.steering_angle = value
        self.steering_value_label.setText(f"{value}°")

    def on_enhancement_change(self):
        """Update enhancement flags on the BirdView object."""
        self.birdview.use_gains = self.gains_checkbox.isChecked()
        self.birdview.use_balance = self.balance_checkbox.isChecked()

    def _set_direction(self, direction):
        """Unified method to set car direction and update all related UI."""
        if direction == "front":
            self.car_direction = "front"
            self.right_view_mode = "front"
            self.up_button.setChecked(True)
            self.down_button.setChecked(False)
            self.front_view_button.setChecked(True)
            self.rear_view_button.setChecked(False)
        elif direction == "back":
            self.car_direction = "back"
            self.right_view_mode = "rear"
            self.up_button.setChecked(False)
            self.down_button.setChecked(True)
            self.front_view_button.setChecked(False)
            self.rear_view_button.setChecked(True)
        print(f"Direction set to: {self.car_direction}")

    def on_direction_change(self):
        sender = self.sender()
        if sender == self.up_button or (sender is None and self.up_button.isChecked()):
            self._set_direction("front")
        elif sender == self.down_button or (
            sender is None and self.down_button.isChecked()
        ):
            self._set_direction("back")

    def on_view_change(self):
        sender = self.sender()
        if sender == self.front_view_button:
            self._set_direction("front")
        elif sender == self.rear_view_button:
            self._set_direction("back")

    @pyqtSlot(int, np.ndarray)
    def update_raw_frame(self, camera_id, frame):
        """Slot to receive and cache raw frames from camera threads."""
        self.raw_frames[camera_id] = frame

    def update_frames(self):
        # --- Get all necessary frames ---
        birdview_frame = self.birdview.get()
        front_frame = self.raw_frames.get(self.camera_ids[0])  # 前视摄像头索引
        rear_frame = self.raw_frames.get(self.camera_ids[1])   # 后视摄像头索引
        left_frame = self.raw_frames.get(self.camera_ids[2])   # 左侧摄像头索引
        right_frame = self.raw_frames.get(self.camera_ids[3])  # 右侧摄像头索引

        # --- Block 1: Update AVM (Left Panel) ---
        if birdview_frame is not None:
            qt_image_bird = self.convert_cv_to_qt(birdview_frame)
            pixmap_bird = QPixmap.fromImage(qt_image_bird)
            self.avm_video_label.set_pixmap(pixmap_bird)
            self.avm_video_label.set_path_drawing(False)

        # --- Block 2: Update Main Camera View (Top-Right Panel) ---
        frame_to_show = None
        if self.right_view_mode == "front":
            frame_to_show = front_frame
        else:  # 'rear'
            frame_to_show = rear_frame

        if frame_to_show is not None:
            # No distortion/rotation for the main view
            qt_image_main = self.convert_cv_to_qt(frame_to_show)
            pixmap_main = QPixmap.fromImage(qt_image_main)
            self.main_video_label.set_pixmap(pixmap_main)
            self.main_video_label.set_path_drawing(
                True, self.steering_angle, self.car_direction
            )
        else:
            self.main_video_label.set_pixmap(QPixmap())

        # --- Block 3: Update Left Camera View ---
        if left_frame is not None:
            # Apply distortion and rotation
            corrected_left = self.apply_distortion_correction(left_frame)
            rotated_left = cv2.rotate(corrected_left, cv2.ROTATE_90_COUNTERCLOCKWISE)
            qt_image_left = self.convert_cv_to_qt(rotated_left)
            pixmap_left = QPixmap.fromImage(qt_image_left)
            self.left_video_label.set_pixmap(pixmap_left)
            self.left_video_label.set_path_drawing(False)
        else:
            self.left_video_label.set_pixmap(QPixmap())

        # --- Block 5: Update Right Camera View ---
        if right_frame is not None:
            # Apply distortion and rotation
            corrected_right = self.apply_distortion_correction(right_frame)
            rotated_right = cv2.rotate(corrected_right, cv2.ROTATE_90_CLOCKWISE)
            qt_image_right = self.convert_cv_to_qt(rotated_right)
            pixmap_right = QPixmap.fromImage(qt_image_right)
            self.right_video_label.set_pixmap(pixmap_right)
            self.right_video_label.set_path_drawing(False)
        else:
            self.right_video_label.set_pixmap(QPixmap())

    def apply_distortion_correction(self, img):
        if img is None:
            return None
        h, w = img.shape[:2]
        # Final, hardcoded distortion coefficients
        k1 = -1.0
        k2 = -0.660
        p1 = -0.150
        p2 = 0.030
        k3 = 0.0
        dist_coeffs = np.array([k1, k2, p1, p2, k3])

        # Create a sample camera matrix
        f = w  # Approximate focal length
        cam_matrix = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]])

        # Apply the distortion correction
        return cv2.undistort(img, cam_matrix, dist_coeffs)

    def convert_cv_to_qt(self, cv_img):
        """Convert from an opencv image to a QImage."""
        if cv_img is None:
            return QImage()
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(
            rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888
        )
        return convert_to_Qt_format

    def closeEvent(self, event):
        """Handle window close event."""
        print("Stopping threads...")
        self.timer.stop()

        self.birdview.stop()

        for td in self.process_tds:
            td.stop()

        for td in self.capture_tds:
            td.stop()
            td.disconnect_camera()

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
