# "g19_configurator.py" V1.1

import sys, json, os, psutil, copy, time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTabWidget, 
                             QFormLayout, QLabel, QLineEdit, QPushButton,
                             QColorDialog, QHBoxLayout, QComboBox, QCheckBox, 
                             QGroupBox, QScrollArea, QSpinBox, QDoubleSpinBox, QFileDialog, QFrame)
from PyQt6.QtGui import QColor, QImage, QPixmap, QKeySequence
from PyQt6.QtCore import QTimer, Qt

from g19_screens import AVAILABLE_SCREENS

# Universally resolve the user's home directory (Crucial for open-source deployment!)
CONFIG_PATH = os.path.expanduser("~/.config/G19FullControl/config.json")

# ==========================================
# [1] PREVIEW ENGINE WIDGET
# ==========================================
class LCDPreviewWidget(QWidget):
    """Renders a live 320x240 preview of the LCD screens using Pillow inside a PyQt Label."""
    def __init__(self, available_screens, parent_window):
        super().__init__(parent_window)
        self.available_screens = available_screens
        self.parent_window = parent_window 
        self.current_screen_index = 0
        self.preview_profile_name = "Preview Mode"
        self.init_ui()
        
        # Updates the preview at 2 FPS (500ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self.timer.start(500) 

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Live LCD Preview:"))
        
        self.screen_selector = QComboBox()
        for screen in self.available_screens: self.screen_selector.addItem(screen.name)
        self.screen_selector.currentIndexChanged.connect(self.change_screen)
        layout.addWidget(self.screen_selector)
        
        self.lcd_display = QLabel()
        self.lcd_display.setFixedSize(320, 240)
        self.lcd_display.setStyleSheet("background-color: black; border: 2px solid #555;")
        self.lcd_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lcd_display)
        layout.addStretch()

    def change_screen(self, index):
        self.current_screen_index = index
        self.update_preview()

    def set_screen_by_name(self, name):
        for i in range(self.screen_selector.count()):
            if self.screen_selector.itemText(i) == name:
                self.screen_selector.setCurrentIndex(i)
                break

    def update_preview(self):
        if not self.available_screens: return
        live_cfg = self.parent_window.get_current_config()
        if not live_cfg: return
        try:
            # We pass a dummy cache flag to tell the Screen Engine to skip heavy hardware scans!
            # This prevents UI stuttering while adjusting sliders.
            dummy_cache = {"_IS_PREVIEW": True}
            
            pil_img = self.available_screens[self.current_screen_index].draw(self.preview_profile_name, live_cfg, dummy_cache)
            img_rgba = pil_img.convert("RGBA")
            qimg = QImage(img_rgba.tobytes("raw", "RGBA"), img_rgba.width, img_rgba.height, QImage.Format.Format_RGBA8888)
            self.lcd_display.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e: 
            print(f"Preview Error: {e}")

