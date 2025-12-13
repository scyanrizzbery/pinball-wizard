import os
import time
import logging
import multiprocessing
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.utils import safe_mean

from pbwizard import vision, hardware, agent
from pbwizard.environment import PinballEnv

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StateSyncCallback(BaseCallback):
    """
    Callback to sync simulation state to the main process via a queue.
    """
    def __init__(self, vision_wrapper, state_queue, verbose=0):
        super().__init__(verbose)
        self.vision_wrapper = vision_wrapper
        self.state_queue = state_queue
        self.last_sync = 0

    def _on_step(self) -> bool:
        # Sync at ~30 FPS
        current_time = time.time()
        if current_time - self.last_sync > 0.033:
            if hasattr(self.vision_wrapper.capture, 'get_state'):
                state = self.vision_wrapper.capture.get_state()
                try:
                    # Clear old state if queue is full to avoid lag
                    if self.state_queue.full():
                        try:
                            self.state_queue.get_nowait()
                        except:
                            pass
                    self.state_queue.put(state)
                except:
                    pass
            self.last_sync = current_time
        return True


class QueueStopCallback(BaseCallback):
    """
    Callback to check a multiprocessing queue for a STOP command.
    """
    def __init__(self, command_queue, verbose=0):
        super().__init__(verbose)
        self.command_queue = command_queue

    def _on_step(self) -> bool:
        if not self.command_queue.empty():
            try:
                cmd = self.command_queue.get_nowait()
                if cmd == 'STOP':
                    logger.info("Training stopped by user command.")
                    return False
                elif isinstance(cmd, dict) and cmd.get('type') == 'UPDATE_REWARDS':
                    # Update environment rewards
                    # self.training_env is a VecEnv (DummyVecEnv)
                    if hasattr(self.training_env, 'envs'):
                        for env in self.training_env.envs:
                            # Unwrap Monitor if present
                            while hasattr(env, 'env'):
                                if hasattr(env, 'rewards_config'):
                                    env.rewards_config.update(cmd.get('rewards', {}))
                                    logger.info(f"Updated rewards config: {cmd.get('rewards')}")
                                    break
                                env = env.env
                            else:
                                # If loop finished without break, check the env itself
                                if hasattr(env, 'rewards_config'):
                                    env.rewards_config.update(cmd.get('rewards', {}))
                                    logger.info(f"Updated rewards config: {cmd.get('rewards')}")
            except Exception as e:
                logger.error(f"Error processing command queue: {e}")
        return True


class WebStatsCallback(BaseCallback):
    def __init__(self, status_queue, total_timesteps, model_name="Unknown", verbose=0):
        super().__init__(verbose)
        self.status_queue = status_queue
        self.total_timesteps = total_timesteps
        self.model_name = model_name
        self.start_time = None

    def _on_training_start(self) -> None:
        self.start_time = time.time()

    def _on_step(self) -> bool:
        if self.start_time is None:
            self.start_time = time.time()

        if self.num_timesteps % 100 == 0:
            # Extract stats
            infos = self.locals.get("infos", [{}])[0]
            mean_reward = 0
            if "episode" in infos:
                mean_reward = infos["episode"]["r"]
                logger.info(f"Step {self.num_timesteps}: Episode Reward={mean_reward:.2f}")
            
            # Calculate ETA
            elapsed_time = time.time() - self.start_time
            eta_seconds = 0
            if self.num_timesteps > 0 and elapsed_time > 0:
                fps = self.num_timesteps / elapsed_time
                remaining_steps = self.total_timesteps - self.num_timesteps
                if fps > 0:
                    eta_seconds = remaining_steps / fps

            # Extract PPO metrics from logger
            # SB3 logger stores values in name_to_value
            logger_values = self.logger.name_to_value
            
            def safe_float(val):
                if hasattr(val, 'item'): return val.item()
                try: return float(val)
                except: return 0.0

            # Calculate real-time metrics
            current_fps = 0
            if elapsed_time > 0:
                current_fps = int(self.num_timesteps / elapsed_time)
            
            # Use ep_info_buffer for real-time mean reward
            # This updates every episode, unlike logger which updates every n_steps
            ep_rew_mean = 0.0
            ep_len_mean = 0.0
            if self.model and hasattr(self.model, 'ep_info_buffer'):
                if len(self.model.ep_info_buffer) > 0:
                    ep_rew_mean = safe_mean([ep_info['r'] for ep_info in self.model.ep_info_buffer])
                    ep_len_mean = safe_mean([ep_info['l'] for ep_info in self.model.ep_info_buffer])

            stats = {
                'timesteps': self.num_timesteps,
                'model_name': self.model_name,
                'mean_reward': safe_float(mean_reward),
                'is_training': True,
                'training_progress': self.num_timesteps / self.total_timesteps,
                'current_step': self.num_timesteps,
                'total_steps': self.total_timesteps,
                'eta_seconds': eta_seconds,
                
                # PPO Metrics
                'fps': current_fps, # Use real-time FPS
                'loss': safe_float(logger_values.get('train/loss', 0.0)),
                'value_loss': safe_float(logger_values.get('train/value_loss', 0.0)),
                'policy_gradient_loss': safe_float(logger_values.get('train/policy_gradient_loss', 0.0)),
                'entropy_loss': safe_float(logger_values.get('train/entropy_loss', 0.0)),
                'approx_kl': safe_float(logger_values.get('train/approx_kl', 0.0)),
                'learning_rate': safe_float(logger_values.get('train/learning_rate', 0.0)),
                'explained_variance': safe_float(logger_values.get('train/explained_variance', 0.0)),
                'ep_len_mean': ep_len_mean, # Use real-time mean length
                'ep_rew_mean': ep_rew_mean  # Use real-time mean reward
            }
            try:
                self.status_queue.put(('stats', stats))
            except Exception as e:
                logger.error(f"WebStatsCallback error: {e}")
        return True


