Testfiles - Not Stable! use original Repository from https://github.com/markes12344/g19FullControll !!

# G19FullControl for Linux 🐧⌨️

**G19FullControl** is a complete, open-source Linux replacement for the legacy Logitech Gaming Software. Built from the ground up in Python, it breathes new life into the iconic Logitech G19 keyboard on modern Linux distributions (X11 & Wayland).

It features a lightweight background hardware daemon and a powerful PyQt6 GUI configurator.

![G19FullControl GUI](https://via.placeholder.com/800x400.png?text=G19FullControl+GUI+Screenshot)

## ✨ Key Features

* **Universal Hardware Monitor:** Dynamically polls AMD, Intel, and NVIDIA hardware (Temps, Loads, Fans, Voltages, and Water-cooling Flow Rates) via `psutil`, `lm-sensors`, and `sysfs`.
* **Hardware Macro Recorder (MR):** Use the physical MR key to record keystrokes and timing delays directly to your hardware profile. Injects directly into the Linux Kernel via `evdev` (100% Wayland & X11 compatible).
* **Live LCD Operating System:** Navigate through built-in LCD apps using the keyboard's physical D-Pad.
    * 📊 **Dashboard:** Custom gauges, bar graphs, and line graphs for your PC hardware.
    * 🕒 **Clock:** Analog and Digital faces with custom backgrounds and colours.
    * 🎨 **Backlight Adjuster:** Change your keyboard RGB colours and brightness directly from the LCD.
    * 🎵 **Media Player:** Native `dbus`/`playerctl` integration to show Spotify/Firefox "Now Playing" metadata.
    * 🖼️ **Image Viewer:** Slideshow or static image gallery.
* **Profiles & RGB:** Save up to 3 hardware profiles (M1, M2, M3) with independent macros, LED masks, and RGB backlight colours.
* **Hot-Reloading:** The Daemon instantly detects when you save a profile in the Configurator and pushes the changes directly to the keyboard without needing to restart.

## 📦 Dependencies

To run this software, you will need Python 3 and a few system packages. 

**System Packages (Debian/Ubuntu):**
```bash
sudo apt install python3-pip python3-pyqt6 lm-sensors playerctl
```

**Python PIP Libraries:**
```bash
pip3 install pyusb psutil pillow evdev
```

## 🚀 Installation & Setup

We have included a 1-click install script to handle permissions and setup for you. 

1. Clone or download this repository.
2. Open a terminal in the downloaded folder.
3. Make the installer executable: `chmod +x install.sh`
4. Run the installer: `./install.sh`

### Manual Permissions (If running without the install script)
Because this software communicates directly with USB hardware and injects keystrokes, it requires specific permissions to run without `sudo`.

**1. USB Permissions (PyUSB)**
Create a udev rule to allow access to the Logitech G19:
```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="046d", ATTR{idProduct}=="c229", MODE="0666"' | sudo tee /etc/udev/rules.d/99-g19.rules
```

**2. Virtual Keyboard Permissions (evdev/uinput)**
Create a rule to allow the Macro engine to inject keystrokes:
```bash
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | sudo tee /etc/udev/rules.d/99-uinput.rules
```
*Note: Make sure your Linux user is added to the `input` group! (`sudo usermod -aG input $USER`)*

Reload your udev rules and unplug/replug your keyboard:
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 🛠️ Usage

### 1. The Daemon (`g19_daemon.py`)
The Daemon is the brain of the operation. It must be running in the background for your LCD, RGB, and Macros to function. (If you used the install script, this likely runs automatically on login as a `systemd` service).

To run it manually for testing:
```bash
python3 g19_daemon.py
```

### 2. The Configurator (`g19_configurator.py`)
This is the PyQt6 Desktop GUI. Use this to assign macros, change colours, and build your custom LCD Hardware Monitor layout.

To launch the GUI:
```bash
python3 g19_configurator.py
```
*Configuration files are safely stored in your home directory at `~/.config/G19FullControl/config.json`.*

## 💡 Advanced Macros
Macros are saved inside the Configurator. You can simply type a linux terminal command (like `firefox` or `pavucontrol`) to have a G-Key launch an app. 

Alternatively, if you use the physical **MR** key to record a macro, the Configurator will display it as a JSON Array. You can manually edit these JSON strings for millisecond-perfect timing!
```json
[{"action": "down", "key": "w", "delay": 0.0}, {"action": "up", "key": "w", "delay": 0.15}]
```

## 📝 License
This project is open-source and free to use, modify, and distribute.
