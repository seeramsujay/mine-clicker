import asyncio
import logging
import random
import struct
from typing import Optional

import numpy as np

logger = logging.getLogger("mc_auto.input_bridge")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.warning("pyserial package not found. Microcontroller serial communication will be unavailable.")

try:
    import evdev
    from evdev import ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    logger.warning("evdev package not found. Linux uinput fallback will be unavailable.")


class JitterGenerator:
    """Generates human-like timing delays using a Gaussian-Weibull mixture model."""
    __slots__ = ('mu', 'sigma', 'outlier_rate')

    def __init__(self, mu: float = 18.0, sigma: float = 6.0, outlier_rate: float = 0.02) -> None:
        self.mu: float = mu
        self.sigma: float = sigma
        self.outlier_rate: float = outlier_rate

    def get_jitter(self) -> float:
        """Returns a latency jitter offset in seconds (positive-bounded)."""
        # Determine if this sample is an outlier (human distraction pause)
        if random.random() < self.outlier_rate:
            # Weibull distribution representing distraction pause (150ms-300ms)
            k = 1.5
            scale = 50.0
            jitter_ms = 150.0 + scale * np.random.weibull(k)
            jitter_ms = min(jitter_ms, 300.0)
        else:
            # Gaussian distribution representing mechanical/motor click release jitter
            jitter_ms = np.random.normal(self.mu, self.sigma)
            jitter_ms = max(jitter_ms, 1.0)  # Positive bound

        return jitter_ms / 1000.0


class SerialBridge:
    """Manages raw byte-serialized communication with physical RP2040/ESP32 USB-HID controller."""
    __slots__ = ('port', 'baudrate', 'connection', 'enabled')

    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200) -> None:
        self.port: str = port
        self.baudrate: int = baudrate
        self.connection: Optional[serial.Serial] = None
        self.enabled: bool = False

    def connect(self) -> bool:
        """Attempts to open serial connection to the hardware microcontroller."""
        if not SERIAL_AVAILABLE:
            return False
            
        try:
            self.connection = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.enabled = True
            logger.info(f"Microcontroller serial bridge online on: {self.port}")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to microcontroller on {self.port}: {e}")
            self.enabled = False
            return False

    def send_move(self, dx: int, dy: int) -> None:
        """Sends delta look rotation values to the controller."""
        if self.enabled and self.connection:
            try:
                # 0x01: mouse movement, dx: 16-bit signed, dy: 16-bit signed
                msg = struct.pack('<Bhh', 0x01, dx, dy)
                self.connection.write(msg)
            except Exception as e:
                logger.error(f"Serial transmission failed: {e}")
                self.enabled = False

    def send_click(self, button: str, pressed: bool) -> None:
        """Sends click press/release signals to the controller."""
        if self.enabled and self.connection:
            try:
                # 0x02: click, button_id: (1=left, 2=right), state: (1=press, 0=release)
                btn_id = 1 if button == "left" else 2
                state = 1 if pressed else 0
                msg = struct.pack('<BBBB', 0x02, btn_id, state, 0x00)
                self.connection.write(msg)
            except Exception as e:
                logger.error(f"Serial transmission failed: {e}")
                self.enabled = False

    def close(self) -> None:
        """Closes the active connection."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
            self.enabled = False


class UInputFallback:
    """Virtual Linux Input device driver fallback executing raw kernel events."""
    __slots__ = ('device', 'enabled')

    def __init__(self) -> None:
        self.device: Optional[evdev.UInput] = None
        self.enabled: bool = False

        if not EVDEV_AVAILABLE:
            return

        try:
            # Initialize virtual mouse & keyboard configuration
            capabilities = {
                ecodes.EV_KEY: [
                    ecodes.BTN_LEFT, ecodes.BTN_RIGHT,
                    ecodes.KEY_W, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D
                ],
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]
            }
            self.device = evdev.UInput(capabilities, name="Minecraft-Auto-HID")
            self.enabled = True
            logger.info("Linux uinput virtual input bridge established successfully.")
        except Exception as e:
            logger.warning(f"UInput node creation rejected (requires write permissions to /dev/uinput): {e}")
            self.enabled = False

    def move_mouse(self, dx: int, dy: int) -> None:
        """Fires relative coordinate movement updates."""
        if self.enabled and self.device:
            try:
                self.device.write(ecodes.EV_REL, ecodes.REL_X, dx)
                self.device.write(ecodes.EV_REL, ecodes.REL_Y, dy)
                self.device.syn()
            except Exception as e:
                logger.error(f"uinput mouse write error: {e}")

    def click_mouse(self, button: str, pressed: bool) -> None:
        """Fires button clicks to virtual node."""
        if self.enabled and self.device:
            try:
                code = ecodes.BTN_LEFT if button == "left" else ecodes.BTN_RIGHT
                value = 1 if pressed else 0
                self.device.write(ecodes.EV_KEY, code, value)
                self.device.syn()
            except Exception as e:
                logger.error(f"uinput mouse click write error: {e}")


class InputBridge:
    """Unified entry point routing delta motion/timing signals to downstream drivers."""
    __slots__ = ('serial_bridge', 'uinput_fallback', 'jitter_generator')

    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200, mu: float = 18.0, sigma: float = 6.0, outlier_rate: float = 0.02) -> None:
        self.serial_bridge: SerialBridge = SerialBridge(port, baudrate)
        self.serial_bridge.connect()
        self.uinput_fallback: UInputFallback = UInputFallback()
        self.jitter_generator: JitterGenerator = JitterGenerator(mu, sigma, outlier_rate)

    def move(self, dx: int, dy: int) -> None:
        """Translates rotation deltas to hardware serial signals or virtual device node."""
        if self.serial_bridge.enabled:
            self.serial_bridge.send_move(dx, dy)
        else:
            self.uinput_fallback.move_mouse(dx, dy)

    def click(self, button: str, pressed: bool) -> None:
        """Triggers click signals downstream."""
        if self.serial_bridge.enabled:
            self.serial_bridge.send_click(button, pressed)
        else:
            self.uinput_fallback.click_mouse(button, pressed)

    async def sleep_with_jitter(self) -> None:
        """Yields thread execution using Gaussian-Weibull mixture delay outputs."""
        delay = self.jitter_generator.get_jitter()
        await asyncio.sleep(delay)
