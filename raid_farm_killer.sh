#!/bin/bash

# Configuration for Raid Farm with Iron Swords
HOTBAR_SLOTS=(1 2 3 z x c v b r) # Custom hotbar layout in order
DURABILITY=250             # Iron sword durability (number of hits)
CLICK_INTERVAL=1.0         # Time in seconds between attacks (1.0s ensures full cooldown reset)

DELAY_BETWEEN_SWITCH=0.2   # Delay in seconds when switching weapons
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

echo "[+] Minecraft Raid Farm Left-Click Sword Switcher Started"
echo "[+] Hotbar slots to cycle: ${HOTBAR_SLOTS[*]}"
echo "[+] --- Settings ---"
echo "    - Iron Sword Durability: $DURABILITY hits"
echo "    - Attack Interval      : $CLICK_INTERVAL seconds (Left-Clicks Only)"
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
        
        # Release left-click before switching slots
        xdotool mouseup 1
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Press the slot key
        xdotool key "$slot"
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Attack 250 times with this sword
        for ((click=1; click<=DURABILITY; click++)); do
            echo -ne "    Attacking $click/$DURABILITY...\r"
            
            # Click left mouse button (1)
            xdotool click 1
            sleep "$CLICK_INTERVAL"
        done
        echo -e "\n[+] Slot $slot sword used up! Moving to next slot."
    done
done
