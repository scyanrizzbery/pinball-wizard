import os
import logging
import time
from dotenv import load_dotenv
import eventlet

eventlet.monkey_patch()

load_dotenv()

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import threading
from pbwizard.vision import FrameCapture, SimulatedFrameCapture, BallTracker, ScoreReader, ZoneManager
from pbwizard.hardware import FlipperController, MockController
from pbwizard.environment import PinballEnv
from pbwizard.agent import RLAgent
from pbwizard.agent import RLAgent
from pbwizard.web_server import start_server
from pbwizard.web_server import start_server
from pbwizard.callbacks import WebStatsCallback, ProgressBarCallback
from pbwizard import constants


def main():
    # 1. Initialize Vision System
    sim_mode = os.getenv('SIMULATION_MODE', 'True').strip().lower() == 'true'
    debug_mode = os.getenv('DEBUG_MODE', 'True').strip().lower() == 'true'
    # Force headless mode for training to maximize speed and rely on web server for viz
    headless_mode = True 
    # headless_mode = os.getenv('HEADLESS_MODE', 'False').strip().lower() == 'true'

    cap = None
    if sim_mode:
        logger.info("Initializing Simulated Vision System")
        # Placeholder for width, height - will be set later if not sim
        # For sim, we can define a default resolution or pass it in
        sim_width = int(os.getenv('SIM_WIDTH', constants.DEFAULT_WIDTH))
        sim_height = int(os.getenv('SIM_HEIGHT', constants.DEFAULT_HEIGHT))
        cap = SimulatedFrameCapture(sim_width, sim_height, headless=headless_mode)  # Modified: Pass headless_mode
    else:
        logger.info("Initializing Real Camera System")
        cap = FrameCapture()

    cap.start()

    # Wait for camera/sim to warm up
    time.sleep(2)

    # 2. Initialize Hardware
    # Always use Mock for training to avoid burning out solenoids unless explicitly overridden
    # But for "real" training we might need real hardware.
    # Let's respect DEBUG_MODE but default to Mock if not specified.
    if debug_mode:
        logger.info("Using Mock Controller for Training")
        # Pass vision system to mock controller for simulation
        mock_vision = None
        if sim_mode:
            mock_vision = cap

        logger.info(f"Passing vision system to MockController: {mock_vision}")
        hw = MockController(vision_system=mock_vision)
    else:
        logger.warning("Using REAL Hardware for Training! Ensure this is intended.")
        hw = FlipperController()

    # Get frame dimensions
    frame = cap.get_frame()
    if frame is None:
        logger.error("Error: Could not get frame from camera.")
        cap.stop()
        return

    height, width = frame.shape[:2]
    logger.info(f"Camera Resolution: {width}x{height}")

    # 3. Initialize Environment Components
    tracker = BallTracker()

    # Use the same layout as simulation if available, otherwise default
    layout = cap.layout if hasattr(cap, 'layout') else None
    zone_manager = ZoneManager(width, height, layout=layout)

    class VisionWrapper:
        def __init__(self, capture, tracker, zones):
            self.capture = capture
            self.tracker = tracker
            self.zones = zones
            self.latest_processed_frame = None
            self.lock = threading.Lock()
            self.training_stats = {
                'timesteps': 0,
                'mean_reward': 0.0,
                'length': 0,
                'games_played': 0
            }
            self.high_score = 0
            self.ai_enabled = True
            self.auto_start_enabled = True

        def update_training_stats(self, stats):
            with self.lock:
                self.training_stats.update(stats)

        def get_stats(self):
            # Get live game stats
            current_score = 0
            if hasattr(self.capture, 'score'):
                current_score = self.capture.score
            
            if current_score > self.high_score:
                self.high_score = current_score
                
            balls = len(self.capture.balls) if hasattr(self.capture, 'balls') else 0
            
            # Merge with training stats
            with self.lock:
                stats = self.training_stats.copy()
                
            nudge_data = None
            if hasattr(self.capture, 'last_nudge'):
                nudge_data = self.capture.last_nudge

            stats.update({
                'score': current_score,
                'high_score': self.high_score,
                'balls': balls,
                'is_training': True,
                'nudge': nudge_data
            })
            return stats

        def get_raw_frame(self):
            # PinballEnv calls this to get the raw frame for processing
            return self.capture.get_frame()

        def get_frame(self):
            # Web server calls this to get the processed frame for display
            with self.lock:
                return self.latest_processed_frame.copy() if self.latest_processed_frame is not None else None

        def process_frame(self, frame):
            # PinballEnv calls this to process the frame
            ball_pos, processed_frame = self.tracker.process_frame(frame)
            if processed_frame is not None:
                # Draw zones for visualization
                processed_frame = self.zones.draw_zones(processed_frame)
                # Update latest frame for web server
                with self.lock:
                    self.latest_processed_frame = processed_frame
            return ball_pos, processed_frame

        # Helper for environment if it needs score/ball_lost from sim
        def get_score(self):
            if hasattr(self.capture, 'get_score'):
                return self.capture.get_score()
            return 0

        @property
        def ball_lost(self):
            if hasattr(self.capture, 'ball_lost'):
                return self.capture.ball_lost
            return False

        def launch_ball(self):
            if hasattr(self.capture, 'launch_ball'):
                self.capture.launch_ball()

    vision_wrapper = VisionWrapper(cap, tracker, zone_manager)
    score_reader = ScoreReader()

    # 4. Start Web Server (in separate thread)
    web_thread = threading.Thread(target=start_server, args=(vision_wrapper, int(os.getenv('FLASK_PORT', 5000))))
    web_thread.daemon = True
    web_thread.start()
    logger.info("Web Server started for training visualization.")

    # 5. Initialize Environment
    # Enable random layouts for better generalization
    env = PinballEnv(vision_wrapper, hw, score_reader, headless=headless_mode, random_layouts=True)

    # 6. Initialize Agent
    model_path = "models/ppo_pinball_v1"
    agent = RLAgent(env=env)

    # 7. Train
    try:
        total_timesteps = 100000
        logger.info(f"Training for {total_timesteps} steps...")
        
        # Create callback
        # Create callbacks
        web_callback = WebStatsCallback(vision_wrapper)
        progress_callback = ProgressBarCallback(total_timesteps)
        
        agent.train(total_timesteps=total_timesteps, callbacks=[web_callback, progress_callback])

        # 8. Save
        os.makedirs("models", exist_ok=True)
        agent.save(model_path)
        logger.info("Training finished and model saved.")

    except KeyboardInterrupt:
        logger.info("Training interrupted.")
        agent.save(model_path + "_interrupted")
    finally:
        cap.stop()
        logger.info("Cleanup done.")


if __name__ == "__main__":
    main()
