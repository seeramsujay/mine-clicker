import asyncio
import json
import logging
import os
import sys
import urllib.request
from typing import Dict, Any

# Ensure the root project directory is in the Python path for clean imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Install Twisted Asyncio Reactor first before any Twisted imports
from twisted.internet import asyncioreactor
asyncioreactor.install(asyncio.get_event_loop())

from twisted.internet import reactor
import dearpygui.dearpygui as dpg

from src.scheduler import StateContext, PriorityScheduler
from src.network_proxy import SnifferDownstreamFactory
from src.input_bridge import InputBridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mc_auto.main")


def load_settings(config_path: str) -> Dict[str, Any]:
    """Loads configuration parameters from settings JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load settings from {config_path}: {e}. Using defaults.")
        return {
            "TARGET_VERSION": "1.20.1",
            "PROXY_PORT": 25565,
            "JITTER_MU": 18.0,
            "JITTER_SIGMA": 6.0,
            "OUTLIER_RATE": 0.02
        }


def download_prismarine_schema(version: str) -> Dict[int, Any]:
    """Downloads items.json from PrismarineJS repository if not already cached locally."""
    data_dir = os.path.join("data", version)
    os.makedirs(data_dir, exist_ok=True)
    items_path = os.path.join(data_dir, "items.json")

    if not os.path.exists(items_path):
        url = f"https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/{version}/items.json"
        logger.info(f"Downloading PrismarineJS items schema from {url}...")
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read()
                with open(items_path, "wb") as f:
                    f.write(content)
            logger.info("Items schema cached successfully.")
        except Exception as e:
            logger.error(f"Failed to download items schema: {e}. Proxy will run with fallback durability lookups.")
            return {}

    try:
        with open(items_path, 'r') as f:
            items_list = json.load(f)
            # Map item ID (int) to item data dict
            return {item["id"]: item for item in items_list}
    except Exception as e:
        logger.error(f"Error loading cached schema: {e}")
        return {}


async def main() -> None:
    # 1. Setup workspace paths and configurations
    config_path = os.path.join("config", "settings.json")
    settings = load_settings(config_path)
    
    # 2. Build items schema lookups
    item_lookup = download_prismarine_schema(settings.get("TARGET_VERSION", "1.20.1"))

    # 3. Initialize core domain engine classes
    context = StateContext()
    scheduler = PriorityScheduler(context)
    input_bridge = InputBridge(
        port="/dev/ttyACM0",
        baudrate=115200,
        mu=settings.get("JITTER_MU", 18.0),
        sigma=settings.get("JITTER_SIGMA", 6.0),
        outlier_rate=settings.get("OUTLIER_RATE", 0.02)
    )

    # 4. Bind and start the Sniffer Proxy Factory on Twisted Reactor
    proxy_port = settings.get("PROXY_PORT", 25565)
    proxy_factory = SnifferDownstreamFactory(context, scheduler, item_lookup)
    
    try:
        reactor.listenTCP(proxy_port, proxy_factory)
        logger.info(f"Local proxy sniffer bound to 127.0.0.1:{proxy_port}")
    except Exception as e:
        logger.error(f"Failed to bind proxy listener to port {proxy_port}: {e}")
        sys.exit(1)

    # Start the priority scheduler loop as an asyncio background task
    scheduler_task = asyncio.create_task(scheduler.run())

    # 5. Initialize Dear PyGui Viewport
    dpg.create_context()
    dpg.create_viewport(title="Minecraft Automation Engine Telemetry", width=620, height=450, resizable=False)

    # UI variables
    active_slot_var = dpg.add_value_node(value="0")
    slot_confirmed_var = dpg.add_value_node(value="True")
    durability_var = dpg.add_value_node(value="0")
    multiplier_var = dpg.add_value_node(value="1.0")
    player_pos_var = dpg.add_value_node(value="X: 0.00, Y: 0.00, Z: 0.00")
    server_pos_var = dpg.add_value_node(value="X: 0.00, Y: 0.00, Z: 0.00")
    mining_status_var = dpg.add_value_node(value="Idle")

    # Set up styling (Godly Web Design parameters: sleek dark mode with rounded corners)
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (24, 28, 36, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (0, 180, 166, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 180, 166, 180))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHover, (0, 180, 166, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 150, 140, 255))

    dpg.bind_theme(global_theme)

    with dpg.window(label="Engine Telemetry & Controller", width=600, height=410, no_move=True, no_resize=True, no_collapse=True):
        dpg.add_text("System State Overview", color=(0, 180, 166))
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text("Active Hotbar Slot: ")
            dpg.add_text(tag="slot_text", default_value="0", color=(255, 184, 48))
            
        with dpg.group(horizontal=True):
            dpg.add_text("Slot Confirmed: ")
            dpg.add_text(tag="confirmed_text", default_value="True", color=(52, 211, 153))

        with dpg.group(horizontal=True):
            dpg.add_text("Tool Durability: ")
            dpg.add_text(tag="durability_text", default_value="0", color=(255, 107, 107))

        with dpg.group(horizontal=True):
            dpg.add_text("Tool Speed Multiplier: ")
            dpg.add_text(tag="multiplier_text", default_value="1.0", color=(255, 184, 48))

        dpg.add_spacer(height=10)
        dpg.add_text("Positional Mapping", color=(0, 180, 166))
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text("Client Coordinates: ")
            dpg.add_text(tag="player_pos_text", default_value="X: 0.00, Y: 0.00, Z: 0.00")

        with dpg.group(horizontal=True):
            dpg.add_text("Server Coordinates: ")
            dpg.add_text(tag="server_pos_text", default_value="X: 0.00, Y: 0.00, Z: 0.00")

        dpg.add_spacer(height=10)
        dpg.add_text("Macro Scheduler Controls", color=(0, 180, 166))
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text("Mining Engine: ")
            dpg.add_text(tag="mining_status_text", default_value="Idle")

        # Command interfaces
        async def trigger_test_swing():
            # Schedule a swing action on priority 2
            async def swing_coro():
                context.is_mining = True
                logger.info("Executing simulated test swing...")
                input_bridge.click("left", True)
                await input_bridge.sleep_with_jitter()
                input_bridge.click("left", False)
                context.is_mining = False
                logger.info("Simulated test swing completed.")
                
            scheduler.schedule(2, "test_swing", swing_coro())

        dpg.add_spacer(height=10)
        dpg.add_button(label="Simulate Left-Click Swing", callback=lambda: asyncio.run_coroutine_threadsafe(trigger_test_swing(), asyncio.get_event_loop()))

    dpg.setup_dearpygui()
    dpg.show_viewport()

    # DPG cooperative frame-rendering loop
    try:
        while dpg.is_dearpygui_running():
            # Fetch context variables safely and update the UI controls
            slot_color = (255, 184, 48) if context.slot_confirmed else (255, 107, 107)
            dpg.set_value("slot_text", str(context.active_slot))
            dpg.set_value("confirmed_text", str(context.slot_confirmed))
            dpg.configure_item("confirmed_text", color=(52, 211, 153) if context.slot_confirmed else (255, 107, 107))
            
            dpg.set_value("durability_text", str(context.current_durability))
            dpg.set_value("multiplier_text", f"{context.equipped_tool_multiplier:.1f}x")
            
            dpg.set_value("player_pos_text", f"X: {context.player_x:.2f}, Y: {context.player_y:.2f}, Z: {context.player_z:.2f}")
            dpg.set_value("server_pos_text", f"X: {proxy_factory.server_x:.2f}, Y: {proxy_factory.server_y:.2f}, Z: {proxy_factory.server_z:.2f}")
            
            status = "Mining" if context.is_mining else ("Interrupted" if context.swing_interrupted else "Idle")
            dpg.set_value("mining_status_text", status)
            dpg.configure_item("mining_status_text", color=(255, 107, 107) if context.swing_interrupted else ((255, 184, 48) if context.is_mining else (255, 255, 255)))

            # Render the frame
            dpg.render_dearpygui_frame()
            # Yield control back to asyncio
            await asyncio.sleep(0.016)  # Caps rendering to ~60 FPS and lets other async tasks execute
    finally:
        # Tear down DPG context
        dpg.destroy_context()
        logger.info("Dear PyGui viewport destroyed.")
        # Halt proxy and scheduler
        scheduler.stop()
        try:
            reactor.stop()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        # Run everything through the standard asyncio event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user. Exiting.")
