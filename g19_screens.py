# "g19_screens.py" V3.0

import psutil
import time
import os
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# GLOBAL RESOURCE CACHE
# ==========================================
# We load fonts into RAM once globally. This prevents massive I/O lag 
# and prevents memory leaks from duplicate font loading across different apps.
GLOBAL_FONT_CACHE = {}

def get_font(size):
    """Fetches a font from RAM, or loads it if it hasn't been used yet."""
    if size not in GLOBAL_FONT_CACHE:
        try: 
            # Primary universal Linux font
            GLOBAL_FONT_CACHE[size] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except IOError: 
            try:
                # Fallback for Arch/Fedora users
                GLOBAL_FONT_CACHE[size] = ImageFont.truetype("/usr/share/fonts/liberation/LiberationSans-Regular.ttf", size)
            except IOError:
                # Absolute fallback (looks ugly, but prevents crashing)
                GLOBAL_FONT_CACHE[size] = ImageFont.load_default()
    return GLOBAL_FONT_CACHE[size]


# ==========================================
# SCREEN: HARDWARE MONITOR
# ==========================================
class HardwareMonitorScreen:
    def __init__(self):
        self.name = "Hardware Monitor"
        self.history = {} # Stores graph data points: {'CPU Load': [10, 20, 15...]}

    def format_data(self, raw_val, fmt, hw_id):
        """Converts raw sensor values into human-readable strings (e.g., Bytes -> GB)"""
        
        # --- Automatic Context Guessing ---
        if fmt in ["Auto (%)", "Default (%)"]:
            hw_lower = hw_id.lower()
            if "temp" in hw_lower: return f"{int(raw_val)}°C", raw_val
            elif "freq" in hw_lower or "clock" in hw_lower: return f"{int(raw_val)} MHz", raw_val
            elif "power" in hw_lower: return f"{int(raw_val)} W", raw_val
            elif "fan" in hw_lower: return f"{int(raw_val)} RPM", raw_val
            elif "in" in hw_lower or "volt" in hw_lower: return f"{raw_val:.2f} V", raw_val
            else: return f"{raw_val:.1f}%", raw_val
            
        # --- Explicit Formatting Rules ---
        elif fmt == "Temp (°C)": return f"{int(raw_val)}°C", raw_val
        elif fmt == "Temp (°F)": 
            f_val = (raw_val * 9/5) + 32
            return f"{int(f_val)}°F", f_val
            
        elif fmt == "MHz": return f"{int(raw_val)} MHz", raw_val
        elif fmt == "GHz": return f"{raw_val / 1000.0:.2f} GHz", raw_val
        elif fmt == "Watts": return f"{int(raw_val)} W", raw_val
        
        # Liquid cooling / Fans / Voltage
        elif fmt == "RPM": return f"{int(raw_val)} RPM", raw_val
        elif fmt == "LPM": return f"{raw_val:.1f} L/m", raw_val
        elif fmt == "Gal/h": return f"{raw_val:.1f} Gal/h", raw_val
        elif fmt == "Volts": return f"{raw_val:.3f} V", raw_val
        elif fmt == "mV": return f"{int(raw_val * 1000)} mV", raw_val
            
        # Network Speeds (Bits)
        elif fmt == "Kbps": v = (raw_val * 8) / 1000.0; return f"{v:.1f} Kbps", v
        elif fmt == "Mbps": v = (raw_val * 8) / 1000000.0; return f"{v:.1f} Mbps", v
        elif fmt == "Gbps": v = (raw_val * 8) / 1000000000.0; return f"{v:.2f} Gbps", v
            
        # Storage/RAM (Bytes)
        elif fmt == "KB": v = raw_val / 1024.0; return f"{v:.1f} KB", v
        elif fmt == "MB": v = raw_val / (1024.0 ** 2); return f"{v:.1f} MB", v
        elif fmt == "GB": v = raw_val / (1024.0 ** 3); return f"{v:.1f} GB", v
        elif fmt == "TB": v = raw_val / (1024.0 ** 4); return f"{v:.2f} TB", v
        elif fmt == "Bytes": return f"{int(raw_val)} B", raw_val
            
        return f"{raw_val:.1f}", raw_val

    def get_live_value(self, sensor_cfg, live_data):
        """Extracts data from the Daemon's cache or polls lightweight sensors dynamically."""
        hw_id = sensor_cfg.get("hw_id", "")
        fmt = sensor_cfg.get("data_format", "Auto (%)")
        math_mult = float(sensor_cfg.get("math_mult", 1.0))
        
        data_formats = ["KB", "MB", "GB", "TB", "Bytes", "Kbps", "Mbps", "Gbps"]
        raw_val = 0.0
        
        # 1. Bypass heavy polling if we are currently in the GUI's "Live Preview" tab
        if live_data and "_IS_PREVIEW" in live_data:
            val_text, converted_val = self.format_data(50.0 * math_mult, fmt, hw_id)
            return val_text, converted_val
            
        # 2. Check the Daemon's Cache first (For heavy GPU/Sensors commands)
        if live_data and hw_id in live_data: 
            raw_val = float(live_data[hw_id])
            
        # 3. Poll lightweight System APIs dynamically via psutil
        elif hw_id == "CPU Load": 
            raw_val = psutil.cpu_percent()
        elif hw_id == "CPU Freq":
            raw_val = float(psutil.cpu_freq().current)
        elif hw_id.startswith("CPU Core ") and "Load" in hw_id:
            core_idx = int(hw_id.split(" ")[2]) - 1
            raw_val = float(psutil.cpu_percent(percpu=True)[core_idx])
        elif hw_id == "RAM Load": 
            if fmt in data_formats: raw_val = float(psutil.virtual_memory().used)
            else: raw_val = float(psutil.virtual_memory().percent)
        elif hw_id.startswith("Storage Usage - "):
            mountpoint = hw_id.replace("Storage Usage - ", "")
            try:
                usage = psutil.disk_usage(mountpoint)
                if fmt in data_formats: raw_val = float(usage.used)
                else: raw_val = float(usage.percent)
            except: pass
            
        # 4. Apply GUI Multipliers and format to string
        raw_val = raw_val * math_mult
        val_text, converted_val = self.format_data(raw_val, fmt, hw_id)
        return val_text, converted_val

    def get_max_value_text(self, sensor_cfg):
        """Calculates the absolute maximum boundary for Gauges/Graphs."""
        hw_id = sensor_cfg.get("hw_id", "")
        fmt = sensor_cfg.get("data_format", "Auto (%)")
        
        if not sensor_cfg.get("max_auto", True):
            return sensor_cfg.get("max_manual", "100")
            
        raw_max = float(sensor_cfg.get("gauge_max", 100)) # Default fallback
        
        # Auto-calculate ceilings for storage and memory
        if hw_id == "RAM Load":
            if fmt in ["KB", "MB", "GB", "TB", "Bytes"]: raw_max = float(psutil.virtual_memory().total)
            else: return "100%"
        elif hw_id.startswith("Storage Usage - "):
            mountpoint = hw_id.replace("Storage Usage - ", "")
            try:
                if fmt in ["KB", "MB", "GB", "TB", "Bytes"]: raw_max = float(psutil.disk_usage(mountpoint).total)
                else: return "100%"
            except: pass
        elif hw_id == "CPU Load" and fmt == "Auto (%)":
            return "100%"

        max_str, _ = self.format_data(raw_max, fmt, hw_id)
        return max_str

    def draw(self, profile_name, config=None, live_data=None):
        """Renders the entire Hardware Dashboard into a 320x240 RGB Image"""
        bg_color = (15, 15, 20)
        bg_image_path = ""
        hw_cfg = config.get("screens", {}).get("hw_monitor", {}) if config else {}
        
        if hw_cfg:
            bg_color = tuple(hw_cfg.get("bg_color", bg_color))
            bg_image_path = hw_cfg.get("bg_image", "")

        # Render Background
        if bg_image_path and os.path.exists(bg_image_path):
            try: img = Image.open(bg_image_path).convert('RGB').resize((320, 240))
            except: img = Image.new('RGB', (320, 240), color=bg_color)
        else:
            img = Image.new('RGB', (320, 240), color=bg_color)
            
        draw = ImageDraw.Draw(img)

        # Draw Header Bar
        show_title = hw_cfg.get("show_title_bar", True)
        if show_title:
            title_text = hw_cfg.get("title_text", self.name)
            title_bg = tuple(hw_cfg.get("title_bg", (0, 105, 140)))
            draw.rectangle([0, 0, 320, 30], fill=title_bg)
            draw.text((10, 8), title_text, font=get_font(12), fill=(255, 255, 255))

        # Draw Global Clock/Date Widget
        if hw_cfg.get("show_clock", False):
            t = time.localtime()
            c_24h = hw_cfg.get("clock_24h", True)
            time_str = time.strftime("%H:%M:%S" if c_24h else "%I:%M %p", t)
            draw.text((hw_cfg.get("clock_x", 250), hw_cfg.get("clock_y", 5)), time_str, font=get_font(hw_cfg.get("clock_size", 16)), fill=tuple(hw_cfg.get("clock_colour", [255, 255, 255])))

        if hw_cfg.get("show_date", False):
            t = time.localtime()
            date_str = time.strftime(hw_cfg.get("date_format", "%Y-%m-%d"), t)
            draw.text((hw_cfg.get("date_x", 200), hw_cfg.get("date_y", 20)), date_str, font=get_font(hw_cfg.get("date_size", 12)), fill=tuple(hw_cfg.get("date_colour", [200, 200, 200])))

        # ==================================
        # SENSOR RENDERING ENGINE
        # ==================================
        for sensor in hw_cfg.get("sensor_list", []):
            if not sensor.get("enabled", False): continue

            hw_id = sensor.get("hw_id", "")
            display_type = sensor.get("display_type", "Text Only")
            disp_colour = tuple(sensor.get("disp_colour", [50, 200, 50]))
            disp_col_high = tuple(sensor.get("disp_col_high", [255, 50, 50]))
            
            gauge_max = float(sensor.get("gauge_max", 100)) 
            high_thresh = float(sensor.get("high_thresh", 85))
            
            disp_w = sensor.get("disp_w", 100)
            disp_h = sensor.get("disp_h", 12)
            disp_x, disp_y = sensor.get("disp_x", 150), sensor.get("disp_y", 40)

            # 1. Fetch live data
            val_text, val_num = self.get_live_value(sensor, live_data)
            
            # Switch to High Threshold colour if exceeded
            active_col = disp_col_high if val_num >= high_thresh else disp_colour

            # 2. Draw Custom Label (e.g. "GPU Load")
            draw.text((sensor.get("name_x", 10), sensor.get("name_y", 40)), sensor.get("custom_name", hw_id), font=get_font(sensor.get("name_size", 12)), fill=tuple(sensor.get("name_colour", [255, 255, 255])))

            # 3. Draw Selected Graphic
            scale_pct = min(max(val_num / gauge_max, 0.0), 1.0) if gauge_max > 0 else 0.0

            if display_type == "Horizontal Bar":
                draw.rectangle([disp_x, disp_y, disp_x + disp_w, disp_y + disp_h], outline=(100, 100, 100), width=1)
                fill_w = int(scale_pct * disp_w)
                if fill_w > 1: 
                    draw.rectangle([disp_x + 1, disp_y + 1, disp_x + fill_w - 1, disp_y + disp_h - 1], fill=active_col)
                    
            elif display_type == "Vertical Bar":
                draw.rectangle([disp_x, disp_y - disp_h, disp_x + disp_w, disp_y], outline=(100, 100, 100), width=1)
                fill_h = int(scale_pct * disp_h)
                if fill_h > 1: 
                    draw.rectangle([disp_x + 1, disp_y - fill_h + 1, disp_x + disp_w - 1, disp_y - 1], fill=active_col)
                    
            elif display_type == "Line Graph":
                if hw_id not in self.history: self.history[hw_id] = []
                self.history[hw_id].append(scale_pct)
                if len(self.history[hw_id]) > disp_w: self.history[hw_id].pop(0) # Keep history matching pixel width
                
                draw.rectangle([disp_x, disp_y, disp_x + disp_w, disp_y + disp_h], outline=(50,50,50))
                if len(self.history[hw_id]) > 1:
                    points = [(disp_x + i, disp_y + disp_h - (v * disp_h)) for i, v in enumerate(self.history[hw_id])]
                    draw.line(points, fill=active_col, width=1)
                    
            elif display_type == "Needle Gauge":
                draw.arc([disp_x, disp_y, disp_x + disp_w*2, disp_y + disp_w*2], 135, 45, fill=(100,100,100), width=2)
                angle_rad = math.radians(135 + (scale_pct * 270)) # 270 degree sweeping dial
                cx, cy = disp_x + disp_w, disp_y + disp_w
                draw.line([(cx, cy), (cx + (disp_w * 0.8) * math.cos(angle_rad), cy + (disp_w * 0.8) * math.sin(angle_rad))], fill=active_col, width=2)
                
            elif display_type == "Bar Gauge":
                thick = max(2, disp_h) 
                draw.arc([disp_x, disp_y, disp_x + disp_w*2, disp_y + disp_w*2], 135, 45, fill=(50,50,50), width=thick) 
                end_angle = 135 + int(scale_pct * 270)
                if end_angle > 135: 
                    draw.arc([disp_x, disp_y, disp_x + disp_w*2, disp_y + disp_w*2], 135, min(end_angle, 405), fill=active_col, width=thick)

            # 4. Draw Readout Text
            if sensor.get("show_val", True):
                text_col = disp_col_high if (display_type == "Text Only" and val_num >= high_thresh) else tuple(sensor.get("val_colour", [255, 255, 255]))
                draw.text((sensor.get("val_x", disp_x + disp_w + 5), sensor.get("val_y", disp_y)), val_text, font=get_font(sensor.get("val_size", 12)), fill=text_col)

            # 5. Draw Max Boundary Text
            if sensor.get("show_max", False):
                max_str = self.get_max_value_text(sensor)
                draw.text((sensor.get("max_x", disp_x + disp_w + 5), sensor.get("max_y", disp_y + 15)), max_str, font=get_font(sensor.get("max_size", 10)), fill=tuple(sensor.get("max_colour", [200, 200, 200])))

        return img


