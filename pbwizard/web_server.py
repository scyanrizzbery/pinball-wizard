import base64
import json
import logging
import os
import time

import cv2
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

def log_history_event(event_type, message):
    """Log a non-game event to history."""
    if vision_system and hasattr(vision_system, 'game_history'):
        vision_system.game_history.append({
            'type': 'event',
            'event_type': event_type,
            'message': message,
            'timestamp': time.time()
        })
        # Keep history size manageable
        if len(vision_system.game_history) > 50:
            vision_system.game_history.pop(0)


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
                    socketio.emit('game_state', game_state, namespace='/game')
                    # Also emit stats_update for App.vue compatibility
                    # Also emit stats_update for App.vue compatibility
                    if hasattr(vision_system, 'get_stats'):
                        # logger.info("Calling vision_system.get_stats()")
                        stats_data = vision_system.get_stats()
                    else:
                        logger.warning("vision_system has no get_stats method!")
                        stats_data = {
                            'score': game_state.get('score', 0),
                            'high_score': game_state.get('high_score', 0),
                            'balls': game_state.get('balls_remaining', 0),
                            'ball_count': len(game_state.get('balls', [])),  # Actual balls on table
                            'current_ball': game_state.get('current_ball', 1),
                            'games_played': game_state.get('games_played', 0),
                            'game_history': game_state.get('game_history', []),
                            'is_tilted': game_state.get('is_tilted', False),
                            'tilt_value': game_state.get('tilt_value', 0.0),
                            'nudge': game_state.get('nudge', None),
                            'combo_count': 0,
                            'score_multiplier': 1.0,
                            'combo_active': False,
                            'game_over': game_state.get('game_over', False)
                        }

                    # Add combo data from physics engine
                    try:
                        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
                        if hasattr(capture, 'physics_engine'):
                            combo_status = capture.physics_engine.get_combo_status()
                            stats_data['combo_count'] = combo_status['combo_count']
                            stats_data['combo_active'] = combo_status['combo_active']
                            stats_data['combo_timer'] = combo_status['combo_timer']
                            stats_data['score_multiplier'] = capture.physics_engine.get_multiplier()
                    except Exception as e:
                        logger.error(f"Error adding combo stats: {e}")

                    # Add training stats if available
                    if hasattr(vision_system, 'training_stats'):
                        stats_data.update(vision_system.training_stats)

                    # Sanitize for JSON serialization (handle numpy types)
                    def sanitize_for_json(obj):
                        if isinstance(obj, dict):
                            return {k: sanitize_for_json(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [sanitize_for_json(v) for v in obj]
                        elif hasattr(obj, 'item'):  # Numpy scalar
                            return obj.item()
                        elif hasattr(obj, 'tolist'):  # Numpy array
                            return obj.tolist()
                        return obj

                    stats_data = sanitize_for_json(stats_data)

                    socketio.emit('stats_update', stats_data, namespace='/game')
                    if len(game_state.get('balls', [])) > 0:
                        logger.debug(f"Emitting Game State: {game_state['balls'][0]}")

                # Video Feed - Stream simulation frames
                frame = vision_system.get_frame()
                if frame is not None:
                    # logger.debug("Encoding frame...")
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = base64.b64encode(buffer).decode('utf-8')
                    # logger.debug("Emitting frame...")
                    # Emit 'video_frame' to match App.vue
                    socketio.emit('video_frame', {'image': frame_bytes}, namespace='/game')

                    frame_count += 1
                    if frame_count % 100 == 0:
                        logger.debug(f"Emitted {frame_count} video frames. Size: {len(frame_bytes)}")
                else:
                     frame_count += 1
                     if frame_count % 100 == 0:
                         logger.warning("Vision system returned None frame")
            else:
                logger.warning("Vision system not initialized in stream_frames")
        except Exception as e:
            logger.error(f"Error in stream_frames: {e}")

        socketio.sleep(0.033)  # ~30 FPS


@socketio.on('connect', namespace='/game')
def handle_connect_game():
    logger.info('Client connected to /game')


@socketio.on('connect', namespace='/config')
def handle_connect_config():
    logger.info('Client connected to /config')
    # Sync physics config on connect
    if vision_system:
        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
        if hasattr(capture, 'get_config'):
            config = capture.get_config()
            socketio.emit('physics_config_loaded', config, namespace='/config')
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
                'guide_thickness': getattr(capture, 'guide_thickness', 25.0),
                'guide_length_scale': getattr(capture, 'guide_length_scale', 1.0),
                'guide_angle_offset': getattr(capture, 'guide_angle_offset', 0.0),
                'camera_pitch': np.degrees(capture.pitch) if hasattr(capture, 'pitch') else 45,
                'camera_x': capture.cam_x / capture.width if hasattr(capture, 'cam_x') else 0.5,
                'camera_y': capture.cam_y / capture.height if hasattr(capture, 'cam_y') else 1.5,
                'camera_z': capture.cam_z / capture.width if hasattr(capture, 'cam_z') else 1.5,
                'camera_zoom': capture.focal_length / (capture.width * 1.2) if hasattr(capture,
                                                                                       'focal_length') else 1.0,
                'last_model': getattr(capture, 'last_model', None),
                'last_preset': getattr(capture, 'last_preset', None),
                'zones': capture.layout.zones if hasattr(capture, 'layout') else []
            }
            socketio.emit('physics_config_loaded', config, namespace='/config')


@socketio.on('connect', namespace='/training')
def handle_connect_training():
    logger.info('Client connected to /training')
    # Sync initial AI state
    if vision_system:
        ai_enabled = getattr(vision_system, 'ai_enabled', True)
        socketio.emit('ai_status', {'enabled': ai_enabled}, namespace='/training')


@socketio.on('input_event', namespace='/control')
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

    logger.info(f"🎮 Input Event: {key} {event_type}")

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
            # Use handle_plunger to ensure event is recorded for replay
            if hasattr(capture, 'handle_plunger'):
                capture.handle_plunger({'action': 'press'})
            # Fallback for relaunch (manual ball spawn)
            if hasattr(capture, 'relaunch_ball'):
                capture.relaunch_ball()
        else:
            logger.info("Input: Release Plunger")
            # Use handle_plunger to ensure event is recorded for replay
            if hasattr(capture, 'handle_plunger'):
                capture.handle_plunger({'action': 'release'})
    elif key == 'ShiftLeft' and event_type == 'down':
        if hasattr(capture, 'nudge_left'):
            capture.nudge_left()
    elif key == 'ShiftRight' and event_type == 'down':
        if hasattr(capture, 'nudge_right'):
            capture.nudge_right()


@socketio.on('alien_nudge', namespace='/control')
def handle_alien_nudge():
    """Trigger a free nudge for the alien effect."""
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'alien_nudge'):
        capture.alien_nudge()
        logger.info("👽 Alien Nudge Triggered!")


