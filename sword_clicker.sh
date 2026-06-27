#!/bin/bash

# Configuration for Mending Sword Clicker (Raid Farm / Mob Farm)
CLICK_INTERVAL=1.0         # Time in seconds between attacks (1.0s ensures full cooldown/sweeping reset)
PRE_START_DELAY=5          # Seconds to wait before starting

# Check if xdotool is installed
if ! command -v xdotool &> /dev/null; then
    echo "[-] Error: xdotool is not installed."
    echo "    Install it using: sudo apt-get install xdotool"
    exit 1
fi

# Cleanup function to release the mouse when the script is stopped
cleanup() {
    echo -e "\n[+] Stopping autoclicker and releasing mouse..."
    xdotool mouseup 1
    exit 0
}

# Trap Ctrl+C (SIGINT) and SIGTERM to run the cleanup function
trap cleanup INT TERM

echo "[+] Minecraft Mending Sword Clicker Started"
echo "[+] --- Settings ---"
echo "    - Attack Interval: $CLICK_INTERVAL seconds (Left-Clicks Only)"
echo "    - Durability: Infinite (relying on Mending / XP drops)"
echo "[+] Starting in $PRE_START_DELAY seconds. Switch to Minecraft now!"

# Countdown
for ((i=PRE_START_DELAY; i>0; i--)); do
    echo "    Starting in $i..."
    sleep 1
done

echo "[+] Active! Press Ctrl+C in this terminal to stop."

while true; do
    # Click left mouse button
    xdotool click 1
    sleep "$CLICK_INTERVAL"
done
