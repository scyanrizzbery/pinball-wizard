import base64
import threading
import time
import logging
import os

import cv2
# Force reload v6
import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template
from flask_socketio import SocketIO

from pbwizard import constants

logger = logging.getLogger(__name__)

app = Flask(__name__,
            static_folder="../frontend/dist/assets",
            static_url_path="/assets",
            template_folder="../frontend/dist")
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app, cors_allowed_origins="*")

# Global reference to the vision system (set by main.py)
vision_system = None


@app.route('/')
def index():
    return render_template('index.html')


def stream_frames():
    logger.info("Starting stream_frames loop")
    frame_count = 0
    while True:
        try:
            if vision_system:
                # logger.debug("Getting frame...")
                
                # Emit 3D Game State
                if hasattr(vision_system, 'get_game_state'):
                    game_state = vision_system.get_game_state()
                    socketio.emit('game_state', game_state)
                    # Also emit stats_update for App.vue compatibility
                    # Also emit stats_update for App.vue compatibility
                    stats_data = {
                        'score': game_state.get('score', 0),
                        'high_score': game_state.get('high_score', 0),
                        'balls': game_state.get('balls_remaining', 0),
                        'games_played': game_state.get('games_played', 0),
                        'game_history': game_state.get('game_history', []),
                        'is_tilted': game_state.get('is_tilted', False),
                        'nudge': game_state.get('nudge', None)
                    }
                    
                    # Add training stats if available
                    if hasattr(vision_system, 'training_stats'):
                         stats_data.update(vision_system.training_stats)
                         
                    socketio.emit('stats_update', stats_data)
                    if len(game_state.get('balls', [])) > 0:
                        logger.debug(f"Emitting Game State: {game_state['balls'][0]}")

                # Video Feed - Stream simulation frames
                frame = vision_system.get_frame()
                if frame is not None:
                    # logger.debug("Encoding frame...")
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = base64.b64encode(buffer).decode('utf-8')
                    # logger.debug("Emitting frame...")
                    socketio.emit('video_frame', {'image': frame_bytes})

                    frame_count += 1
                    if frame_count % 100 == 0:
                        logger.debug(f"Emitted {frame_count} frames")
                else:
                    logger.warning("Vision system returned None frame")
            else:
                logger.warning("Vision system not initialized in stream_frames")
        except Exception as e:
            logger.error(f"Error in stream_frames: {e}")

        socketio.sleep(0.033)  # ~30 FPS


@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    # Sync physics config on connect
    if vision_system:
        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
        if hasattr(capture, 'get_config'):
            config = capture.get_config()
            socketio.emit('physics_config_loaded', config)
        elif hasattr(capture, 'gravity'):
            config = {
                'gravity': capture.gravity,
                'friction': capture.friction,
                'restitution': capture.restitution,
                'flipper_speed': capture.flipper_speed,
                'flipper_resting_angle': capture.flipper_resting_angle,
                'flipper_stroke_angle': capture.flipper_stroke_angle,
                'flipper_length': capture.flipper_length,
                'tilt_threshold': capture.tilt_threshold,
                'nudge_cost': capture.nudge_cost,
                'tilt_decay': capture.tilt_decay,
                'camera_pitch': np.degrees(capture.pitch) if hasattr(capture, 'pitch') else 45,
                'camera_x': capture.cam_x / capture.width if hasattr(capture, 'cam_x') else 0.5,
                'camera_y': capture.cam_y / capture.height if hasattr(capture, 'cam_y') else 1.5,
                'camera_z': capture.cam_z / capture.width if hasattr(capture, 'cam_z') else 1.5,
                'camera_zoom': capture.focal_length / (capture.width * 1.2) if hasattr(capture, 'focal_length') else 1.0,
                'last_model': getattr(capture, 'last_model', None),
                'last_preset': getattr(capture, 'last_preset', None),
                'zones': capture.layout.zones if hasattr(capture, 'layout') else []
            }
            socketio.emit('physics_config_loaded', config)

        # Sync initial state
        ai_enabled = getattr(vision_system, 'ai_enabled', True)
        auto_start = getattr(vision_system, 'auto_start_enabled', True)
        socketio.emit('ai_status', {'enabled': ai_enabled})
        socketio.emit('auto_start_status', {'enabled': auto_start})