class ProgressBarCallback(BaseCallback):
    def __init__(self, total_timesteps, verbose=0):
        super().__init__(verbose)
        self.total_timesteps = total_timesteps
        self.last_log = 0

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_log >= 1000:
            progress = self.num_timesteps / self.total_timesteps
            logger.info(f"Training Progress: {progress:.1%} ({self.num_timesteps}/{self.total_timesteps})")
            self.last_log = self.num_timesteps
        return True


def train_worker(config, state_queue, command_queue, status_queue):
    """
    Worker function to run training in a separate process.
    """
    try:
        logger.info(f"Training Worker Started with config: {config}")
        
        # 1. Setup Environment
        width = int(os.getenv('SIM_WIDTH', 450))
        height = int(os.getenv('SIM_HEIGHT', 800))
        
        # Load Layout if specified
        layout_config = None
        layout_name = config.get('layout')
        if layout_name:
            import json
            # Check if it's a filename or "Default"
            if layout_name.lower() == 'default':
                 layout_file = 'default.json'
            else:
                 layout_file = f"{layout_name}.json"
            
            layout_path = os.path.join(os.getcwd(), 'layouts', layout_file)
            if os.path.exists(layout_path):
                try:
                    with open(layout_path, 'r') as f:
                        layout_config = json.load(f)
                    logger.info(f"Training using layout: {layout_name}")
                except Exception as e:
                    logger.error(f"Failed to load layout {layout_path}: {e}")
            else:
                logger.warning(f"Layout file not found: {layout_path}")

        # Always use simulated capture for training
        cap = vision.SimulatedFrameCapture(layout_config=layout_config, width=width, height=height)
        
        # Apply Physics Config if provided
        physics_config = config.get('physics') or {}
        
        # Merge top-level config keys into physics_config for backward compatibility
        # (Since config.json often has flat structure)
        overrides = ['launch_angle', 'flipper_speed', 'auto_plunge_enabled', 'plunger_release_speed']
        for key in overrides:
            if key in config:
                physics_config[key] = config[key]
        # Force auto-plunge for training to prevent negative reward loops
        physics_config['auto_plunge_enabled'] = True
        
        if hasattr(cap, 'update_physics_params'):
            logger.info("Applying custom physics config for training (Auto-Plunge Forced)")
            cap.update_physics_params(physics_config)
            
        cap.start()
        
        # Mock Controller
        hw = hardware.MockController(vision_system=cap)
        
        # Minimal Vision Wrapper
        class TrainingVisionWrapper:
            def __init__(self, capture):
                self.capture = capture
                self.lock = multiprocessing.Lock() # Not really needed in single process, but for compat
                
            def update(self):
                # In headless training, we don't need to process frames with CV
                # We just need to step the environment which steps the sim
                pass
                
            def get_stats(self):
                return {}

            def manual_step(self, dt=None):
                if hasattr(self.capture, 'manual_step'):
                    self.capture.manual_step(dt)

        vision_wrapper = TrainingVisionWrapper(cap)
        
        # Score Reader (Mock)
        class MockScoreReader:
            def read_score(self, frame): return 0
            
        score_reader = MockScoreReader()
        
        # Environment
        from stable_baselines3.common.monitor import Monitor
        env = PinballEnv(vision_wrapper, hw, score_reader, headless=True, random_layouts=config.get('random_layouts', False))
        env = Monitor(env)
        
        # 2. Setup Agent
        model_name = config.get('model_name', 'ppo_pinball')
        total_timesteps = config.get('total_timesteps', 100000)
        
        agent_wrapper = agent.RLAgent(env=env)
        
        # 3. Callbacks
        callbacks = [
            StateSyncCallback(vision_wrapper, state_queue),
            QueueStopCallback(command_queue),
            WebStatsCallback(status_queue, total_timesteps, model_name=model_name),
            ProgressBarCallback(total_timesteps)
        ]
        
        # 4. Train
        status_queue.put(('status', 'started'))
        agent_wrapper.train(total_timesteps=total_timesteps, callbacks=callbacks, hyperparams=config)
        
        # 5. Save
        models_dir = "models"
        os.makedirs(models_dir, exist_ok=True)
        
        # Auto-increment version
        import re
        pattern = re.compile(rf"{model_name}_v(\d+).zip")
        max_version = 0
        for filename in os.listdir(models_dir):
            match = pattern.match(filename)
            if match:
                version = int(match.group(1))
                if version > max_version:
                    max_version = version
        next_version = max_version + 1
        
        save_path = os.path.join(models_dir, f"{model_name}_v{next_version}")
        agent_wrapper.save(save_path)
        
        logger.info(f"Training finished. Model saved to {save_path}")
        # Send model name (basename) so main process can load it
        model_filename = f"{model_name}_v{next_version}.zip"
        status_queue.put(('status', {'state': 'finished', 'model': model_filename}))
        
    except Exception as e:
        logger.error(f"Training Worker Error: {e}")
        status_queue.put(('error', str(e)))
    finally:
        if 'cap' in locals():
            cap.stop()
