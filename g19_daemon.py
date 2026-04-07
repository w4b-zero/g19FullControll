# "g19_daemon.py" V6.1

# G19FullControl Hardware Daemon
# This script runs in the background. It communicates directly with the Logitech G19 hardware 
# via USB (PyUSB), polls system sensors (psutil, lm-sensors, sysfs), and handles Wayland-compatible 
# macro injections (evdev).

import os
import usb.core
import usb.util
import asyncio
import subprocess
import time
import psutil
from PIL import Image, ImageDraw
import json
import evdev
from evdev import UInput, ecodes
from g19_screens import AVAILABLE_SCREENS, MainMenuScreen

# ==========================================
# [1] CORE CONFIGURATION & CONSTANTS
# ==========================================
CONFIG_PATH = os.path.expanduser("~/.config/G19FullControl/config.json")

# L-Key (D-Pad) Hardware Bitmasks mapped to integer values
G19_L_LEFT   = 32
G19_L_RIGHT  = 16
G19_L_UP     = 128
G19_L_DOWN   = 64
G19_L_OK     = 8
G19_L_CANCEL = 2
G19_L_MENU   = 4

# HDATA: The magic 512-byte header required by the G19 LCD before sending image data.
# This tells the internal display controller to expect a new 320x240 RGB565 frame.
HDATA = bytes([
    0x10, 0x0f, 0x00, 0x58, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3f,
    0x01, 0xef, 0x00, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23,
    0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x3b,
    0x3c, 0x3d, 0x3e, 0x3f, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
    0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x50, 0x51, 0x52, 0x53,
    0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b, 0x5c, 0x5d, 0x5e, 0x5f,
    0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x6b,
    0x6c, 0x6d, 0x6e, 0x6f, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77,
    0x78, 0x79, 0x7a, 0x7b, 0x7c, 0x7d, 0x7e, 0x7f, 0x80, 0x81, 0x82, 0x83,
    0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x8b, 0x8c, 0x8d, 0x8e, 0x8f,
    0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0x9b,
    0x9c, 0x9d, 0x9e, 0x9f, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7,
    0xa8, 0xa9, 0xaa, 0xab, 0xac, 0xad, 0xae, 0xaf, 0xb0, 0xb1, 0xb2, 0xb3,
    0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xbb, 0xbc, 0xbd, 0xbe, 0xbf,
    0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xcb,
    0xcc, 0xcd, 0xce, 0xcf, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7,
    0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde, 0xdf, 0xe0, 0xe1, 0xe2, 0xe3,
    0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xeb, 0xec, 0xed, 0xee, 0xef,
    0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb,
    0xfc, 0xfd, 0xfe, 0xff, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13,
    0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b,
    0x2c, 0x2d, 0x2e, 0x2f, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f, 0x40, 0x41, 0x42, 0x43,
    0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b,
    0x5c, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67,
    0x68, 0x69, 0x6a, 0x6b, 0x6c, 0x6d, 0x6e, 0x6f, 0x70, 0x71, 0x72, 0x73,
    0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x7b, 0x7c, 0x7d, 0x7e, 0x7f,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x8b,
    0x8c, 0x8d, 0x8e, 0x8f, 0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97,
    0x98, 0x99, 0x9a, 0x9b, 0x9c, 0x9d, 0x9e, 0x9f, 0xa0, 0xa1, 0xa2, 0xa3,
    0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xab, 0xac, 0xad, 0xae, 0xaf,
    0xb0, 0xb1, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xbb,
    0xbc, 0xbd, 0xbe, 0xbf, 0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7,
    0xc8, 0xc9, 0xca, 0xcb, 0xcc, 0xcd, 0xce, 0xcf, 0xd0, 0xd1, 0xd2, 0xd3,
    0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde, 0xdf,
    0xe0, 0xe1, 0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xeb,
    0xec, 0xed, 0xee, 0xef, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7,
    0xf8, 0xf9, 0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff
])

# Global Runtime States
current_profile_index = 0
current_screen_index = 0
is_in_menu = True
menu_selection_index = 0
SYSTEM_CACHE = {} # Stores polled hardware stats to prevent LCD display lag

