import threading
import time
import os
import logging
import json
import random

import cv2
import numpy as np

from pbwizard.physics import PymunkEngine


logger = logging.getLogger(__name__)

class ReplayManager:
    """
    Manages regarding and playing back game inputs to ensure deterministic replays.
    """
    def __init__(self):
        self.is_recording = False
        self.is_playing = False
        self.replay_data = {
            'seed': None,
            'layout': None, 
            'events': [] # List of (frame_index, type, value)
        }
        self.current_frame = 0
        self.event_cursor = 0
        self.lock = threading.Lock()

    def start_recording(self, seed, layout_name):
        with self.lock:
            self.is_recording = True
            self.is_playing = False
            self.replay_data = {
                'seed': seed,
                'layout': layout_name,
                'events': []
            }
            self.current_frame = 0
            logger.info(f"Replay Recording Started. Seed: {seed}")

    def stop_recording(self):
        with self.lock:
            self.is_recording = False
            logger.info(f"Replay Recording Stopped. Total Frames: {self.current_frame}, Total Events: {len(self.replay_data['events'])}")

    def record_event(self, event_type, value):
        if not self.is_recording: return
        with self.lock:
            self.replay_data['events'].append({
                'frame': self.current_frame,
                'type': event_type,
                'value': value
            })

    def start_playback(self, replay_json):
        with self.lock:
            self.is_playing = True
            self.is_recording = False
            self.replay_data = replay_json
            self.current_frame = 0
            self.event_cursor = 0
            logger.info(f"Replay Playback Started. Seed: {self.replay_data.get('seed')}")
            return self.replay_data.get('seed')

    def stop_playback(self):
        with self.lock:
            self.is_playing = False

    def get_events_for_frame(self):
        if not self.is_playing: return []
        
        events = []
        with self.lock:
            while self.event_cursor < len(self.replay_data['events']):
                evt = self.replay_data['events'][self.event_cursor]
                if evt['frame'] <= self.current_frame:
                    events.append(evt)
                    self.event_cursor += 1
                else:
                    break
        return events

    def tick(self):
        with self.lock:
            self.current_frame += 1


try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = object  # Dummy base class
    FileSystemEventHandler = object # Dummy base class
    logger.warning("watchdog module not found. Layout file watching will be disabled.")

try:
    import pytesseract
except ImportError:
    pytesseract = None
    logger.warning("pytesseract module not found. Score reading will be disabled.")

class ZoneManager:
    def __init__(self, width, height, layout=None):
        self.width = width
        self.height = height
        self.layout = layout

    def get_zone_status(self, x, y):
        """
        Determine which zones the ball is currently in.
        Returns a dictionary with boolean flags for 'left' and 'right' zones.
        """
        # Default simple split if no complex logic
        # Left Zone: x < 50% width
        # Right Zone: x >= 50% width
        
        # Optional: Dead zone at the very top (e.g. plunger lane only?)
        # For now, simplistic split serves the reflex agent well efficiently.
        
        is_left = x < (self.width / 2)
        is_right = x >= (self.width / 2)
        
        return {
            'left': is_left,
            'right': is_right
        }


class LayoutFileHandler(FileSystemEventHandler):
    def __init__(self, vision_system):
        self.vision_system = vision_system
        self.last_reload = 0

    def on_any_event(self, event):
        if not WATCHDOG_AVAILABLE: return
        if event.is_directory:
            return
        
        if event.event_type not in ['created', 'modified', 'deleted']:
            return

        filename = os.path.basename(event.src_path)
        if not filename.endswith('.json'):
            return

        # Debounce reloads (watchdog can fire multiple events for one save)
        current_time = time.time()
        if current_time - self.last_reload < 0.5:
            return
        self.last_reload = current_time

        logger.info(f"Layout file changed: {event.src_path} ({event.event_type})")
        self.vision_system.refresh_layouts(filename if event.event_type != 'deleted' else None)


class FrameCapture:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(int(camera_index))
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.start()
        logger.info(f"Camera started on index {int(self.cap.get(cv2.CAP_PROP_POS_MSEC)) if self.cap.isOpened() else 'Unknown'}")

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                logger.warning("Failed to read frame from camera")
            time.sleep(0.01)

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        self.thread.join()
        if self.cap:
            self.cap.release()
            logger.info("Camera stopped")


