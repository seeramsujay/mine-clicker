#!/bin/bash

# Configuration
HOTBAR_SLOTS=(1 2 3 z x c v b r) # The hotbar slots to cycle through (custom: 1, 2, 3, z, x, c, v, b, r)
MINE_DURATION=15           # How many seconds to mine with each tool before switching
DELAY_BETWEEN_SWITCH=0.2   # Delay in seconds when switching tools
PRE_START_DELAY=5          # Seconds to wait before starting so you can switch to Minecraft

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

echo "[+] Minecraft Cobblestone Generator Miner & Tool Switcher Started"
echo "[+] Hotbar slots to cycle: ${HOTBAR_SLOTS[*]}"
echo "[+] Mining time per slot: ${MINE_DURATION} seconds"
echo "[+] Starting in $PRE_START_DELAY seconds. Switch to Minecraft now!"

# Countdown
for ((i=PRE_START_DELAY; i>0; i--)); do
    echo "    Starting in $i..."
    sleep 1
done

echo "[+] Active! Press Ctrl+C in this terminal to stop."

while true; do
    for slot in "${HOTBAR_SLOTS[@]}"; do
        echo "[+] Switching to hotbar slot $slot..."
        
        # Release mouse before switching slots (just in case)
        xdotool mouseup 1
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Press the slot key (1-9)
        xdotool key "$slot"
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Start holding down left click (mousedown 1)
        echo "[+] Mining with slot $slot for $MINE_DURATION seconds..."
        xdotool mousedown 1
        
        # Sleep for the duration of mining
        sleep "$MINE_DURATION"
    done
done