@socketio.on('relaunch_ball', namespace='/game')
def handle_relaunch_ball():
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system

    if hasattr(capture, 'relaunch_ball'):
        capture.relaunch_ball()
        logger.info("Relaunch ball command received and executed")


@socketio.on('start_game', namespace='/control')
def handle_start_game():
    """Start a new game by spawning and firing ball (for auto-start)."""
    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system

    logger.info("Start game command received")

    # Always reset game state for a new game
    if hasattr(capture, 'reset_game_state'):
        logger.info("Starting new game: Resetting game state")
        capture.reset_game_state()
    elif hasattr(capture, 'physics_engine'):
        # Fallback if reset not available (should not happen)
        if len(capture.physics_engine.balls) == 0:
            if hasattr(capture, 'add_ball'):
                capture.add_ball()

# Replay Endpoints
@socketio.on('load_replay', namespace='/game')
def handle_load_replay(data):
    """Load and play a replay from JSON data"""
    if not vision_system: return
    
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'handle_load_replay'):
        # Notify frontend that replay is loading
        socketio.emit('replay_status', {'status': 'loading', 'hash': data.get('hash')}, namespace='/game')
        
        # Pass the replay JSON data directly to the capture system
        # Data should contain: seed, events, layout
        success = capture.handle_load_replay(data)
        
        if success:
            socketio.emit('replay_status', {'status': 'playing', 'hash': data.get('hash')}, namespace='/game')
        else:
            socketio.emit('replay_status', {'status': 'error', 'message': 'Failed to load replay'}, namespace='/game')
        
