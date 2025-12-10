import eventlet
eventlet.monkey_patch()

import os
import threading
import multiprocessing
try:
    multiprocessing.set_start_method('spawn', force=True) # Force restart v2
except RuntimeError:
    pass

import time
import logging
# Force restart v2
import numpy as np
from dotenv import load_dotenv


logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

from pbwizard import vision, hardware, agent, web_server, constants
import train # Import train module


def main():
    logger.info("Starting Pinball Bot...")
    
    # Debug: Log environment variables
    sim_mode = os.getenv('SIMULATION_MODE', 'False').strip()
    debug_mode = os.getenv('DEBUG_MODE', 'False').strip()
    logger.info(f"Environment Config: SIMULATION_MODE='{sim_mode}', DEBUG_MODE='{debug_mode}'")

    # 1. Initialize Vision System (First, so we can pass it to HW)
    if sim_mode.lower() == 'true':
        logger.info("Simulation Mode: Using Simulated Video Feed")
        
        # Create capture with default layout first
        cap = vision.SimulatedFrameCapture(width=450, height=800, layout_config=None, socketio=web_server.socketio)

        # Try to load last selected layout (this will properly set filepath)
        last_layout_name = None
        try:
            import json
            if os.path.exists("config.json"):
                with open("config.json", 'r') as f:
                    config_data = json.load(f)
                    last_layout_name = config_data.get('current_layout_id', None)
                    if last_layout_name:
                        layout_path = f"layouts/{last_layout_name}.json"
                        if os.path.exists(layout_path):
                            logger.info(f"Loading last selected layout: {last_layout_name}")
                            # Use load_layout() to properly set the filepath
                            cap.load_layout(last_layout_name)
                        else:
                            logger.warning(f"Last layout not found: {layout_path}, using default")
        except Exception as e:
            logger.error(f"Error loading last layout: {e}")
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
    if hasattr(cap, 'zone_manager'):
        zone_manager = cap.zone_manager
    else:
        zone_manager = vision.ZoneManager(width, height)
    score_reader = vision.ScoreReader()

    # 3. Initialize Agent
    use_rl = os.getenv('USE_RL_AGENT', 'False').strip().lower() == 'true'
    if use_rl:
        logger.info("Using RL Agent (PPO)")
        model_path = "models/ppo_pinball_v1.zip"
        
        # Try to load last used model from config
        try:
            import json
            if os.path.exists("config.json"):
                with open("config.json", 'r') as f:
                    config = json.load(f)
                    if 'last_model' in config and config['last_model']:
                        last_model = config['last_model']
                        last_model_path = os.path.join("models", last_model)
                        if os.path.exists(last_model_path):
                            model_path = last_model_path
                            logger.info(f"Loading last used model: {last_model}")
        except Exception as e:
            logger.error(f"Error loading config for model: {e}")
            
        # Fallback: If model_path doesn't exist, try to find ANY model
        if not os.path.exists(model_path):
            logger.warning(f"Default/Configured model not found: {model_path}")
            models_dir = "models"
            if os.path.exists(models_dir):
                files = [f for f in os.listdir(models_dir) if f.endswith('.zip')]
                if files:
                    model_path = os.path.join(models_dir, files[0])
                    logger.info(f"Falling back to first available model: {files[0]}")
            
        agnt = agent.RLAgent(model_path=model_path)
    else:
        logger.info("Using Reflex Agent")
        agnt = agent.ReflexAgent(zone_manager, hw)


    # 4. Start Web Server (in separate thread)
    class VisionWrapper:
        def __init__(self, capture, tracker, zones, is_simulation=False):
            self.capture = capture
            self.tracker = tracker
            self.zones = zones
            self.is_simulation = is_simulation
            self.latest_processed_frame = None
            self.lock = threading.Lock()
            self.ai_enabled = True
            self.high_score = 0
            self.games_played = 0
            self.last_ball_count = 0
            self.high_score = 0
            self.games_played = 0
            self.current_ball_count = 0
            self.last_ball_count = 0
            self.game_history = [] # List of {type, score, timestamp, ...}
            self.training_stats = {
                'timesteps': 0,
                'mean_reward': 0.0,
                'is_training': False
            }

        def add_history_event(self, event_type, data=None):
            """Add a non-game event to history"""
            event = {
                'type': event_type,
                'timestamp': time.time()
            }
            if data:
                event.update(data)
            
            with self.lock:
                self.game_history.append(event)
                # Keep last 50 entries (increased from 20 to allow for events)
                if len(self.game_history) > 50:
                    self.game_history.pop(0)

        def update_training_stats(self, stats):
            with self.lock:
                self.training_stats.update(stats)

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
                            # Count actual balls on table (not balls_remaining which is balls left to play)
                            if hasattr(self.capture, 'physics_engine') and self.capture.physics_engine:
                                self.current_ball_count = len(self.capture.physics_engine.balls)
                            elif hasattr(self.capture, 'balls'):
                                self.current_ball_count = sum(1 for ball in self.capture.balls if not ball.get('lost', False))
                            else:
                                self.current_ball_count = 0
                    return ball_pos
            
            # Fallback to CV tracking
            raw_frame = self.capture.get_frame()
            if raw_frame is not None:
                ball_pos, processed_frame = self.tracker.process_frame(raw_frame)
                
                # Update ball count based on detection
                with self.lock:
                    self.current_ball_count = 1 if ball_pos is not None else 0

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
                
            # Get real-time ball count directly from physics engine for accurate stats
            current_balls = 0
            engine = None
            game_hash = None
            seed = None
            
            if hasattr(self.capture, 'physics_engine') and self.capture.physics_engine:
                engine = self.capture.physics_engine
                current_balls = len(engine.balls)
                game_hash = getattr(engine, 'game_hash', None)
                seed = getattr(engine, 'seed', None)
            else:
                current_balls = self.current_ball_count

            if self.last_ball_count > 0 and current_balls == 0:
                self.games_played += 1
                
                is_high_score = False
                if current_score == self.high_score and current_score > 0:
                        is_high_score = True

                # Add to history
                self.game_history.append({
                    'type': 'game',
                    'score': current_score,
                    'hash': game_hash, 
                    'seed': seed,
                    'timestamp': time.time(),
                    'is_high_score': is_high_score
                })
                # Keep last 50 entries
                if len(self.game_history) > 50:
                    self.game_history.pop(0)
                
                # Reset score for new game
                if hasattr(self.capture, 'score'):
                    self.capture.score = 0
                if engine:
                    engine.score = 0
                    engine.set_tilt(False)
                # Reset tilt
                if hasattr(self.capture, 'tilt_value'):
                    self.capture.tilt_value = 0.0
                if hasattr(self.capture, 'is_tilted'):
                    self.capture.is_tilted = False

                # Reset balls_remaining for new game
                if hasattr(self.capture, 'balls_remaining'):
                    self.capture.balls_remaining = 1
                # Reset drop targets
                if hasattr(self.capture, 'drop_target_states') and hasattr(self.capture, 'layout'):
                    self.capture.drop_target_states = [True] * len(self.capture.layout.drop_targets)
                    
            self.last_ball_count = current_balls
                
            nudge_data = None
            if hasattr(self.capture, 'last_nudge'):
                nudge_data = self.capture.last_nudge
            
            tilt_value = 0.0
            is_tilted = False
            if hasattr(self.capture, 'tilt_value'):
                tilt_value = self.capture.tilt_value
            if hasattr(self.capture, 'is_tilted'):
                is_tilted = self.capture.is_tilted

            stats = {
                'score': current_score,
                'high_score': self.high_score,
                'balls': current_balls,
                'ball_count': current_balls,  # Actual balls on table
                'games_played': self.games_played,
                'nudge': nudge_data,
                'tilt_value': tilt_value,
                'is_tilted': is_tilted,
                'is_simulation': self.is_simulation,
                'game_history': self.game_history,
                'hash': game_hash,
                'seed': seed
            }
            
            # Fetch Hash/Seed from Physics Engine
            if hasattr(self.capture, 'physics_engine') and self.capture.physics_engine:
                 engine = self.capture.physics_engine
                 stats['hash'] = getattr(engine, 'game_hash', None)
                 stats['seed'] = getattr(engine, 'seed', None)
                 
            # Note: We need to also add hash to history events when a game ends.
            # But the 'game_history' append happened above, before we fetched the hash?
            # Actually, the hash is persistent for the CURRENT game.
            # When current game ENDS (current_balls == 0), we append logic.
            # Let's verify if we need to update the append block above.
            # Yes, we should include the hash of the FINISHED game in the history.
            
            

            # Merge training stats
            with self.lock:
                stats.update(self.training_stats)
                
            return stats

        def get_game_state(self):
            if hasattr(self.capture, 'get_game_state'):
                return self.capture.get_game_state()
            return {}

        def __getattr__(self, name):
            if name in ['ai_enabled']:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            return getattr(self.capture, name)

    vision_wrapper = VisionWrapper(cap, tracker, zone_manager, is_simulation=(sim_mode.lower() == 'true'))
    vision_wrapper.agent = agnt # Assign agent regardless of type so web server can control it
    
    if use_rl:
        # RL Agent Logic
        pass # Already handled by assignment above
    
    # 5. Bot Controller (Manages Play/Train modes)
    # 5. Bot Controller (Manages Play/Train modes)
    class BotController:
        def __init__(self):
            self.mode = 'PLAY' # 'PLAY' or 'TRAIN'
            self.training_config = {}
            self.stop_training_flag = False
            self.lock = threading.Lock()
            
            # Multiprocessing queues (Use Manager for eventlet compatibility)
            self.manager = multiprocessing.Manager()
            self.state_queue = self.manager.Queue(maxsize=10)
            self.command_queue = self.manager.Queue()
            self.status_queue = self.manager.Queue()
            self.training_process = None

        def start_training(self, config):
            with self.lock:
                if self.mode == 'TRAIN':
                    logger.warning("Already in training mode")
                    return
                
                self.mode = 'TRAIN'
                self.training_config = config
                self.stop_training_flag = False
                
                # Clear queues
                while not self.state_queue.empty(): self.state_queue.get()
                while not self.command_queue.empty(): self.command_queue.get()
                while not self.status_queue.empty(): self.status_queue.get()
                
                logger.info(f"Switching to TRAINING mode with config: {config}")
                
                # Start Training Process
                self.training_process = multiprocessing.Process(
                    target=train.train_worker,
                    args=(config, self.state_queue, self.command_queue, self.status_queue)
                )
                self.training_process.start()

        def stop_training(self):
            with self.lock:
                self.stop_training_flag = True
                logger.info("Stop training requested...")
                self.command_queue.put('STOP')

        def switch_to_play(self):
            with self.lock:
                self.mode = 'PLAY'
                self.stop_training_flag = False
                logger.info("Switching to PLAY mode")
                
                if self.training_process and self.training_process.is_alive():
                    self.command_queue.put('STOP')
                    self.training_process.join(timeout=5)
                    if self.training_process.is_alive():
                        self.training_process.terminate()
                    self.training_process = None
                
                # Reset stats
                vision_wrapper.update_training_stats({'is_training': False})

    controller = BotController()

    # Attach controller to vision wrapper so web server can access it
    vision_wrapper.controller = controller

    web_thread = threading.Thread(target=web_server.start_server, args=(vision_wrapper, int(os.getenv('FLASK_PORT', 5000))))
    web_thread.daemon = True
    web_thread.start()

    logger.info("Bot Running. Press Ctrl+C to stop.")

    # State tracking for RL
    last_ball_pos = None
    last_pos_time = time.time()
    last_vx, last_vy = 0.0, 0.0

    try:
        while True:
            # Check Mode
            current_mode = 'PLAY'
            with controller.lock:
                current_mode = controller.mode
            
            if current_mode == 'TRAIN':
                # In Training Mode, we listen for state updates from the worker
                # and update our local vision wrapper for visualization
                
                # 1. Check Status Queue
                try:
                    while not controller.status_queue.empty():
                        msg_type, msg_data = controller.status_queue.get_nowait()
                        if msg_type == 'stats':
                            # logger.info(f"Main received stats: {msg_data}") # Verbose
                            vision_wrapper.update_training_stats(msg_data)
                        elif msg_type == 'status':
                            # Handle both string and dict status for backward compatibility
                            status_state = msg_data
                            new_model = None
                            if isinstance(msg_data, dict):
                                status_state = msg_data.get('state')
                                new_model = msg_data.get('model')

                            if status_state == 'finished':
                                logger.info("Training process finished.")
                                controller.switch_to_play()
                                # Refresh model list for UI
                                try:
                                    web_server.handle_get_models()
                                except Exception as e:
                                    logger.error(f"Failed to refresh models list: {e}")
                                
                                # Auto-load new model if available
                                if new_model:
                                    logger.info(f"Auto-selected new model: {new_model}")
                                    web_server.emit_training_finished(new_model)
                                    logger.info(f"Auto-loading new model: {new_model}")
                                    try:
                                        # Simulate load_model call
                                        web_server.handle_load_model({'model': new_model})
                                        # Also notify UI to update selection
                                        web_server.socketio.emit('model_selected', {'model': new_model})
                                    except Exception as e:
                                        logger.error(f"Failed to auto-load model {new_model}: {e}")
                        elif msg_type == 'error':
                            logger.error(f"Training process error: {msg_data}")
                            controller.switch_to_play() # FIX: Reset state on error
                            # Notify UI
                            try:
                                web_server.socketio.emit('training_error', {'message': str(msg_data)}, namespace='/training')
                            except Exception:
                                pass
                except Exception as e:
                    logger.error(f"Error processing status queue: {e}")
                
                # 2. Check State Queue (Visuals)
                try:
                    latest_state = None
                    while not controller.state_queue.empty():
                        latest_state = controller.state_queue.get_nowait()
                    
                    if latest_state:
                        # Update local vision wrapper
                        # We need to set external_control = True on the capture object
                        if hasattr(vision_wrapper.capture, 'external_control'):
                            vision_wrapper.capture.external_control = True
                            vision_wrapper.capture.set_state(latest_state)
                except:
                    pass
                
                # Sleep a bit to avoid busy loop
                time.sleep(0.01)
                
            else:
                # PLAY Mode (Normal Inference with Fixed Timestep)
                
                # Ensure external control is off
                if hasattr(vision_wrapper.capture, 'external_control'):
                    vision_wrapper.capture.external_control = False

                current_time = time.time()
                dt = 0.016 # Target ~60Hz
                
                # 1. Update Vision
                # ball_pos = vision_wrapper.update() # Legacy variable update
                
                # Fixed Timestep Update
                # We enforce this via vision_wrapper.update() if it passes it down, or relies on internal fixed update of sim
                # Currently vision.py's SimulatedFrameCapture uses its own time.sleep().
                # For strict determinism, we should control the step here.
                # However, modifying that deeply might break things.
                # For now, let's stick to the previous loop style BUT with calculated DT if possible
                # Actually, simply calling update() triggers one frame step which is 1/60s in simulation.
                
                ball_pos = vision_wrapper.update()
                
                if ball_pos is not None:
                    
                    # Calculate velocity only if position changed (new frame)
                    # This prevents v=0 when main loop is faster than camera
                    if last_ball_pos is not None and (ball_pos[0] != last_ball_pos[0] or ball_pos[1] != last_ball_pos[1]):
                        real_dt = current_time - last_pos_time
                        if real_dt > 0:
                            last_vx = (ball_pos[0] - last_ball_pos[0]) / real_dt
                            last_vy = (ball_pos[1] - last_ball_pos[1]) / real_dt
                            last_pos_time = current_time
                            last_ball_pos = ball_pos
                    elif last_ball_pos is None:
                        last_ball_pos = ball_pos
                        last_pos_time = current_time
                        
                    vx, vy = last_vx, last_vy

                    if use_rl:
                        
                        # Check if ball is in any zone
                        zones = zone_manager.get_zone_status(ball_pos[0], ball_pos[1])
                        
                        action = constants.ACTION_NOOP
                        
                        if vision_wrapper.ai_enabled:
                            # logger.debug(f"RL Agent: Ball at ({ball_pos[0]:.1f}, {ball_pos[1]:.1f}), Zones={zones}, Vel=({vx:.1f}, {vy:.1f})")
                            if zones['left'] or zones['right']:
                                logger.debug(f"AI Active in Zone! Zones={zones}, Action={action}")
                            
                            # Construct observation [x, y, vx, vy, t1, t2, t3, t4]
                            # Match environment.py: _create_observation
                            obs = np.zeros(8, dtype=np.float32)
                            obs[0] = ball_pos[0] / width
                            obs[1] = ball_pos[1] / height
                            obs[2] = np.clip(vx / 50.0, -1, 1)
                            obs[3] = np.clip(vy / 50.0, -1, 1)
                            
                            # Add Drop Target States
                            target_states = []
                            if hasattr(vision_wrapper.capture, 'drop_target_states'):
                                target_states = vision_wrapper.capture.drop_target_states
                                
                            # Pad or Truncate to fixed size 4
                            for i in range(4):
                                if i < len(target_states):
                                    obs[4 + i] = 1.0 if target_states[i] else 0.0
                                else:
                                    obs[4 + i] = 0.0 # Pad with 0
                            
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
                            hw.hold_left()
                        else:
                            hw.release_left()

                        # Right Flipper
                        should_flip_right = (action == constants.ACTION_FLIP_RIGHT or action == constants.ACTION_FLIP_BOTH)
                        
                        # # Safety Override: If ball is in right zone and moving down, force flip
                        # if vision_wrapper.ai_enabled and zones['right'] and vy > 100: # Pixel/sec threshold
                        #     should_flip_right = True
                        
                        if should_flip_right and zones['right']:
                            hw.hold_right()
                        else:
                            hw.release_right()
                    else:
                        # Reflex Agent
                        if vision_wrapper.ai_enabled:
                            # logger.debug(f"Reflex Agent Act: Pos={ball_pos}, Vel=({vx:.1f}, {vy:.1f})")
                            agnt.act(ball_pos, width, height, velocity=(vx, vy))
                    
                    # last_ball_pos updated above
                else:
                    # Ball lost
                    last_ball_pos = None
                    last_vx, last_vy = 0.0, 0.0
                
                # Rate limiting (approx 60 Hz)
                # Ensure we don't drift too far from realtime
                elapsed = time.time() - current_time
                if elapsed < 0.016:
                    time.sleep(0.016 - elapsed)

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        cap.stop()
        logger.info("Clean exit.")


if __name__ == "__main__":
    main()