# ==========================================
# [2] HARDWARE SENSOR ROW (ACCORDION UI)
# ==========================================
class SensorRowWidget(QFrame):
    """A highly dense, collapsible settings block for a single hardware sensor."""
    def __init__(self, hw_id, saved_data, parent_ui):
        super().__init__()
        self.hw_id = hw_id
        self.parent_ui = parent_ui
        
        self.setObjectName("sensor_row")
        self.setStyleSheet("#sensor_row { border: 1px solid #666; border-radius: 4px; margin-bottom: 2px; }")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        # --- Top Bar (Always Visible Checkbox) ---
        top_bar = QHBoxLayout()
        self.btn_toggle = QPushButton()
        self.btn_toggle.setFixedWidth(30)
        self.btn_toggle.setFlat(True)
        self.btn_toggle.setStyleSheet("font-weight: bold; font-size: 14px; border: none;")
        self.btn_toggle.clicked.connect(self.toggle_expanded)
        
        self.chk_enable = QCheckBox(f" {hw_id}")
        self.chk_enable.setChecked(saved_data.get("enabled", False))
        self.chk_enable.setStyleSheet("font-weight: bold; font-size: 13px;")
        
        top_bar.addWidget(self.btn_toggle)
        top_bar.addWidget(self.chk_enable)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # --- Settings Container (Hidden by Default) ---
        self.settings_container = QWidget()
        settings_layout = QVBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(35, 10, 10, 5) 
        settings_layout.setSpacing(5)

        # LINE 1: Label Customization
        l1 = QHBoxLayout()
        l1.addWidget(QLabel("Label:"))
        self.txt_name = QLineEdit(saved_data.get("custom_name", hw_id)); self.txt_name.setFixedWidth(120); l1.addWidget(self.txt_name)
        
        self.btn_name_col = QPushButton("Colour")
        self.name_colour = saved_data.get("name_colour", [255, 255, 255])
        self.btn_name_col.setStyleSheet(f"background-color: rgb({self.name_colour[0]},{self.name_colour[1]},{self.name_colour[2]}); color: {self._get_tc(self.name_colour)}; border: 1px solid #777;")
        self.btn_name_col.setFixedWidth(65); self.btn_name_col.clicked.connect(self.pick_name_colour); l1.addWidget(self.btn_name_col)

        self.spn_name_size = QSpinBox(); self.spn_name_size.setRange(8, 40); self.spn_name_size.setValue(saved_data.get("name_size", 12))
        self.spn_name_x = QSpinBox(); self.spn_name_x.setRange(0, 320); self.spn_name_x.setValue(saved_data.get("name_x", 10))
        self.spn_name_y = QSpinBox(); self.spn_name_y.setRange(0, 240); self.spn_name_y.setValue(saved_data.get("name_y", 40))
        l1.addWidget(QLabel("Size:")); l1.addWidget(self.spn_name_size)
        l1.addWidget(QLabel("X:")); l1.addWidget(self.spn_name_x)
        l1.addWidget(QLabel("Y:")); l1.addWidget(self.spn_name_y)
        l1.addStretch()
        settings_layout.addLayout(l1)

        # LINE 2: Graphic Display (Bars, Gauges, Graphs)
        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Graphic:"))
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Text Only", "Horizontal Bar", "Vertical Bar", "Line Graph", "Needle Gauge", "Bar Gauge"])
        self.cmb_type.setCurrentText(saved_data.get("display_type", "Text Only")); self.cmb_type.setFixedWidth(100); l2.addWidget(self.cmb_type)

        self.btn_disp_col = QPushButton("Norm Col")
        self.disp_colour = saved_data.get("disp_colour", [50, 200, 50])
        self.btn_disp_col.setStyleSheet(f"background-color: rgb({self.disp_colour[0]},{self.disp_colour[1]},{self.disp_colour[2]}); color: {self._get_tc(self.disp_colour)}; border: 1px solid #777;")
        self.btn_disp_col.setFixedWidth(65); self.btn_disp_col.clicked.connect(self.pick_disp_colour); l2.addWidget(self.btn_disp_col)

        self.spn_max = QDoubleSpinBox(); self.spn_max.setRange(0.1, 1000000000.0); self.spn_max.setDecimals(2)
        self.spn_max.setValue(float(saved_data.get("gauge_max", 100)))
        l2.addWidget(QLabel("Gauge Max:")); l2.addWidget(self.spn_max)

        self.spn_thresh = QDoubleSpinBox(); self.spn_thresh.setRange(0.0, 1000000000.0); self.spn_thresh.setDecimals(2)
        self.spn_thresh.setValue(float(saved_data.get("high_thresh", 85)))
        
        self.btn_high_col = QPushButton("High Col")
        self.disp_col_high = saved_data.get("disp_col_high", [255, 50, 50])
        self.btn_high_col.setStyleSheet(f"background-color: rgb({self.disp_col_high[0]},{self.disp_col_high[1]},{self.disp_col_high[2]}); color: {self._get_tc(self.disp_col_high)}; border: 1px solid #777;")
        self.btn_high_col.setFixedWidth(65); self.btn_high_col.clicked.connect(self.pick_high_colour)
        l2.addWidget(QLabel("High Trigger:")); l2.addWidget(self.spn_thresh); l2.addWidget(self.btn_high_col)

        leg_sz = saved_data.get("disp_size", 12)
        self.spn_disp_w = QSpinBox(); self.spn_disp_w.setRange(8, 300); self.spn_disp_w.setValue(saved_data.get("disp_w", 100 if saved_data.get("display_type") == "Horizontal Bar" else leg_sz))
        self.spn_disp_h = QSpinBox(); self.spn_disp_h.setRange(2, 200); self.spn_disp_h.setValue(saved_data.get("disp_h", leg_sz))
        self.spn_disp_x = QSpinBox(); self.spn_disp_x.setRange(0, 320); self.spn_disp_x.setValue(saved_data.get("disp_x", 150))
        self.spn_disp_y = QSpinBox(); self.spn_disp_y.setRange(0, 240); self.spn_disp_y.setValue(saved_data.get("disp_y", 40))
        l2.addWidget(QLabel("W:")); l2.addWidget(self.spn_disp_w)
        l2.addWidget(QLabel("H:")); l2.addWidget(self.spn_disp_h)
        l2.addWidget(QLabel("X:")); l2.addWidget(self.spn_disp_x)
        l2.addWidget(QLabel("Y:")); l2.addWidget(self.spn_disp_y)
        l2.addStretch()
        settings_layout.addLayout(l2)

        # LINE 3: Value Text & Math
        l3 = QHBoxLayout()
        self.chk_val = QCheckBox("Value Text"); self.chk_val.setChecked(saved_data.get("show_val", True))
        self.btn_val_col = QPushButton("Colour")
        self.val_colour = saved_data.get("val_colour", [255, 255, 255])
        self.btn_val_col.setStyleSheet(f"background-color: rgb({self.val_colour[0]},{self.val_colour[1]},{self.val_colour[2]}); color: {self._get_tc(self.val_colour)}; border: 1px solid #777;")
        self.btn_val_col.setFixedWidth(65); self.btn_val_col.clicked.connect(self.pick_val_colour)

        self.cmb_fmt = QComboBox(); self.cmb_fmt.addItems(self._get_format_options(self.hw_id))
        saved_fmt = saved_data.get("data_format", "Auto (%)")
        if saved_fmt in [self.cmb_fmt.itemText(i) for i in range(self.cmb_fmt.count())]: self.cmb_fmt.setCurrentText(saved_fmt)

        self.spn_math = QDoubleSpinBox()
        self.spn_math.setRange(0.001, 10000.0)
        self.spn_math.setDecimals(3)
        self.spn_math.setValue(float(saved_data.get("math_mult", 1.0)))

        self.spn_val_size = QSpinBox(); self.spn_val_size.setRange(8, 60); self.spn_val_size.setValue(saved_data.get("val_size", 12))
        self.spn_val_x = QSpinBox(); self.spn_val_x.setRange(0, 320); self.spn_val_x.setValue(saved_data.get("val_x", self.spn_disp_x.value() + 20))
        self.spn_val_y = QSpinBox(); self.spn_val_y.setRange(0, 240); self.spn_val_y.setValue(saved_data.get("val_y", self.spn_disp_y.value()))
        
        l3.addWidget(self.chk_val); l3.addWidget(self.btn_val_col)
        l3.addWidget(QLabel("Format:")); l3.addWidget(self.cmb_fmt)
        l3.addWidget(QLabel("x")); l3.addWidget(self.spn_math)
        l3.addWidget(QLabel("Size:")); l3.addWidget(self.spn_val_size)
        l3.addWidget(QLabel("X:")); l3.addWidget(self.spn_val_x)
        l3.addWidget(QLabel("Y:")); l3.addWidget(self.spn_val_y)
        l3.addStretch()
        settings_layout.addLayout(l3)

        # LINE 4: Max Value Text
        l4 = QHBoxLayout()
        self.chk_max = QCheckBox("Max Value"); self.chk_max.setChecked(saved_data.get("show_max", False))
        
        self.btn_max_col = QPushButton("Colour")
        self.max_colour = saved_data.get("max_colour", [200, 200, 200])
        self.btn_max_col.setStyleSheet(f"background-color: rgb({self.max_colour[0]},{self.max_colour[1]},{self.max_colour[2]}); color: {self._get_tc(self.max_colour)}; border: 1px solid #777;")
        self.btn_max_col.setFixedWidth(65); self.btn_max_col.clicked.connect(self.pick_max_colour)

        self.chk_max_auto = QCheckBox("Auto"); self.chk_max_auto.setChecked(saved_data.get("max_auto", True))
        self.txt_max_manual = QLineEdit(saved_data.get("max_manual", "100")); self.txt_max_manual.setFixedWidth(60)

        self.spn_max_size = QSpinBox(); self.spn_max_size.setRange(8, 60); self.spn_max_size.setValue(saved_data.get("max_size", 10))
        self.spn_max_x = QSpinBox(); self.spn_max_x.setRange(0, 320); self.spn_max_x.setValue(saved_data.get("max_x", self.spn_disp_x.value() + self.spn_disp_w.value() + 5))
        self.spn_max_y = QSpinBox(); self.spn_max_y.setRange(0, 240); self.spn_max_y.setValue(saved_data.get("max_y", self.spn_disp_y.value() + 15))

        l4.addWidget(self.chk_max); l4.addWidget(self.btn_max_col)
        l4.addWidget(self.chk_max_auto); l4.addWidget(self.txt_max_manual)
        l4.addWidget(QLabel("Size:")); l4.addWidget(self.spn_max_size)
        l4.addWidget(QLabel("X:")); l4.addWidget(self.spn_max_x)
        l4.addWidget(QLabel("Y:")); l4.addWidget(self.spn_max_y)
        l4.addStretch()
        settings_layout.addLayout(l4)
        
        self.chk_max_auto.toggled.connect(self.txt_max_manual.setDisabled)
        self.txt_max_manual.setDisabled(self.chk_max_auto.isChecked())

        main_layout.addWidget(self.settings_container)

        self.is_expanded = self.chk_enable.isChecked()
        self.settings_container.setVisible(self.is_expanded)
        self.btn_toggle.setText("▼" if self.is_expanded else "▶")

    def toggle_expanded(self):
        self.is_expanded = not self.is_expanded
        self.settings_container.setVisible(self.is_expanded)
        self.btn_toggle.setText("▼" if self.is_expanded else "▶")

    def _get_format_options(self, hw_id):
        hw_lower = hw_id.lower()
        if hw_id == "CPU Load" or hw_id.endswith("Load") and "core" in hw_lower: return ["Auto (%)"]
        elif "freq" in hw_lower or "clock" in hw_lower: return ["MHz", "GHz"]
        elif "power" in hw_lower: return ["Watts"]
        elif "network" in hw_lower: return ["Auto (%)", "Kbps", "Mbps", "Gbps", "KB", "MB", "GB", "TB", "Bytes"]
        elif "storage" in hw_lower or "ram load" in hw_lower or "vram" in hw_lower: return ["Auto (%)", "KB", "MB", "GB", "TB", "Bytes"]
        elif "temp" in hw_lower: return ["Auto (%)", "Temp (°C)", "Temp (°F)"]
        elif "fan" in hw_lower: return ["RPM", "LPM", "Gal/h"] 
        elif "in" in hw_lower or "volt" in hw_lower: return ["Volts", "mV"] 
        else: return ["Auto (%)", "Temp (°C)", "Temp (°F)", "Kbps", "Mbps", "Gbps", "KB", "MB", "GB", "TB", "Bytes", "MHz", "GHz", "Watts", "RPM", "LPM", "Gal/h", "Volts", "mV"]
    
    def _get_tc(self, color_list):
        """Calculates contrast to keep button text readable."""
        r, g, b = color_list
        return "black" if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else "white"

    def pick_name_colour(self):
        c = QColorDialog.getColor(QColor(*self.name_colour), self)
        if c.isValid(): self.name_colour = [c.red(), c.green(), c.blue()]; self.btn_name_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {self._get_tc(self.name_colour)}; border: 1px solid #777;")
    def pick_disp_colour(self):
        c = QColorDialog.getColor(QColor(*self.disp_colour), self)
        if c.isValid(): self.disp_colour = [c.red(), c.green(), c.blue()]; self.btn_disp_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {self._get_tc(self.disp_colour)}; border: 1px solid #777;")
    def pick_high_colour(self):
        c = QColorDialog.getColor(QColor(*self.disp_col_high), self)
        if c.isValid(): self.disp_col_high = [c.red(), c.green(), c.blue()]; self.btn_high_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {self._get_tc(self.disp_col_high)}; border: 1px solid #777;")
    def pick_val_colour(self):
        c = QColorDialog.getColor(QColor(*self.val_colour), self)
        if c.isValid(): self.val_colour = [c.red(), c.green(), c.blue()]; self.btn_val_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {self._get_tc(self.val_colour)}; border: 1px solid #777;")
    def pick_max_colour(self):
        c = QColorDialog.getColor(QColor(*self.max_colour), self)
        if c.isValid(): self.max_colour = [c.red(), c.green(), c.blue()]; self.btn_max_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {self._get_tc(self.max_colour)}; border: 1px solid #777;")

    def get_data(self):
        return {
            "hw_id": self.hw_id, "enabled": self.chk_enable.isChecked(), "custom_name": self.txt_name.text(),
            "name_colour": self.name_colour, "name_size": self.spn_name_size.value(), "name_x": self.spn_name_x.value(), "name_y": self.spn_name_y.value(),
            "display_type": self.cmb_type.currentText(), "disp_colour": self.disp_colour, "disp_col_high": self.disp_col_high, 
            "gauge_max": self.spn_max.value(), "high_thresh": self.spn_thresh.value(),
            "disp_w": self.spn_disp_w.value(), "disp_h": self.spn_disp_h.value(), "disp_x": self.spn_disp_x.value(), "disp_y": self.spn_disp_y.value(),
            "show_val": self.chk_val.isChecked(), "val_colour": self.val_colour, "data_format": self.cmb_fmt.currentText(), "math_mult": self.spn_math.value(),
            "val_size": self.spn_val_size.value(), "val_x": self.spn_val_x.value(), "val_y": self.spn_val_y.value(),
            "show_max": self.chk_max.isChecked(), "max_auto": self.chk_max_auto.isChecked(), "max_manual": self.txt_max_manual.text(),
            "max_colour": self.max_colour, "max_size": self.spn_max_size.value(), "max_x": self.spn_max_x.value(), "max_y": self.spn_max_y.value()
        }

