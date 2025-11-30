import logging
from pbwizard.constants import ACTION_NOOP
import numpy as np
import os
import random

from stable_baselines3 import PPO


logger = logging.getLogger(__name__)


class ReflexAgent:

    def __init__(self, zone_manager, hardware_controller):
        self.zone_manager = zone_manager
        self.hw = hardware_controller

    def act(self, ball_pos, frame_width, frame_height, velocity=(0, 0)):
        if ball_pos is None:
            return

        x, y = ball_pos
        vx, vy = velocity
        zones = self.zone_manager.get_zone_status(x, y)
        
        # Debug Log (Throttle?)
        if random.random() < 0.05: # Log 5% of frames to avoid spam
             logger.info(f"Agent Act: Pos=({x:.1f}, {y:.1f}), Vel=({vx:.1f}, {vy:.1f}), Zones={zones}")

        # Only flip if ball is moving down (vy > 0) to prevent flailing
        # Also could check if ball is in lower part of zone for better timing
        
        # Anti-holding logic
        if not hasattr(self, 'left_hold_steps'): self.left_hold_steps = 0
        if not hasattr(self, 'right_hold_steps'): self.right_hold_steps = 0
        if not hasattr(self, 'left_cooldown'): self.left_cooldown = 0
        if not hasattr(self, 'right_cooldown'): self.right_cooldown = 0
        
        MAX_HOLD = 60 # approx 2 seconds
        MIN_HOLD = 10 # approx 0.3 seconds
        COOLDOWN = 30 # approx 1 second
        
        # Left Flipper Logic
        if self.left_cooldown > 0:
            self.left_cooldown -= 1
            self.hw.release_left()
        else:
            # Check if we should START flipping
            should_flip = zones['left'] and vy > 0
            
            # Check if we are ALREADY holding
            is_holding = self.left_hold_steps > 0
            
            if is_holding:
                # If holding, check if we should CONTINUE
                # Continue if:
                # 1. We haven't reached MIN_HOLD (forced hold)
                # 2. We haven't reached MAX_HOLD AND (ball is still in zone OR moving down)
                
                force_hold = self.left_hold_steps < MIN_HOLD
                valid_hold = (zones['left'] or vy > 0) and self.left_hold_steps < MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_left()
                    self.left_hold_steps += 1
                else:
                    self.hw.release_left()
                    self.left_cooldown = COOLDOWN
                    self.left_hold_steps = 0
            elif should_flip:
                # Start flipping
                logger.debug("Ball in Left Zone & Moving Down -> Flip Left")
                self.hw.flip_left()
                self.left_hold_steps = 1
            else:
                self.hw.release_left()
                self.left_hold_steps = 0
        
        # Right Flipper Logic
        if self.right_cooldown > 0:
            self.right_cooldown -= 1
            self.hw.release_right()
        else:
            should_flip = zones['right'] and vy > 0
            is_holding = self.right_hold_steps > 0
            
            if is_holding:
                force_hold = self.right_hold_steps < MIN_HOLD
                valid_hold = (zones['right'] or vy > 0) and self.right_hold_steps < MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_right()
                    self.right_hold_steps += 1
                else:
                    self.hw.release_right()
                    self.right_cooldown = COOLDOWN
                    self.right_hold_steps = 0
            elif should_flip:
                logger.debug("Ball in Right Zone & Moving Down -> Flip Right")
                self.hw.flip_right()
                self.right_hold_steps = 1
            else:
                self.hw.release_right()
                self.right_hold_steps = 0


class RLAgent:

    def __init__(self, env=None, model_path=None):
        self.model = None
        if model_path and os.path.exists(model_path):
            logger.info(f"Loading RL model from {model_path}")
            self.model = PPO.load(model_path)
        elif env:
            logger.info("Initializing new PPO model")
            self.model = PPO("MlpPolicy", env, verbose=1)
        else:
            logger.warning("RLAgent initialized without env or model_path. Cannot train or predict.")

    def train(self, total_timesteps=10000, callbacks=None):
        if self.model:
            logger.info(f"Starting training for {total_timesteps} timesteps...")
            self.model.learn(total_timesteps=total_timesteps, callback=callbacks)
            logger.info("Training complete.")
        else:
            logger.error("No model to train.")

    def predict(self, observation):
        if self.model:
            action, _ = self.model.predict(observation)
            return action
        return ACTION_NOOP # No-op

    def save(self, path):
        if self.model:
            self.model.save(path)
            logger.info(f"Model saved to {path}")

    def load_model(self, path):
        if os.path.exists(path):
            logger.info(f"Loading RL model from {path}")
            # We need to preserve the environment if we reload
            env = self.model.get_env() if self.model else None
            self.model = PPO.load(path, env=env)
            return True
        else:
            logger.error(f"Model path not found: {path}")
            return False
