#!/bin/bash

# Configuration
BUTTON=1                   # Mouse button: 1 = Left Click, 3 = Right Click
CPS=10                     # Clicks per second
PRE_START_DELAY=5          # Seconds to wait before starting

# Check if xdotool is installed
if ! command -v xdotool &> /dev/null; then
    echo "[-] Error: xdotool is not installed."
    echo "    Install it using: sudo apt-get install xdotool"
    exit 1
fi

DELAY=$(echo "scale=4; 1 / $CPS" | bc -l)

echo "[+] Minecraft Autoclicker Started"
echo "[+] Target Button: $BUTTON (1 = Left, 3 = Right)"
echo "[+] Speed: $CPS clicks per second (delay: ${DELAY}s)"
echo "[+] Starting in $PRE_START_DELAY seconds. Switch to Minecraft now!"

# Countdown
for ((i=PRE_START_DELAY; i>0; i--)); do
    echo "    Starting in $i..."
    sleep 1
done

echo "[+] Active! Press Ctrl+C in this terminal to stop."

while true; do
    xdotool click $BUTTON
    sleep $DELAY
done