# ==========================================
# SCREEN: CLOCK
# ==========================================
class ClockScreen:
    def __init__(self):
        self.name = "Clock"

    def draw(self, profile_name, config=None, live_data=None):
        c_cfg = config.get("screens", {}).get("clock", {}) if config else {}
        
        # Background Logic
        bg_colour = tuple(c_cfg.get("bg_colour", [15, 15, 20]))
        bg_image_path = c_cfg.get("bg_image", "")
        if bg_image_path and os.path.exists(bg_image_path):
            try: img = Image.open(bg_image_path).convert('RGB').resize((320, 240))
            except: img = Image.new('RGB', (320, 240), color=bg_colour)
        else:
            img = Image.new('RGB', (320, 240), color=bg_colour)
            
        draw = ImageDraw.Draw(img)

        # Draw Header
        if c_cfg.get("show_title_bar", False):
            draw.rectangle([0, 0, 320, 30], fill=(50, 50, 50))
            draw.text((10, 8), f"{self.name}", font=get_font(12), fill=(255, 255, 255))

        t = time.localtime()
        face_type = c_cfg.get("face_type", "Digital")
        show_date = c_cfg.get("show_date", True)
        date_fmt = c_cfg.get("date_format", "%A, %B %d")

        # --- DIGITAL FACE ---
        if face_type == "Digital":
            dig_col = tuple(c_cfg.get("clock_colour", [0, 255, 255]))
            dat_col = tuple(c_cfg.get("date_colour", [200, 200, 200]))
            
            time_format = "%H:%M:%S" if c_cfg.get("use_24h", True) else "%I:%M:%S %p"
            
            draw.text((c_cfg.get("digital_x", 40), c_cfg.get("digital_y", 90)), time.strftime(time_format, t), font=get_font(c_cfg.get("digital_size", 40)), fill=dig_col)
            if show_date: 
                draw.text((c_cfg.get("date_x", 60), c_cfg.get("date_y", 150)), time.strftime(date_fmt, t), font=get_font(c_cfg.get("date_size", 20)), fill=dat_col)
        
        # --- ANALOG FACE ---
        elif face_type == "Analog":
            cx, cy, r = 160, 135, 90 
            
            # Draw Face & Outline
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(c_cfg.get("face_colour", [15, 15, 20])), outline=tuple(c_cfg.get("outline_colour", [100, 100, 100])), width=2)
            
            # Draw 12 Hour Ticks
            for i in range(12):
                angle = math.radians(i * 30 - 90)
                start_x, start_y = cx + (r - 10) * math.cos(angle), cy + (r - 10) * math.sin(angle)
                end_x, end_y = cx + r * math.cos(angle), cy + r * math.sin(angle)
                draw.line([(start_x, start_y), (end_x, end_y)], fill=tuple(c_cfg.get("outline_colour", [100, 100, 100])), width=2)

            h, m, s = t.tm_hour, t.tm_min, t.tm_sec
            
            # Math: Hour Hand (Accounts for minute progression)
            h_angle = math.radians((h % 12 + m / 60) * 30 - 90)
            draw.line([(cx, cy), (cx + (r * 0.5) * math.cos(h_angle), cy + (r * 0.5) * math.sin(h_angle))], fill=tuple(c_cfg.get("hour_colour", [0, 255, 255])), width=4)
            
            # Math: Minute Hand
            m_angle = math.radians((m + s / 60) * 6 - 90)
            draw.line([(cx, cy), (cx + (r * 0.75) * math.cos(m_angle), cy + (r * 0.75) * math.sin(m_angle))], fill=tuple(c_cfg.get("min_colour", [0, 255, 255])), width=3)
            
            # Math: Second Hand
            s_angle = math.radians(s * 6 - 90)
            draw.line([(cx, cy), (cx + (r * 0.9) * math.cos(s_angle), cy + (r * 0.9) * math.sin(s_angle))], fill=tuple(c_cfg.get("sec_colour", [255, 50, 50])), width=1)
            
            # Center Pin
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255))
            
            if show_date:
                draw.text((10, 215), time.strftime(date_fmt, t), font=get_font(12), fill=tuple(c_cfg.get("date_colour", [150, 150, 150])))

        return img
    

