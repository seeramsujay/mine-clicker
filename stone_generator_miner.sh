#!/bin/bash

# Configuration for Custom Cobblestone Generator with Stone Pickaxe
HOTBAR_SLOTS=(1 2 3 z x c v b r) # Custom hotbar layout in order
DURABILITY=131             # Stone pickaxe durability (number of uses)

# Cycle Timings
MINE_TIME=1              # Time in seconds to hold click (breaks 1 block; stone pickaxe takes 0.75s)
REGEN_TIME=2            # Time in seconds to wait for cobblestone to reform/lava to flow

DELAY_BETWEEN_SWITCH=0.2   # Delay in seconds when switching tools
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

echo "[+] Minecraft Tailored Cobblestone Generator Miner Started"
echo "[+] Hotbar slots to cycle: ${HOTBAR_SLOTS[*]}"
echo "[+] --- The Math & Timing ---"
echo "    - Mining Hold Time: $MINE_TIME seconds (to break 1 block)"
echo "    - Regeneration Wait: $REGEN_TIME seconds"
echo "    - Total Cycle Time: $(echo "$MINE_TIME + $REGEN_TIME" | bc -l) seconds"
echo "    - Blocks per Pickaxe: $DURABILITY (switches slots after $DURABILITY blocks)"
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
        
        # Release mouse before switching slots
        xdotool mouseup 1
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Press the slot key
        xdotool key "$slot"
        sleep "$DELAY_BETWEEN_SWITCH"
        
        # Mine 131 blocks with this tool
        for ((block=1; block<=DURABILITY; block++)); do
            echo -ne "    Mining block $block/$DURABILITY...\r"
            
            # Start holding down left click
            xdotool mousedown 1
            sleep "$MINE_TIME"
            
            # Release click and wait for cobblestone to reform
            xdotool mouseup 1
            sleep "$REGEN_TIME"
        done
        echo -e "\n[+] Slot $slot tool used up! Moving to next slot."
    done
done
