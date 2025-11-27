import base64
import threading
import time
import logging

import cv2
import eventlet
from flask import Flask, render_template
from flask_socketio import SocketIO

from pbwizard import constants

logger = logging.getLogger(__name__)

app = Flask(__name__)
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
                frame = vision_system.get_frame()
                if frame is not None:
                    # logger.debug("Encoding frame...")
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = base64.b64encode(buffer).decode('utf-8')
                    # logger.debug("Emitting frame...")
                    socketio.emit('video_frame', {'image': frame_bytes})

                    # Emit stats if available
                    if hasattr(vision_system, 'get_stats'):
                        stats = vision_system.get_stats()
                        # logger.debug(f"Emitting stats: {stats}") # Uncomment for verbose debugging
                        socketio.emit('stats', stats)

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
        if hasattr(capture, 'gravity'):
            config = {
                'gravity': capture.gravity,
                'friction': capture.friction,
                'restitution': capture.restitution,
                'flipper_speed': capture.flipper_speed,
                'flipper_resting_angle': capture.flipper_resting_angle,
                'flipper_stroke_angle': capture.flipper_stroke_angle
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
    elif key == 'Space' and event_type == 'down':
        logger.info("Input: Launch Ball Triggered")
        capture.launch_ball()


@socketio.on('update_physics')
def handle_physics_update(data):
    if not vision_system:
        return

    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'update_physics_params'):
        capture.update_physics_params(data)


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
    capture = vision_system.capture if hasattr(vision_system, 'capture') else vision_system
    if hasattr(capture, 'load_config'):
        config = capture.load_config()
        if config:
            socketio.emit('physics_config_loaded', config)
            logger.info("Physics config loaded via web request")
@socketio.on('toggle_ai')
def handle_toggle_ai(data):
    if not vision_system:
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
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add to root logger or specific logger
    logging.getLogger(constants.LOGGER_NAME).addHandler(handler)
    
    # Start streaming thread
    socketio.start_background_task(stream_frames)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
