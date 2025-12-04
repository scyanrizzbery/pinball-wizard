import logging
from pbwizard.constants import ACTION_NOOP
import numpy as np
import os
import random

from stable_baselines3 import PPO


logger = logging.getLogger(__name__)




class ReflexAgent:
    
    # Difficulty Presets
    DIFFICULTY_PARAMS = {
        'easy': {
            'MIN_HOLD': 15,  # Longer minimum hold
            'MAX_HOLD': 90,  # Longer maximum hold (3 seconds)
            'COOLDOWN': 45,  # Longer cooldown
            'VY_THRESHOLD': 100,  # Higher threshold = less sensitive
            'USE_VELOCITY_PREDICTION': False
        },
        'medium': {
            'MIN_HOLD': 10,
            'MAX_HOLD': 60,
            'COOLDOWN': 30,
            'VY_THRESHOLD': 50,
            'USE_VELOCITY_PREDICTION': False
        },
        'hard': {
            'MIN_HOLD': 5,  # Quick, precise flips
            'MAX_HOLD': 40,  # Shorter max hold
            'COOLDOWN': 20,  # Quick recovery
            'VY_THRESHOLD': 20,  # Very sensitive
            'USE_VELOCITY_PREDICTION': True  # Predictive flipping
        }
    }

    def __init__(self, zone_manager, hardware_controller, difficulty='medium'):
        self.zone_manager = zone_manager
        self.hw = hardware_controller
        self.difficulty = difficulty
        
        # Load difficulty parameters
        params = self.DIFFICULTY_PARAMS.get(difficulty, self.DIFFICULTY_PARAMS['medium'])
        self.MIN_HOLD = params['MIN_HOLD']
        self.MAX_HOLD = params['MAX_HOLD']
        self.COOLDOWN = params['COOLDOWN']
        self.VY_THRESHOLD = params['VY_THRESHOLD']
        self.USE_VELOCITY_PREDICTION = params['USE_VELOCITY_PREDICTION']
        
        # Initialize state tracking
        self.left_hold_steps = 0
        self.right_hold_steps = 0
        self.left_cooldown = 0
        self.right_cooldown = 0

    def act(self, ball_pos, frame_width, frame_height, velocity=(0, 0)):
        # Check if agent is enabled
        if not getattr(self, 'enabled', True):
            return
        
        if ball_pos is None:
            return

        x, y = ball_pos
        vx, vy = velocity
        zones = self.zone_manager.get_zone_status(x, y)
        
        # Debug Log (Throttle?)
        if random.random() < 0.1: # Log 10% of frames
             logger.info(f"Agent Act [{self.difficulty}]: Pos=({x:.1f}, {y:.1f}), Vel=({vx:.1f}, {vy:.1f}), Zones={zones}, LeftCooldown={self.left_cooldown}, RightCooldown={self.right_cooldown}")

        # Only flip if ball is moving down (vy > threshold) to prevent flailing
        
        # Left Flipper Logic
        if self.left_cooldown > 0:
            self.left_cooldown -= 1
            self.hw.release_left()
        else:
            # Check if we should START flipping
            should_flip = zones['left'] and vy > self.VY_THRESHOLD
            
            # Hard mode: predictive flipping based on velocity
            if self.USE_VELOCITY_PREDICTION and not should_flip:
                # Predict if ball will be in zone soon based on velocity
                frames_ahead = 5
                predicted_y = y + (vy * frames_ahead / 30.0)  # Approximate position
                if zones['left'] and vy > self.VY_THRESHOLD * 0.5:
                    should_flip = True
                    logger.debug("Predictive flip (hard mode)")
            
            # Check if we are ALREADY holding
            is_holding = self.left_hold_steps > 0
            
            if is_holding:
                # If holding, check if we should CONTINUE
                # Continue if:
                # 1. We haven't reached MIN_HOLD (forced hold)
                # 2. We haven't reached MAX_HOLD AND (ball is still in zone OR moving down)
                
                force_hold = self.left_hold_steps < self.MIN_HOLD
                valid_hold = (zones['left'] or vy > self.VY_THRESHOLD) and self.left_hold_steps < self.MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_left()
                    self.left_hold_steps += 1
                else:
                    self.hw.release_left()
                    self.left_cooldown = self.COOLDOWN
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
            should_flip = zones['right'] and vy > self.VY_THRESHOLD
            
            # Hard mode: predictive flipping
            if self.USE_VELOCITY_PREDICTION and not should_flip:
                frames_ahead = 5
                predicted_y = y + (vy * frames_ahead / 30.0)
                if zones['right'] and vy > self.VY_THRESHOLD * 0.5:
                    should_flip = True
                    logger.debug("Predictive flip (hard mode)")
            
            is_holding = self.right_hold_steps > 0
            
            if is_holding:
                force_hold = self.right_hold_steps < self.MIN_HOLD
                valid_hold = (zones['right'] or vy > self.VY_THRESHOLD) and self.right_hold_steps < self.MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_right()
                    self.right_hold_steps += 1
                else:
                    self.hw.release_right()
                    self.right_cooldown = self.COOLDOWN
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
            logger.debug(f"RL Agent predict: obs={observation}, action={action}")
            return action
        else:
            logger.warning("RL Agent predict called but no model loaded, returning NOOP")
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
