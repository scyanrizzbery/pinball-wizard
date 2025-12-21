import sys
import os

# Create a flag to allow eventlet patching before other imports
# We only patch if we are the MANAGER (not a worker)
if "--worker" not in sys.argv:
    import eventlet
    eventlet.monkey_patch()

import argparse
import logging
import time
import json
import optuna
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import BaseCallback

from pbwizard import vision, hardware
from pbwizard.environment import PinballEnv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(processName)s: %(message)s')
logger = logging.getLogger(__name__)

# Force Headless Mode for Simulation
os.environ['HEADLESS_SIM'] = 'true'

# Prevent NumPy/PyTorch from using multiple threads per process (oversubscription)
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

# Conditional imports for Main process
socketio_server = None

class ProgressCallback(BaseCallback):
    def __init__(self, verbose=0, socketio=None):
        super().__init__(verbose)
        self.last_time = time.time()
        self.last_emit_time = time.time()
        self.socketio = socketio
        self.frame_count = 0
        
    def _on_step(self) -> bool:
        # Crucial: Yield to eventlet green threads if using eventlet
        if self.socketio:
            time.sleep(0) # Yield for cooperative multitasking
        
        # 1. Log FPS every 5000 steps
        if self.n_calls % 5000 == 0:
            elapsed = time.time() - self.last_time
            fps = 5000 / elapsed if elapsed > 0 else 0
            self.last_time = time.time()
            logger.info(f"Trial Step {self.n_calls} - {fps:.2f} FPS")

        # 2. Emit to UI (Time-throttled to ~15 FPS)
        if self.socketio:
            current_time = time.time()
            if current_time - self.last_emit_time > 0.066: # Approx 15 FPS
                self.last_emit_time = current_time
                try:
                    # Access the environment
                    env = self.training_env.envs[0].unwrapped
                    # vision.wrapper -> capture
                    cap = env.vision.capture
                    
                    # Emit Frame
                    if hasattr(cap, 'render'):
                        cap.render() # Force render for UI snapshot
                        
                    frame = cap.get_frame()
                    if frame is not None:
                         import cv2
                         import base64
                         _, buffer = cv2.imencode('.jpg', frame)
                         frame_bytes = base64.b64encode(buffer).decode('utf-8')
                         self.socketio.emit('video_frame', {'image': frame_bytes}, namespace='/game')
                    
                    # Emit Stats
                    game_state = cap.get_game_state()
                    self.socketio.emit('game_state', game_state, namespace='/game')
                    
                    stats_data = {
                        'score': game_state.get('score', 0),
                        'high_score': game_state.get('high_score', 0),
                        'balls': game_state.get('balls', []),
                        'is_tilted': game_state.get('is_tilted', False)
                    }
                    self.socketio.emit('stats_update', stats_data, namespace='/game')

                except Exception as e:
                    pass # Don't crash training on UI error
        return True


def create_env(trial=None, socketio=None):
    """
    Creates a headless pinball environment for optimization.
    """
    width = 450
    height = 800
    
    # Load global config.json if available
    global_config = {}
    config_path = 'config.json'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                global_config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")

    # Use default layout
    layout_config = None
    layout_path = os.path.join(os.getcwd(), 'layouts', 'default.json')
    if os.path.exists(layout_path):
        with open(layout_path, 'r') as f:
            layout_config = json.load(f)
            
    # Merge config.json overrides into layout_config
    if layout_config and global_config:
        overrides = ['launch_angle', 'flipper_speed', 'auto_plunge_enabled', 'plunger_release_speed']
        for key in overrides:
            if key in global_config:
                layout_config[key] = global_config[key]
        
        # Merge 'physics' dict if present
        if 'physics' in global_config:
             if 'physics' not in layout_config: layout_config['physics'] = {}
             layout_config['physics'].update(global_config['physics'])

    # Sim Capture

    # Simulated Capture
    cap = vision.SimulatedFrameCapture(layout_config=layout_config, width=width, height=height, socketio=socketio)
    cap.start()

    # Mock Controller
    hw = hardware.MockController(vision_system=cap)

    # Training Vision Wrapper
    class TrainingVisionWrapper:
        def __init__(self, capture):
            self.capture = capture
        def update(self): pass
        def get_stats(self): return {}
        def get_events(self): 
            if hasattr(self.capture, 'get_events'):
                return self.capture.get_events()
            return []
        def get_score(self):
            if hasattr(self.capture, 'get_score'):
                return self.capture.get_score()
            return 0
        def get_ball_status(self):
            if hasattr(self.capture, 'get_ball_status'):
                return self.capture.get_ball_status()
            return None

    vision_wrapper = TrainingVisionWrapper(cap)
    
    # Mock Score Reader
    class MockScoreReader:
        def read_score(self, frame): return 0
    
    score_reader = MockScoreReader()

    # Create Environment
    env = PinballEnv(vision_wrapper, hw, score_reader, headless=True)
    return env, cap