@socketio.on('get_game_hash', namespace='/game')
def handle_get_game_hash():
    """Get current game hash/seed"""
    if not vision_system: return
    
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'physics_engine'):
        socketio.emit('game_hash', {
            'seed': getattr(capture.physics_engine, 'seed', ''),
            'hash': getattr(capture.physics_engine, 'game_hash', ''),
            'is_replay': capture.replay_manager.is_playing if hasattr(capture, 'replay_manager') else False
        }, namespace='/game')


@socketio.on('update_physics', namespace='/config')
def handle_physics_update_legacy(data):
    """Legacy handler for update_physics (v1) - proxies to v2."""
    logger.info(f"🔵 LEGACY handle_physics_update (v1) CALLED with data: {data}")
    handle_physics_update(data)


@socketio.on('set_physics_param', namespace='/config')
def handle_set_physics_param(data):
    """Handle single parameter update (used by App.vue)."""
    # data is {key: 'param_name', value: val}
    key = data.get('key')
    value = data.get('value')
    if key:
        handle_physics_update({key: value})


@socketio.on('update_physics_v2', namespace='/config')
def handle_physics_update(data):
    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    
    if hasattr(capture, 'update_physics_params'):
        # Check if only camera parameters are being updated
        camera_params = {'camera_x', 'camera_y', 'camera_z', 'camera_pitch', 'camera_zoom'}
        data_keys = set(data.keys())
        only_camera = data_keys.issubset(camera_params)
        
        logger.info(f"Physics update: keys={list(data_keys)}, only_camera={only_camera}, will_save={not only_camera}")
        
        # Don't save layout/config if only camera parameters changed
        capture.update_physics_params(data, save=not only_camera)
        if not only_camera:
             log_history_event('physics', "Updated physics settings")  # Log event
        
        # Emit updated config to sync clients (e.g. Pinball3D view)
        # if hasattr(capture, 'get_config'):
        #     config = capture.get_config()
        #     socketio.emit('physics_config_loaded', config, namespace='/config')
    else:
        logger.error("🔴 capture does not have update_physics_params method!")

@socketio.on('save_new_layout', namespace='/config')
def handle_save_new_layout(data):
    """Handle saving layout as new file."""
    if not vision_system: return

    name = data.get('name')
    if name:
        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
        if hasattr(capture, 'save_new_layout'):
            success = capture.save_new_layout(name)
            if success:
                log_history_event('layout', f"Created new layout: {name}")  # Log event
                socketio.emit('status', {'msg': f"Layout '{name}' saved"}, namespace='/config')
                # Emit updated config/layout list might be needed, but client usually refreshes
            else:
                socketio.emit('status', {'msg': "Failed to save layout"}, namespace='/config')


@socketio.on('save_layout', namespace='/config')
def handle_save_layout():
    """Handle saving current layout (overwrite)."""
    if not vision_system: return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_layout'):
        capture.save_layout()
        socketio.emit('status', {'msg': "Layout saved"}, namespace='/config')


@socketio.on('update_zones', namespace='/config')
def handle_update_zones(zones_data):
    """Handle zone updates from frontend."""
    if vision_system:
        vision_system.update_zones(zones_data)
        socketio.emit('status', {'msg': 'Zones updated and saved'}, namespace='/config')