# Macro Recorder (MR) States
mr_state = 0 # 0: Off, 1: Waiting for G-Key Target, 2: Actively Recording
mr_target = None
mr_events = []
mr_last_time = 0
mr_flash_task = None


# ==========================================
# [2] EVDEV & KEYBOARD SNIFFER SETUP
# ==========================================
# Create a virtual keyboard. This allows us to inject keypresses directly into the Linux 
# input subsystem, bypassing display server restrictions (Works natively on Wayland & X11).
VIRTUAL_KB = None
try:
    VIRTUAL_KB = UInput(name="FullControl Emitter")
    print("Virtual Keyboard Engine Online (evdev).")
except Exception as ex:
    print(f"Warning: Could not create Virtual Keyboard. {ex}")

# Automatically find the physical G19 typing interface so we can sniff keys for the Macro Recorder
physical_kb = None
for path in evdev.list_devices():
    dev = evdev.InputDevice(path)
    # Target only the specific G19 interface that supports standard letter keys (like 'A')
    if "G19" in dev.name and "Virtual" not in dev.name and "Emitter" not in dev.name:
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if ecodes.KEY_A in caps:
            physical_kb = dev
            break

if physical_kb: 
    print(f"Hardware MR Sniffer attached to: {physical_kb.name}")
else:
    print("WARNING: Could not find physical QWERTY G19 keyboard for MR Sniffer!")

# Mapping dictionary for JSON macro text strings to Linux ecodes
KEY_MAP = {
    'a': ecodes.KEY_A, 'b': ecodes.KEY_B, 'c': ecodes.KEY_C, 'd': ecodes.KEY_D, 'e': ecodes.KEY_E, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G, 
    'h': ecodes.KEY_H, 'i': ecodes.KEY_I, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L, 'm': ecodes.KEY_M, 'n': ecodes.KEY_N, 
    'o': ecodes.KEY_O, 'p': ecodes.KEY_P, 'q': ecodes.KEY_Q, 'r': ecodes.KEY_R, 's': ecodes.KEY_S, 't': ecodes.KEY_T, 'u': ecodes.KEY_U, 
    'v': ecodes.KEY_V, 'w': ecodes.KEY_W, 'x': ecodes.KEY_X, 'y': ecodes.KEY_Y, 'z': ecodes.KEY_Z, '1': ecodes.KEY_1, '2': ecodes.KEY_2, 
    '3': ecodes.KEY_3, '4': ecodes.KEY_4, '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7, '8': ecodes.KEY_8, '9': ecodes.KEY_9, 
    '0': ecodes.KEY_0, 'space': ecodes.KEY_SPACE, 'ctrl': ecodes.KEY_LEFTCTRL, 'shift': ecodes.KEY_LEFTSHIFT, 'alt': ecodes.KEY_LEFTALT,
    'tab': ecodes.KEY_TAB, 'enter': ecodes.KEY_ENTER, 'esc': ecodes.KEY_ESC, 'backspace': ecodes.KEY_BACKSPACE
}


# ==========================================
# [3] HELPER FUNCTIONS & USB PROTOCOLS
# ==========================================
def load_config():
    """Safely loads and returns the user's config.json file."""
    if not os.path.exists(CONFIG_PATH):
        print(f"FATAL: Config file not found at {CONFIG_PATH}")
        return None
    try:
        with open(CONFIG_PATH, 'r') as f: return json.load(f)
    except Exception as e:
        print(f"FATAL: Error loading config file: {e}")
        return None

def set_mkey_led(dev, mask):
    """Sends a USB control transfer to turn on specific M1/M2/M3/MR LEDs."""
    try:
        # bmRequestType: 0x21 (Host to Device), bRequest: 0x09 (Set Report), wValue: 0x0305
        dev.ctrl_transfer(0x21, 0x09, 0x0305, 1, [0x10, mask])
    except Exception as e:
        print(f"Warning: Could not set M-key LED: {e}")