# ==========================================
# [3] MACRO RECORDER (G-KEY ROW)
# ==========================================
class GKeyRowWidget(QWidget):
    """Handles parsing string commands or trapping live JSON macros."""
    def __init__(self, g_number, saved_data, parent=None):
        super().__init__(parent)
        self.g_number = g_number
        
        # Auto-upgrade legacy string configs to the new dictionary format safely
        if isinstance(saved_data, str) or isinstance(saved_data, list):
            self.data = {"action": saved_data, "note": ""}
        else:
            self.data = saved_data if saved_data else {"action": "", "note": ""}
            
        self.is_recording = False
        self.start_time = 0
        self.last_event_time = 0
        self.recorded_events = []

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 5)
        layout.addWidget(QLabel(f"G{self.g_number}:"))

        self.txt_input = QLineEdit()
        action_data = self.data.get("action", "")
        
        if isinstance(action_data, list): self.txt_input.setText(json.dumps(action_data))
        else: self.txt_input.setText(str(action_data))
            
        layout.addWidget(self.txt_input, stretch=2)

        self.btn_record = QPushButton("⏺ Record")
        self.btn_record.clicked.connect(self.toggle_record)
        layout.addWidget(self.btn_record)

        layout.addWidget(QLabel(" Note:"))
        self.txt_note = QLineEdit(self.data.get("note", ""))
        self.txt_note.setPlaceholderText("What does this do?")
        layout.addWidget(self.txt_note, stretch=3)

    def toggle_record(self):
        if not self.is_recording:
            self.is_recording = True
            self.recorded_events = []
            self.start_time = time.time()
            self.last_event_time = self.start_time
            
            self.btn_record.setText("Confirm (or ESC)")
            self.btn_record.setStyleSheet("background-color: #aa0000; color: white; font-weight: bold;")
            self.txt_input.setText("Listening...")
            self.grabKeyboard() # Lock UI focus to catch typing
        else:
            self.stop_recording()

    def stop_recording(self):
        self.is_recording = False
        self.releaseKeyboard()
        self.btn_record.setText("⏺ Record")
        self.btn_record.setStyleSheet("")
        
        if self.recorded_events: self.txt_input.setText(json.dumps(self.recorded_events))
        elif self.txt_input.text() == "Listening...": self.txt_input.setText("")

    def get_key_name(self, event):
        key_text = event.text().lower()
        if key_text and key_text.isprintable(): return key_text
        return QKeySequence(event.key()).toString().lower()

    def keyPressEvent(self, event):
        if self.is_recording:
            if event.key() == Qt.Key.Key_Escape:
                self.stop_recording()
                return
            if event.isAutoRepeat(): return
            
            now = time.time()
            self.recorded_events.append({"action": "down", "key": self.get_key_name(event), "delay": round(now - self.last_event_time, 3)})
            self.last_event_time = now
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.is_recording:
            if event.key() == Qt.Key.Key_Escape: return 
            if event.isAutoRepeat(): return

            now = time.time()
            self.recorded_events.append({"action": "up", "key": self.get_key_name(event), "delay": round(now - self.last_event_time, 3)})
            self.last_event_time = now
        else:
            super().keyReleaseEvent(event)

    def get_data(self):
        text_val = self.txt_input.text().strip()
        if not text_val and not self.txt_note.text(): return None
        
        # Power User Feature: If the box contains a JSON array, save it as a Macro!
        # If it fails to parse, we assume it's just a normal linux shell command string.
        try:
            parsed = json.loads(text_val)
            if isinstance(parsed, list):
                return {"action": parsed, "note": self.txt_note.text()}
        except Exception:
            pass 
            
        return {"action": text_val, "note": self.txt_note.text()}