@socketio.on('update_rails', namespace='/config')
def handle_update_rails(rails_data):
    """Handle rail updates from frontend."""
    if vision_system:
        if hasattr(vision_system, 'update_rails'):
            vision_system.update_rails(rails_data)
        elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'update_rails'):
            vision_system.capture.update_rails(rails_data)

        socketio.emit('status', {'msg': 'Rails updated and saved'}, namespace='/config')


@socketio.on('create_rail', namespace='/config')
def handle_create_rail(rail_data):
    """Handle creating a new rail."""
    if vision_system:
        if hasattr(vision_system, 'create_rail'):
            vision_system.create_rail(rail_data)
        elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'create_rail'):
            vision_system.capture.create_rail(rail_data)

        socketio.emit('status', {'msg': 'Rail created'}, namespace='/config')
        # Emit updated config
        if hasattr(vision_system, 'capture'):
            socketio.emit('physics_config_loaded', vision_system.capture.get_config(), namespace='/config')


@socketio.on('delete_rail', namespace='/config')
def handle_delete_rail(data):
    """Handle deleting a rail."""
    if vision_system:
        rail_index = data.get('index')
        if rail_index is not None:
            if hasattr(vision_system, 'delete_rail'):
                vision_system.delete_rail(rail_index)
            elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'delete_rail'):
                vision_system.capture.delete_rail(rail_index)

            socketio.emit('status', {'msg': 'Rail deleted'}, namespace='/config')
            # Emit updated config
            if hasattr(vision_system, 'capture'):
                socketio.emit('physics_config_loaded', vision_system.capture.get_config(), namespace='/config')


@socketio.on('update_bumpers', namespace='/config')
def handle_update_bumpers(bumpers_data):
    """Handle bumper updates from frontend."""
    if vision_system:
        if hasattr(vision_system, 'update_bumpers'):
            vision_system.update_bumpers(bumpers_data)
        elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'update_bumpers'):
            vision_system.capture.update_bumpers(bumpers_data)

        socketio.emit('status', {'msg': 'Bumpers updated and saved'}, namespace='/config')
        # Emit updated config
        if hasattr(vision_system, 'capture'):
            socketio.emit('physics_config_loaded', vision_system.capture.get_config(), namespace='/config')


@socketio.on('create_bumper', namespace='/config')
def handle_create_bumper(bumper_data):
    """Handle creating a new bumper."""
    if vision_system:
        if hasattr(vision_system, 'create_bumper'):
            vision_system.create_bumper(bumper_data)
        elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'create_bumper'):
            vision_system.capture.create_bumper(bumper_data)

        socketio.emit('status', {'msg': 'Bumper created'}, namespace='/config')
        # Emit updated config
        if hasattr(vision_system, 'capture'):
            socketio.emit('physics_config_loaded', vision_system.capture.get_config(), namespace='/config')


@socketio.on('delete_bumper', namespace='/config')
def handle_delete_bumper(data):
    """Handle deleting a bumper."""
    if vision_system:
        index = data.get('index')
        if index is not None:
            if hasattr(vision_system, 'delete_bumper'):
                vision_system.delete_bumper(index)
            elif hasattr(vision_system, 'capture') and hasattr(vision_system.capture, 'delete_bumper'):
                vision_system.capture.delete_bumper(index)

            socketio.emit('status', {'msg': 'Bumper deleted'}, namespace='/config')

        socketio.emit('status', {'msg': 'Bumpers updated and saved'}, namespace='/config')
        # Emit updated config
        if hasattr(vision_system, 'capture'):
            socketio.emit('physics_config_loaded', vision_system.capture.get_config(), namespace='/config')


@socketio.on('reset_zones', namespace='/config')
def handle_reset_zones():
    """Handle request to reset zones to default."""
    if vision_system:
        capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
        if hasattr(capture, 'reset_zones'):
            capture.reset_zones()
            # Emit updated config to all clients
            if hasattr(capture, 'get_config'):
                config = capture.get_config()
                socketio.emit('physics_config_loaded', config, namespace='/config')
            socketio.emit('status', {'msg': 'Zones reset to default'}, namespace='/config')