class PinballLayout:
    def __init__(self, config=None, filepath=None):
        # Default values
        self.width = 0.6  # 60cm
        self.height = 1.2 # 120cm
        self.name = 'Default'
        
        # Flipper Configuration (Normalized 0-1)
        # Widened to match 3D view aesthetics (was 0.35/0.65)
        self.left_flipper_x_min = 0.25
        self.left_flipper_x_max = 0.30
        self.left_flipper_y_min = 0.8
        self.left_flipper_y_max = 0.9
        
        self.right_flipper_x_min = 0.70
        self.right_flipper_x_max = 0.75
        self.right_flipper_y_min = 0.8
        self.right_flipper_y_max = 0.9
        
        # Ball Captures (Hold ball for X seconds)
        self.captures = []
        # Bumpers and Drop Targets (initialize as empty lists)
        self.bumpers = []
        self.drop_targets = []

        # Ramps (Entrance -> Exit with velocity boost)
        # Connect Main Playfield (Bottom Right) to Upper Deck (Top Left)
        self.ramps = []
        
        # Teleports (Entrance -> Exit instantly)
        self.teleports = []
        
        # Upper Deck (Area definition)
        # Top Left Corner
        self.upper_deck = None
        
        # Upper Flippers
        self.upper_flippers = []
        
        # Rails (Inlane/Outlane guides)
        # Prevent direct side drains
        self.rails = [
            # Left Rail - angled inward to catch center balls
            {'p1': {'x': 0.18, 'y': 0.40}, 'p2': {'x': 0.36, 'y': 0.83}},
            # Right Rail - angled inward to catch center balls
            {'p1': {'x': 0.82, 'y': 0.50}, 'p2': {'x': 0.64, 'y': 0.83}}
        ]
        
        
        # Rail Translation Offsets (Defaults)
        self.rail_x_offset = 0.0
        self.rail_y_offset = 0.0
        
        # Physics Parameters (Persisted per layout)
        self.physics_params = {}
        
        # Camera Presets (Default views for the 3D camera)
        self.camera_presets = {
            'Top Down': {
                'camera_x': 0.5,
                'camera_y': 0.5,
                'camera_z': 2.0,
                'camera_pitch': 0,
                'camera_zoom': 1.0
            },
            'Player View': {
                'camera_x': 0.5,
                'camera_y': 0.9,
                'camera_z': 0.3,
                'camera_pitch': 60,
                'camera_zoom': 1.0
            },
            'Isometric': {
                'camera_x': 0.5,
                'camera_y': 0.6,
                'camera_z': 1.2,
                'camera_pitch': 45,
                'camera_zoom': 1.0
            },
            'Side View': {
                'camera_x': 1.5,
                'camera_y': 0.5,
                'camera_z': 0.5,
                'camera_pitch': 75,
                'camera_zoom': 1.0
            }
        }
        self.last_preset = ''

        if filepath:
            self.load_from_file(filepath)
        elif config:
            self.load(config)


    def load_from_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            self.load(config)
            # Store the filepath so we can save back to it later
            self.filepath = filepath
        except Exception as e:
            logger.error(f"Failed to load layout from {filepath}: {e}")

    def save_to_file(self, filepath):
        # Remove duplicate 'upper_deck' key
        config = {
            'width': self.width,
            'height': self.height,
            'left_flipper_x_min': self.left_flipper_x_min,
            'left_flipper_x_max': self.left_flipper_x_max,
            'left_flipper_y_min': self.left_flipper_y_min,
            'left_flipper_y_max': self.left_flipper_y_max,
            'right_flipper_x_min': self.right_flipper_x_min,
            'right_flipper_x_max': self.right_flipper_x_max,
            'right_flipper_y_min': self.right_flipper_y_min,
            'right_flipper_y_max': self.right_flipper_y_max,
            'bumpers': self.bumpers,
            'drop_targets': self.drop_targets,
            'captures': self.captures,
            'ramps': self.ramps,
            'teleports': self.teleports,
            'upper_deck': self.upper_deck,
            'upper_flippers': self.upper_flippers,
            'rails': self.rails,
            'rail_x_offset': self.rail_x_offset,
            'rail_y_offset': self.rail_y_offset,
            'physics': self.physics_params,
            'camera_presets': self.camera_presets,
            'last_preset': self.last_preset
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save layout to {filepath}: {e}")

    def load(self, config):
        if 'name' in config:
            self.name = config['name']
            
        if 'flippers' in config:
            f = config['flippers']
            if 'left' in f:
                l = f['left']
                self.left_flipper_x_min = l.get('x_min', self.left_flipper_x_min)
                self.left_flipper_x_max = l.get('x_max', self.left_flipper_x_max)
                self.left_flipper_y_min = l.get('y_min', self.left_flipper_y_min)
                self.left_flipper_y_max = l.get('y_max', self.left_flipper_y_max)
            if 'right' in f:
                r = f['right']
                self.right_flipper_x_min = r.get('x_min', self.right_flipper_x_min)
                self.right_flipper_x_max = r.get('x_max', self.right_flipper_x_max)
                self.right_flipper_y_min = r.get('y_min', self.right_flipper_y_min)
                self.right_flipper_y_max = r.get('y_max', self.right_flipper_y_max)
        
        if 'bumpers' in config:
            self.bumpers = config['bumpers']
            
        if 'drop_targets' in config:
            self.drop_targets = config['drop_targets']
            
        if 'physics' in config:
            self.physics_params = config['physics']
            # Load rail offsets from physics params (preferred location)
            if 'rail_x_offset' in self.physics_params:
                self.rail_x_offset = self.physics_params['rail_x_offset']
            if 'rail_y_offset' in self.physics_params:
                self.rail_y_offset = self.physics_params['rail_y_offset']

        # Also load offsets from root config if present (overrides physics if both exist? or fallback?)
        # Let's check root if not in physics, or overwrite. 
        # Persistence saves to root.
        if 'rail_x_offset' in config:
            self.rail_x_offset = config['rail_x_offset']
        if 'rail_y_offset' in config:
            self.rail_y_offset = config['rail_y_offset']

        if 'captures' in config:
            self.captures = config['captures']
            
        if 'ramps' in config:
            self.ramps = config['ramps']
            
        if 'teleports' in config:
            self.teleports = config['teleports']
            
        if 'upper_deck' in config:
            self.upper_deck = config['upper_deck']
            
        if 'upper_flippers' in config:
            self.upper_flippers = config['upper_flippers']
            
        if 'rails' in config:
            self.rails = config['rails']

        if 'camera_presets' in config:
            self.camera_presets = config['camera_presets']

        if 'last_preset' in config:
            self.last_preset = config['last_preset']

    def update_physics_params(self, params, save=True):
        """Update physics parameters and apply them to the physics engine."""
        logger.info(f"update_physics_params called with: {params}")
        self.physics_params.update(params)
        
        # Apply parameters to physics engine
        if self.physics_engine:
            # Handle flipper dimensions that require rebuilding
            if 'flipper_length' in params:
                if hasattr(self.physics_engine, 'update_flipper_length'):
                    self.physics_engine.update_flipper_length(params['flipper_length'])
                    logger.info(f"✓ Updated flipper_length = {params['flipper_length']} (flippers rebuilt)")
                else:
                    logger.warning("✗ Physics engine missing update_flipper_length method")

            if 'flipper_width' in params:
                if hasattr(self.physics_engine, 'update_flipper_width'):
                    self.physics_engine.update_flipper_width(params['flipper_width'])
                    logger.info(f"✓ Updated flipper_width = {params['flipper_width']} (flippers rebuilt)")
                else:
                    logger.warning("✗ Physics engine missing update_flipper_width method")

            if 'flipper_tip_width' in params:
                if hasattr(self.physics_engine, 'update_flipper_tip_width'):
                    self.physics_engine.update_flipper_tip_width(params['flipper_tip_width'])
                    logger.info(f"✓ Updated flipper_tip_width = {params['flipper_tip_width']} (flippers rebuilt)")
                else:
                    logger.warning("✗ Physics engine missing update_flipper_tip_width method")

            # Map of parameter names to physics engine attributes
            physics_engine_params = {
                'launch_angle': 'launch_angle',
                'plunger_release_speed': 'plunger_release_speed',
                'friction': 'friction',
                'restitution': 'restitution',
                'flipper_speed': 'flipper_speed',
                'flipper_elasticity': 'flipper_elasticity',
                'bumper_force': 'bumper_force',
                'god_mode': 'god_mode',
                'table_tilt': 'table_tilt',
            }
            
            for param_name, value in params.items():
                # Skip flipper dimensions as they're handled above
                if param_name in ['flipper_length', 'flipper_width', 'flipper_tip_width']:
                    continue

                # Special handling for table_tilt - needs to update gravity
                if param_name == 'table_tilt':
                    if hasattr(self.physics_engine, 'update_table_tilt'):
                        self.physics_engine.update_table_tilt(value)
                        logger.info(f"✓ Updated table_tilt = {value} (gravity recalculated)")
                    else:
                        logger.warning("✗ Physics engine missing update_table_tilt method")
                    continue

                if param_name in physics_engine_params:
                    engine_attr = physics_engine_params[param_name]
                    if hasattr(self.physics_engine, engine_attr):
                        setattr(self.physics_engine, engine_attr, value)
                        logger.info(f"✓ Updated physics_engine.{engine_attr} = {value}")
                    else:
                        logger.warning(f"✗ Physics engine missing attribute: {engine_attr}")
                else:
                    logger.debug(f"⊘ Parameter '{param_name}' not in mapping (this is normal for layout/camera params)")
        else:
            logger.error("Physics engine is None, cannot update parameters")
        
        # Save to config if requested
        if save and hasattr(self, 'save_config'):
            self.save_config()



class BallTracker:
    def __init__(self):
        # Initial color range for orange ball
        self.lower_color = np.array([5, 150, 150])
        self.upper_color = np.array([25, 255, 255])

    def process_frame(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        
        # Noise reduction
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        
        center = None
        if len(cnts) > 0:
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            if M["m00"] > 0:
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                
                # Draw on frame
                cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 255), 2)
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                
        return center, frame
        