# ==========================================
# SCREEN: BACKLIGHT ADJUSTER
# ==========================================
class BacklightScreen:
    """Allows hardware-level D-Pad manipulation of RGB keyboard lights"""
    def __init__(self):
        self.name = "Backlight Adjuster"
        self.r = 255
        self.g = 255
        self.b = 255
        self.brightness = 100
        self.selection = 0 # 0=Red, 1=Green, 2=Blue, 3=Brightness

    def handle_input(self, key_byte):
        if key_byte == 128: self.selection = (self.selection - 1) % 4 # UP
        elif key_byte == 64: self.selection = (self.selection + 1) % 4 # DOWN
        elif key_byte == 32: # LEFT (Decrease)
            if self.selection == 0: self.r = max(0, self.r - 10)
            elif self.selection == 1: self.g = max(0, self.g - 10)
            elif self.selection == 2: self.b = max(0, self.b - 10)
            elif self.selection == 3: self.brightness = max(0, self.brightness - 5)
        elif key_byte == 16: # RIGHT (Increase)
            if self.selection == 0: self.r = min(255, self.r + 10)
            elif self.selection == 1: self.g = min(255, self.g + 10)
            elif self.selection == 2: self.b = min(255, self.b + 10)
            elif self.selection == 3: self.brightness = min(100, self.brightness + 5)

    def draw(self, profile_name, config=None, live_data=None):
        # Sync with UI Configurator Live Preview automatically!
        if config:
            for prof in config.get('profiles', []):
                if prof.get('name') == profile_name:
                    c = prof.get('backlight_color', [255, 255, 255])
                    self.r, self.g, self.b = c[0], c[1], c[2]
                    self.brightness = prof.get('backlight_brightness', 100)
                    break

        img = Image.new('RGB', (320, 240), color=(15, 15, 20))
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 320, 30], fill=(50, 50, 50))
        draw.text((10, 8), self.name, font=get_font(12), fill=(255, 255, 255))
        
        # Simulated Brightness Preview Box
        prev_r = int(self.r * (self.brightness / 100.0))
        prev_g = int(self.g * (self.brightness / 100.0))
        prev_b = int(self.b * (self.brightness / 100.0))
        draw.rectangle([210, 50, 290, 190], fill=(prev_r, prev_g, prev_b), outline=(255,255,255), width=2)
        draw.text((220, 200), "Preview", font=get_font(12), fill=(200, 200, 200))

        channels = [("Red", self.r, (255, 50, 50), 255), 
                    ("Green", self.g, (50, 255, 50), 255), 
                    ("Blue", self.b, (50, 150, 255), 255),
                    ("Brightness", self.brightness, (200, 200, 200), 100)]

        start_y = 45
        for i, (name, val, col, max_val) in enumerate(channels):
            y = start_y + (i * 45)
            
            # Draw Pointer Triangle
            if i == self.selection:
                draw.polygon([(10, y+5), (20, y+10), (10, y+15)], fill=(255, 255, 255))

            draw.text((25, y), f"{name}: {val}", font=get_font(14), fill=(255, 255, 255))
            
            # Draw Progress Bar
            bar_x, bar_y, bar_w, bar_h = 25, y + 20, 150, 10
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=(100, 100, 100))
            fill_w = int((val / float(max_val)) * bar_w)
            if fill_w > 1:
                draw.rectangle([bar_x + 1, bar_y + 1, bar_x + fill_w - 1, bar_y + bar_h - 1], fill=col)

        return img
    
