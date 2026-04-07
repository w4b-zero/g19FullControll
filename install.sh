#!/bin/bash
# "install.sh" V1.3

echo "--- G19FullControl Installer ---"

# Ensure the script is run with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "FATAL: Please run this installer with sudo: sudo ./install.sh" 
    exit 1 
fi

# Get the actual user who ran sudo
REAL_USER=${SUDO_USER:-$USER} 
USER_HOME=$(eval echo ~$REAL_USER) 
USER_UID=$(id -u $REAL_USER)

echo "[1/6] Installing required dependencies..." 
apt update 
apt install -y python3-usb python3-psutil python3-pil python3-evdev python3-pyqt6 playerctl

echo "[2/6] Configuring Udev permissions (USB & uinput)..."
# Add user to the input group for evdev/uinput access
usermod -aG input $REAL_USER

# Write USB rules for the Logitech G19
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="046d", ATTR{idProduct}=="c229", MODE="0666"' > /etc/udev/rules.d/99-g19.rules

# Write Virtual Keyboard rules
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' > /etc/udev/rules.d/99-uinput.rules

# Reload Udev rules
udevadm control --reload-rules && udevadm trigger

echo "[3/6] Creating application directories in /opt/G19FullControl..." 
mkdir -p /opt/G19FullControl 
cp g19_daemon.py /opt/G19FullControl/ 
cp g19_screens.py /opt/G19FullControl/ 
cp g19_configurator.py /opt/G19FullControl/

# Copy the icon if it exists
if [ -f "g19_icon.png" ]; then 
    cp g19_icon.png /opt/G19FullControl/ 
    echo "Custom icon found and copied." 
fi

chmod +x /opt/G19FullControl/*.py

echo "[4/6] Creating Desktop Shortcut (App Menu Integration)..." 
cat << 'EOF' > /usr/share/applications/g19configurator.desktop
[Desktop Entry]
Version=1.0
Name=G19 Configurator
Comment=Configure your Logitech G19 Keyboard
Exec=/usr/bin/python3 /opt/G19FullControl/g19_configurator.py
Icon=/opt/G19FullControl/g19_icon.png
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
EOF

chmod 644 /usr/share/applications/g19configurator.desktop

echo "[5/6] Setting up the background Daemon..." 
mkdir -p $USER_HOME/.config/systemd/user/

cat << 'EOF' > $USER_HOME/.config/systemd/user/g19daemon.service
[Unit]
Description=G19FullControl Hardware Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/G19FullControl/g19_daemon.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

chown -R $REAL_USER:$REAL_USER $USER_HOME/.config/systemd/user/

echo "[6/6] Reloading and starting the service for user: $REAL_USER..."
# Export the XDG_RUNTIME_DIR so systemctl --user works inside a sudo script
su - $REAL_USER -c "export XDG_RUNTIME_DIR=/run/user/$USER_UID; systemctl --user daemon-reload" 
su - $REAL_USER -c "export XDG_RUNTIME_DIR=/run/user/$USER_UID; systemctl --user enable g19daemon.service" 
su - $REAL_USER -c "export XDG_RUNTIME_DIR=/run/user/$USER_UID; systemctl --user restart g19daemon.service"

echo ""
echo "--- INSTALLATION COMPLETE! ---" 
echo "IMPORTANT: You MUST reboot your PC (or log out and back in) for the new keyboard permissions to take effect!"
echo "You can now find 'G19 Configurator' in your app menu."
