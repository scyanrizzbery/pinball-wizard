import os
import time
import logging
import threading


logger = logging.getLogger(__name__)

try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class FlipperController:
    def __init__(self):
        self.left_pin = int(os.getenv('GPIO_PIN_LEFT_FLIPPER', 17))
        self.right_pin = int(os.getenv('GPIO_PIN_RIGHT_FLIPPER', 18))
        
        if GPIO_AVAILABLE:
            self.left_flipper = OutputDevice(self.left_pin)
            self.right_flipper = OutputDevice(self.right_pin)
        else:
            logger.warning("GPIO not available, using mock outputs")
            self.left_flipper = None
            self.right_flipper = None

    def flip_left(self, duration=0.1):
        def _flip():
            if self.left_flipper:
                self.left_flipper.on()
                time.sleep(duration)
                self.left_flipper.off()
            else:
                logger.debug(f"[HARDWARE] Flip Left (Pin {self.left_pin})")
        threading.Thread(target=_flip).start()

    def flip_right(self, duration=0.1):
        def _flip():
            if self.right_flipper:
                self.right_flipper.on()
                time.sleep(duration)
                self.right_flipper.off()
            else:
                logger.debug(f"[HARDWARE] Flip Right (Pin {self.right_pin})")
        threading.Thread(target=_flip).start()

    def hold_left(self):
        if self.left_flipper:
            self.left_flipper.on()
        else:
            logger.debug(f"[HARDWARE] Hold Left (Pin {self.left_pin})")

    def release_left(self):
        if self.left_flipper:
            self.left_flipper.off()
        else:
            logger.debug(f"[HARDWARE] Release Left (Pin {self.left_pin})")

    def hold_right(self):
        if self.right_flipper:
            self.right_flipper.on()
        else:
            logger.debug(f"[HARDWARE] Hold Right (Pin {self.right_pin})")

    def release_right(self):
        if self.right_flipper:
            self.right_flipper.off()
        else:
            logger.debug(f"[HARDWARE] Release Right (Pin {self.right_pin})")

    def nudge_left(self):
        logger.debug("[HARDWARE] Nudge Left (Not implemented for real hardware)")

    def nudge_right(self):
        logger.debug("[HARDWARE] Nudge Right (Not implemented for real hardware)")


class MockController(FlipperController):
    def __init__(self, vision_system=None):
        # Force mock behavior even if GPIO is available
        self.left_pin = 17
        self.right_pin = 18
        self.left_flipper = None
        self.right_flipper = None
        self.vision_system = vision_system
        self.left_held = False
        self.right_held = False
        logger.info(f"[MockController] Initialized with vision_system: {self.vision_system}")

    def flip_left(self, duration=0.1):
        def _flip():
            logger.debug(f"[HARDWARE] Flip Left (Pin {self.left_pin})")
            if self.vision_system:
                logger.debug("[HARDWARE] Triggering Vision System Left")
                if hasattr(self.vision_system, 'trigger_left'):
                    self.vision_system.trigger_left()
                    time.sleep(duration)
                    self.vision_system.release_left()
                else:
                    logger.error("[HARDWARE] Vision System has no trigger_left method")
            else:
                logger.warning("[HARDWARE] No Vision System connected to MockController")
        threading.Thread(target=_flip).start()

    def flip_right(self, duration=0.1):
        def _flip():
            logger.debug(f"[HARDWARE] Flip Right (Pin {self.right_pin})")
            if self.vision_system:
                logger.debug("[HARDWARE] Triggering Vision System Right")
                if hasattr(self.vision_system, 'trigger_right'):
                    self.vision_system.trigger_right()
                    time.sleep(duration)
                    self.vision_system.release_right()
                else:
                    logger.error("[HARDWARE] Vision System has no trigger_right method")
            else:
                logger.warning("[HARDWARE] No Vision System connected to MockController")
        threading.Thread(target=_flip).start()

    def hold_left(self):
        if not self.left_held:
            logger.debug(f"[HARDWARE] Hold Left (Pin {self.left_pin})")
            self.left_held = True
            if self.vision_system and hasattr(self.vision_system, 'trigger_left'):
                self.vision_system.trigger_left()

    def release_left(self):
        if self.left_held:
            logger.debug(f"[HARDWARE] Release Left (Pin {self.left_pin})")
            self.left_held = False
            if self.vision_system and hasattr(self.vision_system, 'release_left'):
                self.vision_system.release_left()

    def hold_right(self):
        if not self.right_held:
            logger.debug(f"[HARDWARE] Hold Right (Pin {self.right_pin})")
            self.right_held = True
            if self.vision_system and hasattr(self.vision_system, 'trigger_right'):
                self.vision_system.trigger_right()

    def release_right(self):
        if self.right_held:
            logger.debug(f"[HARDWARE] Release Right (Pin {self.right_pin})")
            self.right_held = False
            if self.vision_system and hasattr(self.vision_system, 'release_right'):
                self.vision_system.release_right()

    def nudge_left(self):
        logger.debug("[HARDWARE] Mock Nudge Left")
        if self.vision_system and hasattr(self.vision_system, 'nudge_left'):
            self.vision_system.nudge_left()

    def nudge_right(self):
        logger.debug("[HARDWARE] Mock Nudge Right")
        if self.vision_system and hasattr(self.vision_system, 'nudge_right'):
            self.vision_system.nudge_right()