@socketio.on('save_physics', namespace='/config')
def handle_save_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_config'):
        capture.save_config()
        logger.info("Physics config saved via web request")


@socketio.on('load_physics', namespace='/config')
def handle_load_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'load_config'):
        config = capture.load_config()
        if config:
            logger.debug(f"Loaded config from file: {config}")
            socketio.emit('physics_config_loaded', config, namespace='/config')
            logger.info("Physics config loaded via web request")


@socketio.on('reset_physics', namespace='/config')
def handle_reset_physics():
    if not vision_system:
        return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'reset_to_defaults'):
        config = capture.reset_to_defaults()
        if config:
            socketio.emit('physics_config_loaded', config, namespace='/config')
            logger.info("Physics config reset to defaults")


@socketio.on('load_layout', namespace='/config')
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
                log_history_event('layout', f"Loaded layout: {data}")  # Log event
                socketio.emit('layout_loaded', {'status': 'success'}, namespace='/config')

                # Emit updated config (including new layout zones/targets) to frontend
                if hasattr(capture, 'get_config'):
                    config = capture.get_config()
                    socketio.emit('physics_config_loaded', config, namespace='/config')

                # Add to history
                layout_name = data.get('name', 'Unknown Layout')
                if hasattr(vision_system, 'add_history_event'):
                    vision_system.add_history_event('layout_change', {'layout': layout_name})
            else:
                logger.error("Failed to load layout")
                socketio.emit('layout_loaded', {'status': 'error', 'message': 'Failed to load layout'},
                              namespace='/config')
        except Exception as e:
            logger.error(f"Error loading layout: {e}")
            socketio.emit('layout_loaded', {'status': 'error', 'message': str(e)}, namespace='/config')
    else:
        logger.warning("Vision system does not support layout loading")
        socketio.emit('layout_loaded', {'status': 'error', 'message': 'Not supported'}, namespace='/config')


@socketio.on('save_preset', namespace='/config')
def handle_save_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_camera_preset'):
        name = data.get('name')
        if name:
            presets = capture.save_camera_preset(name)
            socketio.emit('presets_updated', presets, namespace='/config')


@socketio.on('apply_preset', namespace='/config')
def handle_apply_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    preset_name = data.get('name')
    if preset_name and hasattr(capture, 'save_config'):
        # Save the selected preset name
        capture.last_preset = preset_name
        capture.save_config()
        logger.info(f"Applied and saved camera preset: {preset_name}")


@socketio.on('delete_preset', namespace='/config')
def handle_delete_preset(data):
    if not vision_system: return
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'delete_camera_preset'):
        name = data.get('name')
        if name:
            presets = capture.delete_camera_preset(name)
            socketio.emit('presets_updated', presets, namespace='/config')

        socketio.emit('layout_loaded', {'status': 'error', 'message': 'Not supported'})


@socketio.on('get_layouts', namespace='/config')
def handle_get_layouts():
    try:
        # Get layouts from snake_case.json via vision system
        if vision_system:
            capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
            if hasattr(capture, 'available_layouts'):
                layouts = []
                for key, data in capture.available_layouts.items():
                    # Use the 'name' property from the layout data if available
                    display_name = data.get('name', key.replace('_', ' ').title())
                    layouts.append({
                        'id': key,
                        'name': display_name
                    })
                logger.info(f"Sending layouts list: {layouts}")
                socketio.emit('layouts_list', layouts, namespace='/config')
                return

        # Fallback to file system if needed (or just return empty)
        socketio.emit('layouts_list', [], namespace='/config')
    except Exception as e:
        logger.error(f"Error listing layouts: {e}")