def set_backlight_color(dev, color_list, brightness=100):
    """Calculates requested brightness and sends an RGB control transfer to the keyboard."""
    try:
        r = int(color_list[0] * (brightness / 100.0))
        g = int(color_list[1] * (brightness / 100.0))
        b = int(color_list[2] * (brightness / 100.0))
        # bmRequestType: 0x21 (Host to Device), bRequest: 0x09 (Set Report), wValue: 0x0307
        dev.ctrl_transfer(0x21, 0x09, 0x0307, 1, [255, r, g, b])
    except Exception as e:
        print(f"Warning: Could not set backlight colour: {e}")

def image_to_g19_bytes(img):
    """
    Converts a standard Pillow image (RGB888) into the native G19 format (RGB565).
    In RGB565, 16 bits define a pixel: Red(5 bits), Green(6 bits), Blue(5 bits).
    """
    img = img.resize((320, 240)).convert('RGB')
    pixels = img.load()
    data = bytearray(153600) # 320 * 240 * 2 bytes per pixel
    idx = 0
    for x in range(320):
        for y in range(240):
            r, g, b = pixels[x, y]
            # Bitshift math to crush RGB888 down to RGB565 format
            color_val = ((r // 8) << 11) | ((g // 4) << 5) | (b // 8)
            data[idx] = color_val & 0xFF
            data[idx+1] = (color_val >> 8) & 0xFF
            idx += 2
    return data


# ==========================================
# [4] ASYNC ENGINES & LOOPS
# ==========================================
async def execute_macro(macro_array):
    """Executes a list of keystrokes with precision timing using evdev."""
    if not VIRTUAL_KB: return
    for event in macro_array:
        delay = event.get("delay", 0)
        if delay > 0: await asyncio.sleep(delay)
        
        ecode = KEY_MAP.get(event.get("key", ""))
        if ecode:
            # 1 = Key Down, 0 = Key Up
            VIRTUAL_KB.write(ecodes.EV_KEY, ecode, 1 if event.get("action") == "down" else 0)
            VIRTUAL_KB.syn()

async def hardware_key_sniffer():
    """Listens directly to the physical keyboard. Active ONLY during MR Recording (State 2)."""
    global mr_state, mr_events, mr_last_time
    if not physical_kb: return
    try:
        async for event in physical_kb.async_read_loop():
            # Only track key-down (1) and key-up (0), ignore auto-repeat OS holds (2)
            if event.type == ecodes.EV_KEY and mr_state == 2:
                if event.value == 2: continue 
                
                key_code_str = evdev.ecodes.KEY.get(event.code, "")
                if isinstance(key_code_str, list): key_code_str = key_code_str[0]
                if not isinstance(key_code_str, str) or not key_code_str.startswith("KEY_"): continue
                
                now = time.time()
                action = "down" if event.value == 1 else "up"
                key_name = key_code_str.replace("KEY_", "").lower()
                
                print(f"Hardware MR Sniffer Recorded: {key_name} {action}")
                mr_events.append({"action": action, "key": key_name, "delay": round(now - mr_last_time, 3)})
                mr_last_time = now
    except Exception as ex: 
        print(f"Hardware Sniffer Error: {ex}")

async def flash_mr_led(pyusb_dev, config):
    """Flashes the MR / M-Key LEDs to guide the user through the Macro Recording states."""
    global mr_state, current_profile_index
    toggle = False
    
    while mr_state > 0:
        try:
            base_mask = config['profiles'][current_profile_index]['m_led_mask']
            # State 1: Flashing the current Profile M-Key
            if mr_state == 1: mask = base_mask if toggle else 0
            # State 2: Flashing the MR Key (Hardware Mask = 16)
            elif mr_state == 2: mask = 16 if toggle else 0
                
            set_mkey_led(pyusb_dev, mask)
        except Exception: pass
            
        toggle = not toggle
        await asyncio.sleep(0.3)
        
    # State 0: Recording finished/cancelled. Restore normal solid M-key LED.
    try: set_mkey_led(pyusb_dev, config['profiles'][current_profile_index]['m_led_mask'])
    except Exception: pass

async def config_watcher_loop(pyusb_dev, config):
    """Watches config.json for GUI saves and hot-reloads the daemon in real-time."""
    global current_profile_index
    print("Config Watcher Online.")
    last_mtime = os.path.getmtime(CONFIG_PATH)

    while True:
        await asyncio.sleep(1) 
        try:
            current_mtime = os.path.getmtime(CONFIG_PATH)
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                print("\n--- Config Change Detected! Hot-Reloading... ---")
                
                new_config = load_config()
                if new_config:
                    config.clear()
                    config.update(new_config)
                    # Push updated lighting directly to hardware instantly
                    active_prof = config['profiles'][current_profile_index]
                    set_mkey_led(pyusb_dev, active_prof['m_led_mask'])
                    set_backlight_color(pyusb_dev, active_prof['backlight_color'], active_prof.get('backlight_brightness', 100))
        except Exception as e:
            print(f"Watcher Error: {e}")

async def hardware_polling_loop():
    """
    Polls heavy system sensors (GPU, Fans, Network) and caches them to prevent LCD lag.
    Universally supports Intel, AMD, and NVIDIA hardware safely.
    """
    global SYSTEM_CACHE
    print("Hardware Polling Engine Online.")
    
    last_net = psutil.net_io_counters()
    last_time = time.time()
    
    while True:
        # 1. NVIDIA GPU Polling (Via proprietary CLI tool)
        try:
            out = subprocess.check_output(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,clocks.gr,clocks.mem,power.draw", "--format=csv,noheader,nounits"], text=True)
            vals = out.strip().split(', ')
            if len(vals) == 6:
                SYSTEM_CACHE["NVIDIA - Core Temp"] = float(vals[0])
                SYSTEM_CACHE["NVIDIA - Core Load"] = float(vals[1])
                SYSTEM_CACHE["NVIDIA - VRAM Load"] = float(vals[2])
                SYSTEM_CACHE["NVIDIA - Core Clock"] = float(vals[3])
                SYSTEM_CACHE["NVIDIA - VRAM Clock"] = float(vals[4])
                SYSTEM_CACHE["NVIDIA - Power Draw"] = float(vals[5])
        except Exception: pass

        # 2. Universal Motherboard/CPU/GPU Sensors (Via lm-sensors)
        # Note: This naturally picks up AMD Ryzen (k10temp), Intel Core (coretemp), 
        # and AMD Radeon GPUs (amdgpu) for temperatures, fans, and power automatically!
        try:
            sensors_out = subprocess.check_output(["sensors", "-j"], text=True, stderr=subprocess.DEVNULL)
            sensors_data = json.loads(sensors_out)
            for adapter, blocks in sensors_data.items():
                for block_name, block_data in blocks.items():
                    if type(block_data) is dict:
                        for key, val in block_data.items():
                            if key.endswith("_input"):
                                clean_name = key.replace("_input", "")
                                SYSTEM_CACHE[f"{adapter} - {clean_name}"] = float(val)
        except Exception: pass

        # 3. AMD GPU & Intel Integrated GPU Load (Via standard Linux Kernel SysFS)
        try:
            # Scan for all active DRM rendering cards
            if os.path.exists('/sys/class/drm/'):
                for card in os.listdir('/sys/class/drm/'):
                    if card.startswith('card') and not '-' in card:
                        busy_path = f"/sys/class/drm/{card}/device/gpu_busy_percent"
                        if os.path.exists(busy_path):
                            with open(busy_path, 'r') as f:
                                # Saves as "GPU card0 - Core Load" for example
                                SYSTEM_CACHE[f"GPU {card} - Core Load"] = float(f.read().strip())
        except Exception: pass
        
        # 4. Global Network Delta Calculation
        try:
            now = time.time()
            dt = now - last_time
            net = psutil.net_io_counters()
            SYSTEM_CACHE["Network - Download"] = (net.bytes_recv - last_net.bytes_recv) / dt
            SYSTEM_CACHE["Network - Upload"] = (net.bytes_sent - last_net.bytes_sent) / dt
            last_net = net
            last_time = now
        except Exception: pass
            
        await asyncio.sleep(2.0) # Rest to prevent CPU spiking

async def display_loop(lcd_endpoint, config):
    """Continuously draws the active screen (or OS Menu) to a Pillow Image and pushes to USB."""
    global current_screen_index, current_profile_index, is_in_menu, menu_selection_index
    print("Display Engine Online.")

    main_menu = MainMenuScreen(AVAILABLE_SCREENS)
    
    while True:
        if lcd_endpoint:
            try:
                # 1. Determine which screen to draw
                if is_in_menu: dashboard_img = main_menu.draw(menu_selection_index)
                else:
                    active_screen = AVAILABLE_SCREENS[current_screen_index]
                    active_profile_name = config['profiles'][current_profile_index]['name']
                    dashboard_img = active_screen.draw(active_profile_name, config, live_data=SYSTEM_CACHE)

                # 2. Convert to hardware bytes and prepend the Magic Header
                image_bytes = image_to_g19_bytes(dashboard_img)
                final_payload = HDATA + image_bytes
                
                # 3. Blast the frame to the LCD bulk endpoint
                lcd_endpoint.write(final_payload, timeout=100)
            except usb.core.USBError as e:
                # 110 is the standard USB timeout error, safely ignore it.
                if e.errno != 110: print(f"Display write error: {e}")
                await asyncio.sleep(1)

        await asyncio.sleep(0.05) # Targeting roughly 20 FPS

async def input_loop(pyusb_dev, mkey_ep, lkey_ep, config):
    """Listens to physical interrupt endpoints for G-Keys, M-Keys, and L-Keys."""
    global current_profile_index, current_screen_index, is_in_menu, menu_selection_index
    global mr_state, mr_target, mr_events, mr_last_time 
    print("Input Engine Online. Listening for G/M/L keys...")

    while True:
        # --- [A] READ M & G KEYS (Endpoint 0x83) ---
        try:
            report = mkey_ep.read(8, timeout=10) 
            if report:
                report_id = report[0]

                # Report ID 2 represents the Profile cluster (M1, M2, M3, MR)
                if report_id == 2:
                    mkey_byte = report[2]
                    
                    # --- MR KEY LOGIC ---
                    if mkey_byte == 128:
                        if VIRTUAL_KB: # Pulse Esc to cancel any ongoing OS tasks safely
                            VIRTUAL_KB.write(ecodes.EV_KEY, ecodes.KEY_ESC, 1); VIRTUAL_KB.syn()
                            VIRTUAL_KB.write(ecodes.EV_KEY, ecodes.KEY_ESC, 0); VIRTUAL_KB.syn()
                            
                        if mr_state == 0:
                            mr_state = 1
                            print("MR State 1: Flashing... Press a target G-Key.")
                            global mr_flash_task
                            if mr_flash_task and not mr_flash_task.done(): mr_flash_task.cancel()
                            mr_flash_task = asyncio.create_task(flash_mr_led(pyusb_dev, config))
                            
                        elif mr_state == 1:
                            mr_state = 0 
                            print("MR State: Cancelled.")
                        elif mr_state == 2:
                            mr_state = 0
                            print(f"MR State: Saved Macro to G{mr_target}!")
                            if mr_target:
                                prof = config['profiles'][current_profile_index]
                                gmap = prof.setdefault('g_key_map', {})
                                existing_note = gmap.get(mr_target, {}).get("note", "") if isinstance(gmap.get(mr_target), dict) else ""
                                gmap[mr_target] = {"action": mr_events, "note": existing_note}
                                with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=4)
                        continue
                    
                    # --- PROFILE SWITCHING (M1/M2/M3) ---
                    new_profile = -1
                    if mkey_byte == 16: new_profile = 0   
                    elif mkey_byte == 32: new_profile = 1 
                    elif mkey_byte == 64: new_profile = 2 

                    if new_profile != -1 and new_profile != current_profile_index and new_profile < len(config['profiles']):
                        if mr_state > 0: continue # Block switching while recording a macro
                        current_profile_index = new_profile
                        print(f"--- Profile switched to {config['profiles'][current_profile_index].get('name', 'M')} ---")
                        set_mkey_led(pyusb_dev, config['profiles'][current_profile_index]['m_led_mask']) 
                        set_backlight_color(pyusb_dev, config['profiles'][current_profile_index]['backlight_color'], config['profiles'][current_profile_index].get('backlight_brightness', 100))

                # Report ID 3 represents the Macro Bank (G1 - G12)
                elif report_id == 3:
                    gkey_code = report[1]
                    if gkey_code != 0:
                        gkey_str = str(gkey_code)
                        
                        # Set Target for Macro Recorder
                        if mr_state == 1:
                            mr_target = gkey_str
                            mr_state = 2
                            mr_events = []
                            mr_last_time = time.time()
                            print(f"MR State 2: Recording Keystrokes for G{gkey_str}...")
                            continue
                        
                        # Normal Playback
                        if mr_state == 0:
                            active_map = config['profiles'][current_profile_index].get('g_key_map', {})
                            if gkey_str in active_map:
                                data = active_map[gkey_str]
                                action = data.get("action") if isinstance(data, dict) else data

                                if isinstance(action, str) and action:
                                    print(f"Executing Shell Command: {action}")
                                    subprocess.Popen(action.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                elif isinstance(action, list):
                                    print(f"Executing Virtual Macro: G{gkey_str}")
                                    asyncio.create_task(execute_macro(action))

        except usb.core.USBError as err:
            if err.errno != 110: print(f"M/G Key USB Error: {err}")
        except Exception as err:
            print(f"M/G Key Error: {err}")

        # --- [B] READ L-KEYS (Endpoint 0x81) ---
        try:
            l_report = lkey_ep.read(2, timeout=10) 
            if l_report:
                lkey_byte = l_report[0]

                if lkey_byte != 0:
                    # --- MENU TOGGLE ---
                    if lkey_byte == G19_L_MENU:
                        if not is_in_menu:
                            active_screen = AVAILABLE_SCREENS[current_screen_index]
                            if active_screen.name == "Backlight Adjuster":
                                try:
                                    with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=4)
                                    print("Saved new backlight settings to config.json.")
                                except Exception as e: print(f"Error saving config: {e}")
                                
                        is_in_menu = not is_in_menu
                        print(f"L-Key: Menu | Menu Active: {is_in_menu}")
                    
                    # --- OS MENU SCROLLING ---
                    elif is_in_menu:
                        if lkey_byte == G19_L_UP: menu_selection_index = (menu_selection_index - 1) % len(AVAILABLE_SCREENS)
                        elif lkey_byte == G19_L_DOWN: menu_selection_index = (menu_selection_index + 1) % len(AVAILABLE_SCREENS)
                        elif lkey_byte == G19_L_OK:
                            current_screen_index = menu_selection_index
                            is_in_menu = False
                            print(f"L-Key: OK | Screen switched to {AVAILABLE_SCREENS[current_screen_index].name}")

                            # Pre-load the current profile's lighting when opening the Backlight App
                            active_screen = AVAILABLE_SCREENS[current_screen_index]
                            if active_screen.name == "Backlight Adjuster":
                                current_col = config['profiles'][current_profile_index]['backlight_color']
                                current_bri = config['profiles'][current_profile_index].get('backlight_brightness', 100)
                                active_screen.r, active_screen.g, active_screen.b = current_col
                                active_screen.brightness = current_bri
                    
                    # --- APP SPECIFIC L-PAD INPUT ---
                    else:
                        active_screen = AVAILABLE_SCREENS[current_screen_index]
                        
                        # Hardware Clock Face Toggle
                        if active_screen.name == "Clock" and lkey_byte in [G19_L_LEFT, G19_L_RIGHT]:
                            c_cfg = config.setdefault('screens', {}).setdefault('clock', {})
                            current_face = c_cfg.get('face_type', 'Digital')
                            c_cfg['face_type'] = "Analog" if current_face == "Digital" else "Digital"
                            try:
                                with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=4)
                            except Exception: pass
                            
                        # Standard App Inputs (Passes through to current Screen Class)
                        if hasattr(active_screen, 'handle_input'):
                            active_screen.handle_input(lkey_byte)
                            
                            # Physical Hardware Hook for Backlight App (Instant USB pushing)
                            if active_screen.name == "Backlight Adjuster" and lkey_byte in [G19_L_LEFT, G19_L_RIGHT]:
                                new_col = [active_screen.r, active_screen.g, active_screen.b]
                                set_backlight_color(pyusb_dev, new_col, active_screen.brightness)
                                config['profiles'][current_profile_index]['backlight_color'] = new_col
                                config['profiles'][current_profile_index]['backlight_brightness'] = active_screen.brightness

        except usb.core.USBError as err:
            if err.errno != 110: print(f"L-Key USB Error: {err}")
        except Exception as err:
            print(f"L-Key Error: {err}")

        await asyncio.sleep(0.01)


# ==========================================
# [5] DAEMON BOOT SEQUENCE
# ==========================================
async def main():
    global current_profile_index
    
    config = load_config()
    if not config: return 

    G19_VENDOR_ID = int(config['hardware']['vendor_id'], 16)
    G19_PRODUCT_ID = int(config['hardware']['product_id'], 16)
    
    pyusb_dev = None
    print("--- G19FullControl Daemon V6.1 Starting ---")

    try:
        # Find the physical keyboard via PyUSB
        pyusb_dev = usb.core.find(idVendor=G19_VENDOR_ID, idProduct=G19_PRODUCT_ID)
        if pyusb_dev is None:
            print("FATAL: G19 USB device not found.")
            return

        # Detach default OS drivers so we can control the hardware directly
        for i in [0, 1]:
            if pyusb_dev.is_kernel_driver_active(i):
                try:
                    pyusb_dev.detach_kernel_driver(i)
                except Exception as e:
                    print(f"WARNING: Could not detach from interface {i}: {e}")

        pyusb_dev.set_configuration()
        cfg = pyusb_dev.get_active_configuration()

        # Interface 0: Claim LCD Display (0x02) and L-Keys (0x81)
        usb.util.claim_interface(pyusb_dev, 0)
        intf0 = cfg[(0,0)]
        lcd_endpoint = usb.util.find_descriptor(intf0, bEndpointAddress=0x02)
        lkey_ep = usb.util.find_descriptor(intf0, bEndpointAddress=0x81) 

        # Interface 1: Claim M-Keys and G-Keys (0x83)
        usb.util.claim_interface(pyusb_dev, 1)
        mkey_ep = usb.util.find_descriptor(cfg[(1,0)], bEndpointAddress=0x83)

        if None in (lcd_endpoint, mkey_ep, lkey_ep):
            print("FATAL: Could not find all necessary USB endpoints.")
            return
        
        print("SUCCESS: All Interfaces Claimed.")

        # Initialize lights dynamically from config for the starting profile
        initial_color = config['profiles'][current_profile_index]['backlight_color']
        initial_mask = config['profiles'][current_profile_index]['m_led_mask']
        initial_bri = config['profiles'][current_profile_index].get('backlight_brightness', 100)
        set_mkey_led(pyusb_dev, initial_mask)
        set_backlight_color(pyusb_dev, initial_color, initial_bri)

        print("--- All Systems Go! ---")
        
        # Fire up all asynchronous tasks concurrently
        await asyncio.gather(
            display_loop(lcd_endpoint, config),
            input_loop(pyusb_dev, mkey_ep, lkey_ep, config),
            config_watcher_loop(pyusb_dev, config),
            hardware_polling_loop(),
            hardware_key_sniffer()
        )

    except PermissionError:
        print("FATAL: Permission denied. Please run with 'sudo' or check Udev rules.")
    except usb.core.USBError as e:
        print(f"FATAL USB Error during setup: {e}")
    except KeyboardInterrupt:
        print("\nStopping Daemon...")
    finally:
        # Graceful shutdown: release hardware back to the OS
        if pyusb_dev:
            try: usb.util.release_interface(pyusb_dev, 0)
            except: pass
            try: usb.util.release_interface(pyusb_dev, 1)
            except: pass
            try: pyusb_dev.reset()
            except: pass

if __name__ == "__main__":
    asyncio.run(main())