@socketio.on('input_event')
def handle_input(data):
    # data: {'key': 'ShiftLeft', 'type': 'down'}
    if not vision_system:
        return

    # Check if we are in simulation mode (SimulatedFrameCapture has trigger methods)
    # If we want to control real hardware, we'd need access to 'hw' controller here too.
    # For now, let's assume we are controlling the simulation via the vision system methods we just added.
    # Or we can check if vision_system.capture is SimulatedFrameCapture

    # We need to access the underlying capture object if it's wrapped
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system

    # Check if it has the methods
    if not hasattr(capture, 'trigger_left'):
        return

    key = data.get('key')
    event_type = data.get('type')

    logger.debug(f"Input Event: {key} {event_type}")

    if key == 'KeyZ':
        if event_type == 'down':
            capture.trigger_left()
        else:
            capture.release_left()
    elif key == 'Slash':
        if event_type == 'down':
            capture.trigger_right()
        else:
            capture.release_right()
    elif key == 'Space':
        if event_type == 'down':
            logger.info("Input: Pull Plunger")
            if hasattr(capture, 'pull_plunger'):
                capture.pull_plunger(1.0) # Full pull for now
        else:
            logger.info("Input: Release Plunger")
            if hasattr(capture, 'release_plunger'):
                capture.release_plunger()
    elif key == 'ShiftLeft' and event_type == 'down':
        if hasattr(capture, 'nudge_left'):
            capture.nudge_left()
    elif key == 'ShiftRight' and event_type == 'down':
        if hasattr(capture, 'nudge_right'):
            capture.nudge_right()


@socketio.on('update_physics_v2')
def handle_physics_update(data):
    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'update_physics_params'):
        capture.update_physics_params(data)
        # Emit updated config to sync clients (e.g. Pinball3D view)
        if hasattr(capture, 'get_config'):
            config = capture.get_config()
            socketio.emit('physics_config_loaded', config)


@socketio.on('update_zones')
def handle_update_zones(zones_data):
    """Handle zone updates from frontend."""
    if vision_system:
        vision_system.update_zones(zones_data)
        # Save config automatically? Or wait for explicit save?
        # Let's wait for explicit save or trigger it if desired.
        # For now, just update runtime.
        socketio.emit('status', {'msg': 'Zones updated'})

@socketio.on('reset_zones')
def handle_reset_zones():
    """Handle request to reset zones to default."""
    if vision_system:
        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
        if hasattr(capture, 'reset_zones'):
            capture.reset_zones()
            # Emit updated config to all clients
            if hasattr(capture, 'get_config'):
                config = capture.get_config()
                socketio.emit('physics_config_loaded', config)
            socketio.emit('status', {'msg': 'Zones reset to default'})

@socketio.on('save_physics')
def handle_save_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_config'):
        capture.save_config()
        logger.info("Physics config saved via web request")


@socketio.on('load_physics')
def handle_load_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system # The requested change was syntactically incorrect and has been ignored.
    if hasattr(capture, 'load_config'):
        config = capture.load_config()
        if config:
            logger.debug(f"Loaded config from file: {config}")
            socketio.emit('physics_config_loaded', config)
            logger.info("Physics config loaded via web request")


@socketio.on('reset_physics')
def handle_reset_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'reset_to_defaults'):
        config = capture.reset_to_defaults()
        if config:
            socketio.emit('physics_config_loaded', config)
            logger.info("Physics config reset to defaults")


