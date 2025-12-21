import logging
import time
import numpy as np

import gymnasium as gym
from gymnasium import spaces

from pbwizard import constants


logger = logging.getLogger(__name__)


class PinballEnv(gym.Env):

    metadata = {'render_modes': ['human', 'rgb_array'], 'render_fps': 30}


    def __init__(self,
                 vision_system,
                 hardware_controller,
                 score_reader,
                 headless: bool = False,
                 random_layouts: bool = False,
                 difficulty: str = 'medium'):

        super(PinballEnv, self).__init__()
        
        self.vision = vision_system
        self.hw = hardware_controller
        self.score_reader = score_reader
        self.headless = headless
        self.random_layouts = random_layouts
        self.difficulty = difficulty  # easy, medium, hard
        
        # Action Space: 0: No-op, 1: Left Flip, 2: Right Flip, 3: Both Flip
        self.action_space = spaces.Discrete(4)
        
        # Observation Space: [ball_x, ball_y, ball_vx, ball_vy, target_1, target_2, target_3, target_4]
        # We use a fixed size of 4 targets to handle layout randomization
        self.observation_space = spaces.Box(low=0, high=1, shape=(8,), dtype=np.float32)
        
        self.last_score = 0
        self.current_score = 0
        self.last_ball_pos = None
        self.last_time = time.time()
        self.steps_without_ball = 0
        self.max_steps_without_ball = 100 # Reset if ball lost for too long
        self.holding_steps = 0
        self.last_combo_count = 0
        self.last_multiplier = 1.0
        self.step_count = 0
        self.max_episode_steps = 5000  # Prevent infinite episodes

        self.load_config()

    def load_config(self):
        import json
        import os

        # Default rewards
        self.rewards_config = {
            "score_log_scale": 0.106,
            "combo_increase_factor": 0.1,
            "multiplier_increase_factor": 0.5,
            "flipper_penalty": 0.00001,  # Updated from 0.0001 to match config.json
            "bumper_hit": 0.5,
            "drop_target_hit": 1.0,
            "rail_hit": 0.5
        }

        try:
            if os.path.exists("config.json"):
                with open("config.json", 'r') as f:
                    config_data = json.load(f)
                    rewards = config_data.get('rewards', {})
                    self.rewards_config.update(rewards)
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def step(self, action: int):
        """
        Execute one time step within the environment.
        
        Args:
            action (int): The action to perform (0: No-op, 1: Left, 2: Right, 3: Both)
            
        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """
        # Execute action (may be overridden by heuristics later)
        self._execute_action(action)

        # 3. Wait for Latency/Physics
        if not self.headless:
            time.sleep(0.033) # ~30Hz control loop
        else:
            # In headless mode, manually step the physics simulation
            if hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'manual_step'):
                self.vision.capture.manual_step(dt=0.016, render=False)  # Step physics at ~60Hz (No render)
            elif hasattr(self.vision, 'manual_step'):
                self.vision.manual_step(dt=0.016)

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
        if frame is not None:
            height, width = frame.shape[:2]
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'width'):
            width = self.vision.capture.width
            height = self.vision.capture.height
        else:
            height, width = constants.DEFAULT_HEIGHT, constants.DEFAULT_WIDTH
        obs = self._create_observation(ball_pos, vx, vy, width, height)
            
        # 5. Calculate Reward
        self._update_score(frame)
        score_diff = self.current_score - self.last_score
        self.last_score = self.current_score
        
        # Get difficulty parameters
        difficulty_params = self._get_difficulty_params()
        
        # Reward Shaping
        # Log scaling to handle exponential score explosion (e.g. 100 -> 4.6, 1M -> 13.8)
        # We scale by 0.1 to keep rewards in a manageable range (~0-1.5 mostly)
        # Clip negative diffs to 0 to ignore read errors/resets
        clipped_diff = max(0, score_diff)
        score_reward = np.log1p(clipped_diff) * self.rewards_config['score_log_scale']
        reward = score_reward
        reward += difficulty_params['survival_reward'] # Survival reward (scaled by difficulty)
        reward_components = {
            'score': score_reward,
            'survival': difficulty_params['survival_reward'],
            'combo': 0.0,
            'multiplier': 0.0,
            'events': 0.0,
            'height': 0.0,
            'flipper_penalty': 0.0,
            'holding_penalty': 0.0,
            'ball_lost': 0.0
        }

        # Combo Bonus Reward - encourage maintaining combos
        # CHANGE: Only award bonus on INCREASE to prevent per-frame explosion
        if hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'physics_engine'):
            combo_status = self.vision.capture.physics_engine.get_combo_status()
            multiplier = self.vision.capture.physics_engine.get_multiplier()
            
            current_combo = combo_status['combo_count']
            
            # Award bonus only when combo count INCREASES
            if combo_status['combo_active'] and current_combo > self.last_combo_count and current_combo > 1:
                # One-time bonus for hitting a new combo tier
                combo_increase_bonus = self.rewards_config['combo_increase_factor'] * current_combo
                reward += combo_increase_bonus
                reward_components['combo'] += combo_increase_bonus
                logger.debug(f"Combo increase bonus: +{combo_increase_bonus:.2f} ({self.last_combo_count} -> {current_combo})")
            
            self.last_combo_count = current_combo if combo_status['combo_active'] else 0

            # Extra reward for multiplier INCREASE
            if multiplier > self.last_multiplier:
                multiplier_increase_bonus = (multiplier - self.last_multiplier) * self.rewards_config['multiplier_increase_factor']
                reward += multiplier_increase_bonus
                reward_components['multiplier'] += multiplier_increase_bonus
                logger.debug(f"Multiplier increase bonus: +{multiplier_increase_bonus:.2f} ({self.last_multiplier:.1f}x -> {multiplier:.1f}x)")
            
            self.last_multiplier = multiplier

        # Flipper Penalty (Discourage spamming)
        # 0: No-op, 1: Left, 2: Right, 3: Both
        if action in [constants.ACTION_FLIP_LEFT, constants.ACTION_FLIP_RIGHT, constants.ACTION_FLIP_BOTH]:
             penalty = self.rewards_config['flipper_penalty']
             reward -= penalty
             reward_components['flipper_penalty'] -= penalty
             # logger.debug("Penalty: Flipper Usage (-0.0001)")

        # Event-based Reward (Explicit feedback for hitting targets)
        events = []
        if hasattr(self.vision, 'get_events'):
            events = self.vision.get_events()
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'get_events'):
            events = self.vision.capture.get_events()
            
        for event in events:
            if event['type'] == 'collision':
                # Base rewards for hitting features (independent of score/combo)
                if 'bumper' in event['label']:
                    reward += self.rewards_config['bumper_hit'] # Significant reward for action (was 0.01)
                    reward_components['events'] += self.rewards_config['bumper_hit']
                    logger.debug("Reward: Bumper Hit (+0.5)")
                elif 'drop_target' in event['label']:
                    reward += self.rewards_config['drop_target_hit'] # Significant reward for targets (was 0.05)
                    reward_components['events'] += self.rewards_config['drop_target_hit']
                    logger.debug("Reward: Drop Target Hit (+1.0)")
                elif 'rail' in event['label']:
                    reward += self.rewards_config['rail_hit'] # Encouragement for loop shots (was 0.01)
                    reward_components['events'] += self.rewards_config['rail_hit']
                    logger.debug("Reward: Rail Hit (+0.5)")

        # Debug logging for start of episode
        # Debug logging for start of episode (only first step)
        if self.steps_without_ball == 0 and self.last_ball_pos is None and ball_pos is not None:
             logger.info(f"Ball Detected at {ball_pos}")
        
        # Height Reward: Encourage keeping ball up (y is 0 at top, 1 at bottom)
        if ball_pos is not None:
             height_term = (1.0 - (ball_pos[1] / height)) * 0.005
             reward += height_term
             reward_components['height'] += height_term

             # Flipper Hit Reward: Detect if we imparted upward velocity
             # If we are in lower area (y > 0.8) and have strong upward velocity (vy < -50)
             if ball_pos[1] / height > 0.8 and vy < -100: # Moving UP fast
                 reward += 0.01 # Reduced from 0.02
                 logger.debug("Reward: Strong Upward Shot (+0.01)")
             
             # Holding Penalty (scaled by difficulty)
             # Calculate velocity magnitude
             velocity_mag = np.sqrt(vx**2 + vy**2)
             if velocity_mag < 20.0: # Threshold for "holding" (pixels/sec approx)
                 # Ignore if in plunger lane (Right 20% of screen)
                 if ball_pos[0] < width * 0.8:
                    self.holding_steps += 1
                 else:
                    self.holding_steps = 0
             else:
                 self.holding_steps = 0
                 
             holding_threshold = difficulty_params['holding_threshold']
             if self.holding_steps > holding_threshold: # Threshold varies by difficulty
                 reward -= difficulty_params['holding_penalty'] # Penalty scaled by difficulty
                 reward_components['holding_penalty'] -= difficulty_params['holding_penalty']

                 # STUCK BALL HEURISTIC: Force Nudge if stuck for too long
                 if self.holding_steps > holding_threshold + 20:
                      import random
                      # Force Nudge Left or Right
                      nudge_action = random.choice([constants.ACTION_NUDGE_LEFT, constants.ACTION_NUDGE_RIGHT])
                      self._execute_action(nudge_action)
                      logger.warning(f"Stuck ball detected. Forcing nudge action. Steps: {self.holding_steps}")
                      self.holding_steps = 0 # Reset to prevent log spam and give physics time to react

        terminated = False
        truncated = False
        info = {}

        # DEBUG: Trace termination cause
        if self.steps_without_ball > 0 or ball_pos is None or (ball_pos and ball_pos[1] > height * 0.9):
             logger.debug(f"Step Debug: BallPos={ball_pos}, StepsNoBall={self.steps_without_ball}, Headless={self.headless}")


        # Episode termination conditions
        if ball_pos is None:
            self.steps_without_ball += 1
            logger.info("Ball not detected! Incrementing steps_without_ball.")

            if self.steps_without_ball >= self.max_steps_without_ball:
                terminated = True
                logger.warning("Max steps without ball reached. Terminating episode.")
        else:
            self.steps_without_ball = 0 # Reset counter if ball is detected

        # Ball Lost Check (Termination)
        # Grace period: Detect "lost" ball only after initial grace period (e.g. 20 steps)
        # and if we have seen the ball at least once or grace period expired.
        
        # Initial wait for physics to spawn ball
        if self.steps_without_ball > 20 and self.last_ball_pos is None:
             terminated = True
             logger.warning("Ball failed to spawn/detect after 20 steps.")

        ball_lost = False
        if hasattr(self.vision, 'ball_lost'):
            ball_lost = self.vision.ball_lost
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'ball_lost'):
            ball_lost = self.vision.capture.ball_lost
        
        # Override ball_lost during grace period AND if ball is high up (likely spawning)
        is_spawning = False
        if ball_pos is not None and ball_pos[1] < 0.2: # Top 20%
             is_spawning = True
             
        if ball_pos is not None and ball_pos[1] > height * 0.98:
             logger.debug(f"Ball Lost Check: y={ball_pos[1]} > {height * 0.98} (Limit)")
             ball_lost = True

        if ball_lost and not is_spawning:
            if ball_lost:
                reward -= 1.0 # Reduced penalty (was -5.0) to allow positive runs
                reward_components['ball_lost'] -= 1.0
                logger.warning(f"TERMINATION: ball_lost flag was True. Spawning={is_spawning}. Pos={ball_pos}. Reward Penalty: -1.0")
            terminated = True
        
        if self.steps_without_ball > self.max_steps_without_ball:
            truncated = True
        
        # Increment step counter and check max episode length
        self.step_count += 1
        if self.step_count >= self.max_episode_steps:
            truncated = True
            logger.info(f"Episode truncated: reached max steps ({self.max_episode_steps})")


        info = {'reward_breakdown': reward_components}

        return obs, reward, terminated, truncated, info

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        
        self.current_score = 0
        self.last_score = 0
        self.steps_without_ball = 0
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_ball_pos = None # Added this back from original
        self.holding_steps = 0 # Added this back from original
        
        # Reset counters
        self.last_combo_count = 0
        self.last_multiplier = 1.0
        self.step_count = 0  # Reset episode step counter
        
        # Call reset_game on vision system to reset physics engine
        if hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'reset_game_state'):
            self.vision.capture.reset_game_state()
            logger.debug("Reset game state via vision.capture.reset_game_state()")
        elif hasattr(self.vision, 'reset_game_state'):
             self.vision.reset_game_state()
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'physics_engine'):
            # Manually reset physics engine if reset_game_state doesn't exist
            if hasattr(self.vision.capture.physics_engine, 'balls'):
                self.vision.capture.physics_engine.balls = [] # Force clear
                # self.vision.capture.physics_engine.reset() # Prefer full reset if available
                logger.info("Cleared balls from physics engine (manual)")
        
        if not self.headless:
             time.sleep(0.1) # Wait for reset to propogate
        else:
             # In headless mode, we must ensure the "add_ball" callback (queued in reset) 
             # is actually processed before we look for the ball.
             # This requires stepping the physics engine at least once.
             if hasattr(self.vision, 'manual_step'):
                 self.vision.manual_step(0.016)
                 self.vision.manual_step(0.016) # Do two steps to be safe (add + settle)
                 logger.debug("Forced manual_step in reset (headless)")
             elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'manual_step'):
                 self.vision.capture.manual_step(0.016)
                 self.vision.capture.manual_step(0.016)
                 logger.debug("Forced capture.manual_step in reset (headless)")
        
        # Random layouts if enabled
        if self.random_layouts and hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'layout'):
            if hasattr(self.vision.capture.layout, 'randomize'):
                self.vision.capture.layout.randomize()
                self.vision.capture.load_layout(self.vision.capture.layout.to_dict())
                logger.info("Randomized layout for new episode")

        # Add a ball to start the episode
        # REMOVED: physics.reset() now handles initial ball spawning
        # if hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'add_ball'):
        #     self.vision.capture.add_ball()
        #     logger.debug("Ball added during environment reset")
        # elif hasattr(self.vision, 'add_ball'):
        #     self.vision.add_ball()
        #     logger.debug("Ball added during environment reset")

        # Initial observation
        observation = np.zeros(self.observation_space.shape, dtype=np.float32)
        info = {}
        return observation, info

    def render(self):
        return None

    def close(self):
        pass

    def _execute_action(self, action: int):
        # Map discrete actions to hardware controller methods
        if action == constants.ACTION_FLIP_LEFT:
            self.hw.hold_left()
            self.hw.release_right()
        elif action == constants.ACTION_FLIP_RIGHT:
            self.hw.hold_right()
            self.hw.release_left()
        elif action == constants.ACTION_FLIP_BOTH:
            self.hw.hold_left()
            self.hw.hold_right()
        elif action == constants.ACTION_NUDGE_LEFT:
            if hasattr(self.vision, 'nudge_left'):
                self.vision.nudge_left()
            elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'nudge_left'):
                self.vision.capture.nudge_left()
        elif action == constants.ACTION_NUDGE_RIGHT:
            if hasattr(self.vision, 'nudge_right'):
                self.vision.nudge_right()
            elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'nudge_right'):
                self.vision.capture.nudge_right()
        else:
            self.hw.release_left()
            self.hw.release_right()

    def _get_current_frame(self):
        if hasattr(self.vision, 'get_frame'):
            return self.vision.get_frame()
        if hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'get_frame'):
            return self.vision.capture.get_frame()
        return None

    def _create_observation(self, ball_pos, vx, vy, width, height):
        obs = np.zeros(self.observation_space.shape, dtype=np.float32)
        if ball_pos is not None:
            obs[0] = np.clip(ball_pos[0] / width, 0.0, 1.0)
            obs[1] = np.clip(ball_pos[1] / height, 0.0, 1.0)
        obs[2] = np.clip(vx / width, -1.0, 1.0)
        obs[3] = np.clip(vy / height, -1.0, 1.0)
        
        # Add Drop Targets
        target_states = []
        if hasattr(self.vision, 'drop_target_states'):
             target_states = self.vision.drop_target_states
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'drop_target_states'):
             target_states = self.vision.capture.drop_target_states
             
        for i in range(4):
            if i < len(target_states):
                obs[4 + i] = 1.0 if target_states[i] else 0.0
        return obs

    def _update_score(self, frame):
        # Prefer vision capture score if available
        if hasattr(self.vision, 'get_score'):
            self.current_score = self.vision.get_score()
        elif hasattr(self.vision, 'capture') and hasattr(self.vision.capture, 'get_score'):
            self.current_score = self.vision.capture.get_score()
        elif hasattr(self.score_reader, 'read_score') and frame is not None:
            self.current_score = self.score_reader.read_score(frame)

    def _get_difficulty_params(self):
        # Tuned difficulty parameters
        presets = {
            'easy': {
                'survival_reward': 0.0001,  # Reduced from 0.01
                'holding_threshold': 120,  # 4 seconds - more lenient
                'holding_penalty': 0.001  # Lower penalty
            },
            'medium': {
                'survival_reward': 0.005,  # Increased from 0.001 to value life more
                'holding_threshold': 90,  # 3 seconds
                'holding_penalty': 0.002
            },
            'hard': {
                'survival_reward': 0.0005,  # Moderate survival pressure
                'holding_threshold': 60,  # 2 seconds - aggressive
                'holding_penalty': 0.008
            }
        }
        return presets.get(self.difficulty, presets['medium'])

    def get_game_state(self):
        return {
            'score': self.current_score,
            'last_ball_pos': self.last_ball_pos,
            'steps_without_ball': self.steps_without_ball,
        }
