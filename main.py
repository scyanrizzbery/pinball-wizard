import eventlet
eventlet.monkey_patch()

import os
import threading
import time
import logging
import numpy as np
from dotenv import load_dotenv


logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

from pbwizard import vision, hardware, agent, web_server, constants


def main():
    logger.info("Starting Pinball Bot...")
    
    # Debug: Log environment variables
    sim_mode = os.getenv('SIMULATION_MODE', 'False').strip()
    debug_mode = os.getenv('DEBUG_MODE', 'False').strip()
    logger.info(f"Environment Config: SIMULATION_MODE='{sim_mode}', DEBUG_MODE='{debug_mode}'")

    # 1. Initialize Vision System (First, so we can pass it to HW)
    if sim_mode.lower() == 'true':
        logger.info("Simulation Mode: Using Simulated Video Feed")
        cap = vision.SimulatedFrameCapture(width=450, height=800)
    else:
        camera_index = int(os.getenv('CAMERA_INDEX', 0))
        logger.info(f"Using Camera Index: {camera_index}")
        cap = vision.FrameCapture(camera_index)
    
    # 2. Initialize Hardware
    if debug_mode.lower() == 'true':
        logger.info("Debug Mode: Using Mock Controller")
        # Pass vision system to mock controller for simulation
        hw = hardware.MockController(vision_system=cap if sim_mode.lower() == 'true' else None)
    else:
        hw = hardware.FlipperController()
    
    cap.start()
    
    # Wait for camera to warm up
    time.sleep(2)

    # Get frame dimensions
    frame = cap.get_frame()
    if frame is None:
        logger.error("Error: Could not get frame from camera.")
        cap.stop()
        return

    height, width = frame.shape[:2]
    logger.info(f"Camera Resolution: {width}x{height}")

    tracker = vision.BallTracker()
    zone_manager = vision.ZoneManager(width, height)
    score_reader = vision.ScoreReader()

    # 3. Initialize Agent
    use_rl = os.getenv('USE_RL_AGENT', 'False').strip().lower() == 'true'
    if use_rl:
        logger.info("Using RL Agent (PPO)")
        model_path = "models/ppo_pinball_v1.zip"
        agnt = agent.RLAgent(model_path=model_path)
    else:
        logger.info("Using Reflex Agent")
        agnt = agent.ReflexAgent(zone_manager, hw)


    # 4. Start Web Server (in separate thread)
    class VisionWrapper:
        def __init__(self, capture, tracker, zones):
            self.capture = capture
            self.tracker = tracker
            self.zones = zones
            self.latest_processed_frame = None
            self.lock = threading.Lock()
            self.ai_enabled = True
            self.high_score = 0
            self.games_played = 0
            self.last_ball_count = 0

        def update(self):
            # Try to get ground truth from simulation first
            if hasattr(self.capture, 'get_ball_status'):
                status = self.capture.get_ball_status()
                if status:
                    ball_pos, _ = status
                    # Still get frame for display
                    raw_frame = self.capture.get_frame()
                    if raw_frame is not None:
                        # Draw debug info on frame if needed
                        with self.lock:
                            self.latest_processed_frame = raw_frame
                    return ball_pos

            # Fallback to CV tracking
            raw_frame = self.capture.get_frame()
            if raw_frame is not None:
                ball_pos, processed_frame = self.tracker.process_frame(raw_frame)
                if processed_frame is not None:
                    # processed_frame = self.zones.draw_zones(processed_frame) # Removed to avoid 2D overlay on 3D sim
                    with self.lock:
                        self.latest_processed_frame = processed_frame
                return ball_pos
            return None

        def get_frame(self):
            with self.lock:
                return self.latest_processed_frame.copy() if self.latest_processed_frame is not None else None

        def get_stats(self):
            current_score = 0
            if hasattr(self.capture, 'score'):
                current_score = self.capture.score
                
            if current_score > self.high_score:
                self.high_score = current_score
                
            current_balls = len(self.capture.balls) if hasattr(self.capture, 'balls') else 0
            
            if self.last_ball_count > 0 and current_balls == 0:
                self.games_played += 1
                
            self.last_ball_count = current_balls
                
            return {
                'score': current_score,
                'high_score': self.high_score,
                'balls': current_balls,
                'games_played': self.games_played
            }

        @property
        def auto_start_enabled(self):
            return getattr(self.capture, 'auto_start_enabled', False)

        @auto_start_enabled.setter
        def auto_start_enabled(self, value):
            if hasattr(self.capture, 'auto_start_enabled'):
                self.capture.auto_start_enabled = value

        def __getattr__(self, name):
            if name in ['ai_enabled', 'auto_start_enabled']:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            return getattr(self.capture, name)

    vision_wrapper = VisionWrapper(cap, tracker, zone_manager)
    
    web_thread = threading.Thread(target=web_server.start_server, args=(vision_wrapper, int(os.getenv('FLASK_PORT', 5000))))
    web_thread.daemon = True
    web_thread.start()

    logger.info("Bot Running. Press Ctrl+C to stop.")

    # State tracking for RL
    last_ball_pos = None
    last_time = time.time()

    try:
        while True:
            # Main Control Loop
            ball_pos = vision_wrapper.update()
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            if ball_pos is not None:
                if use_rl:
                    # Calculate velocity
                    vx, vy = 0, 0
                    if last_ball_pos is not None:
                        vx = (ball_pos[0] - last_ball_pos[0]) / dt
                        vy = (ball_pos[1] - last_ball_pos[1]) / dt
                    
                    # Check if ball is in any zone
                    # Check if ball is in any zone
                    zones = zone_manager.get_zone_status(ball_pos[0], ball_pos[1])
                    
                    if zones['left'] or zones['right']:
                        # Construct observation [x, y, vx, vy] normalized
                        # Assuming 640x480 for normalization as in environment.py
                        obs = np.array([
                            ball_pos[0] / width,
                            ball_pos[1] / height,
                            np.clip(vx / 50.0, -1, 1),
                            np.clip(vy / 50.0, -1, 1)
                        ], dtype=np.float32)
                        
                        action = agnt.predict(obs)

                        # Anti-holding for RL
                        if not hasattr(vision_wrapper, 'rl_hold_steps'): vision_wrapper.rl_hold_steps = 0
                        if not hasattr(vision_wrapper, 'rl_cooldown'): vision_wrapper.rl_cooldown = 0
                        
                        if vision_wrapper.rl_cooldown > 0:
                            vision_wrapper.rl_cooldown -= 1
                            action = constants.ACTION_NOOP
                        else:
                            is_holding = (action != constants.ACTION_NOOP)
                            if is_holding:
                                vision_wrapper.rl_hold_steps += 1
                            else:
                                vision_wrapper.rl_hold_steps = 0
                                
                            if vision_wrapper.rl_hold_steps > 90: # 3 seconds
                                action = constants.ACTION_NOOP
                                vision_wrapper.rl_cooldown = 30 # 1 second cooldown
                                vision_wrapper.rl_hold_steps = 0
                        
                        # Execute action with zone restrictions
                        # Logic matches environment.py: _execute_action
                        
                        # Left Flipper
                        if (action == constants.ACTION_FLIP_LEFT or action == constants.ACTION_FLIP_BOTH) and zones['left']:
                            if vision_wrapper.ai_enabled:
                                hw.hold_left()
                            else:
                                hw.release_left()
                        else:
                            hw.release_left()

                        # Right Flipper
                        if (action == constants.ACTION_FLIP_RIGHT or action == constants.ACTION_FLIP_BOTH) and zones['right']:
                            if vision_wrapper.ai_enabled:
                                hw.hold_right()
                            else:
                                hw.release_right()
                        else:
                            hw.release_right()
                else:
                    # Calculate velocity for Reflex Agent too
                    vx, vy = 0, 0
                    if last_ball_pos is not None:
                        vx = (ball_pos[0] - last_ball_pos[0]) / dt
                        vy = (ball_pos[1] - last_ball_pos[1]) / dt
                    
                    if vision_wrapper.ai_enabled:
                        agnt.act(ball_pos, width, height, velocity=(vx, vy))
                
                last_ball_pos = ball_pos
            else:
                last_ball_pos = None
            
            # Rate limiting (approx 60 Hz)
            time.sleep(0.016)

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        cap.stop()
        logger.info("Clean exit.")

if __name__ == "__main__":
    main()