@socketio.on('load_layout')
def handle_load_layout(data):
    if not vision_system:
        return
    
    logger.info("Received load_layout request")
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'load_layout'):
        try:
            success = capture.load_layout(data)
            if success:
                logger.info("Layout loaded successfully")
                socketio.emit('layout_loaded', {'status': 'success'})
                
                # Emit updated config (including new layout zones/targets) to frontend
                if hasattr(capture, 'get_config'):
                    config = capture.get_config()
                    socketio.emit('physics_config_loaded', config)
                
                # Add to history
                layout_name = data.get('name', 'Unknown Layout')
                if hasattr(vision_system, 'add_history_event'):
                    vision_system.add_history_event('layout_change', {'layout': layout_name})
            else:
                logger.error("Failed to load layout")
                socketio.emit('layout_loaded', {'status': 'error', 'message': 'Failed to load layout'})
        except Exception as e:
            logger.error(f"Error loading layout: {e}")
            socketio.emit('layout_loaded', {'status': 'error', 'message': str(e)})
    else:
        logger.warning("Vision system does not support layout loading")
        socketio.emit('layout_loaded', {'status': 'error', 'message': 'Not supported'})


@socketio.on('save_preset')
def handle_save_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_camera_preset'):
        name = data.get('name')
        if name:
            presets = capture.save_camera_preset(name)
            socketio.emit('presets_updated', presets)

@socketio.on('apply_preset')
def handle_apply_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    preset_name = data.get('name')
    if preset_name and hasattr(capture, 'save_config'):
        # Save the selected preset name
        capture.last_preset = preset_name
        capture.save_config()
        logger.info(f"Applied and saved camera preset: {preset_name}")

@socketio.on('delete_preset')
def handle_delete_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'delete_camera_preset'):
        name = data.get('name')
        if name:
            presets = capture.delete_camera_preset(name)
            socketio.emit('presets_updated', presets)


        socketio.emit('layout_loaded', {'status': 'error', 'message': 'Not supported'})


@socketio.on('get_layouts')
def handle_get_layouts():
    try:
        layouts_dir = os.path.join(os.getcwd(), 'layouts')
        if not os.path.exists(layouts_dir):
            os.makedirs(layouts_dir)
            
        files = [f for f in os.listdir(layouts_dir) if f.endswith('.json')]
        layout_list = []
        for f in files:
            try:
                with open(os.path.join(layouts_dir, f), 'r') as json_file:
                    import json
                    data = json.load(json_file)
                    name = data.get('name', os.path.splitext(f)[0])
                    layout_list.append({'filename': os.path.splitext(f)[0], 'name': name})
            except Exception:
                layout_list.append({'filename': os.path.splitext(f)[0], 'name': os.path.splitext(f)[0]})
        
        socketio.emit('layouts_list', layout_list)
    except Exception as e:
        logger.error(f"Error listing layouts: {e}")


