import os
import time
import logging
import numpy as np
import multiprocessing
from stable_baselines3.common.callbacks import BaseCallback

from pbwizard import vision, hardware, agent, constants
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
            except:
                pass
        return True

class WebStatsCallback(BaseCallback):
    def __init__(self, status_queue, total_timesteps, verbose=0):
        super().__init__(verbose)
        self.status_queue = status_queue
        self.total_timesteps = total_timesteps
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
            
            # Calculate ETA
            elapsed_time = time.time() - self.start_time
            eta_seconds = 0
            if self.num_timesteps > 0 and elapsed_time > 0:
                fps = self.num_timesteps / elapsed_time
                remaining_steps = self.total_timesteps - self.num_timesteps
                if fps > 0:
                    eta_seconds = remaining_steps / fps

            stats = {
                'timesteps': self.num_timesteps,
                'mean_reward': mean_reward,
                'is_training': True,
                'training_progress': self.num_timesteps / self.total_timesteps,
                'current_step': self.num_timesteps,
                'total_steps': self.total_timesteps,
                'eta_seconds': eta_seconds
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
        
        # Always use simulated capture for training
        cap = vision.SimulatedFrameCapture(width=width, height=height, headless=True)
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

        vision_wrapper = TrainingVisionWrapper(cap)
        
        # Score Reader (Mock)
        class MockScoreReader:
            def read_score(self, frame): return 0
            
        score_reader = MockScoreReader()
        
        # Environment
        env = PinballEnv(vision_wrapper, hw, score_reader, headless=True, random_layouts=config.get('random_layouts', False))
        
        # 2. Setup Agent
        model_name = config.get('model_name', 'ppo_pinball')
        total_timesteps = config.get('total_timesteps', 100000)
        
        agent_wrapper = agent.RLAgent(env=env)
        
        # 3. Callbacks
        callbacks = [
            StateSyncCallback(vision_wrapper, state_queue),
            QueueStopCallback(command_queue),
            WebStatsCallback(status_queue, total_timesteps),
            ProgressBarCallback(total_timesteps)
        ]
        
        # 4. Train
        status_queue.put(('status', 'started'))
        agent_wrapper.train(total_timesteps=total_timesteps, callbacks=callbacks)
        
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
        status_queue.put(('status', 'finished'))
        
    except Exception as e:
        logger.error(f"Training Worker Error: {e}")
        status_queue.put(('error', str(e)))
    finally:
        if 'cap' in locals():
            cap.stop()
