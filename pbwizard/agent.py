import logging
import os
import random

from stable_baselines3 import PPO

from pbwizard.constants import ACTION_NOOP


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

    def __init__(self, hardware_controller, difficulty='medium'):
        self.hw = hardware_controller
        self.difficulty = difficulty
        self.enabled = True  # AI enabled by default
        
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
        # Wrapper for single ball compatibility
        if ball_pos is None:
            self.tick_state(action_left=False, action_right=False)
            return
            
        self.act_multiball([(ball_pos, velocity)], frame_width, frame_height)

    def act_multiball(self, balls_data, frame_width, frame_height):
        # balls_data is list of tuples: [ (pos, vel), ... ]
        if not getattr(self, 'enabled', True):
            self.hw.release_left()
            self.hw.release_right()
            return
            
        should_flip_left = False
        should_flip_right = False
        
        # Analyze each ball
        for ball_pos, velocity in balls_data:
            if ball_pos is None: continue
            
            x, y = ball_pos
            vx, vy = velocity
            
            # --- Left Logic ---
            # Check if this ball wants to flip left
            ball_flip_left = False
            is_prediction = False
            
            if vy > self.VY_THRESHOLD:
                ball_flip_left = True
            elif self.USE_VELOCITY_PREDICTION:
                 # Predict
                 frames_ahead = 5
                 predicted_y = y + (vy * frames_ahead / 30.0)
                 if vy > self.VY_THRESHOLD * 0.5:
                     ball_flip_left = True
                     is_prediction = True
            
            if ball_flip_left:
                should_flip_left = True
                
            # --- Right Logic ---
            ball_flip_right = False
            if vy > self.VY_THRESHOLD:
                ball_flip_right = True
            elif self.USE_VELOCITY_PREDICTION:
                 if vy > self.VY_THRESHOLD * 0.5:
                     ball_flip_right = True

            if ball_flip_right:
                should_flip_right = True
                
        # Now apply state logic (Cooldowns and Holds) ONCE
        
        # Left State
        if self.left_cooldown > 0:
            self.left_cooldown -= 1
            self.hw.release_left()
        else:
            is_holding = self.left_hold_steps > 0
            
            if is_holding:
                # Continue holding if valid or forced
                # NOTE: We assume 'should_flip_left' represents "ball is in danger"
                force_hold = self.left_hold_steps < self.MIN_HOLD
                valid_hold = should_flip_left and self.left_hold_steps < self.MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_left()
                    self.left_hold_steps += 1
                else:
                    self.hw.release_left()
                    self.left_cooldown = self.COOLDOWN
                    self.left_hold_steps = 0
            elif should_flip_left:
                self.hw.flip_left()
                self.left_hold_steps = 1
            else:
                self.hw.release_left()
                self.left_hold_steps = 0
                
        # Right State
        if self.right_cooldown > 0:
            self.right_cooldown -= 1
            self.hw.release_right()
        else:
            is_holding = self.right_hold_steps > 0
            
            if is_holding:
                force_hold = self.right_hold_steps < self.MIN_HOLD
                valid_hold = should_flip_right and self.right_hold_steps < self.MAX_HOLD
                
                if force_hold or valid_hold:
                    self.hw.flip_right()
                    self.right_hold_steps += 1
                else:
                    self.hw.release_right()
                    self.right_cooldown = self.COOLDOWN
                    self.right_hold_steps = 0
            elif should_flip_right:
                self.hw.flip_right()
                self.right_hold_steps = 1
            else:
                self.hw.release_right()
                self.right_hold_steps = 0
                
    def tick_state(self, action_left, action_right):
        # Helper to just tick down cooldowns if no action
        if self.left_cooldown > 0: self.left_cooldown -= 1
        if self.right_cooldown > 0: self.right_cooldown -= 1


class RLAgent:

    def __init__(self, env=None, model_path=None, tensorboard_log=None):
        self.model = None
        self.enabled = True  # AI enabled by default
        self._warned_no_model = False
        if model_path and os.path.exists(model_path):
            logger.info(f"Loading RL model from {model_path}")
            self.model = PPO.load(model_path)
        elif env:
            # Check for optimized hyperparameters
            hp_path = "hyperparams.json"
            hyperparams = {
                "ent_coef": 0.01,
                "learning_rate": 3e-4,
                "n_steps": 2048,
                "batch_size": 64,
                "gamma": 0.99,
                "gae_lambda": 0.95
            }
            
            if os.path.exists(hp_path):
                try:
                    import json
                    with open(hp_path, 'r') as f:
                        loaded_params = json.load(f)
                        # Only update valid keys
                        for k, v in loaded_params.items():
                             if k in hyperparams or k == 'gae_lambda':
                                 hyperparams[k] = v
                    logger.info(f"Loaded optimized hyperparameters: {hyperparams}")
                except Exception as e:
                    logger.error(f"Failed to load hyperparameters: {e}")

            logger.info("Initializing new PPO model")
            self.model = PPO(
                "MlpPolicy", 
                env, 
                verbose=1,
                ent_coef=hyperparams['ent_coef'],
                learning_rate=hyperparams['learning_rate'],
                n_steps=int(hyperparams['n_steps']),
                batch_size=int(hyperparams['batch_size']),
                gamma=hyperparams['gamma'],
                gae_lambda=hyperparams.get('gae_lambda', 0.95),
                device='cpu',
                tensorboard_log=tensorboard_log
            )
        else:
            logger.warning("RLAgent initialized without env or model_path. Cannot train or predict.")

    def train(self, total_timesteps=10000, callbacks=None, hyperparams=None):
        if hyperparams:
            logger.info(f"Re-initializing model with custom hyperparameters: {hyperparams}")
            self.model = PPO(
                "MlpPolicy",
                self.model.env if self.model else None, # Reuse env if available
                verbose=1,
                ent_coef=hyperparams.get('ent_coef', 0.01),
                learning_rate=hyperparams.get('learning_rate', 3e-4),
                n_steps=int(hyperparams.get('n_steps', 2048)),
                batch_size=int(hyperparams.get('batch_size', 64)),
                gamma=hyperparams.get('gamma', 0.99),
                gae_lambda=hyperparams.get('gae_lambda', 0.95),
                device='cpu',
                tensorboard_log=self.model.tensorboard_log if self.model else None
            )

        if self.model:
            logger.info(f"Starting training for {total_timesteps} timesteps...")
            self.model.learn(total_timesteps=total_timesteps, callback=callbacks)
            logger.info("Training complete.")
        else:
            logger.error("No model to train.")

    def predict(self, observation):
        if self.model:
            try:
                action, _ = self.model.predict(observation)
                logger.debug(f"RL Agent predict: obs={observation}, action={action}")
                return action
            except ValueError as e:
                # Catch shape mismatch error from SB3
                if "Unexpected observation shape" in str(e):
                    if not getattr(self, '_warned_shape_mismatch', False):
                        logger.error(f"Observation shape mismatch (Active Model vs Current Env). Disabling RL inference. Error: {e}")
                        self._warned_shape_mismatch = True
                    return 0 # ACTION_NOOP
                raise e # Re-raise other errors
        else:
            if not self._warned_no_model:
                logger.warning("RL Agent predict called but no model loaded, returning NOOP (suppressing further warnings)")
                self._warned_no_model = True
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
            self._warned_no_model = False
            return True
        else:
            logger.error(f"Model path not found: {path}")
            return False