class ScoreReader:
    def __init__(self):
        pass

    def read_score(self, frame):
        if pytesseract is None:
            return 0
        
        # Define ROI (Top right usually)
        height, width = frame.shape[:2]
        roi = frame[0:int(height*0.2), int(width*0.5):width]
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        try:
            text = pytesseract.image_to_string(thresh, config='--psm 6 digits')
            score = int(''.join(filter(str.isdigit, text)))
            return score
        except:
            return 0

class SimulatedFrameCapture(FrameCapture):

    def __init__(self, width=600, height=800, layout_config=None, socketio=None):
        self.layout = PinballLayout(config=layout_config)
        self.current_layout_id = 'Default'  # Track the current layout ID
        self.width = width
        self.height = height
        self.socketio = socketio
        self.replay_manager = ReplayManager()
        self._saving_config = False  # Flag to prevent reload loop when saving
        self.cap = None

        # Physics Engine
        # Initial seed
        self.current_seed = None # Will be set on reset
        self.physics_engine = None
        self._init_physics()

        self.balls = [] # list of dicts: {'pos': [x,y], 'vel': [vx,vy], 'radius': r, 'lost': False}
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.ball_radius = 10
        self.headless = os.getenv('HEADLESS_SIM', 'False').lower() == 'true'

        # Flipper State
        self.left_flipper_active = False
        self.right_flipper_active = False
        self._left_flipper_inputs = [] # Log of recent inputs for debug
        
        # Flipper Angles (Degrees)
        self.flipper_angles = {'left': 0.0, 'right': 0.0}
        self.flipper_resting_angle = self.layout.flipper_resting_angle if hasattr(self.layout, 'flipper_resting_angle') else -30.0
        
        # Camera / View Parameters
        # Default to Top-Down 2D-ish view or whatever matches typical 2D
        # These correspond to the "cam_x", "cam_y", "cam_z" expected by get_config
        self.cam_x = width * 0.5
        self.cam_y = height * 0.5
        self.cam_z = width * 1.5 # reasonable zoom out
        self.pitch = 0.0 # Top down
        self.roll = 0.0
        self.focal_length = width * 1.2 # Standard FOV estimate
        self.flipper_resting_angle = 30.0
        self.flipper_stroke_angle = 40.0
        self.flipper_speed = 1500.0 # deg/s
        
        self.current_left_angle = self.flipper_resting_angle
        self.current_right_angle = 180.0 - self.flipper_resting_angle
        self.current_upper_angles = []

        # Camera / View
        self.camera_zoom = 1.0 # 1.0 = fit height
        self.camera_offset_y = 0.0 # Vertical scroll
        self.view_mode = '2d' # '2d' or '3d'
        
        # 3D Projection Params
        self.pitch = 0.5 # Radians (tilt backward)
        self.yaw = 0.0 # Rotation
        self.fov = 1000.0 # Perspective div
        
        # Physics / Gameplay State
        self.score = 0
        self.high_score = 0  # Track high score for this session
        self.lives = 3
        self.game_over = False
        
        # Multiball
        self.multiball_cooldown_timer = 0.0
        
        # Nudge/Tilt
        self.nudge_x = 0.0
        self.nudge_y = 0.0
        self.nudge_decay = 0.9
        self.tilt_value = 0.0
        self.tilt_threshold = 50.0  # Max accumulated tilt before TILT
        self.tilt_warning_threshold = 30.0
        self.is_tilted = False
        self.last_nudge = None
        
        # Drop Targets
        self.drop_target_states = [] # True = Up
        
        # Initialize Watchdog
        if WATCHDOG_AVAILABLE:
            self.observer = Observer()
            self.observer.schedule(LayoutFileHandler(self), path='layouts', recursive=False)
            self.observer.start()
            
        # Socket Listeners
        if self.socketio:
            self.socketio.on_event('flipper_input', self.handle_input, namespace='/game')
            self.socketio.on_event('nudge_input', self.handle_nudge, namespace='/game')
            self.socketio.on_event('plunger_input', self.handle_plunger, namespace='/game')
            self.socketio.on_event('select_layout', self.handle_layout_selection, namespace='/game')
            self.socketio.on_event('reload_layout', self.handle_reload, namespace='/game')
            # Camera Controls
            self.socketio.on_event('set_view_mode', self.handle_view_mode, namespace='/game')
            self.socketio.on_event('camera_pan', self.handle_pan, namespace='/game')
            self.socketio.on_event('camera_zoom', self.handle_zoom, namespace='/game')
            # Reset
            self.socketio.on_event('reset_game', self.handle_reset, namespace='/game')
            
            # Replay Endpoints
            self.socketio.on_event('load_replay', self.handle_load_replay, namespace='/game')
        
        # Load available layouts from disk
        self._load_available_layouts()

    def update_rails(self, rails_data):
        """Update rails from frontend editor."""
        self.layout.rails = rails_data
        if self.physics_engine:
            self.physics_engine.layout.rails = rails_data
            self.physics_engine._rebuild_rails()
            logger.info(f"Updated rails: {len(rails_data)} rails")

    def update_zones(self, zones_data):
        """Update zones from frontend editor."""
        self.layout.zones = zones_data
        # Zones are mostly logical/visual, but used for Agent input.
        # Physics engine doesn't track zones directly (yet), main loop does.
        # But if we persist them to layout, they are safe.
        logger.info(f"Updated zones: {len(zones_data)} zones")

    def update_bumpers(self, bumpers_data):
        """Update bumpers from frontend editor."""
        self.layout.bumpers = bumpers_data
        if self.physics_engine and hasattr(self.physics_engine, 'update_bumpers'):
            self.physics_engine.update_bumpers(bumpers_data)
            logger.info(f"Updated physics bumpers: {len(bumpers_data)} bumpers")
        else:
            logger.warning("Physics engine update_bumpers not available")

    def create_rail(self, rail_data):
        """Create a new rail."""
        if not hasattr(self.layout, 'rails') or self.layout.rails is None:
            self.layout.rails = []
        
        self.layout.rails.append(rail_data)
        self.update_rails(self.layout.rails)
        logger.info("Created new rail")

    def delete_rail(self, index):
        """Delete a rail by index."""
        if hasattr(self.layout, 'rails') and self.layout.rails:
            if 0 <= index < len(self.layout.rails):
                self.layout.rails.pop(index)
                self.update_rails(self.layout.rails)
                logger.info(f"Deleted rail {index}")
            else:
                logger.error(f"Invalid rail index {index}")

    def create_bumper(self, bumper_data):
        """Create a new bumper."""
        if not hasattr(self.layout, 'bumpers') or self.layout.bumpers is None:
            self.layout.bumpers = []
            
        self.layout.bumpers.append(bumper_data)
        self.update_bumpers(self.layout.bumpers)
        logger.info("Created new bumper")

    def delete_bumper(self, index):
        """Delete a bumper by index."""
        if hasattr(self.layout, 'bumpers') and self.layout.bumpers:
            if 0 <= index < len(self.layout.bumpers):
                self.layout.bumpers.pop(index)
                self.update_bumpers(self.layout.bumpers)
                logger.info(f"Deleted bumper {index}")
            else:
                logger.error(f"Invalid bumper index {index}")

    @property
    def available_layouts(self):
        """Return dictionary of available layouts for the frontend."""
        return getattr(self, '_available_layouts', {})
    
    def _load_available_layouts(self):
        """Scan layouts directory and build available layouts dictionary."""
        self._available_layouts = {}
        layouts_dir = 'layouts'
        
        if not os.path.exists(layouts_dir):
            logger.warning(f"Layouts directory not found: {layouts_dir}")
            return
        
        try:
            for filename in os.listdir(layouts_dir):
                if not filename.endswith('.json'):
                    continue
                
                layout_id = filename[:-5]  # Remove .json extension
                filepath = os.path.join(layouts_dir, filename)
                
                # Try to load layout to get its name
                try:
                    with open(filepath, 'r') as f:
                        layout_data = json.load(f)
                    
                    # Use the 'name' field if it exists, otherwise use ID
                    display_name = layout_data.get('name', layout_id.replace('_', ' ').title())
                    
                    self._available_layouts[layout_id] = {
                        'name': display_name,
                        'file': filename
                    }
                except Exception as e:
                    logger.error(f"Error loading layout {filename}: {e}")
                    # Still add it with ID as name
                    self._available_layouts[layout_id] = {
                        'name': layout_id.replace('_', ' ').title(),
                        'file': filename
                    }
            
            logger.info(f"Loaded {len(self._available_layouts)} available layouts")
        except Exception as e:
            logger.error(f"Error scanning layouts directory: {e}")


    def _init_physics(self, seed=None):
        if self.physics_engine:
            try:
                # Clean up shapes to prevent memory leaks?
                # Pymunk space is re-created in __init__, so it's fine.
                pass
            except:
                pass
        
        # Use provided seed or generate new one
        if seed is None:
            # Check if we should record (if not playing back)
            if not self.replay_manager.is_playing:
                 # Generate a random seed
                 self.current_seed = str(time.time_ns())
            else:
                 # Should have been provided
                 pass
        else:
            self.current_seed = str(seed)

        self.physics_engine = PymunkEngine(self.layout, self.width, self.height, seed=self.current_seed)
        
        # Start recording if not replaying
        if not self.replay_manager.is_playing:
            self.replay_manager.start_recording(self.current_seed, self.layout.name)

        self.drop_target_states = [True] * len(self.layout.drop_targets)
        self.current_upper_angles = []
        for uf in self.layout.upper_flippers:
            if uf['type'] == 'left':
                self.current_upper_angles.append(self.flipper_resting_angle)
            else:
                self.current_upper_angles.append(180.0 - self.flipper_resting_angle)
        
        # Emit game info with hash
        if self.socketio:
             self.socketio.emit('game_init', {
                 'seed': self.current_seed,
                 'hash': self.physics_engine.game_hash,
                 'is_replay': self.replay_manager.is_playing
             }, namespace='/game')

    def get_config(self):
        """Get current configuration dictionary."""
        # Start with default/layout config logic
        config = {
             # Camera/View Defaults
            'camera_x': self.cam_x / self.width,
            'camera_y': self.cam_y / self.height,
            'camera_z': self.cam_z / self.width,
            'pitch': np.degrees(self.pitch),
            'camera_roll': getattr(self, 'roll', 0.0),
            'camera_fov': 45.0,
            
            # Legacy/Layout values
            'guide_thickness': 10.0,
            'guide_length_scale': 1.0, 
            'guide_angle_offset': 0.0,
        }

        # Merge Physics Config if available (Source of Truth)
        if self.physics_engine:
             physics_data = self.physics_engine.config.to_dict()
             config.update(physics_data)
        
        # Merge specific layout visual properties
        if hasattr(self, 'layout'):
             config.update({
                 'zones': getattr(self.layout, 'zones', []),
                 'rails': getattr(self.layout, 'rails', []),
                 'bumpers': getattr(self.layout, 'bumpers', []),
                 'drop_targets': getattr(self.layout, 'drop_targets', []),
                 'ramps': getattr(self.layout, 'ramps', []),
                 'teleports': getattr(self.layout, 'teleports', []),
                 'upper_deck': getattr(self.layout, 'upper_deck', {}),
                 'upper_flippers': getattr(self.layout, 'upper_flippers', []),
                 'camera_presets': getattr(self.layout, 'camera_presets', {}),
                 'last_preset': getattr(self.layout, 'last_preset', ''),
             })
             
             # Flipper Layout Coordinates (Visual)
             config.update({
                'left_flipper_pos_x': self.layout.left_flipper_x_min,
                'left_flipper_pos_y': self.layout.left_flipper_y_min,
                'left_flipper_pos_y_max': self.layout.left_flipper_y_max,
                'right_flipper_pos_x': self.layout.right_flipper_x_min,
                'right_flipper_pos_x_max': self.layout.right_flipper_x_max,
                'right_flipper_pos_y': self.layout.right_flipper_y_min,
                'right_flipper_pos_y_max': self.layout.right_flipper_y_max,  
             })
             
             # Flatten flippers dict for convenience
             config['flippers'] = {
                'left': {
                    'x_min': self.layout.left_flipper_x_min,
                    'y_min': self.layout.left_flipper_y_min,
                    'x_max': self.layout.left_flipper_x_max,
                    'y_max': self.layout.left_flipper_y_max,
                },
                'right': {
                    'x_min': self.layout.right_flipper_x_min,
                    'y_min': self.layout.right_flipper_y_min,
                    'x_max': self.layout.right_flipper_x_max,
                    'y_max': self.layout.right_flipper_y_max,
                }
            }

        # Add other system stats
        config['current_layout_id'] = self.current_layout_id
        config['last_model'] = getattr(self, 'last_model', '')
        config['ai_difficulty'] = getattr(self, 'ai_difficulty', 'medium')
        
        return config

    def load_config(self):
        """Return the current layout and physics configuration (Alias for get_config)."""
        return self.get_config()

    def update_physics_params(self, params, save=True):
        """Update physics parameters and apply them to the physics engine."""
        logger.info(f"SimulatedFrameCapture.update_physics_params called with: {params}")
        
        # Update layout physics params dict (for persistence)
        if hasattr(self.layout, 'physics_params'):
            self.layout.physics_params.update(params)
        
        # 1. Update Physics Config
        if self.physics_engine:
            self.physics_engine.config.update(params)
            self.physics_engine.apply_config_changes()
        
        # 2. Update Visual Layout (SimulatedFrameCapture specific)
        # Some visual elements (e.g. flipper hitboxes in 2D view) need to match physics
        if 'flipper_length' in params or 'left_flipper_pos_x' in params:
             # Recalculate based on config
             current_length = self.physics_engine.config.flipper_length if self.physics_engine else 0.12
             
             # If positions came in params, update them
             if 'left_flipper_pos_x' in params:
                 self.layout.left_flipper_x_min = params['left_flipper_pos_x']
                 self.layout.left_flipper_x_max = params['left_flipper_pos_x'] + current_length
             
             # If only length changed, update max based on existing min
             elif 'flipper_length' in params:
                 self.layout.left_flipper_x_max = self.layout.left_flipper_x_min + current_length
                 self.layout.right_flipper_x_max = self.layout.right_flipper_x_min + current_length

        if 'right_flipper_pos_x' in params:
             current_length = self.physics_engine.config.flipper_length if self.physics_engine else 0.12
             self.layout.right_flipper_x_min = params['right_flipper_pos_x']
             self.layout.right_flipper_x_max = params['right_flipper_pos_x'] + current_length
             
        # Y-Positions (Fixed height assumption for now)
        flipper_height = 0.1
        if 'left_flipper_pos_y' in params:
             self.layout.left_flipper_y_min = params['left_flipper_pos_y']
             self.layout.left_flipper_y_max = params['left_flipper_pos_y'] + flipper_height
        
        if 'right_flipper_pos_y' in params:
             self.layout.right_flipper_y_min = params['right_flipper_pos_y']
             self.layout.right_flipper_y_max = params['right_flipper_pos_y'] + flipper_height

        # Nudge/Tilt parameters internal to vision system (if any kept here)
        if 'nudge_cost' in params:
             self.nudge_cost = float(params['nudge_cost'])
        if 'tilt_decay' in params:
             self.tilt_decay = float(params['tilt_decay'])
        if 'tilt_threshold' in params:
             self.tilt_threshold = float(params['tilt_threshold'])

    def load_layout(self, layout_name):
        """Load a layout by name (str) OR dictionary config."""
        if isinstance(layout_name, dict):
            try:
                self.layout = PinballLayout(config=layout_name)
                self.current_layout_id = layout_name.get('name', 'custom')
                self._init_physics()
                # self._load_available_layouts() # Not needed for custom dict
                logger.info(f"Successfully loaded custom layout from dict")
                return True
            except Exception as e:
                 logger.error(f"Failed to load custom layout: {e}")
                 return False

        layouts_dir = 'layouts'
        filename = f"{layout_name}.json"
        filepath = os.path.join(layouts_dir, filename)
        
        if not os.path.exists(filepath):
            logger.error(f"Layout file not found: {filepath}")
            return False
        
        try:
            logger.info(f"Loading layout: {layout_name}")
            # Load the new layout
            self.layout = PinballLayout(filepath=filepath)
            
            # Track the layout ID (filename without extension)
            self.current_layout_id = layout_name

            # Reinitialize physics engine with new layout
            # This will also start a new game with a fresh seed
            self._init_physics()
            
            # Reload available layouts (in case layout files changed)
            self._load_available_layouts()
            
            logger.info(f"Successfully loaded layout: {layout_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load layout {layout_name}: {e}")
            return False

    def add_ball(self, pos=None):
        """Add a ball to the game (delegates to physics engine)."""
        if not self.physics_engine:
            logger.error("Cannot add ball: physics engine not initialized")
            return
        
        # Use default plunger position if not specified
        if pos is None:
            pos = (self.width * 0.94, self.height * 0.93)  # Near the plunger at 0.95
        
        self.physics_engine.add_ball(pos=pos)
        logger.debug(f"Ball added at position {pos}")

    def trigger_left(self):
        """Activate left flipper."""
        logger.debug("🎮 trigger_left called")
        self.handle_input({'side': 'left', 'action': 'hold'})
    
    def release_left(self):
        """Deactivate left flipper."""
        logger.debug("🎮 release_left called")
        self.handle_input({'side': 'left', 'action': 'release'})
    
    def trigger_right(self):
        """Activate right flipper."""
        logger.debug("🎮 trigger_right called")
        self.handle_input({'side': 'right', 'action': 'hold'})
    
    def release_right(self):
        """Deactivate right flipper."""
        logger.debug("🎮 release_right called")
        self.handle_input({'side': 'right', 'action': 'release'})

    def handle_load_replay(self, data):
        """Start a replay from JSON data or Hash"""
        try:
            replay_json = data
            
            # If data only contains 'hash', try to load from disk
            if 'hash' in data and 'events' not in data:
                 replays_dir = 'replays'
                 filename = f"{data['hash']}.json"
                 filepath = os.path.join(replays_dir, filename)
                 if os.path.exists(filepath):
                     with open(filepath, 'r') as f:
                         replay_json = json.load(f)
                 else:
                     logger.error(f"Replay file not found: {filepath}")
                     return

            logger.info(f"Loading Replay... Seed: {replay_json.get('seed')}")
            seed = self.replay_manager.start_playback(replay_json)
            
            # Reset Game with Seed
            self._init_physics(seed=seed)
            self.reset_game_state()
            
        except Exception as e:
            logger.error(f"Failed to load replay: {e}")

    def save_replay(self):
        if self.replay_manager.is_recording:
             self.replay_manager.stop_recording()
             # Logic to save to file?
             # For now, maybe just keep in memory or dump to 'replays/' folder
             replays_dir = 'replays'
             if not os.path.exists(replays_dir):
                 os.makedirs(replays_dir)
             
             replay_data = self.replay_manager.replay_data
             # Use Game Hash as filename
             filename = f"{self.physics_engine.game_hash}.json"
             filepath = os.path.join(replays_dir, filename)
             
             try:
                 with open(filepath, 'w') as f:
                     json.dump(replay_data, f)
                 logger.info(f"Replay saved to {filepath}")
             except Exception as e:
                 logger.error(f"Failed to save replay: {e}")

    def reset_game_state(self):
        # Save previous game replay if it exists
        if self.replay_manager.is_recording:
            self.save_replay()
            
        self.balls = []
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.is_tilted = False
        self.tilt_value = 0.0
        self.drop_target_states = [True] * len(self.layout.drop_targets)
        
        # Start new recording since we are resetting state (and likely physics init called separately)
        # Actually _init_physics handles starting recording if it generates a new seed.
        # But if we just call reset_game_state() without _init_physics(), we might be in trouble?
        # Usually they go together or _init_physics is called first.
        
        # Add initial ball to physics engine
        if self.physics_engine:
            self.physics_engine.add_ball(pos=(self.width * 0.94, self.height * 0.9))

    def handle_input(self, data):
        # Ignore inputs during replay
        if self.replay_manager.is_playing: return
        
        self.replay_manager.record_event('flipper', data)
        self._apply_flipper_input(data)

    def _apply_flipper_input(self, data):
        side = data.get('side')
        action = data.get('action') # 'hold' or 'release'
        active = (action == 'hold')
        
        # If tilted, ignore inputs (solenoids dead)
        if self.is_tilted:
            active = False
            
        if side == 'left':
            self.left_flipper_active = active
            self._left_flipper_inputs.append(1 if active else 0)
            if len(self._left_flipper_inputs) > 60: self._left_flipper_inputs.pop(0)
            self.physics_engine.actuate_flipper('left', active)
        elif side == 'right':
            self.right_flipper_active = active
            self.physics_engine.actuate_flipper('right', active)

    def handle_plunger(self, data):
        if self.replay_manager.is_playing: return
        
        self.replay_manager.record_event('plunger', data)
        self._apply_plunger_input(data)

    def _apply_plunger_input(self, data):
        # 'press', 'release', 'hold' (with value)
        action = data.get('action')
        
        if action == 'press':
            # Start charging (handled in physics)
            pass
        elif action == 'release':
            # Fire (handled in physics)
            self.physics_engine.launch_plunger()

    def handle_nudge(self, data):
        if self.replay_manager.is_playing: return
        
        self.replay_manager.record_event('nudge', data)
        self._apply_nudge_input(data)

    def _apply_nudge_input(self, data):
        direction = data.get('direction') # 'left', 'right', 'up'
        force = data.get('force', 10.0)
        
        if self.game_over or self.is_tilted: return
        
        dx, dy = 0, 0
        if direction == 'left': dx = -force
        elif direction == 'right': dx = force
        elif direction == 'up': dy = -force
        
        self.nudge_x += dx
        self.nudge_y += dy
        
        self.last_nudge = {'direction': direction, 'time': time.time()}
        
        # Tilt Logic
        self.tilt_value += abs(force)
        if self.tilt_value > self.tilt_threshold:
            self.is_tilted = True
            logger.info("TILT!")
            if self.socketio:
                self.socketio.emit('game_event', {'type': 'tilt'}, namespace='/game')
            # Deactivate flippers
            self.left_flipper_active = False
            self.right_flipper_active = False
            self.physics_engine.actuate_flipper('left', False)
            self.physics_engine.actuate_flipper('right', False)

    def handle_layout_selection(self, data):
        filename = data.get('filename')
        if filename:
            self.refresh_layouts(filename)
            self.handle_reset({}) # Reset game on layout switch

    def handle_reload(self, data):
        self.refresh_layouts(self.layout.name + '.json' if hasattr(self.layout, 'name') else None)

    def handle_reset(self, data):
        # Completely restart simulation
        self._init_physics() # Generate NEW seed
        self.reset_game_state()
        
        self.right_flipper_active = False
        self.left_flipper_active = False
        self.nudge_x = 0
        self.nudge_y = 0
        self.tilt_value = 0.0
        self.is_tilted = False
        
        if self.socketio:
            self.socketio.emit('game_reset', {}, namespace='/game')

    def handle_view_mode(self, data):
        mode = data.get('mode')
        if mode in ['2d', '3d']:
            self.view_mode = mode
            logger.info(f"View mode set to {mode}")

    def handle_pan(self, data):
        delta_y = data.get('dy', 0)
        # Adjust scroll (approx pixels)
        # Map pixels to normalized height?
        scale = 0.001
        self.camera_offset_y -= delta_y * scale
        self.camera_offset_y = max(0.0, min(self.camera_offset_y, 0.5))

    def handle_zoom(self, data):
        # Zoom in/out
        # data is usually delta?
        delta = data.get('delta', 0)
        
        # Prevent game reset by checking if zoom is actually intended
        # (Already handled on invalid input?)
        
        self.camera_zoom += delta * 0.001
        self.camera_zoom = max(0.5, min(self.camera_zoom, 2.0))

    def refresh_layouts(self, specific_filename=None):
        # Skip reload if we're currently saving (prevents circular loop)
        if self._saving_config:
            logger.info("Skipping layout reload: save in progress")
            return

        layouts_dir = 'layouts'
        if not os.path.exists(layouts_dir):
            os.makedirs(layouts_dir)
            
        # If specific file provided, load that
        if specific_filename:
             filepath = os.path.join(layouts_dir, specific_filename)
             if os.path.exists(filepath):
                 logger.info(f"Loading layout: {filepath}")
                 try:
                    self.layout = PinballLayout(filepath=filepath)
                    self._init_physics()
                 except Exception as e:
                     logger.error(f"Failed to load specific layout: {e}")
             return

        # Scan directory
        files = [f for f in os.listdir(layouts_dir) if f.endswith('.json')]
        if not files:
            # Create default
            default_layout = PinballLayout()
            default_layout.save_to_file(os.path.join(layouts_dir, 'default.json'))
            self.layout = default_layout
        else:
            # Load first found or default
            filepath = os.path.join(layouts_dir, files[0])
            self.layout = PinballLayout(filepath=filepath)
            
        self._init_physics()

    def nudge_left(self):
        """Apply nudge force to the left (pushes table left, ball moves right)."""
        if self.physics_engine:
            # Table moves Left -> Ball moves Right (+X)
            # We also typically nudge "forward" (Up table, -Y)
            self.physics_engine.nudge(1.0, -0.5)

    def nudge_right(self):
        """Apply nudge force to the right (pushes table right, ball moves left)."""
        if self.physics_engine:
            self.physics_engine.nudge(-1.0, -0.5)

    def nudge_up(self):
        """Apply forward nudge."""
        if self.physics_engine:
            self.physics_engine.nudge(0.0, 1.0)

    def alien_nudge(self):
        """Apply a random 'alien' nudge that doesn't count towards tilt."""
        if self.physics_engine:
             # Random shake
             dx = random.choice([-1.0, 1.0])
             dy = random.choice([-0.5, 0.5, 1.0])
             self.physics_engine.nudge(dx, dy, check_tilt=False)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.start()
        logger.info("Simulation started")

    def _capture_loop(self):
        # We assume 60FPS simulation loop
        while self.running:
            dt = 0.016
            start_time = time.time()
            
            # Physics Step
            if self.physics_engine:
                self.physics_engine.update(dt)
                
            # Process Replay Inputs
            if self.replay_manager.is_playing:
                events = self.replay_manager.get_events_for_frame()
                for evt in events:
                    # Dispatch to apply functions
                    if evt['type'] == 'flipper':
                        self._apply_flipper_input(evt['value'])
                    elif evt['type'] == 'plunger':
                        self._apply_plunger_input(evt['value'])
                    elif evt['type'] == 'nudge':
                        self._apply_nudge_input(evt['value'])
            
            # Tick Replay Clock
            self.replay_manager.tick()
            
            # Render Frame
            self._draw_frame()

            # Sleep remainder
            elapsed = time.time() - start_time
            if not self.headless:
                sleep_time = max(0, dt - elapsed)
                time.sleep(sleep_time)
            # Headless: no sleep - run as fast as possible for training

    def _draw_frame(self):
        # Update sync variables
        if self.physics_engine:
            # Sync balls
            self.balls = []
            for b in self.physics_engine.balls:
                # Get radius from the shape (Circle) attached to the body
                # The first shape should be the circle
                radius = 12.0  # default
                if len(b.shapes) > 0:
                    # b.shapes is a set, not a list, so we need to iterate
                    for shape in b.shapes:
                        if hasattr(shape, 'radius'):
                            radius = shape.radius
                            break  # Use the first shape with a radius
                
                self.balls.append({
                    'pos': [b.position.x, b.position.y],
                    'vel': [b.velocity.x, b.velocity.y],
                    'radius': radius,
                    'lost': False
                })
            
            # Sync Score
            self.score = self.physics_engine.score
            # Update high score if current score is higher
            if self.score > self.high_score:
                self.high_score = self.score
            
            # Sync Drop Targets
            self.drop_target_states = self.physics_engine.drop_target_states
            
            # Sync Tilt State
            self.is_tilted = self.physics_engine.is_tilted
            self.tilt_value = getattr(self.physics_engine, 'tilt_value', 0.0)
            
            # Sync Flipper Angles from physics engine
            if hasattr(self.physics_engine, 'flippers') and self.physics_engine.flippers:
                if 'left'  in self.physics_engine.flippers and self.physics_engine.flippers['left']:
                    flipper_body = self.physics_engine.flippers['left']['body']
                    angle_deg = np.degrees(flipper_body.angle)
                    self.current_left_angle = angle_deg
                    logger.debug(f"Left flipper angle: {angle_deg:.1f}°")
                if 'right' in self.physics_engine.flippers and self.physics_engine.flippers['right']:
                    flipper_body = self.physics_engine.flippers['right']['body']
                    angle_deg = np.degrees(flipper_body.angle)
                    self.current_right_angle = angle_deg
                    logger.debug(f"Right flipper angle: {angle_deg:.1f}°")
        
        # Base Canvas
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Draw Layout (Walls, Flippers, Bumpers) - Simplified 2D
        # Walls
        # ... (Drawing code omitted for brevity, standard 2D render) ...
        # Actually we need this to output a valid frame for the vision system
        
        # Fill Background (Table Color)
        canvas[:] = (20, 20, 20) # Dark Gray
        
        # Draw Rails (if any)
        # Use helper
        if hasattr(self.physics_engine, 'rail_shapes'):
            for shape in self.physics_engine.rail_shapes:
                if hasattr(shape, 'a') and hasattr(shape, 'b'):
                    # Shape is Segment
                    p1 = shape.a
                    p2 = shape.b
                    cv2.line(canvas, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), (100, 100, 100), 2)
                elif hasattr(shape, 'get_vertices'):
                    # Shape is Poly
                    try:
                        pts = [shape.body.local_to_world(v) for v in shape.get_vertices()]
                        pts_np = np.array([[int(p.x), int(p.y)] for p in pts], np.int32)
                        pts_np = pts_np.reshape((-1, 1, 2))
                        cv2.polylines(canvas, [pts_np], True, (100, 100, 100), 2)
                    except Exception as e:
                        logger.error(f"Error drawing poly rail: {e}")

        # Draw Bumpers
        try:
            if hasattr(self.layout, 'bumpers'):
                for i, bumper in enumerate(self.layout.bumpers):
                    pos = (int(bumper['x'] * self.width), int(bumper['y'] * self.height))
                    state = 0.0
                    if self.physics_engine and hasattr(self.physics_engine, 'bumper_states') and i < len(self.physics_engine.bumper_states):
                        state = self.physics_engine.bumper_states[i]
                    
                    # Decay state for visual flash
                    if state > 0:
                        color = (0, 255, 255) # Yellow/Cyan flash
                        radius = 20
                    else:
                        color = (0, 165, 255) # Orange (BGR)
                        radius = 18
                    
                    cv2.circle(canvas, pos, radius, color, -1)
                    cv2.circle(canvas, pos, radius, (0, 100, 200), 2) # Outline
        except Exception as e:
            logger.error(f"Error drawing bumpers: {e}")

        # Draw Drop Targets
        try:
            if hasattr(self.layout, 'drop_targets'):
                for i, target in enumerate(self.layout.drop_targets):
                    # Check state
                    is_up = True
                    if self.physics_engine and hasattr(self.physics_engine, 'drop_target_states') and i < len(self.physics_engine.drop_target_states):
                        is_up = self.physics_engine.drop_target_states[i]
                    
                    # Convert normalized to pixels
                    # Width/Height in config might be normalized
                    cw = int(target['width'] * self.width)
                    ch = int(target['height'] * self.height) if 'height' in target else 20
                    cx = int(target['x'] * self.width)
                    cy = int(target['y'] * self.height)
                    
                    top_left = (cx - cw//2, cy - ch//2)
                    bottom_right = (cx + cw//2, cy + ch//2)
                    
                    if is_up:
                        cv2.rectangle(canvas, top_left, bottom_right, (255, 50, 50), -1) # Blue filled
                        cv2.rectangle(canvas, top_left, bottom_right, (200, 200, 200), 2) # Border
                    else:
                        pass # Invisible if down?
        except Exception as e:
            logger.error(f"Error drawing drop targets: {e}")


        # Draw Flippers (using current angles)
        # Pivot is at (x_min, y_max) for left, (x_max, y_max) for right
        self._draw_flipper(canvas, 'left', self.layout.left_flipper_x_min, self.layout.left_flipper_y_max, 
                           self.layout.left_flipper_x_max, self.layout.left_flipper_y_min, self.current_left_angle)
                           
        self._draw_flipper(canvas, 'right', self.layout.right_flipper_x_max, self.layout.right_flipper_y_max,
                           self.layout.right_flipper_x_min, self.layout.right_flipper_y_min, self.current_right_angle)

        # Upper Flippers
        for i, uf in enumerate(self.layout.upper_flippers):
             # Need to calculate coords again?
             # Just use stored logical ones
             pass # TODO: Draw upper flippers

        # Draw Plunger  
        if self.physics_engine and hasattr(self.physics_engine, 'plunger_body'):
            plunger_pos = self.physics_engine.plunger_body.position
            plunger_w = int(getattr(self.physics_engine, 'plunger_width', 40))
            plunger_h = int(getattr(self.physics_engine, 'plunger_height', 40))
            
            # Draw rectangle for plunger
            top_left = (int(plunger_pos.x - plunger_w/2), int(plunger_pos.y - plunger_h/2))
            bottom_right = (int(plunger_pos.x + plunger_w/2), int(plunger_pos.y + plunger_h/2))
            cv2.rectangle(canvas, top_left, bottom_right, (150, 150, 150), -1)  # Gray filled rectangle

        # Draw Balls
        for ball in self.balls:
            pos = (int(ball['pos'][0]), int(ball['pos'][1]))
            cv2.circle(canvas, pos, int(ball['radius']), (0, 255, 255), -1)
            
        with self.lock:
             self.frame = canvas

    def get_game_state(self):
        """Return current game state for frontend sync."""
        
        # Serialize Balls with normalized coordinates for frontend
        out_balls = []
        with self.lock:
            for ball in self.balls:
                # Normalize positions to 0-1 range for frontend (3D view expects this)
                out_balls.append({
                    'x': ball['pos'][0] / self.width,      # Normalize X (0-1)
                    'y': ball['pos'][1] / self.height,     # Normalize Y (0-1)
                    'vel': ball['vel'],                     # Keep velocity as-is
                    'radius': ball['radius'],
                    'lost': ball.get('lost', False)
                })
        
        # Get collision events from physics engine
        events = []
        if self.physics_engine and hasattr(self.physics_engine, 'get_events'):
            events = self.physics_engine.get_events()

        return {
            'balls': out_balls,
            'score': self.score,
            'high_score': self.high_score,
            'lives': self.lives,
            'game_over': self.game_over,
            'flippers': {
                'left_angle': self.current_left_angle,
                'right_angle': self.current_right_angle,
                'upper_angles': self.current_upper_angles
            },
            'drop_targets': self.drop_target_states,
            'is_tilted': self.is_tilted,
            'tilt_value': self.tilt_value,
            'nudge': {'x': self.nudge_x, 'y': self.nudge_y},
            'bumper_states': getattr(self.physics_engine, 'bumper_states', []) if self.physics_engine else [],
            'plunger': {
                'x': self.physics_engine.plunger_body.position.x / self.width if self.physics_engine and hasattr(self.physics_engine, 'plunger_body') else 0.925,
                'y': self.physics_engine.plunger_body.position.y / self.height if self.physics_engine and hasattr(self.physics_engine, 'plunger_body') else 0.95,
                'state': getattr(self.physics_engine, 'plunger_state', 'resting') if self.physics_engine else 'resting'
            },
            'left_plunger': {
                'x': self.physics_engine.left_plunger_body.position.x / self.width if self.physics_engine and hasattr(self.physics_engine, 'left_plunger_body') else 0.075,
                'y': self.physics_engine.left_plunger_body.position.y / self.height if self.physics_engine and hasattr(self.physics_engine, 'left_plunger_body') else 0.95,
                'state': getattr(self.physics_engine, 'left_plunger_state', 'resting') if self.physics_engine else 'resting'
            },
            'events': events
        }
    
    def _draw_flipper(self, frame, side, x1, y1, x2, y2, angle):
        # Convert normalized to pixels
        px1, py1 = x1 * self.width, y1 * self.height
        px2, py2 = x2 * self.width, y2 * self.height
        
        # Calculate Pivot (Top corner)
        pivot = (int(px1), int(py1))
        
        length = np.hypot(px2-px1, py2-py1)
        
        # For right flipper, invert the angle (it extends in opposite direction)
        if side == 'right':
            angle = 180 - angle
        
        rad = np.radians(angle)
        
        # Calculate end point based on angle
        end_x = px1 + length * np.cos(rad)
        end_y = py1 + length * np.sin(rad)
        
        cv2.line(frame, pivot, (int(end_x), int(end_y)), (200, 200, 0), 5)
        
    # Helper for sync
    def get_ball_status(self):
        """Get ball position and velocity for training/observation.

        This queries the physics engine directly to avoid synchronization issues
        when called from training loops independent of the render loop.
        """
        with self.lock:
            # Query physics engine directly for accurate real-time data
            if self.physics_engine and hasattr(self.physics_engine, 'balls'):
                if not self.physics_engine.balls:
                    return None
                # Return first ball position and velocity
                b = self.physics_engine.balls[0]
                return (b.position.x, b.position.y), (b.velocity.x, b.velocity.y)

            # Fallback to cached balls list (for compatibility)
            if not self.balls:
                return None
            b = self.balls[0]
            return b['pos'], b['vel']

    def save_config(self):
        """Save the current physics parameters back to the layout file."""
        # Use the layout's filepath if it has one, otherwise use our tracked path
        filepath = getattr(self.layout, 'filepath', None) or getattr(self, 'layout_filepath', None)

        if not filepath:
            logger.warning("Cannot save config: no layout filepath available")
            return

        try:
            # Set flag to prevent file watcher from triggering reload
            self._saving_config = True

            logger.info(f"Saving layout configuration to {filepath}")
            self.layout.save_to_file(filepath)
            logger.info(f"✓ Saved layout configuration to {filepath}")

            # Keep flag set for a short time to let file system events settle
            import threading
            def clear_flag():
                time.sleep(0.6)  # Longer than file watcher debounce (0.5s)
                self._saving_config = False
            threading.Thread(target=clear_flag, daemon=True).start()

        except Exception as e:
            logger.error(f"Failed to save layout configuration: {e}")
            self._saving_config = False

    def save_camera_preset(self, name, camera_params=None):
        """Save a camera preset with the current or provided camera parameters."""
        if not hasattr(self.layout, 'camera_presets'):
            self.layout.camera_presets = {}

        # If camera params not provided, extract from layout's physics_params
        if camera_params is None:
            camera_params = {}
            camera_keys = ['camera_x', 'camera_y', 'camera_z', 'camera_pitch', 'camera_zoom']
            for key in camera_keys:
                if hasattr(self.layout, 'physics_params') and key in self.layout.physics_params:
                    camera_params[key] = self.layout.physics_params[key]

        # Save the preset
        self.layout.camera_presets[name] = camera_params
        logger.info(f"Saved camera preset '{name}': {camera_params}")

        # Save to file
        self.save_config()

        # Return all presets for frontend update
        return self.layout.camera_presets

    def delete_camera_preset(self, name):
        """Delete a camera preset by name."""
        if not hasattr(self.layout, 'camera_presets'):
            self.layout.camera_presets = {}
            return self.layout.camera_presets

        if name in self.layout.camera_presets:
            del self.layout.camera_presets[name]
            logger.info(f"Deleted camera preset '{name}'")

            # Save to file
            self.save_config()
        else:
            logger.warning(f"Camera preset '{name}' not found")

        # Return all presets for frontend update
        return self.layout.camera_presets