def objective(trial):
    """
    Optuna objective function.
    """
    # Sample Hyperparameters
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True)
    ent_coef = trial.suggest_float("ent_coef", 0.001, 0.1, log=True)
    gamma = trial.suggest_categorical("gamma", [0.9, 0.95, 0.98, 0.99, 0.995])
    n_steps = trial.suggest_categorical("n_steps", [1024, 2048, 4096])
    batch_size = trial.suggest_categorical("batch_size", [64, 128, 256])
    gae_lambda = trial.suggest_categorical("gae_lambda", [0.9, 0.95, 0.98])
    
    # Setup Environment
    # Pass global socketio_server only if this process has one (Manager)
    env, cap = create_env(socketio=socketio_server)
    
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    env = Monitor(env) # Monitor for stats
    env = DummyVecEnv([lambda: env])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10., gamma=gamma)
    
    try:
        # Initialize Model
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=learning_rate,
            ent_coef=ent_coef,
            gamma=gamma,
            n_steps=n_steps,
            batch_size=batch_size,
            gae_lambda=gae_lambda,
            verbose=0,
            tensorboard_log="./optuna_logs/",
            device='cpu' # Force CPU 
        )

        total_timesteps = 50000 
        model.learn(total_timesteps=total_timesteps, callback=ProgressCallback(socketio=socketio_server))

        # Evaluate logic - get reward from completed episodes
        mean_reward = -1000  # Default 
        
        if len(model.ep_info_buffer) > 0:
            import numpy as np
            rewards = [ep_info['r'] for ep_info in model.ep_info_buffer]
            mean_reward = np.mean(rewards)
            logger.info(f"Trial completed {len(rewards)} episodes, mean reward: {mean_reward:.2f}")
        else:
            logger.warning(f"No episodes completed in {total_timesteps} timesteps!")
            mean_reward = -1000
        
        return mean_reward

    except Exception as e:
        logger.error(f"Trial failed: {e}")
        import traceback
        traceback.print_exc()
        return float('-inf')
    finally:
        cap.stop()
        env.close()

def run_worker(study_name, storage_name, n_trials=None):
    """Worker process function: runs optimization loop."""
    # Re-configure logging for worker process (processName kwarg handles ID)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(processName)s: %(message)s', force=True)
    logger.info(f"Worker process started. PID: {os.getpid()}. Joining study '{study_name}'...")
    try:
        study = optuna.load_study(study_name=study_name, storage=storage_name)
        study.optimize(objective, n_trials=n_trials) 
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pinball Optimization")
    parser.add_argument("--worker", action="store_true", help="Run in worker mode (no web server)")
    parser.add_argument("--trials", type=int, default=100, help="Total number of trials (approximate)")
    args = parser.parse_args()

    study_name = "pinball_ppo_optimization"
    storage_name = "sqlite:///{}.db".format(study_name)

    if args.worker:
        # WORKER MODE: No Eventlet, No UI
        run_worker(study_name, storage_name, n_trials=25) # Each worker does chunk
    else:
        # MANAGER MODE: Eventlet + UI + Subprocesses
        from pbwizard import web_server
        import threading
        import subprocess
        import sys
        
        # Set global for objective to use
        socketio_server = web_server.socketio
        
        # Start Web Server
        def run_server():
            web_server.socketio.run(web_server.app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info("Web Server started on port 5000")

        # Create/Load Study
        logger.info("Creating Optuna Study...")
        study = optuna.create_study(
            study_name=study_name, 
            storage=storage_name, 
            direction="maximize",
            load_if_exists=True,
            pruner=optuna.pruners.MedianPruner()
        )

        # Spawn Workers
        workers = []
        num_cores = max(1, os.cpu_count())
        num_workers = max(1, num_cores - 1) # Reserve 1 core for Manager+Server
        
        logger.info(f"Spawning {num_workers} background workers...")
        
        for i in range(num_workers):
            cmd = [sys.executable, "optimize.py", "--worker"]
            p = subprocess.Popen(cmd)
            workers.append(p)
        
        try:
            # Run Manager's share of trials (Visual)
            # This ensures at least one process is feeding the UI
            logger.info("Manager starting visual optimization loop...")
            try:
                study.optimize(objective, n_trials=args.trials)
                logger.info("Manager finished trials.")
            except KeyboardInterrupt:
                logger.info("Optimization interrupted by user. Saving best parameters so far...")

            logger.info("Optimization finished!")
            
            try:
                logger.info(f"Best trial: {study.best_trial.value}")
                logger.info("Best parameters:")
                for key, value in study.best_trial.params.items():
                    logger.info(f"    {key}: {value}")
                
                with open('frontend/public/hyperparams.json', 'w') as f:
                    json.dump(study.best_trial.params, f, indent=4)
                    
                logger.info("Saved hyperparams.json")
            except ValueError:
                logger.warning("No trials completed, cannot save best params.")
            except Exception as e:
                logger.error(f"Failed to save params: {e}")

        finally:
            logger.info("Terminating workers...")
            for p in workers:
                p.terminate()
                p.wait()