# ==========================================
# SCREEN: IMAGE VIEWER
# ==========================================
class ImageViewerScreen:
    def __init__(self):
        self.name = "Image Viewer"
        self.current_index = 0
        self.last_switch_time = 0
        self.image_list = []
        self.cached_folder = ""

    def handle_input(self, key_byte):
        if not self.image_list: return
        if key_byte == 32: # LEFT (Skip back)
            self.current_index = (self.current_index - 1) % len(self.image_list)
            self.last_switch_time = time.time()
        elif key_byte == 16: # RIGHT (Skip forward)
            self.current_index = (self.current_index + 1) % len(self.image_list)
            self.last_switch_time = time.time()

    def draw(self, profile_name, config=None, live_data=None):
        img = Image.new('RGB', (320, 240), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        iv_cfg = config.get("screens", {}).get("image_viewer", {}) if config else {}
        folder_path = iv_cfg.get("folder_path", "")
        mode = iv_cfg.get("mode", "Slideshow")
        interval = iv_cfg.get("interval", 5)

        # Refresh the file list if the folder changed in the Configurator
        if folder_path and folder_path != self.cached_folder and os.path.exists(folder_path):
            self.cached_folder = folder_path
            valid_ext = ('.png', '.jpg', '.jpeg')
            try:
                self.image_list = sorted([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(valid_ext)])
                self.current_index = 0
            except: self.image_list = []

        if not self.image_list:
            draw.text((80, 110), "No Images Found", font=get_font(16), fill=(255, 50, 50))
            draw.text((40, 140), "Set folder in Configurator UI", font=get_font(12), fill=(150, 150, 150))
            return img

        # Auto-advance logic
        if mode == "Slideshow" and time.time() - self.last_switch_time > interval:
            self.current_index = (self.current_index + 1) % len(self.image_list)
            self.last_switch_time = time.time()

        try:
            current_image_path = self.image_list[self.current_index]
            photo = Image.open(current_image_path).convert('RGB').resize((320, 240))
            img.paste(photo, (0,0))
        except Exception:
            draw.text((10, 110), f"Error loading image", font=get_font(12), fill=(255, 50, 50))

        return img

# ==========================================
# SCREEN: MEDIA PLAYER
# ==========================================
class MediaPlayerScreen:
    """Uses PlayerCTL to pull track data natively from Linux dbus (Spotify, Firefox, etc.)"""
    def __init__(self):
        self.name = "Media Player"
        self.cached_title = "No Media Playing"
        self.cached_artist = ""
        self.cached_album = ""
        self.cached_status = "Stopped"
        self.last_fetch = 0

    def fetch_metadata(self):
        now = time.time()
        # Only poll playerctl once per second to prevent Daemon lag
        if now - self.last_fetch < 1.0: return 
        self.last_fetch = now
        
        try:
            out = subprocess.check_output(
                ['playerctl', 'metadata', '--format', '{{title}}||{{artist}}||{{album}}||{{status}}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            
            if out:
                parts = out.split('||')
                self.cached_title = parts[0] if len(parts) > 0 and parts[0].strip() else "Unknown Title"
                self.cached_artist = parts[1] if len(parts) > 1 and parts[1].strip() else "Unknown Artist"
                self.cached_album = parts[2] if len(parts) > 2 and parts[2].strip() else ""
                self.cached_status = parts[3] if len(parts) > 3 and parts[3].strip() else "Playing"
            else:
                self.cached_title, self.cached_artist, self.cached_album, self.cached_status = "No Media Playing", "", "", "Stopped"
        except Exception:
            self.cached_title, self.cached_artist, self.cached_album, self.cached_status = "No Media Playing", "", "", "Stopped"

    def draw(self, profile_name, config=None, live_data=None):
        self.fetch_metadata()
        
        img = Image.new('RGB', (320, 240), color=(15, 15, 20))
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 320, 30], fill=(50, 50, 60))
        draw.text((10, 8), self.name, font=get_font(12), fill=(255, 255, 255))
        
        # Status Text (Green if playing, Yellow if paused/stopped)
        status_colour = (50, 255, 50) if self.cached_status == "Playing" else (255, 200, 50)
        draw.text((250, 8), self.cached_status, font=get_font(12), fill=status_colour)

        # Truncate strings with slicing [:x] to ensure they fit horizontally
        draw.text((20, 50), "Title:", font=get_font(12), fill=(150, 150, 150))
        draw.text((20, 70), self.cached_title[:28], font=get_font(20), fill=(255, 255, 255))
        
        draw.text((20, 110), "Artist:", font=get_font(12), fill=(150, 150, 150))
        draw.text((20, 130), self.cached_artist[:32], font=get_font(18), fill=(200, 200, 200))

        draw.text((20, 170), "Album:", font=get_font(10), fill=(100, 100, 100))
        draw.text((20, 185), self.cached_album[:40], font=get_font(14), fill=(150, 150, 150))

        return img

# ==========================================
# SCREEN: MAIN MENU
# ==========================================
class MainMenuScreen:
    """The Root Operating System menu. Hardcoded directly into the Daemon logic."""
    def __init__(self, screens):
        self.screens = screens

    def draw(self, selected_index):
        img = Image.new('RGB', (320, 240), color=(20, 20, 25))
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 320, 30], fill=(40, 40, 50))
        draw.text((10, 8), "Main Menu (Select App)", font=get_font(12), fill=(255, 255, 255))

        start_y = 40
        item_height = 30
        for i, screen in enumerate(self.screens):
            y = start_y + (i * item_height)
            
            # Render Selection Box
            if i == selected_index:
                draw.rectangle([10, y, 310, y + item_height - 2], fill=(0, 105, 140))
                text_col = (255, 255, 255)
            else:
                draw.rectangle([10, y, 310, y + item_height - 2], outline=(50, 50, 60))
                text_col = (150, 150, 150)
            
            draw.text((20, y + 6), screen.name, font=get_font(14), fill=text_col)
        
        # Instructions Footer
        draw.text((10, 220), "Up/Down: Scroll  |  OK: Select  |  Menu: Exit", font=get_font(10), fill=(100, 100, 100))

        return img
    
# ==========================================
# APP REGISTRY
# ==========================================
# To add a custom screen, build a Class above and add it to this list!
AVAILABLE_SCREENS = [
    HardwareMonitorScreen(), 
    ClockScreen(), 
    BacklightScreen(), 
    ImageViewerScreen(), 
    MediaPlayerScreen() 
]