@socketio.on('load_layout_by_name', namespace='/config')
def handle_load_layout_by_name(data):
    layout_name = data.get('name')
    if not layout_name:
        return

    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system

    if hasattr(capture, 'load_layout'):
        success = capture.load_layout(layout_name)
        if success:
            socketio.emit('layout_loaded', {'status': 'success', 'layout': layout_name}, namespace='/config')
            # Emit updated config
            if hasattr(capture, 'get_config'):
                config = capture.get_config()
                socketio.emit('physics_config_loaded', config, namespace='/config')
            
            # Record layout change in game history (for chart plotLine)
            if hasattr(vision_system, 'game_history'):
                import time
                vision_system.game_history.append({
                    'type': 'layout_change',
                    'layout': layout_name,
                    'timestamp': time.time(),
                    'date': time.strftime("%Y-%m-%d %H:%M:%S")
                })
                # Keep history limited
                if len(vision_system.game_history) > 50:
                    vision_system.game_history.pop(0)
            
            logger.info(f"Layout changed to: {layout_name}")
        else:
            socketio.emit('layout_loaded', {'status': 'error', 'message': 'Layout not found'}, namespace='/config')


@socketio.on('save_layout_settings', namespace='/config')
def handle_save_layout_settings(data):
    """Save current physics settings to the active layout file."""
    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system

    if hasattr(capture, 'save_layout_settings'):
        success = capture.save_layout_settings()
        if success:
            socketio.emit('layout_settings_saved', {'status': 'success'}, namespace='/config')
            logger.info("Layout settings saved successfully.")
        else:
            socketio.emit('layout_settings_saved', {'status': 'error', 'message': 'Failed to save settings'},
                          namespace='/config')
            logger.error("Failed to save layout settings.")


@socketio.on('toggle_ai', namespace='/training')
def handle_toggle_ai(data):
    logger.info(f"DEBUG: handle_toggle_ai called with {data}")
    if not vision_system:
        logger.error("Vision system is None in handle_toggle_ai")
        return

    enabled = data.get('enabled', True)
    logger.info(f"Received toggle_ai event. Data: {data}, Setting to: {enabled}")

    # Set on vision_system
    if hasattr(vision_system, 'ai_enabled'):
        vision_system.ai_enabled = enabled
        logger.info(f"AI Enabled set to: {enabled}")

    # Also set on agent if it exists
    if hasattr(vision_system, 'agent') and vision_system.agent:
        vision_system.agent.enabled = enabled
        logger.info(f"Agent enabled set to: {enabled}")

    # Broadcast new state to all clients
    socketio.emit('ai_status', {'enabled': enabled}, namespace='/training')



@socketio.on('update_difficulty', namespace='/training')
def handle_update_difficulty(data):
    """Handle AI difficulty level changes."""
    if not vision_system:
        return

    difficulty = data.get('difficulty', 'medium')
    logger.info(f"Received update_difficulty event. Setting to: {difficulty}")

    # Update agent difficulty if reflex agent
    if hasattr(vision_system, 'agent'):
        if hasattr(vision_system.agent, 'difficulty'):
            vision_system.agent.difficulty = difficulty
            # Update difficulty parameters
            params = vision_system.agent.DIFFICULTY_PARAMS.get(difficulty,
                                                               vision_system.agent.DIFFICULTY_PARAMS['medium'])
            vision_system.agent.MIN_HOLD = params['MIN_HOLD']
            vision_system.agent.MAX_HOLD = params['MAX_HOLD']
            vision_system.agent.COOLDOWN = params['COOLDOWN']
            vision_system.agent.VY_THRESHOLD = params['VY_THRESHOLD']
            vision_system.agent.USE_VELOCITY_PREDICTION = params['USE_VELOCITY_PREDICTION']
            logger.info(f"AI Difficulty updated to: {difficulty}")

    # Record difficulty change in game history
    import time
    vision_system.game_history.insert(0, {
        'type': 'difficulty_change',
        'difficulty': difficulty,
        'timestamp': time.time(),
        'date': time.strftime("%Y-%m-%d %H:%M:%S")
    })
    # Keep history limited
    if len(vision_system.game_history) > 50:
        vision_system.game_history.pop()

    # Save to config
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'save_config'):
        # Temporarily set ai_difficulty on capture for saving
        if not hasattr(capture, 'ai_difficulty'):
            capture.ai_difficulty = difficulty
        else:
            capture.ai_difficulty = difficulty
        capture.save_config()

    # Broadcast new state to all clients
    socketio.emit('difficulty_status', {'difficulty': difficulty}, namespace='/training')