@socketio.on('load_layout_by_name')
def handle_load_layout_by_name(data):
    layout_name = data.get('name')
    if not layout_name:
        return

    try:
        filename = f"{layout_name}.json"
        filepath = os.path.join(os.getcwd(), 'layouts', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                import json
                config = json.load(f)
            
            # Ensure name is in config so handle_load_layout can use it
            if 'name' not in config:
                config['name'] = layout_name
            
            # Reuse the existing load_layout logic
            handle_load_layout(config)
        else:
            logger.error(f"Layout file not found: {filepath}")
            socketio.emit('layout_loaded', {'status': 'error', 'message': 'Layout not found'})
            
    except Exception as e:
        logger.error(f"Error loading layout by name: {e}")
        socketio.emit('layout_loaded', {'status': 'error', 'message': str(e)})


@socketio.on('toggle_ai')
def handle_toggle_ai(data):
    logger.info(f"DEBUG: handle_toggle_ai called with {data}")
    if not vision_system:
        logger.error("Vision system is None in handle_toggle_ai")
        return
    
    enabled = data.get('enabled', True)
    logger.info(f"Received toggle_ai event. Data: {data}, Setting to: {enabled}")
    if hasattr(vision_system, 'ai_enabled'):
        vision_system.ai_enabled = enabled
        logger.info(f"AI Enabled set to: {enabled}")
        # Broadcast new state to all clients
        socketio.emit('ai_status', {'enabled': enabled})


@socketio.on('toggle_auto_start')
def handle_toggle_auto_start(data):
    if not vision_system:
        return
    
    enabled = data.get('enabled', True)
    logger.info(f"Received toggle_auto_start event. Data: {data}, Setting to: {enabled}")
    if hasattr(vision_system, 'auto_start_enabled'):
        vision_system.auto_start_enabled = enabled
        logger.info(f"Auto-Start set to: {enabled}")
        # Broadcast new state to all clients
        socketio.emit('auto_start_status', {'enabled': enabled})


@socketio.on('get_models')
def handle_get_models():
    import hashlib
    try:
        models_dir = os.path.join(os.getcwd(), 'models')
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            
        model_list = []
        for f in os.listdir(models_dir):
            if f.endswith('.zip'):
                filepath = os.path.join(models_dir, f)
                # Calculate short hash
                try:
                    with open(filepath, "rb") as file:
                        file_hash = hashlib.sha256(file.read()).hexdigest()[:6]
                except Exception:
                    file_hash = "unknown"
                
                # Get modification time
                try:
                    mtime = os.path.getmtime(filepath)
                    # Format: YYYY-MM-DD HH:MM:SS
                    import datetime
                    dt = datetime.datetime.fromtimestamp(mtime)
                    mod_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    mod_time = "unknown"

                model_list.append({
                    'filename': f,
                    'hash': file_hash,
                    'mod_time': mod_time
                })
        
        # Sort by filename (version)
        model_list.sort(key=lambda x: x['filename'])
        socketio.emit('models_list', model_list)
    except Exception as e:
        logger.error(f"Error listing models: {e}")


@socketio.on('load_model')
def handle_load_model(data):
    model_file = data.get('model')
    model_name = data.get('model')
    if not model_name:
        return
        
    try:
        model_path = os.path.join(os.getcwd(), 'models', model_name)
        if os.path.exists(model_path):
            if hasattr(vision_system, 'agent') and hasattr(vision_system.agent, 'load_model'):
                vision_system.agent.load_model(model_path)
                logger.info(f"Loaded model: {model_name}")
                
                # Save as last loaded model
                if hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'save_config'):
                    vision_system.capture.last_model = model_name
                    vision_system.capture.save_config()
                
                # Add to history
                if hasattr(vision_system, 'add_history_event'):
                    vision_system.add_history_event('model_change', {'model': model_name})

                socketio.emit('model_loaded', {'status': 'success', 'model': model_name})
            else:
                socketio.emit('model_loaded', {'status': 'error', 'message': 'Agent not initialized or does not support loading'})
        else:
            socketio.emit('model_loaded', {'status': 'error', 'message': 'Model file not found'})
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        socketio.emit('model_loaded', {'status': 'error', 'message': str(e)})

@socketio.on('start_training')
def handle_start_training(data):
    logger.info(f"Received start_training event: {data}")
    if hasattr(vision_system, 'controller'):
        config = {
            'model_name': data.get('model_name', 'ppo_pinball'),
            'total_timesteps': int(data.get('total_timesteps', 100000)),
            'learning_rate': float(data.get('learning_rate', 0.0003)),
            'random_layouts': False # Disable random layouts for now
        }
        vision_system.controller.start_training(config)
        socketio.emit('training_started', config)
    else:
        logger.error("No controller attached to vision system")

@socketio.on('stop_training')
def handle_stop_training():
    logger.info("Received stop_training event")
    if hasattr(vision_system, 'controller'):
        vision_system.controller.stop_training()
        socketio.emit('training_stopped')
    else:
        logger.error("No controller attached to vision system")

@socketio.on('camera_control')
def handle_camera_control(data):
    if not vision_system: return
    
    key = data.get('key')
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'adjust_camera'):
        capture.adjust_camera(key)

class SocketIOLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            socketio.emit('log_message', {'message': msg})
        except Exception:
            self.handleError(record)


def start_server(vision_sys, port=5000):
    global vision_system
    vision_system = vision_sys
    
    # Attach SocketIO logger
    handler = SocketIOLogHandler()
    handler.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add to root logger or specific logger
    logging.getLogger(constants.LOGGER_NAME).addHandler(handler)
    
    # Start streaming thread
    socketio.start_background_task(stream_frames)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