# ==========================================
# [4] APP TABS (CLOCK, IMAGE, BACKLIGHT)
# ==========================================
class ClockTabWidget(QWidget):
    def __init__(self, c_cfg, parent=None):
        super().__init__(parent)
        self.c_cfg = c_cfg
        self.init_ui()

    def make_colour_btn(self, default_col):
        btn = QPushButton("Select Colour")
        btn.colour_val = self.c_cfg.get(default_col[0], default_col[1])
        btn.setStyleSheet(f"background-color: rgb({btn.colour_val[0]},{btn.colour_val[1]},{btn.colour_val[2]}); border: 1px solid #777; color: white;")
        btn.clicked.connect(lambda: self.pick_colour(btn))
        return btn

    def pick_colour(self, btn):
        c = QColorDialog.getColor(QColor(*btn.colour_val), self)
        if c.isValid():
            btn.colour_val = [c.red(), c.green(), c.blue()]
            btn.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); border: 1px solid #777; color: white;")

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        gen_group = QGroupBox("General & Background")
        gen_lay = QFormLayout(gen_group)
        self.chk_title = QCheckBox("Show Clock Header"); self.chk_title.setChecked(self.c_cfg.get("show_title_bar", False))
        
        bg_lay = QHBoxLayout()
        self.btn_bg_col = self.make_colour_btn(("bg_colour", [15, 15, 20]))
        self.btn_bg_col.setText("Solid BG Colour")
        self.btn_bg_col.setFixedWidth(120)
        
        self.txt_bg_img = QLineEdit(self.c_cfg.get("bg_image", ""))
        self.txt_bg_img.setPlaceholderText("Path to .png or .jpg BG")
        
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_image)
        
        bg_lay.addWidget(self.btn_bg_col); bg_lay.addWidget(QLabel(" OR ")); bg_lay.addWidget(self.txt_bg_img); bg_lay.addWidget(btn_browse)
        gen_lay.addRow("", self.chk_title); gen_lay.addRow("Background:", bg_lay)
        main_layout.addWidget(gen_group)

        face_group = QGroupBox("Clock Settings")
        face_lay = QFormLayout(face_group)
        self.cmb_face = QComboBox(); self.cmb_face.addItems(["Digital", "Analog"])
        self.cmb_face.setCurrentText(self.c_cfg.get("face_type", "Digital"))
        self.chk_24h = QCheckBox("Use 24h (Digital Only)"); self.chk_24h.setChecked(self.c_cfg.get("use_24h", True))
        self.chk_date = QCheckBox("Show Date"); self.chk_date.setChecked(self.c_cfg.get("show_date", True))
        self.cmb_date_fmt = QComboBox(); self.cmb_date_fmt.addItems(["%A, %B %d", "%Y-%m-%d", "%d/%m/%Y"])
        self.cmb_date_fmt.setCurrentText(self.c_cfg.get("date_format", "%A, %B %d"))
        
        face_lay.addRow("Face Type:", self.cmb_face)
        face_lay.addRow("", self.chk_24h)
        face_lay.addRow("", self.chk_date)
        face_lay.addRow("Date Format:", self.cmb_date_fmt)
        main_layout.addWidget(face_group)

        # Digital Specific
        self.dig_w = QGroupBox("Digital Positioning, Size & Colours")
        dig_lay = QFormLayout(self.dig_w)
        self.btn_dig_col = self.make_colour_btn(("clock_colour", [0, 255, 255]))
        self.btn_dat_col_dig = self.make_colour_btn(("date_colour", [200, 200, 200]))
        
        self.spn_dig_sz = QSpinBox(); self.spn_dig_sz.setRange(10, 100); self.spn_dig_sz.setValue(self.c_cfg.get("digital_size", 40))
        self.spn_dig_x = QSpinBox(); self.spn_dig_x.setRange(0, 320); self.spn_dig_x.setValue(self.c_cfg.get("digital_x", 40))
        self.spn_dig_y = QSpinBox(); self.spn_dig_y.setRange(0, 240); self.spn_dig_y.setValue(self.c_cfg.get("digital_y", 90))
        
        self.spn_dat_sz = QSpinBox(); self.spn_dat_sz.setRange(10, 100); self.spn_dat_sz.setValue(self.c_cfg.get("date_size", 20))
        self.spn_dat_x = QSpinBox(); self.spn_dat_x.setRange(0, 320); self.spn_dat_x.setValue(self.c_cfg.get("date_x", 60))
        self.spn_dat_y = QSpinBox(); self.spn_dat_y.setRange(0, 240); self.spn_dat_y.setValue(self.c_cfg.get("date_y", 150))
        
        dig_lay.addRow("Clock Colour:", self.btn_dig_col)
        dig_lay.addRow("Clock Settings:", self.create_sxy_widget(self.spn_dig_sz, self.spn_dig_x, self.spn_dig_y))
        dig_lay.addRow("Date Colour:", self.btn_dat_col_dig)
        dig_lay.addRow("Date Settings:", self.create_sxy_widget(self.spn_dat_sz, self.spn_dat_x, self.spn_dat_y))
        main_layout.addWidget(self.dig_w)

        # Analog Specific
        self.ana_w = QGroupBox("Analog Hand Colours")
        ana_lay = QFormLayout(self.ana_w)
        self.btn_hr_col = self.make_colour_btn(("hour_colour", [0, 255, 255]))
        self.btn_min_col = self.make_colour_btn(("min_colour", [0, 255, 255]))
        self.btn_sec_col = self.make_colour_btn(("sec_colour", [255, 50, 50]))
        self.btn_face_col = self.make_colour_btn(("face_colour", [15, 15, 20]))
        self.btn_out_col = self.make_colour_btn(("outline_colour", [100, 100, 100]))
        self.btn_dat_col_ana = self.make_colour_btn(("date_colour", [150, 150, 150]))
        
        ana_lay.addRow("Hour Hand:", self.btn_hr_col)
        ana_lay.addRow("Minute Hand:", self.btn_min_col)
        ana_lay.addRow("Second Hand:", self.btn_sec_col)
        ana_lay.addRow("Clock Face BG:", self.btn_face_col)
        ana_lay.addRow("Face Outline:", self.btn_out_col)
        ana_lay.addRow("Date Colour:", self.btn_dat_col_ana)
        main_layout.addWidget(self.ana_w)

        main_layout.addStretch()
        self.cmb_face.currentTextChanged.connect(self.toggle_views)
        self.toggle_views(self.cmb_face.currentText())

    def browse_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Images (*.png *.jpg *.jpeg)")
        if f: self.txt_bg_img.setText(f)

    def create_sxy_widget(self, sp_sz, sp_x, sp_y):
        w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(0,0,0,0)
        l.addWidget(QLabel("Size:")); l.addWidget(sp_sz)
        l.addWidget(QLabel("X:")); l.addWidget(sp_x)
        l.addWidget(QLabel("Y:")); l.addWidget(sp_y)
        l.addStretch()
        return w

    def toggle_views(self, text):
        self.dig_w.setVisible(text == "Digital")
        self.ana_w.setVisible(text == "Analog")

    def get_data(self):
        return {
            "show_title_bar": self.chk_title.isChecked(), "bg_image": self.txt_bg_img.text(), "bg_colour": self.btn_bg_col.colour_val,
            "face_type": self.cmb_face.currentText(), "use_24h": self.chk_24h.isChecked(), 
            "show_date": self.chk_date.isChecked(), "date_format": self.cmb_date_fmt.currentText(),
            "clock_colour": self.btn_dig_col.colour_val, "date_colour": self.btn_dat_col_dig.colour_val if self.cmb_face.currentText() == "Digital" else self.btn_dat_col_ana.colour_val,
            "digital_size": self.spn_dig_sz.value(), "digital_x": self.spn_dig_x.value(), "digital_y": self.spn_dig_y.value(), 
            "date_size": self.spn_dat_sz.value(), "date_x": self.spn_dat_x.value(), "date_y": self.spn_dat_y.value(),
            "hour_colour": self.btn_hr_col.colour_val, "min_colour": self.btn_min_col.colour_val, "sec_colour": self.btn_sec_col.colour_val,
            "face_colour": self.btn_face_col.colour_val, "outline_colour": self.btn_out_col.colour_val
        }
    