@socketio.on('get_models', namespace='/training')
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
                    'mod_time': mod_time,
                    'mtime_timestamp': mtime  # Store timestamp for sorting
                })

        # Sort by modification time (newest first)
        model_list.sort(key=lambda x: x.get('mtime_timestamp', 0), reverse=True)
        socketio.emit('models_list', model_list, namespace='/training')
    except Exception as e:
        logger.error(f"Error listing models: {e}")



@socketio.on('get_hyperparams', namespace='/training')
def handle_get_hyperparams():
    """Load optimized hyperparameters from JSON file."""
    hp_path = "frontend/public/hyperparams.json"
    if os.path.exists(hp_path):
        try:
            with open(hp_path, 'r') as f:
                params = json.load(f)
                socketio.emit('hyperparams_loaded', params, namespace='/training')
                logger.info(f"Emitted hyperparams: {params}")
        except Exception as e:
            logger.error(f"Error loading hyperparams: {e}")
    else:
        logger.info("No hyperparams.json found")


@socketio.on('start_training', namespace='/training')
def handle_start_training(data):
    logger.info(f"Received start_training event: {data}")
    if hasattr(vision_system, 'controller'):
        config = {
            'model_name': data.get('model_name', 'ppo_pinball'),
            'total_timesteps': int(data.get('total_timesteps', 100000)),
            'learning_rate': float(data.get('learning_rate', 0.0003)),
            # If layout not specified, use currently loaded layout
            'layout': data.get('layout') or (
                vision_system.capture.current_layout_id if hasattr(vision_system, 'capture') else None),
            'physics': data.get('physics'),
            'random_layouts': data.get('random_layouts', False)
        }
        logger.info(f"STARTING TRAINING WITH CONFIG: {config}")
        vision_system.controller.start_training(config)
        socketio.emit('training_started', config, namespace='/training')
    else:
        logger.error("No controller attached to vision system")


@socketio.on('stop_training', namespace='/training')
def handle_stop_training():
    logger.info("Received stop_training event")
    if hasattr(vision_system, 'controller'):
        vision_system.controller.stop_training()
        socketio.emit('training_stopped', namespace='/training')
    else:
        logger.error("No controller attached to vision system")


def emit_training_finished(model_name):
    """Called by main loop when training finishes."""
    if socketio:
        socketio.emit('training_finished', {'model': model_name}, namespace='/training')


@socketio.on('camera_control', namespace='/config')
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
            socketio.emit('log_message', {'message': msg}, namespace='/game')
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

@socketio.on('update_rewards', namespace='/config')
def handle_update_rewards(rewards_data):
    """Handle reward updates from frontend."""
    import json
    import os

    try:
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
        else:
            config_data = {}

        # Merge with existing rewards if partial update
        if 'rewards' not in config_data:
            config_data['rewards'] = {}

        config_data['rewards'].update(rewards_data)

        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)

        # Notify controller if training is running
        if vision_system and hasattr(vision_system, 'controller'):
            if hasattr(vision_system.controller, 'update_rewards'):
                vision_system.controller.update_rewards(rewards_data)

        socketio.emit('status', {'msg': 'Rewards updated and saved'}, namespace='/config')
        logger.info(f"Rewards updated: {rewards_data}")

    except Exception as e:
        logger.error(f"Error updating rewards: {e}")
        socketio.emit('status', {'msg': f'Error updating rewards: {e}'}, namespace='/config')

