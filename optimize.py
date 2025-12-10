import eventlet
eventlet.monkey_patch()

import os
import logging
import time
import json
import optuna
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.monitor import Monitor
from optuna.visualization import plot_optimization_history, plot_param_importances

from pbwizard import vision, hardware, agent
from pbwizard.environment import PinballEnv

import threading
from pbwizard import web_server 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force Headless Mode for Simulation (Unlocks FPS)
os.environ['HEADLESS_SIM'] = 'true'

from stable_baselines3.common.callbacks import BaseCallback

class ProgressCallback(BaseCallback):
    def __init__(self, verbose=0, socketio=None):
        super().__init__(verbose)
        self.last_time = time.time()
        self.last_emit_time = time.time()
        self.socketio = socketio
        self.frame_count = 0
        
    def _on_step(self) -> bool:
        # Crucial: Yield to eventlet green threads (web server, physics)
        # Without this, the training loop starves the background threads.
        time.sleep(0)
        
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
    
    # Use default layout
    layout_config = None
    layout_path = os.path.join(os.getcwd(), 'layouts', 'symmetry.json')
    if os.path.exists(layout_path):
        with open(layout_path, 'r') as f:
            layout_config = json.load(f)

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

    vision_wrapper = TrainingVisionWrapper(cap)
    
    # We need to set this global for web_server.stream_frames to work (if used)
    # But here we are manually pushing frames.
    # web_server.vision_system = vision_wrapper

    # Mock Score Reader
    class MockScoreReader:
        def read_score(self, frame): return 0
    
    score_reader = MockScoreReader()

    # Create Environment
    # If trial is provided, we could potentially optimize environment params too!
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
    env, cap = create_env(socketio=web_server.socketio)
    env = Monitor(env) # Monitor for stats
    
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
            device='cpu' # Force CPU for MlpPolicy to avoid GPU overhead (small data)
        )

        # Train for a limited budget (e.g., 50k steps) to evaluate performance
        # Using a PruningCallback would be ideal here if using SB3's integration, 
        # but for simplicity we'll just train and return final mean reward.
        total_timesteps = 50000 
        model.learn(total_timesteps=total_timesteps, callback=ProgressCallback(socketio=web_server.socketio))

        # Evaluate logic (e.g. last 100 episodes mean reward)
        # We can extract this from the environment Monitor wrapper or model.ep_info_buffer
        mean_reward = -1000
        if len(model.ep_info_buffer) > 0:
            import numpy as np
            mean_reward = np.mean([ep_info['r'] for ep_info in model.ep_info_buffer])
        
        return mean_reward

    except Exception as e:
        logger.error(f"Trial failed: {e}")
        import traceback
        traceback.print_exc()
        return float('-inf')
    finally:
        cap.stop()
        env.close()

if __name__ == "__main__":
    # Check for GPU
    import torch
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"🚀 CUDA Available! Using GPU: {device_name}")
    else:
        logger.warning("⚠️ CUDA Not Available. running on CPU.")

    # Start Web Server in Background Thread
    def run_server():
        web_server.socketio.run(web_server.app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info("Web Server started on port 5000")

    study_name = "pinball_ppo_optimization"
    storage_name = "sqlite:///{}.db".format(study_name)
    
    logger.info("Starting Optuna Optimization...")
    study = optuna.create_study(
        study_name=study_name, 
        storage=storage_name, 
        direction="maximize",
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner()
    )
    
    # Run optimization
    study.optimize(objective, n_trials=20) # Start with 20 trials

    # Print results
    logger.info("Optimization finished!")
    logger.info(f"Best trial: {study.best_trial.value}")
    logger.info("Best parameters:")
    for key, value in study.best_trial.params.items():
        logger.info(f"    {key}: {value}")
    
    # Save best params to file
    with open('hyperparams.json', 'w') as f:
        json.dump(study.best_trial.params, f, indent=4)