class ImageViewerTabWidget(QWidget):
    def __init__(self, iv_cfg, parent=None):
        super().__init__(parent)
        self.iv_cfg = iv_cfg
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)
        
        folder_lay = QHBoxLayout()
        self.txt_folder = QLineEdit(self.iv_cfg.get("folder_path", ""))
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_folder)
        folder_lay.addWidget(self.txt_folder); folder_lay.addWidget(self.btn_browse)
        
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Static", "Slideshow"])
        self.cmb_mode.setCurrentText(self.iv_cfg.get("mode", "Slideshow"))
        
        self.spn_interval = QSpinBox()
        self.spn_interval.setRange(1, 3600)
        self.spn_interval.setValue(self.iv_cfg.get("interval", 5))
        self.spn_interval.setSuffix(" seconds")
        
        layout.addRow("Image Folder:", folder_lay)
        layout.addRow("Display Mode:", self.cmb_mode)
        layout.addRow("Slideshow Interval:", self.spn_interval)
        
    def browse_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if f: self.txt_folder.setText(f)

    def get_data(self):
        return {
            "folder_path": self.txt_folder.text(),
            "mode": self.cmb_mode.currentText(),
            "interval": self.spn_interval.value()
        }

class BacklightTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        info_lbl = QLabel(
            "<h3>Backlight Adjuster Screen</h3>"
            "<p>The Backlight Adjuster allows you to modify the keyboard LEDs using the D-Pad.</p>"
            "<p><b>Note:</b> Because LED settings are tied to your hardware M-Keys, you must configure the default colours and brightness inside the <b>Profile</b> tabs above.</p>"
            "<p>Use the Live Preview on the right to see how this app looks on the LCD.</p>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(info_lbl)
        layout.addStretch()

# ==========================================
# [5] MAIN CONFIGURATOR WINDOW
# ==========================================
class G19Configurator(QWidget):
    def __init__(self):
        super().__init__()
        self.config = None
        self.sensor_rows = []
        self.profile_widgets = []
        self.available_sensors = self.get_system_sensors()
        self.init_ui()
        self.load_config_to_ui()

    def get_system_sensors(self):
        """Dynamically scans the Linux system for available hardware sensors."""
        sensors = ["CPU Load", "CPU Freq", "RAM Load", "Network - Download", "Network - Upload", 
                   "NVIDIA - Core Temp", "NVIDIA - Core Load", "NVIDIA - VRAM Load",
                   "NVIDIA - Core Clock", "NVIDIA - VRAM Clock", "NVIDIA - Power Draw"]
        
        try: # 1. Individual CPU Cores
            num_cores = psutil.cpu_count(logical=True) or 4
            for i in range(num_cores):
                sensors.append(f"CPU Core {i+1} Load")
                sensors.append(f"CPU Core {i+1} Freq")
        except: pass

        try: # 2. Physical Storage & ZFS
            valid_fs = ['ext2', 'ext3', 'ext4', 'fat', 'fat16', 'fat32', 'vfat', 'exfat', 'ntfs', 'xfs', 'btrfs', 'zfs']
            seen_devices = set()
            partitions = sorted(psutil.disk_partitions(all=False), key=lambda p: len(p.mountpoint))
            for part in partitions:
                fstype = part.fstype.lower()
                is_zfs = (fstype == 'zfs')
                if fstype not in valid_fs: continue
                if not part.device.startswith('/dev/') and not is_zfs: continue
                if '/dev/loop' in part.device: continue
                
                device_id = part.device.split('/')[0] if is_zfs else part.device
                if device_id in seen_devices: continue
                seen_devices.add(device_id)
                sensors.append(f"Storage Usage - {part.mountpoint}")
        except: pass

        try: # 3. Hardware Temps
            temps = psutil.sensors_temperatures()
            for hw_name, entries in temps.items():
                for i, entry in enumerate(entries):
                    label = entry.label if entry.label else f"Sensor {i+1}"
                    sensors.append(f"{hw_name} - {label}")
        except: pass
        
        try: # 4. Motherboard Fans and Voltages
            import json, subprocess
            sensors_out = subprocess.check_output(["sensors", "-j"], text=True, stderr=subprocess.DEVNULL)
            sensors_data = json.loads(sensors_out)
            for adapter, blocks in sensors_data.items():
                for block_name, block_data in blocks.items():
                    if type(block_data) is dict:
                        for key in block_data.keys():
                            if key.endswith("_input"):
                                clean_name = key.replace("_input", "")
                                sensors.append(f"{adapter} - {clean_name}")
        except: pass

        try: # 5. Universal AMD / Intel GPU Load Scanning
            if os.path.exists('/sys/class/drm/'):
                for card in os.listdir('/sys/class/drm/'):
                    if card.startswith('card') and not '-' in card:
                        busy_path = f"/sys/class/drm/{card}/device/gpu_busy_percent"
                        if os.path.exists(busy_path):
                            sensors.append(f"GPU {card} - Core Load")
        except: pass
        
        return sensors

    def init_ui(self):
        self.setWindowTitle("G19FullControl Configurator V1.1")
        self.resize(1300, 600)
        self.main_layout = QHBoxLayout(self)

        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.sync_preview_tab) 
        self.left_layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 Save Config to Hardware")
        self.save_button.setStyleSheet("background-color: #2a5a2a; color: white; font-weight: bold; padding: 5px;")
        self.save_button.clicked.connect(self.save_ui_to_config)
        
        self.reload_button = QPushButton("🔄 Reload from Hardware")
        self.reload_button.setStyleSheet("background-color: #2a2a5a; color: white; font-weight: bold; padding: 5px;")
        self.reload_button.clicked.connect(lambda: self.load_config_to_ui(force_reload_file=True))
        
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.reload_button)
        self.left_layout.addLayout(btn_layout)
        
        self.preview_widget = LCDPreviewWidget(AVAILABLE_SCREENS, self)
        
        self.main_layout.addWidget(self.left_widget, stretch=2)
        self.main_layout.addWidget(self.preview_widget, stretch=1)
        self.setLayout(self.main_layout)

    def sync_preview_tab(self, index):
        tab_name = self.tabs.tabText(index)
        if "Hardware Monitor" in tab_name: self.preview_widget.set_screen_by_name("Hardware Monitor")
        elif "Clock" in tab_name: self.preview_widget.set_screen_by_name("Clock")
        elif "Image Viewer" in tab_name: self.preview_widget.set_screen_by_name("Image Viewer")
        elif "Profile" in tab_name or "Backlight" in tab_name: self.preview_widget.set_screen_by_name("Backlight Adjuster")

    def _get_default_config(self):
        """Failsafe template if config.json is deleted."""
        return {
            "hardware": {"vendor_id": "0x046d", "product_id": "0xc229"},
            "profiles": [
                {"name": "Profile 1", "description": "Default", "m_led_mask": 128, "backlight_color": [255, 50, 50], "backlight_brightness": 100, "g_key_map": {}},
                {"name": "Profile 2", "description": "", "m_led_mask": 64, "backlight_color": [50, 255, 50], "backlight_brightness": 100, "g_key_map": {}},
                {"name": "Profile 3", "description": "", "m_led_mask": 32, "backlight_color": [50, 50, 255], "backlight_brightness": 100, "g_key_map": {}}
            ],
            "screens": {
                "hw_monitor": {"show_title_bar": True, "title_text": "Hardware Monitor", "sensor_list": []},
                "clock": {"face_type": "Digital", "show_date": True, "use_24h": True},
                "image_viewer": {"mode": "Slideshow", "interval": 5}
            }
        }
    
    def load_config_to_ui(self, force_reload_file=True):
        if force_reload_file:
            try:
                with open(CONFIG_PATH, 'r') as f: self.config = json.load(f)
            except Exception: 
                print("No config found or corrupted. Generating fresh default config.")
                self.config = self._get_default_config()
                os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
                try:
                    with open(CONFIG_PATH, 'w') as f: json.dump(self.config, f, indent=4)
                except Exception as e: print(f"Failed to save default config: {e}")

        if not self.config: return

        saved_tab_index = self.tabs.currentIndex()
        self.tabs.clear()
        self.profile_widgets.clear()
        self.sensor_rows.clear()

        # --- Profiles Tab (M1, M2, M3) ---
        for i, profile in enumerate(self.config['profiles']):
            if profile.get('name') == "MR (Macro Recorder)": continue 
            
            p_tab = QWidget()
            p_lay = QVBoxLayout(p_tab) 
            
            header_group = QGroupBox(f"M{i+1} Configuration")
            header_lay = QVBoxLayout(header_group)
            
            nd_lay = QFormLayout()
            txt_name = QLineEdit(profile.get('name', f"Profile {i+1}")); txt_name.setObjectName("prof_name")
            txt_desc = QLineEdit(profile.get('description', "")); txt_desc.setObjectName("prof_desc")
            nd_lay.addRow("Profile Name:", txt_name)
            nd_lay.addRow("Description:", txt_desc)
            header_lay.addLayout(nd_lay)
            
            ctrl_lay = QHBoxLayout()
            btn_imp = QPushButton("⬇ Import"); btn_imp.clicked.connect(lambda checked, idx=i: self.import_profile(idx))
            btn_exp = QPushButton("⬆ Export"); btn_exp.clicked.connect(lambda checked, idx=i: self.export_profile(idx))
            btn_clr = QPushButton("🗑 Clear G-Keys"); btn_clr.setStyleSheet("background-color: #5a2a2a; color: white;")
            btn_clr.clicked.connect(lambda checked, pt=p_tab: self.clear_profile_gkeys(pt))
            
            ctrl_lay.addWidget(btn_imp); ctrl_lay.addWidget(btn_exp); ctrl_lay.addWidget(btn_clr)
            ctrl_lay.addWidget(QLabel("   |   Backlight:"))
            
            btn_col = QPushButton("Colour")
            prof_col = profile.get('backlight_color', [255, 255, 255])
            tc = "black" if (prof_col[0] * 0.299 + prof_col[1] * 0.587 + prof_col[2] * 0.114) > 128 else "white"
            btn_col.setStyleSheet(f"background-color: rgb({prof_col[0]},{prof_col[1]},{prof_col[2]}); color: {tc}; border: 1px solid #777;")
            btn_col.clicked.connect(lambda checked, idx=i, b=btn_col: self.open_profile_color_picker(idx, b))
            ctrl_lay.addWidget(btn_col)
            
            bri_spn = QSpinBox(); bri_spn.setRange(0, 100); bri_spn.setSuffix("%")
            bri_spn.setValue(profile.get('backlight_brightness', 100)); bri_spn.setObjectName("brightness_spinner")
            ctrl_lay.addWidget(QLabel("Brightness:")); ctrl_lay.addWidget(bri_spn)
            ctrl_lay.addStretch()
            
            header_lay.addLayout(ctrl_lay)
            p_lay.addWidget(header_group)
            
            gmap = profile.get('g_key_map', {})
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            g_container = QWidget()
            g_layout = QVBoxLayout(g_container)
            
            for g in range(1, 13):
                key_code = str(57 + g)
                row_widget = GKeyRowWidget(g, gmap.get(key_code, ""), g_container)
                row_widget.setObjectName(f"gkey_row_{key_code}") 
                g_layout.addWidget(row_widget)
                
            g_layout.addStretch()
            scroll.setWidget(g_container)
            p_lay.addWidget(scroll)

            self.tabs.addTab(p_tab, f"M{i+1}")
            self.profile_widgets.append(p_tab)


        # --- Hardware Monitor Tab ---
        hw_tab = QWidget()
        hw_layout = QVBoxLayout(hw_tab)
        hw_cfg = self.config.get('screens', {}).get('hw_monitor', {})

        ei_lay = QHBoxLayout()
        btn_import = QPushButton("⬇ Import Layout"); btn_import.clicked.connect(self.import_hw_layout)
        btn_export = QPushButton("⬆ Export Layout"); btn_export.clicked.connect(self.export_hw_layout)
        btn_clear = QPushButton("🗑 Clear All Sensors"); btn_clear.setStyleSheet("background-color: #5a2a2a; color: white;")
        btn_clear.clicked.connect(self.clear_all_sensors)
        ei_lay.addWidget(btn_import); ei_lay.addWidget(btn_export); ei_lay.addWidget(btn_clear); ei_lay.addStretch()
        hw_layout.addLayout(ei_lay)

        hw_gen_group = QGroupBox("General & Header Settings")
        hw_gen_lay = QVBoxLayout(hw_gen_group)

        l1 = QHBoxLayout()
        self.chk_title = QCheckBox("Top Title Bar"); self.chk_title.setChecked(hw_cfg.get("show_title_bar", True))
        self.txt_title = QLineEdit(hw_cfg.get("title_text", "")); self.txt_title.setPlaceholderText("Custom Title Text")
        l1.addWidget(self.chk_title); l1.addWidget(self.txt_title)
        hw_gen_lay.addLayout(l1)

        l2 = QHBoxLayout()
        self.btn_bg_col = QPushButton("Solid BG Colour")
        self.bg_colour = hw_cfg.get("bg_colour", [15, 15, 20])
        self.btn_bg_col.setStyleSheet(f"background-color: rgb({self.bg_colour[0]},{self.bg_colour[1]},{self.bg_colour[2]}); color: white; border: 1px solid #777;")
        self.btn_bg_col.setFixedWidth(120)
        self.btn_bg_col.clicked.connect(self.pick_hw_bg_colour)
        self.txt_bg_img = QLineEdit(hw_cfg.get("bg_image", "")); self.txt_bg_img.setPlaceholderText("Path to .png or .jpg BG")
        btn_browse = QPushButton("Browse..."); btn_browse.clicked.connect(self.browse_image)
        l2.addWidget(self.btn_bg_col); l2.addWidget(QLabel(" OR ")); l2.addWidget(self.txt_bg_img); l2.addWidget(btn_browse)
        hw_gen_lay.addLayout(l2)

        l3 = QHBoxLayout()
        self.chk_hw_clock = QCheckBox("Enable Clock"); self.chk_hw_clock.setChecked(hw_cfg.get("show_clock", False))
        self.chk_hw_clock_24h = QCheckBox("24hr"); self.chk_hw_clock_24h.setChecked(hw_cfg.get("clock_24h", True))
        self.spn_hw_clock_sz = QSpinBox(); self.spn_hw_clock_sz.setRange(8, 60); self.spn_hw_clock_sz.setValue(hw_cfg.get("clock_size", 16))
        self.spn_hw_clock_x = QSpinBox(); self.spn_hw_clock_x.setRange(0, 320); self.spn_hw_clock_x.setValue(hw_cfg.get("clock_x", 250))
        self.spn_hw_clock_y = QSpinBox(); self.spn_hw_clock_y.setRange(0, 240); self.spn_hw_clock_y.setValue(hw_cfg.get("clock_y", 5))
        self.hw_clock_colour = hw_cfg.get("clock_colour", [255, 255, 255])
        self.btn_hw_clock_col = QPushButton("")
        self.btn_hw_clock_col.setStyleSheet(f"background-color: rgb({self.hw_clock_colour[0]},{self.hw_clock_colour[1]},{self.hw_clock_colour[2]}); border: 1px solid #777;")
        self.btn_hw_clock_col.setFixedWidth(40); self.btn_hw_clock_col.clicked.connect(self.pick_hw_clock_colour)
        l3.addWidget(self.chk_hw_clock); l3.addWidget(self.chk_hw_clock_24h)
        l3.addWidget(QLabel("Size:")); l3.addWidget(self.spn_hw_clock_sz)
        l3.addWidget(QLabel("X:")); l3.addWidget(self.spn_hw_clock_x)
        l3.addWidget(QLabel("Y:")); l3.addWidget(self.spn_hw_clock_y)
        l3.addWidget(QLabel("Colour:")); l3.addWidget(self.btn_hw_clock_col)
        l3.addStretch()
        hw_gen_lay.addLayout(l3)

        l4 = QHBoxLayout()
        self.chk_hw_date = QCheckBox("Enable Date"); self.chk_hw_date.setChecked(hw_cfg.get("show_date", False))
        self.cmb_hw_date_fmt = QComboBox(); self.cmb_hw_date_fmt.addItems(["%A, %B %d", "%Y-%m-%d", "%d/%m/%Y"])
        self.cmb_hw_date_fmt.setCurrentText(hw_cfg.get("date_format", "%Y-%m-%d"))
        self.spn_hw_date_sz = QSpinBox(); self.spn_hw_date_sz.setRange(8, 60); self.spn_hw_date_sz.setValue(hw_cfg.get("date_size", 12))
        self.spn_hw_date_x = QSpinBox(); self.spn_hw_date_x.setRange(0, 320); self.spn_hw_date_x.setValue(hw_cfg.get("date_x", 200))
        self.spn_hw_date_y = QSpinBox(); self.spn_hw_date_y.setRange(0, 240); self.spn_hw_date_y.setValue(hw_cfg.get("date_y", 20))
        self.hw_date_colour = hw_cfg.get("date_colour", [200, 200, 200])
        self.btn_hw_date_col = QPushButton("")
        self.btn_hw_date_col.setStyleSheet(f"background-color: rgb({self.hw_date_colour[0]},{self.hw_date_colour[1]},{self.hw_date_colour[2]}); border: 1px solid #777;")
        self.btn_hw_date_col.setFixedWidth(40); self.btn_hw_date_col.clicked.connect(self.pick_hw_date_colour)
        l4.addWidget(self.chk_hw_date); l4.addWidget(self.cmb_hw_date_fmt)
        l4.addWidget(QLabel("Size:")); l4.addWidget(self.spn_hw_date_sz)
        l4.addWidget(QLabel("X:")); l4.addWidget(self.spn_hw_date_x)
        l4.addWidget(QLabel("Y:")); l4.addWidget(self.spn_hw_date_y)
        l4.addWidget(QLabel("Colour:")); l4.addWidget(self.btn_hw_date_col)
        l4.addStretch()
        hw_gen_lay.addLayout(l4)

        hw_layout.addWidget(hw_gen_group)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.table_layout = QVBoxLayout(scroll_content)

        saved_sensor_list = hw_cfg.get("sensor_list", [])
        for hw_id in self.available_sensors:
            saved_data = {}
            for s in saved_sensor_list:
                if s.get("hw_id") == hw_id: saved_data = s; break
            row = SensorRowWidget(hw_id, saved_data, self)
            self.sensor_rows.append(row)
            self.table_layout.addWidget(row)
            
        self.table_layout.addStretch()
        scroll.setWidget(scroll_content)
        hw_layout.addWidget(scroll)
        self.tabs.addTab(hw_tab, "Hardware Monitor")

        # --- Other Screen Tabs ---
        c_cfg = self.config.get('screens', {}).get('clock', {})
        self.clock_tab_widget = ClockTabWidget(c_cfg, self)
        self.tabs.addTab(self.clock_tab_widget, "Clock Settings")

        iv_cfg = self.config.get('screens', {}).get('image_viewer', {})
        self.image_tab_widget = ImageViewerTabWidget(iv_cfg, self)
        self.tabs.addTab(self.image_tab_widget, "Image Viewer")

        self.tabs.addTab(BacklightTabWidget(self), "Backlight App")

        # Restore previous tab index
        if saved_tab_index >= 0 and saved_tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(saved_tab_index)

    def pick_hw_bg_colour(self):
        c = QColorDialog.getColor(QColor(*self.bg_colour), self)
        if c.isValid():
            self.bg_colour = [c.red(), c.green(), c.blue()]
            self.btn_bg_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: white; border: 1px solid #777;")
    def pick_hw_clock_colour(self):
        c = QColorDialog.getColor(QColor(*self.hw_clock_colour), self)
        if c.isValid():
            self.hw_clock_colour = [c.red(), c.green(), c.blue()]
            self.btn_hw_clock_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); border: 1px solid #777;")
    def pick_hw_date_colour(self):
        c = QColorDialog.getColor(QColor(*self.hw_date_colour), self)
        if c.isValid():
            self.hw_date_colour = [c.red(), c.green(), c.blue()]
            self.btn_hw_date_col.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); border: 1px solid #777;")
    def browse_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f: self.txt_bg_img.setText(f)

    def get_current_config(self):
        """Scrapes the entire GUI to construct a new JSON configuration dictionary."""
        if not self.config: return None
        new_config = copy.deepcopy(self.config)

        try:
            for i, p_tab in enumerate(self.profile_widgets):
                if i >= len(new_config['profiles']): break
                
                name_box = p_tab.findChild(QLineEdit, "prof_name")
                if name_box: new_config['profiles'][i]['name'] = name_box.text()
                
                desc_box = p_tab.findChild(QLineEdit, "prof_desc")
                if desc_box: new_config['profiles'][i]['description'] = desc_box.text()
                
                spn = p_tab.findChild(QSpinBox, "brightness_spinner")
                if spn: new_config['profiles'][i]['backlight_brightness'] = spn.value()

                new_gmap = {}
                for g in range(1, 13):
                    key_code = str(57 + g)
                    row_widget = p_tab.findChild(GKeyRowWidget, f"gkey_row_{key_code}")
                    if row_widget:
                        data = row_widget.get_data()
                        if data: new_gmap[key_code] = data
                new_config['profiles'][i]['g_key_map'] = new_gmap

            if 'screens' not in new_config: new_config['screens'] = {}
            
            # Hardware Monitor Tab
            if hasattr(self, 'txt_bg_img'):
                if 'hw_monitor' not in new_config['screens']: new_config['screens']['hw_monitor'] = {}
                new_config['screens']['hw_monitor']['bg_image'] = self.txt_bg_img.text()
                new_config['screens']['hw_monitor']['bg_colour'] = self.bg_colour
                new_config['screens']['hw_monitor']['show_title_bar'] = self.chk_title.isChecked()
                new_config['screens']['hw_monitor']['title_text'] = self.txt_title.text()
                
                new_config['screens']['hw_monitor']['show_clock'] = self.chk_hw_clock.isChecked()
                new_config['screens']['hw_monitor']['clock_24h'] = self.chk_hw_clock_24h.isChecked()
                new_config['screens']['hw_monitor']['clock_size'] = self.spn_hw_clock_sz.value()
                new_config['screens']['hw_monitor']['clock_x'] = self.spn_hw_clock_x.value()
                new_config['screens']['hw_monitor']['clock_y'] = self.spn_hw_clock_y.value()
                new_config['screens']['hw_monitor']['clock_colour'] = self.hw_clock_colour

                new_config['screens']['hw_monitor']['show_date'] = self.chk_hw_date.isChecked()
                new_config['screens']['hw_monitor']['date_format'] = self.cmb_hw_date_fmt.currentText()
                new_config['screens']['hw_monitor']['date_size'] = self.spn_hw_date_sz.value()
                new_config['screens']['hw_monitor']['date_x'] = self.spn_hw_date_x.value()
                new_config['screens']['hw_monitor']['date_y'] = self.spn_hw_date_y.value()
                new_config['screens']['hw_monitor']['date_colour'] = self.hw_date_colour

                new_config['screens']['hw_monitor']['sensor_list'] = [row.get_data() for row in self.sensor_rows]

            # Standard Tabs
            if hasattr(self, 'clock_tab_widget'): new_config['screens']['clock'] = self.clock_tab_widget.get_data()
            if hasattr(self, 'image_tab_widget'): new_config['screens']['image_viewer'] = self.image_tab_widget.get_data()

        except AttributeError:
            pass

        return new_config
    
    def export_profile(self, index):
        cur_cfg = self.get_current_config()
        if not cur_cfg: return
        prof_data = cur_cfg['profiles'][index]
        f, _ = QFileDialog.getSaveFileName(self, f"Export Profile {index+1}", f"g19_profile_m{index+1}.json", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'w') as file: json.dump(prof_data, file, indent=4)
                print(f"SUCCESS: Exported Profile to {f}")
            except Exception as e: print(f"ERROR: Export Failed: {e}")

    def import_profile(self, index):
        f, _ = QFileDialog.getOpenFileName(self, f"Import Profile to M{index+1}", "", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'r') as file: imported_data = json.load(file)
                if "g_key_map" in imported_data:
                    current_ui_state = self.get_current_config()
                    if current_ui_state: self.config = current_ui_state
                    
                    preserved_mask = self.config['profiles'][index]['m_led_mask']
                    self.config['profiles'][index] = imported_data
                    self.config['profiles'][index]['m_led_mask'] = preserved_mask
                    
                    self.load_config_to_ui(force_reload_file=False)
                    self.tabs.setCurrentIndex(index)
                    print(f"SUCCESS: Imported Profile. Click 'Save Config' to apply.")
            except Exception as e: print(f"ERROR: Import Failed: {e}")

    def clear_profile_gkeys(self, p_tab):
        for g in range(1, 13):
            key_code = str(57 + g)
            row_widget = p_tab.findChild(GKeyRowWidget, f"gkey_row_{key_code}")
            if row_widget:
                row_widget.txt_input.setText("")
                row_widget.txt_note.setText("")
                row_widget.macro_data = None
                row_widget.on_text_changed("")

    def save_ui_to_config(self):
        self.config = self.get_current_config()
        if not self.config: return
        try:
            with open(CONFIG_PATH, 'w') as f: json.dump(self.config, f, indent=4)
            print("SUCCESS: Config saved.")
        except Exception as e: print(f"ERROR: {e}")

    def open_profile_color_picker(self, idx, btn):
        current_color = self.config['profiles'][idx]['backlight_color']
        c = QColorDialog.getColor(QColor(*current_color), self)
        if c.isValid(): 
            new_color = [c.red(), c.green(), c.blue()]
            self.config['profiles'][idx]['backlight_color'] = new_color
            
            tc = "black" if (c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114) > 128 else "white"
            btn.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); color: {tc}; border: 1px solid #777;")

    def export_hw_layout(self):
        cur_cfg = self.get_current_config()
        if not cur_cfg: return
        hw_data = cur_cfg.get('screens', {}).get('hw_monitor', {})
        f, _ = QFileDialog.getSaveFileName(self, "Export Hardware Monitor Layout", "", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'w') as file: json.dump(hw_data, file, indent=4)
                print(f"SUCCESS: Exported layout to {f}")
            except Exception as e: print(f"ERROR: Export Failed: {e}")

    def import_hw_layout(self):
        f, _ = QFileDialog.getOpenFileName(self, "Import Hardware Monitor Layout", "", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'r') as file: imported_data = json.load(file)
                if "sensor_list" in imported_data:
                    current_ui_state = self.get_current_config()
                    if current_ui_state: self.config = current_ui_state
                        
                    if "screens" not in self.config: self.config["screens"] = {}
                    self.config["screens"]["hw_monitor"] = imported_data
                    
                    self.load_config_to_ui(force_reload_file=False)
                    self.tabs.setCurrentIndex(1)
                    print(f"SUCCESS: Imported layout from {f}. Click 'Save Config' to apply.")
                else: print("ERROR: Invalid Layout File.")
            except Exception as e: print(f"ERROR: Import Failed: {e}")

    def clear_all_sensors(self):
        for row in self.sensor_rows:
            row.chk_enable.setChecked(False)
            if row.is_expanded: row.toggle_expanded()
        print("All sensors cleared from UI.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    configurator = G19Configurator()
    configurator.show()
    sys.exit(app.exec())