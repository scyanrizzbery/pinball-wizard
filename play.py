import os
import logging
import time
import threading
from dotenv import load_dotenv
import eventlet

# Patch eventlet for socketio
eventlet.monkey_patch()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from pbwizard.vision import SimulatedFrameCapture, BallTracker, ZoneManager
from pbwizard.web_server import start_server
from pbwizard import constants


class VisionWrapper:
    """Wraps the vision system to add overlays for the web view"""
    def __init__(self, capture, tracker, zone_manager):
        self.capture = capture
        self.tracker = tracker
        self.zones = zone_manager
        self.ball_lost = True
        self.high_score = 0
        self.games_played = 0
        self.last_ball_count = 0
        self.ai_enabled = True
        # self.auto_start_enabled = True # Delegated to capture

    def get_stats(self):
        current_score = 0
        if hasattr(self.capture, 'score'):
            current_score = self.capture.score
            
        if current_score > self.high_score:
            self.high_score = current_score
            
        current_balls = len(self.capture.balls) if hasattr(self.capture, 'balls') else 0
        
        # Detect Game Over (Balls dropped to 0 from > 0)
        # Note: In simulation, balls might be 0 at start, so we need to be careful.
        # But usually we launch a ball.
        # A simple heuristic: if we had balls and now we don't, game over.
        if self.last_ball_count > 0 and current_balls == 0:
            self.games_played += 1
            
        self.last_ball_count = current_balls
            
        return {
            'score': current_score,
            'high_score': self.high_score,
            'balls': current_balls,
            'games_played': self.games_played
        }

    def get_frame(self):
        # Get raw frame from capture
        frame = self.capture.get_frame()
        if frame is None:
            return None
            
        # Process frame (track ball)
        ball_pos, frame = self.tracker.process_frame(frame)
        self.ball_lost = (ball_pos is None)
        
        # Draw Zones
        frame = self.zones.draw_zones(frame)
        
        return frame

    @property
    def auto_start_enabled(self):
        return getattr(self.capture, 'auto_start_enabled', False)

    @auto_start_enabled.setter
    def auto_start_enabled(self, value):
        if hasattr(self.capture, 'auto_start_enabled'):
            self.capture.auto_start_enabled = value

    def __getattr__(self, name):
        # Delegate other calls to the capture object (e.g., trigger_left)
        # But don't delegate our own attributes if they are missing (recursion risk)
        if name in ['ai_enabled', 'auto_start_enabled']:
             raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return getattr(self.capture, name)


def main():
    logger.info("Starting Pinball Manual Play Mode...")

    # 1. Initialize Vision System (Simulation)
    logger.info("Initializing Simulated Vision System...")
    cap = SimulatedFrameCapture(width=constants.DEFAULT_WIDTH, height=constants.DEFAULT_HEIGHT)
    cap.start()

    # 2. Initialize Helpers
    tracker = BallTracker()
    zone_manager = ZoneManager(constants.DEFAULT_WIDTH, constants.DEFAULT_HEIGHT)
    
    # 3. Wrap Vision for Web Server
    vision_wrapper = VisionWrapper(cap, tracker, zone_manager)

    # 4. Start Web Server
    port = int(os.getenv('FLASK_PORT', 5000))
    logger.info(f"Starting Web Server on port {port}...")
    logger.info(f"Open http://localhost:{port} in your browser to play.")
    
    # Start server in main thread since it blocks
    try:
        start_server(vision_wrapper, port=port)
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        cap.stop()


if __name__ == "__main__":
    main()
