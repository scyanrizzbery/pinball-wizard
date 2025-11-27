import logging
import os
import time

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from pbwizard import constants


logger = logging.getLogger(__name__)


class PinballEnv(gym.Env):

    metadata = {'render_modes': ['human', 'rgb_array'], 'render_fps': 30}

    def __init__(self, vision_system, hardware_controller, score_reader, headless: bool = False):
        super(PinballEnv, self).__init__()
        
        self.vision = vision_system
        self.hw = hardware_controller
        self.score_reader = score_reader
        self.headless = headless
        
        # Action Space: 0: No-op, 1: Left Flip, 2: Right Flip, 3: Both Flip
        self.action_space = spaces.Discrete(4)
        
        # Observation Space: [ball_x, ball_y, ball_vx, ball_vy] (normalized)
        self.observation_space = spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
        
        self.last_score = 0
        self.current_score = 0
        self.last_ball_pos = None
        self.last_time = time.time()
        self.steps_without_ball = 0
        self.max_steps_without_ball = 100 # Reset if ball lost for too long
        self.holding_steps = 0

    def step(self, action: int):
        """
        Execute one time step within the environment.
        
        Args:
            action (int): The action to perform (0: No-op, 1: Left, 2: Right, 3: Both)
            
        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """
        # 1. Enforce Zone Restrictions
        allowed_action = self._enforce_zones(action)

        # 2. Execute Action
        # Safety Override for Training/Execution:
        # If ball is in right zone and moving down fast, force right flip
        # This helps the agent "discover" the right flipper if it's stuck in a local optimum
        if self.last_ball_pos is not None and hasattr(self.vision, 'zone_manager'):
             zones = self.vision.zone_manager.get_zone_status(self.last_ball_pos[0], self.last_ball_pos[1])
             # Calculate velocity if not available? We need vy.
             # We can use the previous step's velocity or calculate it.
             # Let's use a simple heuristic: if we are in the zone, we probably want to flip.
             # But we need to know if it's moving down.
             # We can't easily get vy here without passing it or recalculating.
             # Let's rely on the fact that if it's in the zone, it's likely coming down.
             
             # Get velocity
             vx, vy = 0, 0
             if hasattr(self.vision, 'get_ball_status'):
                 status = self.vision.get_ball_status()
                 if status: _, (vx, vy) = status

             # Left Safety
             if zones['left'] and vy > 50:
                 if allowed_action == constants.ACTION_NOOP:
                     allowed_action = constants.ACTION_FLIP_LEFT
                 elif allowed_action == constants.ACTION_FLIP_RIGHT:
                     allowed_action = constants.ACTION_FLIP_BOTH

             # Right Safety
             if zones['right'] and vy > 50:
                 if allowed_action == constants.ACTION_NOOP:
                     allowed_action = constants.ACTION_FLIP_RIGHT
                 elif allowed_action == constants.ACTION_FLIP_LEFT:
                     allowed_action = constants.ACTION_FLIP_BOTH

        self._execute_action(allowed_action)
            
        # 3. Wait for Latency/Physics
        if not self.headless:
            time.sleep(0.033) # ~30Hz control loop 
        
        # 4. Get New State (Observation)
        frame = None
        if not self.headless:
            frame = self._get_current_frame()
            
        ball_pos = None
        vx, vy = 0.0, 0.0
        
        # Always process frame if available (for visualization wrappers)
        if hasattr(self.vision, 'process_frame') and frame is not None:
            # We ignore the result if we have better status from sim, but we need to call it
            # so the wrapper can update its internal display frame
            vision_ball_pos, _ = self.vision.process_frame(frame)
            if ball_pos is None:
                ball_pos = vision_ball_pos

        # Check if we can get direct status from sim (more accurate for multiball)
        if hasattr(self.vision, 'get_ball_status'):
             status = self.vision.get_ball_status()
             if status:
                 ball_pos, (vx, vy) = status
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'get_ball_status'):
             status = self.vision.capture.get_ball_status()
             if status:
                 ball_pos, (vx, vy) = status
        else:
            # Vision fallback (already processed above)
            pass
            
            # Calculate velocity manually if not provided
            current_time = time.time()
            dt = current_time - self.last_time
            self.last_time = current_time
            
            if ball_pos is not None and self.last_ball_pos is not None:
                vx = (ball_pos[0] - self.last_ball_pos[0]) / dt
                vy = (ball_pos[1] - self.last_ball_pos[1]) / dt
        
        self.last_ball_pos = ball_pos
        
        # Normalize observation
        # Use default dimensions if frame is not available (headless)
        height, width = frame.shape[:2] if frame is not None else (constants.DEFAULT_HEIGHT, constants.DEFAULT_WIDTH)
        obs = self._create_observation(ball_pos, vx, vy, width, height)
            
        # 5. Calculate Reward
        self._update_score(frame)
        score_diff = self.current_score - self.last_score
        self.last_score = self.current_score
        
        # Reward Shaping
        reward = score_diff / 100.0 # Scale score (e.g. 500 -> 5.0)
        reward += 0.2 # Survival reward
        
        # Debug logging for start of episode
        # Debug logging for start of episode (only first step)
        if self.steps_without_ball == 0 and self.last_ball_pos is None and ball_pos is not None:
             logger.info(f"Ball Detected at {ball_pos}")
        
        # Height Reward: Encourage keeping ball up (y is 0 at top, 1 at bottom)
        if ball_pos is not None:
             # Reward is higher when y is smaller (top of screen)
             # Max reward approx 0.1 per step at top
             reward += (1.0 - (ball_pos[1] / height)) * 0.1
             
             # Holding Penalty
             # Calculate velocity magnitude
             velocity_mag = np.sqrt(vx**2 + vy**2)
             if velocity_mag < 20.0: # Threshold for "holding" (pixels/sec approx)
                 self.holding_steps += 1
             else:
                 self.holding_steps = 0
                 
             if self.holding_steps > 90: # Approx 3 seconds at 30Hz
                 reward -= 0.5 # Significant penalty to force action
                 # logger.info(f"Holding Penalty Applied: {self.holding_steps} steps")
        else:
            self.holding_steps = 0
        
        # 6. Check Termination
        terminated, truncated = self._check_termination(ball_pos, height)
        
        if terminated:
            reward -= 5.0 # Ball loss penalty
        
        return obs, reward, terminated, truncated, {}

    def _enforce_zones(self, action: int) -> int:
        if self.last_ball_pos is None or not hasattr(self.vision, 'zone_manager'):
            return action
            
        zones = self.vision.zone_manager.get_zone_status(self.last_ball_pos[0], self.last_ball_pos[1])
        allowed_action = action
        
        # Check Left
        if (action == constants.ACTION_FLIP_LEFT or action == constants.ACTION_FLIP_BOTH) and not zones['left']:
            allowed_action = constants.ACTION_FLIP_RIGHT if action == constants.ACTION_FLIP_BOTH else constants.ACTION_NOOP
        
        # Check Right (on potentially modified action)
        current_check = allowed_action
        if (current_check == constants.ACTION_FLIP_RIGHT or current_check == constants.ACTION_FLIP_BOTH) and not zones['right']:
            allowed_action = constants.ACTION_FLIP_LEFT if current_check == constants.ACTION_FLIP_BOTH else constants.ACTION_NOOP
            
        return allowed_action

    def _execute_action(self, action: int):
        if action == constants.ACTION_FLIP_LEFT:
            self.hw.hold_left()
            self.hw.release_right()
        elif action == constants.ACTION_FLIP_RIGHT:
            self.hw.release_left()
            self.hw.hold_right()
        elif action == constants.ACTION_FLIP_BOTH:
            self.hw.hold_left()
            self.hw.hold_right()
        else: # constants.ACTION_NOOP
            self.hw.release_left()
            self.hw.release_right()

    def _get_current_frame(self):
        if hasattr(self.vision, 'get_raw_frame'):
            return self.vision.get_raw_frame()
        return self.vision.get_frame()

    def _create_observation(self, ball_pos, vx, vy, width, height):
        obs = np.array([0, 0, 0, 0], dtype=np.float32)
        if ball_pos is not None:
            obs[0] = ball_pos[0] / width
            obs[1] = ball_pos[1] / height
            # Velocity normalization: 50.0 covers typical range better than 1000.0
            obs[2] = np.clip(vx / 50.0, -1, 1)
            obs[3] = np.clip(vy / 50.0, -1, 1)
            self.steps_without_ball = 0
        else:
            self.steps_without_ball += 1
        return obs

    def _update_score(self, frame):
        if hasattr(self.vision, 'get_score'):
            self.current_score = self.vision.get_score()
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'get_score'):
             self.current_score = self.vision.capture.get_score()
        else:
            self.current_score = self.score_reader.get_score(frame) if frame is not None else 0

    def _check_termination(self, ball_pos, height):
        terminated = False 
        truncated = False
        
        ball_lost = False
        if hasattr(self.vision, 'ball_lost'):
            ball_lost = self.vision.ball_lost
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'ball_lost'):
            ball_lost = self.vision.capture.ball_lost
        
        if ball_pos is not None and ball_pos[1] > height * 0.98:
             ball_lost = True

        if ball_lost:
            terminated = True
        
        if self.steps_without_ball > self.max_steps_without_ball:
            truncated = True
            
        return terminated, truncated

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.last_score = 0
        self.current_score = 0
        self.last_ball_pos = None
        self.steps_without_ball = 0
        self.holding_steps = 0
        self.last_time = time.time()
        
        # Launch ball if in simulation and auto-start is enabled
        should_launch = True
        if hasattr(self.vision, 'auto_start_enabled'):
            should_launch = self.vision.auto_start_enabled
            
        if should_launch:
            if hasattr(self.vision, 'launch_ball'):
                self.vision.launch_ball()
            elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'launch_ball'):
                self.vision.capture.launch_ball()
        
        # Initial observation
        if hasattr(self.vision, 'get_raw_frame'):
            frame = self.vision.get_raw_frame()
        else:
            frame = self.vision.get_frame()
            
        # Process frame for visualization
        if hasattr(self.vision, 'process_frame') and frame is not None:
            self.vision.process_frame(frame)

        # For simplicity, return zeros or wait for ball
        return np.array([0, 0, 0, 0], dtype=np.float32), {}

    def render(self):
        pass # Visualization is handled by the web server
