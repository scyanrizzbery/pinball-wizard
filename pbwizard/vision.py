import threading
import time
import os
import logging
import json
import random

import cv2
import numpy as np

from pbwizard import constants
from pbwizard.physics import PymunkEngine


logger = logging.getLogger(__name__)


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
        self.left_flipper_x_min = 0.3
        self.left_flipper_x_max = 0.35
        self.left_flipper_y_min = 0.8
        self.left_flipper_y_max = 0.9
        
        self.right_flipper_x_min = 0.65
        self.right_flipper_x_max = 0.7
        self.right_flipper_y_min = 0.8
        self.right_flipper_y_max = 0.9
        
        # Zones: List of dicts {'id': str, 'type': 'left'|'right', 'points': [{'x':, 'y':}]}
        self.zones = [
            {
                'id': 'default_left',
                'type': 'left',
                'is_screen_space': False,
                'points': [{'x': 0.18, 'y': 0.65}, {'x': 0.42, 'y': 0.65}, {'x': 0.42, 'y': 0.85}, {'x': 0.18, 'y': 0.85}]
            },
            {
                'id': 'default_right',
                'type': 'right',
                'is_screen_space': False,
                'points': [{'x': 0.58, 'y': 0.65}, {'x': 0.82, 'y': 0.65}, {'x': 0.82, 'y': 0.85}, {'x': 0.58, 'y': 0.85}]
            }
        ]
        
        self.bumpers = [
            {'x': 0.5, 'y': 0.3, 'radius_ratio': 0.05, 'value': 100},
            {'x': 0.3, 'y': 0.4, 'radius_ratio': 0.04, 'value': 50},
            {'x': 0.7, 'y': 0.4, 'radius_ratio': 0.04, 'value': 50}
        ]
        

        
        self.drop_targets = [
            {'x': 0.4, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500},
            {'x': 0.5, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500},
            {'x': 0.6, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500}
        ]
        
        # Ball Captures (Hold ball for X seconds)
        self.captures = []
        
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
        self.rail_x_offset = -0.61
        self.rail_y_offset = -0.11
        
        # Physics Parameters (Persisted per layout)
        self.physics_params = {}
        
        if filepath:
            self.load_from_file(filepath)
        elif config:
            self.load(config)

    def reset_zones(self):
        """Resets zones to their default values."""
        self.zones = [
            {
                'id': 'default_left',
                'type': 'left',
                'is_screen_space': False,
                'points': [{'x': 0.15, 'y': 0.75}, {'x': 0.45, 'y': 0.75}, {'x': 0.45, 'y': 0.95}, {'x': 0.15, 'y': 0.95}]
            },
            {
                'id': 'default_right',
                'type': 'right',
                'is_screen_space': False,
                'points': [{'x': 0.55, 'y': 0.75}, {'x': 0.85, 'y': 0.75}, {'x': 0.85, 'y': 0.95}, {'x': 0.55, 'y': 0.95}]
            }
        ]

    def load_from_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            self.load(config)
        except Exception as e:
            logger.error(f"Failed to load layout from {filepath}: {e}")

    def save_to_file(self, filepath):
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
            'zones': self.zones,
            'bumpers': self.bumpers,
            'drop_targets': self.drop_targets,
            'captures': self.captures,
            'ramps': self.ramps,
            'teleports': self.teleports,
            'upper_deck': self.upper_deck,
            'upper_deck': self.upper_deck,
            'upper_flippers': self.upper_flippers,
            'rails': self.rails,
            'rail_x_offset': self.rail_x_offset,
            'rail_y_offset': self.rail_y_offset,
            'physics': self.physics_params
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
        
        if 'zones' in config:
            self.zones = config['zones']
        
        if 'bumpers' in config:
            self.bumpers = config['bumpers']
            
        if 'drop_targets' in config:
            self.drop_targets = config['drop_targets']
            
        if 'physics' in config:
            self.physics_params = config['physics']
        if 'rails' in config:
            self.rails = config['rails']
            
        if 'rail_x_offset' in config:
            self.rail_x_offset = config['rail_x_offset']
        if 'rail_y_offset' in config:
            self.rail_y_offset = config['rail_y_offset']

    def to_dict(self):
        return {
            "flippers": {
                "left": {
                    "x_min": self.left_flipper_x_min,
                    "x_max": self.left_flipper_x_max,
                    "y_min": self.left_flipper_y_min,
                    "y_max": self.left_flipper_y_max
                },
                "right": {
                    "x_min": self.right_flipper_x_min,
                    "x_max": self.right_flipper_x_max,
                    "y_min": self.right_flipper_y_min,
                    "y_max": self.right_flipper_y_max
                }
            },
            "zones": self.zones,
            "bumpers": self.bumpers,
            "drop_targets": self.drop_targets,
            "rails": self.rails,
            "rail_x_offset": self.rail_x_offset,
            "rail_y_offset": self.rail_y_offset
        }

    def randomize(self):
        """Randomize layout parameters for training variety."""
        # Randomize flipper gap (difficulty)
        # Keep y positions relatively stable, just move x
        gap_width = np.random.uniform(0.15, 0.25)
        center = 0.5
        
        self.left_flipper_x_max = center - (gap_width / 2)
        self.left_flipper_x_min = self.left_flipper_x_max - 0.2
        
        self.right_flipper_x_min = center + (gap_width / 2)
        self.right_flipper_x_max = self.right_flipper_x_min + 0.2
        
        # Randomize bumpers
        num_bumpers = np.random.randint(0, 8)
        self.bumpers = []
        for _ in range(num_bumpers):
            # Avoid flipper area (bottom center)
            while True:
                x = np.random.uniform(0.1, 0.9)
                y = np.random.uniform(0.1, 0.7)
                
                # Simple check to avoid center drain area
                if y > 0.6 and 0.3 < x < 0.7:
                    continue
                
                self.bumpers.append({
                    'x': x,
                    'y': y,
                    'radius_ratio': np.random.uniform(0.03, 0.06),
                    'value': int(np.random.choice([50, 100, 500]))
                })
                break
        
        # Randomize drop targets
        num_targets = np.random.randint(0, 4)
        self.drop_targets = []
        if num_targets > 0:
            y_pos = np.random.uniform(0.05, 0.2)
            spacing = 0.05
            start_x = 0.5 - ((num_targets - 1) * spacing) / 2
            
            for i in range(num_targets):
                self.drop_targets.append({
                    'x': start_x + i * spacing,
                    'y': y_pos,
                    'width': 0.03,
                    'height': 0.01,
                    'value': 500
                })

class SimulatedFrameCapture:
    # Physics Constants
    FLIPPER_SPEED = 15.0  # Degrees per frame
    FLIPPER_LENGTH = 0.12  # Normalized width    # Flipper Angles (Degrees)
    LEFT_DOWN_ANGLE = 30
    LEFT_UP_ANGLE = -30
    RIGHT_DOWN_ANGLE = -30 # Symmetric
    RIGHT_UP_ANGLE = 30    # Symmetric
    GRAVITY = 25.0 # Synced with physics.py
    SUB_STEPS = 20
    FRICTION = 0.5 # Synced with physics.py
    FRICTION = 0.5 # Synced with physics.py
    RESTITUTION = 0.7 # Synced with physics.py
    FLIPPER_LENGTH = 0.18 # Synced with config
    FLIPPER_WIDTH = 0.010 # Synced with config
    
    MAX_BALLS = 5
    
    # Tilt Settings
    TILT_THRESHOLD = 8.0
    NUDGE_COST = 4.0
    TILT_DECAY = 0.05

    def __init__(self, layout_config=None, width=450, height=800, socketio=None, headless=False):
        self.width = width
        self.height = height
        self.socketio = socketio
        self.layout_config = layout_config
        self.headless = headless
        self.last_model = None  # Track last loaded model
        self.last_preset = None  # Track last selected camera preset
        self.current_layout_id = 'default' # Track current layout ID
        self.layout = PinballLayout() # Removed 'layout' parameter from init, so always create new
        if layout_config:
            self.layout.load(layout_config)
        self.physics_engine = PymunkEngine(self.layout, width, height) # Initialize Physics Engine
        self.zone_manager = ZoneManager(width, height, self.layout)
        
        # Load layouts from layouts directory
        self.available_layouts = {}
        layouts_dir = os.path.join(os.getcwd(), 'layouts')
        if not os.path.exists(layouts_dir):
            os.makedirs(layouts_dir)
            
        try:
            for filename in os.listdir(layouts_dir):
                if filename.endswith('.json'):
                    layout_name = filename[:-5] # Remove .json
                    filepath = os.path.join(layouts_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            layout_data = json.load(f)
                            # Store both data and filepath if needed, or just data
                            # For consistency with previous implementation, store data
                            # But we also want to know the filename for saving back
                            self.available_layouts[layout_name] = layout_data
                    except Exception as e:
                        logger.error(f"Failed to load layout {filename}: {e}")
                        
            logger.info(f"Loaded {len(self.available_layouts)} layouts from {layouts_dir}")
        except Exception as e:
            logger.error(f"Failed to scan layouts directory: {e}")


        
        # Table Tilt (Degrees)
        self.table_tilt = 6.0 # Standard pinball tilt
        self.launch_angle = 0.0 # Launch angle (degrees)
        
        # Instance physics parameters (initialized from class constants)
        # Calculate gravity based on tilt
        BASE_GRAVITY = 25000.0
        self.gravity = BASE_GRAVITY * np.sin(np.radians(self.table_tilt))
        
        self.friction = self.FRICTION
        self.restitution = self.RESTITUTION
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_length = self.FLIPPER_LENGTH
        self.flipper_width = self.FLIPPER_WIDTH
        
        # Tilt Parameters
        self.tilt_threshold = self.TILT_THRESHOLD
        self.nudge_cost = self.NUDGE_COST
        self.tilt_decay = self.TILT_DECAY
        
        self.show_rail_debug = False # Toggle for yellow rail lines
        
        # Table Tilt (Degrees)
        self.table_tilt = 6.0 # Standard pinball tilt
        
        # Flipper Angles (Symmetric Control)
        self.flipper_resting_angle = -30.0
        self.flipper_stroke_angle = 50.0
        
        self.flipper_stroke_angle = 50.0
        
        
        # Rail Parameters (for UI control)
        self.rail_thickness = 10.0
        self.rail_length_scale = 1.0
        self.rail_angle_offset = 0.0
        
        # Rail endpoint parameters (direct control)
        self.rail_left_p1_x = 0.18
        self.rail_left_p1_y = 0.50
        self.rail_left_p2_x = 0.36
        self.rail_left_p2_y = 0.83
        self.rail_right_p1_x = 0.82
        self.rail_right_p1_y = 0.50
        self.rail_right_p2_x = 0.64
        self.rail_right_p2_y = 0.83
        
        # Rail translation offsets
        self.rail_x_offset = -0.61
        self.rail_y_offset = -0.11
        
        self.plunger_release_speed = 1500.0 # Default

        self.auto_start_enabled = True # Default to True for easier testing
        
        # Load Assets
        self.assets = {}
        self._load_assets()
        
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.running = False
        self.lock = threading.RLock()
        
        # Ball State (List of balls)
        self.balls = [] # List of dicts: {'pos': np.array, 'vel': np.array, 'lost': bool}
        # Ball State (List of balls)
        self.balls = [] # List of dicts: {'pos': np.array, 'vel': np.array, 'lost': bool}
        self.ball_radius = int(width * 0.025) # Scale ball with width
        self.balls_remaining = 1 # Single ball game
        
        # Tilt State
        self.tilt_value = 0.0
        self.is_tilted = False
        
        # Drop Target States (True = Active/Up, False = Inactive/Down)
        self.drop_target_states = [True] * len(self.layout.drop_targets) 
        
        # Flipper states (Reference Counting)
        self._left_flipper_inputs = 0
        self._right_flipper_inputs = 0
        self.current_left_angle = self.flipper_resting_angle
        self.current_right_angle = 180.0 - self.flipper_resting_angle
        
        # Upper Flipper States
        self.current_upper_angles = []
        for uf in self.layout.upper_flippers:
            # Initialize based on type (left/right)
            if uf['type'] == 'left':
                self.current_upper_angles.append(self.flipper_resting_angle)
            else:
                self.current_upper_angles.append(180.0 - self.flipper_resting_angle)
        
        # Initialize zone contours
        # Moved to after camera init
        # self._update_zone_contours()
        
        # Flipper zones (calculated from layout)
        # Flipper zones (calculated from layout)
        self.left_flipper_rect = None
        self.right_flipper_rect = None

        
        self._update_flipper_rects()
        
        # Score and Bumpers
        self.score = 0
        self.high_score = 0
        self.games_played = 0
        self.game_history = []
        self.bumpers = []
        for b in self.layout.bumpers:
            self.bumpers.append({
                'pos': np.array([width * b['x'], height * b['y']]),
                'radius': int(width * b['radius_ratio']),
                'value': b['value']
            })
        
        # Guide Lines (Funnel to flippers)
        # Initialized in _update_flipper_rects
        
        # 3D Camera Settings
        # 3D Camera Settings (Default Preset Values)
        self.cam_x = width * 0.5
        self.cam_y = height * 2.5
        self.cam_z = width * 1.5
        self.focal_length = (width * 1.2) * 2.4 # Base * Zoom
        
        self.pitch = np.radians(73.0)
        
        self.last_nudge = None
        self.multiball_cooldown_timer = 0.0 # Cooldown for multiball trigger

        # Initialize zone contours (requires camera params)
        self._update_zone_contours()

        self.camera_presets = {
            "Default": {
                "camera_pitch": 73.0,
                "camera_x": 0.5,
                "camera_y": 2.5,
                "camera_z": 1.5,
                "camera_zoom": 2.4
            },
            "Top Down": {
                "camera_pitch": 0.0,
                "camera_x": 0.5,
                "camera_y": 0.6,
                "camera_z": 1.4,
                "camera_zoom": 0.8
            },
            "Player View": {
                "camera_pitch": 30.0,
                "camera_x": 0.5,
                "camera_y": 1.3,
                "camera_z": 1.2,
                "camera_zoom": 1.0
            },
            "Side View": {
                "camera_pitch": 45.0,
                "camera_x": 0.0,
                "camera_y": 1.5,
                "camera_z": 1.5,
                "camera_zoom": 1.0
            },
            "Close Up": {
                "camera_pitch": 20.0,
                "camera_x": 0.5,
                "camera_y": 1.3,
                "camera_z": 1.1,
                "camera_zoom": 1.6
            },
            "Wide Angle": {
                "camera_pitch": 60.0,
                "camera_x": 0.5,
                "camera_y": 1.4,
                "camera_z": 1.3,
                "camera_zoom": 0.7
            }
        }

        # Load saved configuration (including zones and camera settings)
        # This ensures flippers work immediately on startup
        self.load_config()



    def _update_flipper_rects(self):
        # Update flipper rectangles based on current flipper_length
        # Left Flipper: Pivot at x_min, length extends to right
        l_x_min = self.layout.left_flipper_x_min
        l_x_max = l_x_min + self.flipper_length
        
        self.left_flipper_rect = (
            int(self.width * l_x_min),
            int(self.height * self.layout.left_flipper_y_min),
            int(self.width * l_x_max),
            int(self.height * self.layout.left_flipper_y_max)
        )
        
        # Sync layout object (so get_config returns correct values)
        self.layout.left_flipper_x_max = l_x_max

        # Right Flipper: Pivot at x_max, length extends to left
        r_x_max = self.layout.right_flipper_x_max
        r_x_min = r_x_max - self.flipper_length
        
        self.right_flipper_rect = (
            int(self.width * r_x_min),
            int(self.height * self.layout.right_flipper_y_min),
            int(self.width * r_x_max),
            int(self.height * self.layout.right_flipper_y_max)
        )

        # Sync layout object
        self.layout.right_flipper_x_min = r_x_min
        


    def _load_assets(self):
        asset_dir = os.path.join(os.path.dirname(__file__), 'assets')
        try:
            wood_path = os.path.join(asset_dir, 'playfield_wood.png')
            if os.path.exists(wood_path):
                self.assets['wood'] = cv2.imread(wood_path)
                logger.info(f"Loaded asset: {wood_path}")
            
            apron_path = os.path.join(asset_dir, 'apron_wood.png')
            if os.path.exists(apron_path):
                self.assets['apron'] = cv2.imread(apron_path)
                logger.info(f"Loaded asset: {apron_path}")
            
            backglass_path = os.path.join(asset_dir, 'backglass.png')
            if os.path.exists(backglass_path):
                self.assets['backglass'] = cv2.imread(backglass_path)
                logger.info(f"Loaded asset: {backglass_path}")
        except Exception as e:
            logger.error(f"Failed to load assets: {e}")

    def _project_3d(self, x, y, z):
        # 1. Translate to Camera Space
        # Camera is at (cam_x, cam_y, cam_z) looking at (width/2, height/2, 0)
        # Simplified: Camera is looking roughly down -Y and -Z
        
        # Relative coordinates
        rx = x - self.cam_x
        ry = y - self.cam_y
        rz = z - self.cam_z
        
        # 2. Rotate Camera (Look at center of table)
        # Pitch down to look at table center
        # Angle calculation:
        # target = (width/2, height/2, 0)
        # dy = target_y - cam_y = -height
        # dz = target_z - cam_z = -width*1.5
        # pitch = atan2(dy, dz)
        
        # Let's use a simpler "look-at" matrix approach or just hardcode a nice view
        # Let's try a simple perspective projection assuming camera is aligned
        
        # Rotate around X axis (Pitch)
        # alpha = pitch angle
        # y' = y*cos(a) - z*sin(a)
        # z' = y*sin(a) + z*cos(a)
        
        pitch = self.pitch
        
        cx = rx
        cy = ry * np.cos(pitch) - rz * np.sin(pitch)
        cz = ry * np.sin(pitch) + rz * np.cos(pitch)
        
        # 3. Project to 2D
        # x_screen = (cx / cz) * f + center_x
        # y_screen = (cy / cz) * f + center_y
        
        if cz == 0: cz = 0.001
        
        scale = self.focal_length / abs(cz)
        
        sx = int(cx * scale + self.width / 2)
        sy = int(cy * scale + self.height / 2) # Removed inversion for correct orientation
        
        # Clamp to prevent integer overflow in OpenCV
        limit = 30000
        sx = max(-limit, min(limit, sx))
        sy = max(-limit, min(limit, sy))
        
        return (sx, sy)

    def _world_to_screen(self, x, y):
        """Compatibility wrapper for _project_3d (z=0)"""
        return self._project_3d(x, y, 0)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop)
        self.thread.start()
        logger.info("Simulated camera started")

    def update_physics_params(self, params):
        changes = []
        cam_changed = False
        if 'table_tilt' in params:
            val = float(params['table_tilt'])
            if val != self.table_tilt:
                self.table_tilt = val
                # Calculate gravity based on tilt
                # Base gravity ~ 25000 px/s^2 (to give ~2500 at 6 degrees)
                BASE_GRAVITY = 25000.0
                gravity_val = BASE_GRAVITY * np.sin(np.radians(self.table_tilt))
                
                self.gravity = gravity_val
                if self.physics_engine:
                    self.physics_engine.space.gravity = (0.0, gravity_val)
                changes.append(f"Table Tilt: {val}° (Gravity: {gravity_val:.1f})")

        if 'friction' in params:
            val = float(params['friction'])
            if val != self.friction:
                self.friction = val
                if self.physics_engine:
                    # Update all shapes
                    for shape in self.physics_engine.space.shapes:
                        shape.friction = val
                changes.append(f"Friction: {val}")
        if 'restitution' in params:
            val = float(params['restitution'])
            if val != self.restitution:
                self.restitution = val
                if self.physics_engine:
                    # Update all shapes
                    for shape in self.physics_engine.space.shapes:
                        shape.elasticity = val
                changes.append(f"Restitution: {val}")
        if 'flipper_speed' in params:
            val = float(params['flipper_speed'])
            if val != self.flipper_speed:
                self.flipper_speed = val
                if self.physics_engine:
                    self.physics_engine.flipper_speed = val
                changes.append(f"Flipper Speed: {val}")
            
        if 'flipper_resting_angle' in params:
            self.flipper_resting_angle = float(params['flipper_resting_angle'])
            if self.physics_engine:
                self.physics_engine.flipper_resting_angle = self.flipper_resting_angle
        if 'flipper_stroke_angle' in params:
            self.flipper_stroke_angle = float(params['flipper_stroke_angle'])
            if self.physics_engine:
                self.physics_engine.flipper_stroke_angle = self.flipper_stroke_angle
            
        if 'flipper_length' in params:
            val = float(params['flipper_length'])
            if val != self.flipper_length:
                self.flipper_length = val
                self._update_flipper_rects()
                if self.physics_engine:
                    self.physics_engine.update_flipper_length(val)
                changes.append(f"Flipper Length: {val}")

        if 'flipper_width' in params:
            val = float(params['flipper_width'])
            if val != self.flipper_width:
                self.flipper_width = val
                changes.append(f"Flipper Width: {val}")
            # Always update physics engine to ensure it has the correct value
            if self.physics_engine:
                self.physics_engine.update_flipper_width(val)
                
        if 'tilt_threshold' in params:
            val = float(params['tilt_threshold'])
            if val != self.tilt_threshold:
                self.tilt_threshold = val
                changes.append(f"Tilt Threshold: {val}")
        if 'nudge_cost' in params:
            val = float(params['nudge_cost'])
            if val != self.nudge_cost:
                self.nudge_cost = val
                changes.append(f"Nudge Cost: {val}")
        if 'tilt_decay' in params:
            val = float(params['tilt_decay'])
            if val != self.tilt_decay:
                self.tilt_decay = val
                changes.append(f"Tilt Decay: {val}")
        if 'tilt_decay' in params:
            val = float(params['tilt_decay'])
            if val != self.tilt_decay:
                self.tilt_decay = val
                changes.append(f"Tilt Decay: {val}")

        if 'plunger_release_speed' in params:
            val = float(params['plunger_release_speed'])
            if val != self.plunger_release_speed:
                self.plunger_release_speed = val
                if self.physics_engine:
                    self.physics_engine.plunger_release_speed = val
                changes.append(f"Plunger Speed: {val}")
        if 'launch_angle' in params:
            val = float(params['launch_angle'])
            if val != self.launch_angle:
                self.launch_angle = val
                if self.physics_engine:
                    self.physics_engine.launch_angle = val
                changes.append(f"Launch Angle: {val}°")
        if 'camera_pitch' in params:
            val = float(params['camera_pitch'])
            # Convert degrees to radians for internal use if needed, but self.pitch seems to be radians in _project_3d
            # Let's assume input is degrees for UI friendliness
            rad_val = np.radians(val)
            if rad_val != self.pitch:
                self.pitch = rad_val
                changes.append(f"Camera Pitch: {val}°")

        if 'camera_y' in params:
            val = float(params['camera_y'])
            # Input is likely a multiplier or offset. self.cam_y was initialized as height * 1.5
            # Let's treat input as the raw Y value for now, or a multiplier relative to height?
            # Let's treat it as a multiplier of height to keep it responsive
            new_y = self.height * val
            if new_y != self.cam_y:
                self.cam_y = new_y
                changes.append(f"Camera Y: {val}x")

        if 'camera_x' in params:
            val = float(params['camera_x'])
            new_x = self.width * val
            if new_x != self.cam_x:
                self.cam_x = new_x
                changes.append(f"Camera X: {val}x")
                cam_changed = True

        if 'camera_z' in params:
            val = float(params['camera_z'])
            new_z = self.width * val
            if new_z != self.cam_z:
                self.cam_z = new_z
                changes.append(f"Camera Z: {val}x")
                cam_changed = True

        if 'camera_zoom' in params:
            val = float(params['camera_zoom'])
            # Treat as multiplier of base focal length (width * 1.2)
            new_focal = (self.width * 1.2) * val
            if new_focal != self.focal_length:
                self.focal_length = new_focal
                changes.append(f"Camera Zoom: {val}x")
                cam_changed = True
                
        if cam_changed:
            self._update_zone_contours()

        # Flipper Zone Layout Params
        zone_changed = False
        
        # Flipper Physical Position (Translation)
        flipper_moved = False
        
        # Left Flipper Translation
        if 'left_flipper_pos_x' in params:
            new_x = float(params['left_flipper_pos_x'])
            if abs(new_x - self.layout.left_flipper_x_min) > 0.0001:
                width = self.layout.left_flipper_x_max - self.layout.left_flipper_x_min
                self.layout.left_flipper_x_min = new_x
                self.layout.left_flipper_x_max = new_x + width
                flipper_moved = True
            
        if 'left_flipper_pos_y' in params:
            new_y = float(params['left_flipper_pos_y'])
            if abs(new_y - self.layout.left_flipper_y_min) > 0.0001:
                height = self.layout.left_flipper_y_max - self.layout.left_flipper_y_min
                self.layout.left_flipper_y_min = new_y
                self.layout.left_flipper_y_max = new_y + height
                flipper_moved = True

        # Right Flipper Translation
        if 'right_flipper_pos_x' in params:
            new_x = float(params['right_flipper_pos_x'])
            if abs(new_x - self.layout.right_flipper_x_min) > 0.0001:
                width = self.layout.right_flipper_x_max - self.layout.right_flipper_x_min
                self.layout.right_flipper_x_min = new_x
                self.layout.right_flipper_x_max = new_x + width
                flipper_moved = True
            
        if 'right_flipper_pos_y' in params:
            new_y = float(params['right_flipper_pos_y'])
            if abs(new_y - self.layout.right_flipper_y_min) > 0.0001:
                height = self.layout.right_flipper_y_max - self.layout.right_flipper_y_min
                self.layout.right_flipper_y_min = new_y
                self.layout.right_flipper_y_max = new_y + height
                flipper_moved = True
                
        if flipper_moved:
            self._update_flipper_rects()
            # Rebuild flippers in physics engine
            if self.physics_engine:
                self.physics_engine._rebuild_flippers()
            # If zones are relative to flippers, we might want to update them too?
            # But we just decoupled them. So let's keep them independent as requested.
            # However, if we move the flipper significantly, the zone might need manual adjustment.
            changes.append("Flipper Position Updated")

        # Rail Parameters
        rail_changed = False
        if 'guide_thickness' in params:  # Frontend still uses 'guide_thickness'
            val = float(params['guide_thickness'])
            self.rail_thickness = val
            rail_changed = True
            changes.append(f"Rail Thickness: {val}")
            
        if 'guide_length_scale' in params:
            val = float(params['guide_length_scale'])
            self.rail_length_scale = val
            rail_changed = True
            changes.append(f"Rail Length: {val}")
            
        if 'guide_angle_offset' in params:
            val = float(params['guide_angle_offset'])
            self.rail_angle_offset = val
            rail_changed = True
            changes.append(f"Rail Angle: {val}°")
            
        if rail_changed and self.physics_engine:
            self.physics_engine.update_rail_params(self.rail_thickness, self.rail_length_scale, self.rail_angle_offset)

        # Rail endpoint parameters - update layout rails directly
        rail_endpoint_changed = False
        endpoint_params = [
            ('rail_left_p1_x', 0, 'p1', 'x'),
            ('rail_left_p1_y', 0, 'p1', 'y'),
            ('rail_left_p2_x', 0, 'p2', 'x'),
            ('rail_left_p2_y', 0, 'p2', 'y'),
            ('rail_right_p1_x', 1, 'p1', 'x'),
            ('rail_right_p1_y', 1, 'p1', 'y'),
            ('rail_right_p2_x', 1, 'p2', 'x'),
            ('rail_right_p2_y', 1, 'p2', 'y'),
        ]
        
        for param_name, rail_idx, point, coord in endpoint_params:
            if param_name in params:
                val = float(params[param_name])
                setattr(self, param_name, val)
                # Update layout rails
                if hasattr(self.layout, 'rails') and len(self.layout.rails) > rail_idx:
                    self.layout.rails[rail_idx][point][coord] = val
                rail_endpoint_changed = True
                changes.append(f"Rail {rail_idx} {point}.{coord}: {val:.2f}")
        
        if rail_endpoint_changed and self.physics_engine:
            # Rebuild rails with new base positions
            self.physics_engine._rebuild_rails()

        # Rail translation offsets - shift both rails
        offset_changed = False
        if 'rail_x_offset' in params:
            val = float(params['rail_x_offset'])
            self.rail_x_offset = val
            if self.layout:
                self.layout.rail_x_offset = val
            offset_changed = True
            changes.append(f"Rail X Offset: {val:.2f}")
            
        if 'rail_y_offset' in params:
            val = float(params['rail_y_offset'])
            self.rail_y_offset = val
            if self.layout:
                self.layout.rail_y_offset = val
            offset_changed = True
            changes.append(f"Rail Y Offset: {val:.2f}")
            
        if offset_changed and self.physics_engine:
            self.physics_engine.rail_x_offset = self.rail_x_offset
            self.physics_engine.rail_y_offset = self.rail_y_offset
            self.physics_engine._rebuild_rails()

        # Zones are now updated via update_zones, not physics params
        
        if 'show_rail_debug' in params:
            val = bool(params['show_rail_debug'])
            if val != self.show_rail_debug:
                self.show_rail_debug = val
                changes.append(f"Rail Debug: {'On' if val else 'Off'}")

        if changes:
            logger.info(f"Physics/Camera updated: {', '.join(changes)}")
            
            # Update layout physics params
            # We only want to store physics params, not camera params (unless we want camera per layout too?)
            # User said "Ball Physics". Usually camera is global or preset-based.
            # But let's save everything that is in 'params' to be safe, or filter?
            # The params dict comes from the UI update.
            # Let's merge into self.layout.physics_params
            if self.layout:
                if not hasattr(self.layout, 'physics_params'):
                    self.layout.physics_params = {}
                
                # Filter for physics-related keys to avoid cluttering with camera if not desired
                # But user might want camera per layout too.
                # Let's save all valid params that were passed and processed.
                # We can just update with 'params' but 'params' might have extra stuff.
                # Let's construct a dict of current physics state to save.
                
                # Actually, simpler: Just update self.layout.physics_params with the keys that changed.
                # But we need the VALUES.
                # We have the current values in self.gravity, etc.
                
                physics_keys = [
                    'gravity', 'friction', 'restitution', 'flipper_speed', 
                    'flipper_resting_angle', 'flipper_stroke_angle', 'flipper_length',
                    'plunger_release_speed', 'launch_angle', 'tilt_threshold', 
                    'nudge_cost', 'tilt_decay'
                ]
                
                for key in physics_keys:
                    if hasattr(self, key):
                        self.layout.physics_params[key] = getattr(self, key)
                
                self.save_layout()

            self.save_config()
            
            # Record settings change in history
            self.game_history.insert(0, {
                'type': 'settings_change',
                'settings': changes,
                'timestamp': time.time(),
                'date': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            # Keep history limited
            if len(self.game_history) > 50:
                self.game_history.pop()

    def _update_zone_contours(self):
        if not self.zone_manager: return
        
        contours = []
        for zone in self.layout.zones:
            pts = []
            for p in zone['points']:
                # p['x'], p['y'] are normalized coords (0-1)
                
                if zone.get('is_screen_space', False):
                    # Screen Space: Just scale to width/height
                    sx = p['x'] * self.width
                    sy = p['y'] * self.height
                else:
                    # Table Space: Project to Screen Space
                    wx = p['x'] * self.width
                    wy = p['y'] * self.height
                    sx, sy = self._project_3d(wx, wy, 0) 
                
                pts.append([int(sx), int(sy)])
            
            contours.append({
                'type': zone['type'],
                'cnt': np.array(pts, dtype=np.int32)
            })
            
        self.zone_manager.set_contours(contours)
        
    def update_zones(self, zones_data):
        """Update zone configuration from frontend."""
        # Update layout zones
        # Tag as Screen Space since they come from frontend (VideoFeed)
        for zone in zones_data:
            zone['is_screen_space'] = True
            
        self.layout.zones = zones_data
        # Update contours in ZoneManager
        self._update_zone_contours()

    def reset_zones(self):
        """Reset zones to default configuration."""
        if self.layout:
            self.layout.reset_zones()
            # Sync ZoneManager with reset layout
            if self.zone_manager:
                self.zone_manager.zones = self.layout.zones
            logger.info("Sim: Zones reset to default")

    def get_config(self):
        config = {
            'table_tilt': self.table_tilt,
            'gravity': self.gravity,
            'friction': self.friction,
            'restitution': self.restitution,
            'flipper_speed': self.flipper_speed,
            'flipper_resting_angle': self.flipper_resting_angle,
            'flipper_stroke_angle': self.flipper_stroke_angle,
            'flipper_length': self.flipper_length,
            'flipper_resting_angle': self.flipper_resting_angle,
            'flipper_stroke_angle': self.flipper_stroke_angle,
            'flipper_length': self.flipper_length,
            'flipper_width': self.flipper_width,
            'plunger_release_speed': self.plunger_release_speed,
            'plunger_release_speed': self.plunger_release_speed,
            'launch_angle': self.launch_angle,
            'tilt_threshold': self.tilt_threshold,
            'nudge_cost': self.nudge_cost,
            'tilt_decay': self.tilt_decay,
            'camera_pitch': np.degrees(self.pitch), # Save as degrees
            'camera_x': self.cam_x / self.width,
            'camera_y': self.cam_y / self.height,
            'camera_z': self.cam_z / self.width,
            'camera_zoom': self.focal_length / (self.width * 1.2), # Save as multiplier
            'left_flipper_pos_x': self.layout.left_flipper_x_min,
            'left_flipper_pos_x_max': self.layout.left_flipper_x_max,
            'left_flipper_pos_y': self.layout.left_flipper_y_min,
            'left_flipper_pos_y_max': self.layout.left_flipper_y_max,
            'right_flipper_pos_x': self.layout.right_flipper_x_min,
            'right_flipper_pos_x_max': self.layout.right_flipper_x_max,
            'right_flipper_pos_y': self.layout.right_flipper_y_min,
            'right_flipper_pos_y_max': self.layout.right_flipper_y_max,
            'camera_presets': self.camera_presets,
            'last_model': getattr(self, 'last_model', None),
            'last_preset': getattr(self, 'last_preset', None),
            'zones': self.layout.zones,
            # Layout Features
            'bumpers': self.layout.bumpers,
            'drop_targets': self.layout.drop_targets,
            'ramps': self.layout.ramps,
            'teleports': self.layout.teleports,
            'upper_deck': self.layout.upper_deck,
            'upper_flippers': self.layout.upper_flippers,
            'rails': self.layout.rails,
            'rail_x_offset': self.rail_x_offset,
            'rail_y_offset': self.rail_y_offset
        }
        
        return config

    def save_config(self, filepath="config.json"):
        config = self.get_config()
        try:
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info(f"Physics config saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def load_config(self, filepath="config.json"):
        if not os.path.exists(filepath):
            logger.info("Config file not found, returning current (default) config")
            return self.get_config()
        
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            self.update_physics_params(config)
            if 'last_model' in config:
                self.last_model = config['last_model']
            if 'last_preset' in config:
                self.last_preset = config['last_preset']
            if 'current_layout_id' in config:
                self.current_layout_id = config['current_layout_id']
            if 'camera_presets' in config:
                # Merge loaded presets into existing (default) presets
                self.camera_presets.update(config['camera_presets'])
            
            # Load layout configuration
            if self.layout:
                self.layout.load(config)
                # Ensure zones are updated (projected) after loading layout
                self._update_zone_contours()
            
            # Return full config (including layout)
            return self.get_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def reset_to_defaults(self):
        # ... (existing reset logic, maybe update to include camera defaults if needed)
        pass

    def save_camera_preset(self, name):
        preset = {
            "camera_pitch": np.degrees(self.pitch),
            "camera_x": self.cam_x / self.width,
            "camera_y": self.cam_y / self.height,
            "camera_z": self.cam_z / self.width,
            "camera_zoom": self.focal_length / (self.width * 1.2)
        }
        self.camera_presets[name] = preset
        self.save_config()
        return self.camera_presets

    def delete_camera_preset(self, name):
        if name in self.camera_presets:
            del self.camera_presets[name]
            self.save_config()
        return self.camera_presets
        """Reset all physics parameters to class constants and save."""
        self.gravity = self.GRAVITY
        self.friction = self.FRICTION
        self.restitution = self.RESTITUTION
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_length = self.FLIPPER_LENGTH
        self.flipper_width = self.FLIPPER_WIDTH
        self.flipper_resting_angle = self.LEFT_DOWN_ANGLE
        self.flipper_resting_angle = self.LEFT_DOWN_ANGLE
        self.flipper_stroke_angle = self.LEFT_UP_ANGLE - self.LEFT_DOWN_ANGLE # 20 - (-30) = 50
        
        self.tilt_threshold = self.TILT_THRESHOLD
        self.nudge_cost = self.NUDGE_COST
        self.tilt_decay = self.TILT_DECAY
        
        self._update_flipper_rects()
        logger.info("Physics parameters reset to defaults")
        
        # Save the defaults
        self.save_config()
        
        return {
            'gravity': self.gravity,
            'friction': self.friction,
            'restitution': self.restitution,
            'flipper_speed': self.flipper_speed,
            'flipper_resting_angle': self.flipper_resting_angle,
            'flipper_stroke_angle': self.flipper_stroke_angle,
            'flipper_resting_angle': self.flipper_resting_angle,
            'flipper_stroke_angle': self.flipper_stroke_angle,
            'flipper_length': self.flipper_length,
            'flipper_width': self.flipper_width,
            'tilt_threshold': self.tilt_threshold,
            'tilt_threshold': self.tilt_threshold,
            'nudge_cost': self.nudge_cost,
            'tilt_decay': self.tilt_decay
        }

    def load_layout(self, layout_source):
        """Load a new table layout from a dictionary or name."""
        with self.lock:
            if isinstance(layout_source, str):
                if layout_source not in self.available_layouts:
                    logger.error(f"Layout '{layout_source}' not found!")
                    return False
                layout_config = self.available_layouts[layout_source]
                logger.info(f"Loading layout from name: {layout_source}")
            else:
                layout_config = layout_source
                
            self.layout.load(layout_config)
            
            # Re-initialize components dependent on layout
            self.zone_manager = ZoneManager(self.width, self.height, self.layout)
            self._update_zone_contours()
            
            # Start simulation thread
            self.running = True
            # Re-init bumpers
            self.bumpers = []
            for b in self.layout.bumpers:
                self.bumpers.append({
                    'pos': np.array([self.width * b['x'], self.height * b['y']]),
                    'radius': int(self.width * b['radius_ratio']),
                    'value': b['value']
                })
                
            # Re-init drop targets
            self.drop_target_states = [True] * len(self.layout.drop_targets)
            
            # ReInitialize physics engine with new layout
            if self.physics_engine:
                from pbwizard.physics import PymunkEngine
                self.physics_engine = PymunkEngine(self.layout, self.width, self.height)
                
                # Sync rail offsets from layout to simulation instance
                self.rail_x_offset = getattr(self.layout, 'rail_x_offset', -0.61)
                self.rail_y_offset = getattr(self.layout, 'rail_y_offset', -0.11)
                self.physics_engine.rail_x_offset = self.rail_x_offset
                self.physics_engine.rail_y_offset = self.rail_y_offset
                
                logger.info(f"Physics engine reinitialized with new layout. Rail Offsets: {self.rail_x_offset}, {self.rail_y_offset}")
            
            # Reset game state
            self.score = 0
            self.balls = []
            self.tilt_value = 0.0
            self.is_tilted = False
            logger.info("Layout loaded and simulation reset")
            
            # Record layout change in history
            self.game_history.insert(0, {
                'type': 'layout_change',
                'layout': self.layout.name,
                'timestamp': time.time(),
                'date': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            # Keep history limited
            if len(self.game_history) > 50:
                self.game_history.pop()
                
            self.save_config() # Persist new layout to config.json
            
            # Apply layout physics if present
            if hasattr(self.layout, 'physics_params') and self.layout.physics_params:
                logger.info(f"Applying physics from layout: {self.layout.physics_params}")
                self.update_physics_params(self.layout.physics_params)
                
            return True

    def save_layout(self):
        """Save the current layout to its file."""
        if self.layout and self.layout.name:
            # Sanitize name to create filename (snake_case preference)
            # If we loaded from a file, we might want to preserve that filename
            # But here we construct it from the name
            safe_name = self.layout.name.lower().replace(' ', '_')
            safe_name = "".join([c for c in safe_name if c.isalnum() or c == '_'])
            
            filename = f"{safe_name}.json"
            filepath = os.path.join(os.getcwd(), 'layouts', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            self.layout.save_to_file(filepath)
            
            # Update available_layouts with new data
            self.available_layouts[safe_name] = self.layout.to_dict()
            
            logger.info(f"Layout saved to {filepath}")

    def launch_ball(self):
        with self.lock:
            # 1. Try to launch existing ball in plunger lane
            if self.physics_engine.launch_plunger():
                logger.info("Sim: Ball Launched from Plunger")
                return

            # 2. If no ball in plunger, and we can add one (e.g. game start or drained)
            # For now, just add one if total balls < MAX
            if len(self.balls) < self.MAX_BALLS:
                if len(self.balls) == 0:
                    # Check if we have balls remaining
                    if self.balls_remaining > 0:
                         self.balls_remaining -= 1
                         logger.debug(f"Sim: Ball {1 - self.balls_remaining} of 1")
                    else:
                        # Game Over Logic - just reset for new game
                        logger.debug(f"Sim: Game Over (Score: {self.score})")
                        
                        # Record Game History
                        self.game_history.insert(0, {
                            'type': 'game',
                            'score': self.score,
                            'timestamp': time.time(),
                            'date': time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        if len(self.game_history) > 50:
                            self.game_history.pop()
                        
                        # Reset Score
                        self.score = 0
                        self.balls_remaining = 3 # Reset balls
                        pass
                
                # Spawn ball in plunger lane
                ball_x = 0.9 * self.width
                ball_y = 0.9 * self.height
                self.physics_engine.add_ball((ball_x, ball_y))
                logger.debug(f"Sim: Ball spawned in plunger lane ({ball_x}, {ball_y})")
                
            else:
                logger.info("Sim: Max balls reached, cannot add more")


    def add_ball(self):
        if len(self.balls) >= self.MAX_BALLS:
            logger.warning(f"Sim: Max balls ({self.MAX_BALLS}) reached, cannot add more.")
            return

        # Add ball to plunger lane (approx 0.9 width, 0.9 height)
        # Physics engine expects pixels
        lane_x = self.width * 0.9
        lane_y = self.height * 0.9
        pos = (lane_x, lane_y)
        
        self.physics_engine.add_ball(pos)
        
        # Sync local balls list (optional, but good for consistency check)
        # Actually, self.balls in vision.py is overwritten by physics state in simulation_loop
        # So we don't need to manually append here if the loop picks it up.
        # But let's append a placeholder to increment count immediately?
        # No, let the loop handle it.
        
        logger.debug(f"Sim: Ball Added to Physics Engine at {pos}")

    @property
    def left_flipper_active(self):
        return self._left_flipper_inputs > 0

    @property
    def right_flipper_active(self):
        return self._right_flipper_inputs > 0

    def trigger_left(self):
        self._left_flipper_inputs += 1
        if self.physics_engine:
            self.physics_engine.actuate_flipper('left', True)

    def release_left(self):
        self._left_flipper_inputs = 0 # Force reset to prevent sticking
        if self.physics_engine:
            self.physics_engine.actuate_flipper('left', False)

    def trigger_right(self):
        self._right_flipper_inputs += 1
        if self.physics_engine:
            self.physics_engine.actuate_flipper('right', True)

    def release_right(self):
        self._right_flipper_inputs = 0 # Force reset to prevent sticking
        if self.physics_engine:
            self.physics_engine.actuate_flipper('right', False)

    def nudge(self, dx, dy):
        """Apply a sudden velocity change to all balls (simulate tilt)."""
        with self.lock:
            if self.is_tilted:
                return

            # Accumulate Tilt
            self.tilt_value += self.nudge_cost
            logger.info(f"Nudge! Tilt Value: {self.tilt_value:.2f} / {self.tilt_threshold:.2f} (Cost: {self.nudge_cost:.2f})")
            if self.tilt_value > self.tilt_threshold:
                self.is_tilted = True
                logger.info("TILT! Game Over for this ball.")
                if self.physics_engine:
                    self.physics_engine.set_tilt(True)
            
            # Delegate nudge to physics engine
            if self.physics_engine:
                self.physics_engine.nudge(dx, dy)
            
            # Record nudge for UI visualization
            self.last_nudge = {
                'time': time.time(),
                'direction': 'left' if dx < 0 else 'right'
            }
            logger.debug(f"Sim: Nudge applied ({dx}, {dy})")

    def nudge_left(self):
        if self.physics_engine:
            self.physics_engine.nudge(-5.0, -2.0)
            
        # Record nudge for UI visualization
        self.last_nudge = {
            'time': time.time(),
            'direction': 'left'
        }

    def nudge_right(self):
        if self.physics_engine:
            self.physics_engine.nudge(5.0, -2.0)
            
        # Record nudge for UI visualization
        self.last_nudge = {
            'time': time.time(),
            'direction': 'right'
        }

    def pull_plunger(self, strength=1.0):
        if self.physics_engine:
            # Auto-load ball if none exist
            if len(self.physics_engine.balls) == 0:
                self.add_ball()
            self.physics_engine.pull_plunger(strength)

    def release_plunger(self):
        if self.physics_engine:
            self.physics_engine.release_plunger()

    def _get_flipper_line_from_angle(self, rect, angle, side):
        # Calculate flipper line segment from a specific angle
        if side == 'left':
            pivot = np.array([rect[0], rect[3]]) # Bottom-left
            length = rect[2] - rect[0]
            rad = np.radians(angle)
            # Use +sin for Left Flipper because +Angle is Down (Positive Y)
            end = pivot + np.array([length * np.cos(rad), length * np.sin(rad)])
        else: # right
            pivot = np.array([rect[2], rect[3]]) # Bottom-right
            length = rect[2] - rect[0]
            rad = np.radians(angle)
            end = pivot + np.array([length * np.cos(rad), -length * np.sin(rad)])
            
        return pivot, end

    def _segment_intersects_segment(self, p1, p2, q1, q2):
        s1 = p2 - p1
        s2 = q2 - q1
        
        denom = -s2[0] * s1[1] + s1[0] * s2[1]
        if denom == 0: return None # Parallel
        
        s = (-s1[1] * (p1[0] - q1[0]) + s1[0] * (p1[1] - q1[1])) / denom
        t = ( s2[0] * (p1[1] - q1[1]) - s2[1] * (p1[0] - q1[0])) / denom
        
        if s >= 0 and s <= 1 and t >= 0 and t <= 1:
            return p1 + (t * s1)
        return None

    def _check_line_collision(self, ball, p1, p2, active, pivot=None, prev_pos=None, thickness=0):
        if ball['lost']: return

        # Vector from p1 to p2
        line_vec = p2 - p1
        line_len = np.linalg.norm(line_vec)
        if line_len == 0: return
        line_unit = line_vec / line_len

        # 1. Standard Distance Check (Static)
        ball_vec = ball['pos'] - p1
        proj = np.dot(ball_vec, line_unit)
        closest_dist = np.clip(proj, 0, line_len)
        closest_point = p1 + closest_dist * line_unit
        dist_vec = ball['pos'] - closest_point
        dist = np.linalg.norm(dist_vec)
        
        collision_detected = False
        normal = np.array([0, -1])
        
        # Check collision with thickness
        effective_radius = self.ball_radius + (thickness / 2.0)
        
        if dist < effective_radius:
            collision_detected = True
            if dist > 0:
                normal = dist_vec / dist
        
        # 2. Continuous Collision Detection (CCD) - Dynamic
        if not collision_detected and prev_pos is not None:
            intersect = self._segment_intersects_segment(prev_pos, ball['pos'], p1, p2)
            if intersect is not None:
                collision_detected = True
                closest_point = intersect
                normal = np.array([-line_unit[1], line_unit[0]])
                if np.dot(prev_pos - closest_point, normal) < 0:
                    normal = -normal
                
                ball['pos'] = intersect + normal * effective_radius * 1.01
                dist = effective_radius

        if collision_detected:
            # Reflect velocity
            v_dot_n = np.dot(ball['vel'], normal)
            v_normal = v_dot_n * normal
            v_tangent = ball['vel'] - v_normal
            
            v_normal = -v_normal * self.restitution # Restitution
            v_tangent = v_tangent * self.friction # Friction
            
            ball['vel'] = v_normal + v_tangent
            
            # Push out
            overlap = effective_radius - dist
            if overlap > 0:
                ball['pos'] += normal * overlap * 1.1

            # Add energy if flipper is active
            if active and pivot is not None:
                impact_dist = np.linalg.norm(closest_point - pivot)
                boost_mag = 10 + (impact_dist * 0.15) 
                ball['vel'] += normal * boost_mag
                ball['vel'][0] += np.random.uniform(-1, 1)

    def _check_bumper_collision(self, ball):
        if ball['lost']: return
        
        for bumper in self.bumpers:
            dist = np.linalg.norm(ball['pos'] - bumper['pos'])
            if dist < self.ball_radius + bumper['radius']:
                self.score += bumper['value']
                
                normal = (ball['pos'] - bumper['pos']) / dist
                ball['vel'] = ball['vel'] - 2 * np.dot(ball['vel'], normal) * normal
                ball['vel'] *= 1.05
                
                speed = np.linalg.norm(ball['vel'])
                if speed > 25.0:
                    ball['vel'] = (ball['vel'] / speed) * 25.0
                
                overlap = (self.ball_radius + bumper['radius']) - dist
                ball['pos'] += normal * overlap

    def _check_drop_target_collision(self, ball):
        if ball['lost']: return
        
        logger.debug(f"Checking drop target collision for ball at {ball['pos']}")
        
        for i, target in enumerate(self.layout.drop_targets):
            # Skip if already hit
            if i >= len(self.drop_target_states) or not self.drop_target_states[i]:
                continue
            
            # Layout x,y are TOP-LEFT corner (to match physics.py line 127-132)
            # Physics does: cx = x + w/2, cy = y + h/2
            # BUT there seems to be a coordinate mismatch - expand the box significantly
            tx = target['x'] * self.width
            ty = target['y'] * self.height
            tw, th = target['width'] * self.width, target['height'] * self.height
            
            # Calculate center from corner (matching physics)
            cx = tx + tw/2
            cy = ty + th/2
            
            bx, by = ball['pos']
            
            # TEMPORARY: Expand collision box by 5x to catch physics collisions
            # This is a workaround until we figure out the coordinate system mismatch
            expand_factor = 5.0
            tw_expanded = tw * expand_factor
            th_expanded = th * expand_factor
            
            logger.debug(f"  Target {i}: corner=({tx:.1f}, {ty:.1f}), center=({cx:.1f}, {cy:.1f}), size=({tw:.1f}x{th:.1f}), expanded=({tw_expanded:.1f}x{th_expanded:.1f}), ball=({bx:.1f}, {by:.1f})")
            
            if (bx > cx - tw_expanded/2 and bx < cx + tw_expanded/2 and
                by > cy - th_expanded/2 and by < cy + th_expanded/2):
                
                # Hit!
                self.drop_target_states[i] = False
                logger.debug(f"DROP TARGET {i} HIT! Ball pos: ({bx}, {by}), Target: ({tx}, {ty})")
                logger.debug(f"Drop Target States: {self.drop_target_states}")
                self.score += target['value']
                ball['vel'][1] *= -1 # Bounce back
                
                # Remove from physics engine if using physics
                if self.physics_engine and hasattr(self.physics_engine, 'drop_target_shapes'):
                    logger.debug(f"Physics engine has {len(self.physics_engine.drop_target_shapes)} drop target shapes")
                    if i < len(self.physics_engine.drop_target_shapes):
                        shape = self.physics_engine.drop_target_shapes[i]
                        if shape in self.physics_engine.space.shapes:
                            self.physics_engine.space.remove(shape)
                            logger.debug(f"✓ Removed drop target {i} shape from physics space")
                        else:
                            logger.warning(f"✗ Drop target {i} shape NOT in physics space (already removed?)")
                    else:
                        logger.error(f"✗ Drop target {i} index out of range for shapes list")
                else:
                    logger.warning("✗ Physics engine or drop_target_shapes not available")
                
                # Check if all targets hit
                if not any(self.drop_target_states):
                    logger.info("ALL DROP TARGETS DOWN!")
                    
                    # Check cooldown
                    if time.time() > self.multiball_cooldown_timer:
                        logger.debug("MULTIBALL ACTIVATED!")
                        self.add_ball()
                        self.multiball_cooldown_timer = time.time() + 5.0 # 5 second cooldown
                    else:
                        logger.info(f"Multiball cooldown active. Remaining: {self.multiball_cooldown_timer - time.time():.1f}s")
                    
                    # Reset targets - add them back to physics
                    self.drop_target_states = [True] * len(self.layout.drop_targets)
                    if self.physics_engine and hasattr(self.physics_engine, 'drop_target_shapes'):
                        for j, shape in enumerate(self.physics_engine.drop_target_shapes):
                            if shape not in self.physics_engine.space.shapes:
                                self.physics_engine.space.add(shape)
                                logger.debug(f"Re-added drop target {j} to physics space")

    def _check_capture_collision(self, ball):
        if ball['lost'] or ball.get('captured', False): return

        for capture in self.layout.captures:
            cx, cy = capture['x'] * self.width, capture['y'] * self.height
            radius = capture['radius'] * self.width
            
            dist = np.linalg.norm(ball['pos'] - np.array([cx, cy]))
            if dist < radius:
                # Capture the ball
                ball['captured'] = True
                ball['capture_timer'] = capture['hold_time']
                ball['pos'] = np.array([cx, cy], dtype=float)
                ball['vel'] = np.zeros(2, dtype=float)
                ball['capture_data'] = capture
                self.score += capture['value']
                logger.info(f"Ball captured! Holding for {capture['hold_time']}s")

    def _check_ramp_collision(self, ball):
        if ball['lost'] or ball.get('captured', False): return

        for ramp in self.layout.ramps:
            ex, ey = ramp['entry_x'] * self.width, ramp['entry_y'] * self.height
            ew = ramp['entry_width'] * self.width
            
            # Simple distance check to entry point
            dist = np.linalg.norm(ball['pos'] - np.array([ex, ey]))
            if dist < ew:
                # Enter ramp
                logger.info("Ramp entered!")
                # Teleport to exit
                exit_x, exit_y = ramp['exit_x'] * self.width, ramp['exit_y'] * self.height
                ball['pos'] = np.array([exit_x, exit_y], dtype=float)
                
                # Apply velocity boost in direction of exit (or keep current direction but boosted)
                speed = np.linalg.norm(ball['vel'])
                if speed > 0:
                    ball['vel'] = (ball['vel'] / speed) * (speed * ramp['boost'])
                else:
                    ball['vel'] = np.array([0, 10.0]) # Default eject velocity

    def _check_teleport_collision(self, ball):
        if ball['lost'] or ball.get('captured', False): return

        for teleport in self.layout.teleports:
            ex, ey = teleport['entry_x'] * self.width, teleport['entry_y'] * self.height
            radius = teleport['entry_radius'] * self.width
            
            dist = np.linalg.norm(ball['pos'] - np.array([ex, ey]))
            if dist < radius:
                # Teleport!
                logger.info("Teleport!")
                exit_x, exit_y = teleport['exit_x'] * self.width, teleport['exit_y'] * self.height
                ball['pos'] = np.array([exit_x, exit_y], dtype=float)

    def nudge_left(self):
        """Apply nudge force to the left."""
        if self.physics_engine:
            self.physics_engine.nudge(-self.nudge_cost, 0)
            self.last_nudge = {'time': time.time(), 'direction': 'left'}
            # Emit event for frontend animation
            if self.socketio:
                self.socketio.emit('stats_update', {'nudge': self.last_nudge})

    def nudge_right(self):
        """Apply nudge force to the right."""
        if self.physics_engine:
            self.physics_engine.nudge(self.nudge_cost, 0)
            self.last_nudge = {'time': time.time(), 'direction': 'right'}
            # Emit event for frontend animation
            if self.socketio:
                self.socketio.emit('stats_update', {'nudge': self.last_nudge})

    def _simulation_loop(self):
        dt = 1.0 / 60.0 # Fixed time step for 60 FPS physics 

        while self.running:
            with self.lock:
                # Remove lost balls
                self.balls = [b for b in self.balls if not b['lost']]
                
                # Decay Tilt
                if self.tilt_value > 0:
                    self.tilt_value = max(0, self.tilt_value - self.tilt_decay)
                    if self.tilt_value == 0 and self.is_tilted:
                        self.is_tilted = False
                        if self.physics_engine:
                            self.physics_engine.set_tilt(False)
                        logger.info("Tilt Recovered.")
                
                if not self.balls:
                    # Auto-start logic
                    if self.auto_start_enabled:
                        current_time = time.time()
                        if not hasattr(self, 'game_over_time') or self.game_over_time is None:
                            self.game_over_time = current_time
                        
                        # Wait 1 second before restart
                        if current_time - self.game_over_time > 1.0:
                            self.launch_ball()
                            # Simulate pull and release
                            self.pull_plunger(1.0)
                            # Schedule release? Or just release immediately?
                            # Immediate release might be too fast for physics step?
                            # Let's just release immediately for now, physics update will handle it
                            self.release_plunger()
                            self.game_over_time = None
                    else:
                        self.game_over_time = None
                    pass
                else:
                    self.game_over_time = None

                # Update Physics (Pymunk)
                if not self.physics_engine:
                    from pbwizard.physics import PymunkEngine
                    self.physics_engine = PymunkEngine(self.layout, self.width, self.height)
                    # Initial ball
                    self.physics_engine.add_ball((self.width * 0.9, self.height * 0.9))

                self.physics_engine.update(dt)
                
                # Sync score from physics engine
                if self.physics_engine.score != self.score:
                    logger.debug(f"Score sync: {self.score} -> {self.physics_engine.score}")
                self.score = self.physics_engine.score
                
            # Sync with Physics Engine
            state = self.physics_engine.get_state()
            logger.debug(f"Sync State Balls: {len(state['balls'])}")
            self.balls = []
            for b_data in state['balls']:
                # b_data is {'x': val, 'y': val, 'vx': val, 'vy': val} (Normalized)
                # We need to convert back to pixels for vision logic?
                # Wait, vision logic uses pixels.
                # physics.py get_state returns NORMALIZED coordinates (0-1).
                # But vision.py expects pixels for self.balls?
                # Let's check self.balls usage.
                # It uses pixels (e.g. self.width * 0.85).
                
                # So we need to denormalize.
                pos_x = b_data['x'] * self.width
                pos_y = b_data['y'] * self.height
                vel_x = b_data['vx']
                vel_y = b_data['vy']
                
                self.balls.append({
                    'pos': np.array([pos_x, pos_y]),
                    'vel': np.array([vel_x, vel_y]),
                    'lost': False 
                })
            
            # Sync flipper angles for 2D draw
            self.current_left_angle = state['flippers']['left_angle']
            self.current_right_angle = state['flippers']['right_angle']
            self.current_upper_angles = state['flippers']['upper_angles']

            # Check drop target collisions (vision system handles drop target state)
            logger.debug(f"VISION: About to check drop targets. Balls: {len(self.balls)}, Targets: {len(self.layout.drop_targets)}, States: {self.drop_target_states}")
            for ball in self.balls:
                self._check_drop_target_collision(ball)

            # Render frame once per simulation step
            self._draw_frame()
            
            # Sleep to control simulation rate
            if not self.headless:
                time.sleep(0.016) # ~60 FPS for local display
            else:
                time.sleep(0.001) # Yield for eventlet in headless mode

    def _update_flipper_angles(self, dt: float):
        # Calculate target angles based on resting + stroke
        # Left: Down = resting, Up = resting + stroke
        l_down = self.flipper_resting_angle
        l_up = self.flipper_resting_angle + self.flipper_stroke_angle
        
        # Right: Mirrored around 90 (vertical) or just 180 - angle?
        r_down = 180.0 - l_down
        r_up = 180.0 - l_up

        # Left Flipper
        # If tilted, force down
        target_left = l_down
        if not self.is_tilted and self.left_flipper_active:
            target_left = l_up
            
        # Debug Log
        if random.random() < 0.01:
             logger.info(f"Flipper Update: Active={self.left_flipper_active}, Target={target_left:.1f}, Current={self.current_left_angle:.1f}, Inputs={self._left_flipper_inputs}")

        if self.current_left_angle < target_left:
            self.current_left_angle = min(self.current_left_angle + self.flipper_speed * dt, target_left)
        elif self.current_left_angle > target_left:
            self.current_left_angle = max(self.current_left_angle - self.flipper_speed * dt, target_left)
            
        # Right Flipper
        # If tilted, force down
        target_right = r_down
        if not self.is_tilted and self.right_flipper_active:
            target_right = r_up
        
        if self.current_right_angle > target_right:
            self.current_right_angle = max(self.current_right_angle - self.flipper_speed * dt, target_right)
        elif self.current_right_angle < target_right:
            self.current_right_angle = min(self.current_right_angle + self.flipper_speed * dt, target_right)

        # Upper Flippers
        for i, uf in enumerate(self.layout.upper_flippers):
            # Determine target angle based on type and input
            if uf['type'] == 'left':
                resting = self.flipper_resting_angle
                stroke = self.flipper_stroke_angle
                target = resting
                if not self.is_tilted and self.left_flipper_active:
                    target = resting + stroke
            else: # right
                resting = 180.0 - self.flipper_resting_angle
                stroke = -self.flipper_stroke_angle # Stroke goes opposite way
                target = resting
                if not self.is_tilted and self.right_flipper_active:
                    target = resting + stroke
            
            # Update angle
            current = self.current_upper_angles[i]
            if current < target:
                self.current_upper_angles[i] = min(current + self.flipper_speed * dt, target)
            elif current > target:
                self.current_upper_angles[i] = max(current - self.flipper_speed * dt, target)

    def _handle_wall_collisions(self, ball):
        if ball['pos'][0] - self.ball_radius < 0:
            ball['pos'][0] = self.ball_radius
            ball['vel'][0] *= -0.8
        elif ball['pos'][0] + self.ball_radius > self.width:
            ball['pos'][0] = self.width - self.ball_radius
            ball['vel'][0] *= -0.8
            
        if ball['pos'][1] - self.ball_radius < 0:
            ball['pos'][1] = self.ball_radius
            ball['vel'][1] *= -0.8
        elif ball['pos'][1] + self.ball_radius > self.height:
            ball['lost'] = True
            logger.info(f"Sim: Ball Lost at {ball['pos']}")

    def _handle_flipper_collisions(self, ball, prev_pos):
        # Calculate targets for "moving up" check
        l_up = self.flipper_resting_angle + self.flipper_stroke_angle
        r_up = 180.0 - l_up
        
        # Left
        l_moving_up = self.left_flipper_active and (abs(self.current_left_angle - l_up) > 0.5)
        l_p1, l_p2 = self._get_flipper_line_from_angle(self.left_flipper_rect, self.current_left_angle, 'left')
        self._check_line_collision(ball, l_p1, l_p2, l_moving_up, pivot=l_p1, prev_pos=prev_pos, thickness=15)
        
        # Right
        r_moving_up = self.right_flipper_active and (abs(self.current_right_angle - r_up) > 0.5)
        r_p1, r_p2 = self._get_flipper_line_from_angle(self.right_flipper_rect, self.current_right_angle, 'right')
        self._check_line_collision(ball, r_p1, r_p2, r_moving_up, pivot=r_p1, prev_pos=prev_pos, thickness=15)

        # Upper Flippers
        for i, uf in enumerate(self.layout.upper_flippers):
            # Calculate rect on the fly (since they don't move base pos)
            # uf has x, y (normalized), length (normalized)
            # Need to convert to pixel rect [x, y, w, h] where w is length, h is thickness
            fx = uf['x'] * self.width
            fy = uf['y'] * self.height
            fl = uf['length'] * self.width
            fh = self.width * 0.02 # Thickness
            
            rect = [fx, fy, fl, fh]
            angle = self.current_upper_angles[i]
            
            # Determine moving_up status
            if uf['type'] == 'left':
                target_up = self.flipper_resting_angle + self.flipper_stroke_angle
                moving_up = self.left_flipper_active and (abs(angle - target_up) > 0.5)
            else:
                target_up = 180.0 - self.flipper_resting_angle - self.flipper_stroke_angle
                moving_up = self.right_flipper_active and (abs(angle - target_up) > 0.5)
            
            p1, p2 = self._get_flipper_line_from_angle(rect, angle, uf['type'])
            self._check_line_collision(ball, p1, p2, moving_up, pivot=p1, prev_pos=prev_pos, thickness=12)

    def _draw_capture(self, frame, capture):
        cx, cy = capture['x'] * self.width, capture['y'] * self.height
        radius = capture['radius'] * self.width
        
        # Project center and radius roughly
        center = self._project_3d(cx, cy, 0)
        # Estimate radius in screen space (using a point on the edge)
        edge = self._project_3d(cx + radius, cy, 0)
        screen_radius = int(np.linalg.norm(np.array(center) - np.array(edge)))
        
        # Draw Red Circle (Danger/Hold)
        cv2.circle(frame, center, screen_radius, (0, 0, 200), 2)
        cv2.circle(frame, center, screen_radius - 2, (0, 0, 100), -1) # Darker fill
        
        # Draw "C" or cross
        cv2.putText(frame, "C", (center[0] - 5, center[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    def _draw_ramp(self, frame, ramp):
        ex, ey = ramp['entry_x'] * self.width, ramp['entry_y'] * self.height
        xx, xy = ramp['exit_x'] * self.width, ramp['exit_y'] * self.height
        width = ramp['entry_width'] * self.width
        
        # Target elevation (match upper deck or default)
        target_elev = 15 
        if self.layout.upper_deck:
            target_elev = self.layout.upper_deck.get('elevation', 15)

        # Create ribbon points (Left and Right edges)
        steps = 10
        points_l = []
        points_r = []
        
        for i in range(steps + 1):
            t = i / steps
            # Interpolate position
            x = ex + (xx - ex) * t
            y = ey + (xy - ey) * t
            # Interpolate elevation (Quadratic ease-in for ramp shape?)
            # Linear for now
            z = target_elev * t
            
            # Calculate perpendicular vector for width
            dx, dy = xx - ex, xy - ey
            length = np.sqrt(dx*dx + dy*dy)
            nx, ny = -dy/length, dx/length
            
            lx = x - nx * width/2
            ly = y - ny * width/2
            rx = x + nx * width/2
            ry = y + ny * width/2
            
            points_l.append(self._project_3d(lx, ly, z))
            points_r.append(self._project_3d(rx, ry, z))
            
        # Draw Ribbon Segments
        for i in range(steps):
            # Surface
            cnt = np.array([points_l[i], points_r[i], points_r[i+1], points_l[i+1]], dtype=np.int32)
            cv2.fillPoly(frame, [cnt], (0, 200, 255)) # Yellow Surface
            cv2.polylines(frame, [cnt], True, (0, 150, 200), 1)
            
            # Sides (Thickness) - optional, but helps depth
            # Draw vertical lines down from edges? Or just rely on the ribbon
            
        # Draw Entry Gate
        p_left = points_l[0]
        p_right = points_r[0]
        cv2.line(frame, p_left, p_right, (0, 200, 200), 3)

    def _draw_teleport(self, frame, teleport):
        ex, ey = teleport['entry_x'] * self.width, teleport['entry_y'] * self.height
        radius = teleport['entry_radius'] * self.width
        
        center = self._project_3d(ex, ey, 0)
        edge = self._project_3d(ex + radius, ey, 0)
        screen_radius = int(np.linalg.norm(np.array(center) - np.array(edge)))
        
        # Stargate Style
        # Outer Ring (Grey)
        cv2.circle(frame, center, screen_radius, (100, 100, 100), 4)
        
        # Inner Event Horizon (Blue/Cyan filled)
        cv2.circle(frame, center, screen_radius - 2, (255, 100, 0), -1) # BGR: Blueish
        
        # Chevrons (Orange markers)
        for angle in range(0, 360, 45):
            rad = np.radians(angle)
            cx = int(center[0] + screen_radius * np.cos(rad))
            cy = int(center[1] + screen_radius * np.sin(rad))
            cv2.circle(frame, (cx, cy), 3, (0, 165, 255), -1) # Orange

    def get_game_state(self):
        """Returns the current state of the simulation for 3D rendering."""
        state = {
            'balls': [],
            'flippers': {
                'left_angle': self.current_left_angle,
                'right_angle': self.current_right_angle,
                'upper_angles': self.current_upper_angles
            },
            'drop_targets': self.drop_target_states,
            'bumper_states': self.physics_engine.bumper_states if self.physics_engine else [],
            'captures': [], # Could add capture status
            'score': self.score,
            'high_score': self.high_score,
            'games_played': self.games_played,
            'game_history': self.game_history,
            'balls_remaining': self.balls_remaining,
            'is_tilted': self.is_tilted,
            'nudge': self.last_nudge
        }
        
        for ball in self.balls:
            if not ball['lost']:
                # Normalize position (0-1)
                pos = ball['pos']
                vel = ball['vel']
                
                # Sanitize values
                x = float(pos[0]) / self.width
                y = float(pos[1]) / self.height
                vx = float(vel[0])
                vy = float(vel[1])
                
                if np.isnan(x) or np.isinf(x): x = 0.5
                if np.isnan(y) or np.isinf(y): y = 0.5
                if np.isnan(vx) or np.isinf(vx): vx = 0.0
                if np.isnan(vy) or np.isinf(vy): vy = 0.0
                
                state['balls'].append({
                    'x': x,
                    'y': y,
                    'vx': vx,
                    'vy': vy
                })

        # Add Plunger Data
        if self.physics_engine:
             if hasattr(self.physics_engine, 'plunger_body'):
                 state['plunger'] = {
                     'y': self.physics_engine.plunger_body.position.y,
                     'state': getattr(self.physics_engine, 'plunger_state', 'resting')
                 }
             if hasattr(self.physics_engine, 'left_plunger_body'):
                 state['left_plunger'] = {
                     'y': self.physics_engine.left_plunger_body.position.y,
                     'state': getattr(self.physics_engine, 'left_plunger_state', 'resting')
                 }
                 
                
        return state

    def _draw_frame(self):
        # logger.debug("Drawing frame v7")
        # Always render frames for web streaming, even if not displaying locally
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # --- 3D Rendering ---
        
        # 1. Draw Floor
        # Project 4 corners of the table
        # Extended playfield bottom to accommodate flipper rotation
        playfield_bottom = self.height * 1.15  # Extend 15% below normal height
        c1 = self._project_3d(0, 0, 0)
        c2 = self._project_3d(self.width, 0, 0)
        c3 = self._project_3d(self.width, playfield_bottom, 0)
        c4 = self._project_3d(0, playfield_bottom, 0)
        
        floor_cnt = np.array([c1, c2, c3, c4], dtype=np.int32)
        floor_cnt = np.array([c1, c2, c3, c4], dtype=np.int32)
        cv2.fillPoly(frame, [floor_cnt], (20, 20, 20)) # Dark Grey Floor
        
        
        # 1.5 Draw Upper Deck
        if self.layout.upper_deck:
            ud = self.layout.upper_deck
            ux, uy = ud['x'] * self.width, ud['y'] * self.height
            uw, uh = ud['width'] * self.width, ud['height'] * self.height
            elev = ud.get('elevation', 15)
            
            # Project corners at elevation (Top)
            u1 = self._project_3d(ux, uy, elev)
            u2 = self._project_3d(ux + uw, uy, elev)
            u3 = self._project_3d(ux + uw, uy + uh, elev)
            u4 = self._project_3d(ux, uy + uh, elev)
            
            # Project corners at floor (Base) for legs
            b1 = self._project_3d(ux, uy, 0)
            b2 = self._project_3d(ux + uw, uy, 0)
            b3 = self._project_3d(ux + uw, uy + uh, 0)
            b4 = self._project_3d(ux, uy + uh, 0)
            
            # Draw Solid Walls
            # Right Wall (u2-u3-b3-b2)
            wall_right = np.array([u2, u3, b3, b2], dtype=np.int32)
            cv2.fillPoly(frame, [wall_right], (60, 60, 100)) # Darker side
            cv2.polylines(frame, [wall_right], True, (100, 100, 150), 1)
            
            # Front Wall (u3-u4-b4-b3)
            wall_front = np.array([u3, u4, b4, b3], dtype=np.int32)
            cv2.fillPoly(frame, [wall_front], (70, 70, 120)) # Slightly lighter front
            cv2.polylines(frame, [wall_front], True, (100, 100, 150), 1)
            
            # Draw Deck Floor
            deck_cnt = np.array([u1, u2, u3, u4], dtype=np.int32)
            cv2.fillPoly(frame, [deck_cnt], (80, 80, 140)) # Much brighter blue-grey
            cv2.polylines(frame, [deck_cnt], True, (150, 150, 200), 2) # Brighter outline

        # Draw Plunger
        if self.physics_engine and hasattr(self.physics_engine, 'plunger_body'):
            pb = self.physics_engine.plunger_body
            ps = self.physics_engine.plunger_shape
            
            # Plunger is a box. Get corners.
            # Local corners
            # Shape is Poly.create_box(body, (w, h))
            # Vertices are relative to body position
            # We need to rotate/translate them manually or use pymunk helpers
            # Since it's axis aligned and doesn't rotate, we can just use pos +/- size/2
            
            px, py = pb.position
            pw = self.physics_engine.plunger_width
            ph = self.physics_engine.plunger_height
            
            # Top-Left, Top-Right, Bottom-Right, Bottom-Left
            # Pymunk Y is down? Yes.
            # Top is y - h/2?
            # Wait, create_box centers it.
            
            pl_x1 = px - pw/2
            pl_y1 = py - ph/2
            pl_x2 = px + pw/2
            pl_y2 = py + ph/2
            
            # Project to 3D
            # Plunger is at floor level? Or slightly elevated?
            # Let's say it has height 20 units
            pl_z = 20
            
            pc1 = self._project_3d(pl_x1, pl_y1, pl_z)
            pc2 = self._project_3d(pl_x2, pl_y1, pl_z)
            pc3 = self._project_3d(pl_x2, pl_y2, pl_z)
            pc4 = self._project_3d(pl_x1, pl_y2, pl_z)
            
            plunger_cnt = np.array([pc1, pc2, pc3, pc4], dtype=np.int32)
            cv2.fillPoly(frame, [plunger_cnt], (150, 150, 150)) # Light Grey
            cv2.polylines(frame, [plunger_cnt], True, (200, 200, 200), 2)

        # Draw Left Plunger (Kickback)
        if self.physics_engine and hasattr(self.physics_engine, 'left_plunger_body'):
            pb = self.physics_engine.left_plunger_body
            
            # Get corners relative to body position
            pw = self.physics_engine.left_plunger_width
            ph = self.physics_engine.left_plunger_height
            
            # Body pos is center
            bx, by = pb.position
            
            # Corners (Top-Left, Top-Right, Bottom-Right, Bottom-Left)
            # Y is down.
            c1 = (bx - pw/2, by - ph/2)
            c2 = (bx + pw/2, by - ph/2)
            c3 = (bx + pw/2, by + ph/2)
            c4 = (bx - pw/2, by + ph/2)
            
            # Transform to screen coords
            pc1 = self._project_3d(c1[0], c1[1], 0)
            pc2 = self._project_3d(c2[0], c2[1], 0)
            pc3 = self._project_3d(c3[0], c3[1], 0)
            pc4 = self._project_3d(c4[0], c4[1], 0)
            
            plunger_cnt = np.array([pc1, pc2, pc3, pc4], dtype=np.int32)
            cv2.fillPoly(frame, [plunger_cnt], (150, 150, 150)) # Light Grey
            cv2.polylines(frame, [plunger_cnt], True, (200, 200, 200), 2)

        # Draw Bumpers
        bumper_states = self.physics_engine.bumper_states if self.physics_engine else []
        for i, bumper in enumerate(self.bumpers):
            # Project center
            # bumper['pos'] is in pixels (width * ratio, height * ratio)
            # We need to project it to 3D
            bx, by = bumper['pos']
            bz = 15 # Elevation
            
            center = self._project_3d(bx, by, bz)
            base = self._project_3d(bx, by, 0)
            
            # Radius in screen space
            edge = self._project_3d(bx + bumper['radius'], by, bz)
            radius = int(np.linalg.norm(np.array(center) - np.array(edge)))
            
            # Draw Base (Cylinder side)
            cv2.circle(frame, base, radius, (50, 0, 50), -1)
            cv2.line(frame, center, base, (100, 0, 100), 2)
            
            # Draw Top
            if i < len(bumper_states) and bumper_states[i] > 0:
                # Active Flash (Cyan/White)
                cv2.circle(frame, center, radius, (255, 255, 0), -1)
                cv2.circle(frame, center, radius, (255, 255, 255), 2)
            else:
                # Inactive (Purple/Pink)
                cv2.circle(frame, center, radius, (200, 0, 200), -1)
                cv2.circle(frame, center, radius, (255, 100, 255), 2)
            
            # Draw "Pop" ring
            cv2.circle(frame, center, int(radius * 0.7), (255, 255, 255), 1)

        # Draw Grid
        for x in np.linspace(0, self.width, 11):
            p1 = self._project_3d(x, 0, 0)
            p2 = self._project_3d(x, playfield_bottom, 0)
            cv2.line(frame, p1, p2, (40, 40, 40), 1)
            
        for y in np.linspace(0, playfield_bottom, 21):
            p1 = self._project_3d(0, y, 0)
            p2 = self._project_3d(self.width, y, 0)
            cv2.line(frame, p1, p2, (40, 40, 40), 1)

        # Draw Drop Targets (only if active)
        for i, target in enumerate(self.layout.drop_targets):
            if i < len(self.drop_target_states) and self.drop_target_states[i]:
                tx, ty = target['x'] * self.width, target['y'] * self.height
                tw, th = target['width'] * self.width, target['height'] * self.height
                tz = 20  # Elevation
                
                # Calculate corners
                x1 = tx - tw/2
                x2 = tx + tw/2
                y1 = ty - th/2
                y2 = ty + th/2
                
                # Top Face
                t1 = self._project_3d(x1, y1, tz)
                t2 = self._project_3d(x2, y1, tz)
                t3 = self._project_3d(x2, y2, tz)
                t4 = self._project_3d(x1, y2, tz)
                
                top_cnt = np.array([t1, t2, t3, t4], dtype=np.int32)
                
                # Front Face (y2)
                b3 = self._project_3d(x2, y2, 0)
                b4 = self._project_3d(x1, y2, 0)
                front_cnt = np.array([t4, t3, b3, b4], dtype=np.int32)
                
                # Draw
                cv2.fillPoly(frame, [front_cnt], (0, 140, 255)) # Orange Side
                cv2.fillPoly(frame, [top_cnt], (0, 165, 255)) # Lighter Orange Top
                cv2.polylines(frame, [top_cnt], True, (255, 255, 255), 1)

        # Draw Advanced Features (Captures, Ramps, Teleports)
        for capture in self.layout.captures:
            self._draw_capture(frame, capture)
            
        for ramp in self.layout.ramps:
            self._draw_ramp(frame, ramp)
            
        for teleport in self.layout.teleports:
            self._draw_teleport(frame, teleport)
            
        # Draw Rails (apply parameters for visual consistency with physics)
        if hasattr(self.layout, 'rails'):
            for rail in self.layout.rails:
                p1_base = rail['p1']
                p2_base = rail['p2']
                
                # Apply length scale and angle offset (same as physics)
                p1_x = p1_base['x'] * self.width
                p1_y = p1_base['y'] * self.height
                p2_x = p2_base['x'] * self.width
                p2_y = p2_base['y'] * self.height
                
                dx = p1_x - p2_x
                dy = p1_y - p2_y
                length = np.sqrt(dx*dx + dy*dy)
                
                if length > 0:
                    scaled_length = length * self.rail_length_scale
                    ux = dx / length
                    uy = dy / length
                    p1_x_scaled = p2_x + ux * scaled_length
                    p1_y_scaled = p2_y + uy * scaled_length
                    
                    # Apply angle offset
                    if abs(self.rail_angle_offset) > 0.01:
                        angle_rad = np.radians(self.rail_angle_offset)
                        dx_new = p1_x_scaled - p2_x
                        dy_new = p1_y_scaled - p2_y
                        p1_x_final = p2_x + dx_new * np.cos(angle_rad) - dy_new * np.sin(angle_rad)
                        p1_y_final = p2_y + dx_new * np.sin(angle_rad) + dy_new * np.cos(angle_rad)
                    else:
                        p1_x_final = p1_x_scaled
                        p1_y_final = p1_y_scaled
                else:
                    p1_x_final = p1_x
                    p1_y_final = p1_y
                
                # Project to 3D
                start = self._project_3d(p1_x_final, p1_y_final, 0)
                end = self._project_3d(p2_x, p2_y, 0)
                
                # Draw with thickness parameter
                thickness = max(1, int(self.rail_thickness / 2))  # Scale down for visual
                cv2.line(frame, start, end, (200, 200, 200), thickness)
                
                # DEBUG: Draw the actual physics polygon vertices to see exact collision boundaries
                if self.physics_engine and hasattr(self.physics_engine, 'rail_shapes'):
                    for i, shape in enumerate(self.physics_engine.rail_shapes):
                        vertices = shape.get_vertices()
                        poly_points = []
                        for v in vertices:
                            world_v = v.rotated(shape.body.angle) + shape.body.position
                            screen_point = self._project_3d(world_v.x, world_v.y, 0)
                            poly_points.append(screen_point)
                        
                        if poly_points and self.show_rail_debug:
                            poly_array = np.array(poly_points, dtype=np.int32)
                            cv2.polylines(frame, [poly_array], True, (0, 255, 255), 2)  # Bright yellow outline
            
        # Draw Upper Flippers
        for i, uf in enumerate(self.layout.upper_flippers):
            fx = uf['x'] * self.width
            fy = uf['y'] * self.height
            fl = uf['length'] * self.width
            fh = self.width * 0.02
            rect = [fx, fy, fl, fh]
            angle = self.current_upper_angles[i]
            
            # Use elevation if on upper deck? 
            # For simplicity, draw at base elevation or assume they are "floating" correctly
            # Ideally we project them at 'elev' but _get_flipper_line_from_angle returns 2D points.
            # We can just draw them as lines for now.
            


# ... (Context match to locate thickness change)

        # 4. Draw Flippers (Prisms)
        flipper_height = 15
        for side, rect, angle in [('left', self.left_flipper_rect, self.current_left_angle), 
                                  ('right', self.right_flipper_rect, 180.0 - self.current_right_angle)]:
            p1, p2 = self._get_flipper_line_from_angle(rect, angle, side)
            
            # Thickness vector (perpendicular to flipper line)
            vec = p2 - p1
            length = np.linalg.norm(vec)
            if length > 0:
                perp = np.array([-vec[1], vec[0]]) / length * 5 # 5px width (Total 10px to match physics)
                
                # 4 corners of base
                c1 = p1 + perp
                c2 = p1 - perp
                c3 = p2 - perp
                c4 = p2 + perp
                
                # Project base and top
                poly_base = [self._project_3d(p[0], p[1], 0) for p in [c1, c2, c3, c4]]
                poly_top = [self._project_3d(p[0], p[1], flipper_height) for p in [c1, c2, c3, c4]]
                
                # Draw sides
                for i in range(4):
                    side_cnt = np.array([poly_base[i], poly_base[(i+1)%4], poly_top[(i+1)%4], poly_top[i]])
                    cv2.fillPoly(frame, [side_cnt], (150, 0, 0))
                
                # Draw top
                cv2.fillPoly(frame, [np.array(poly_top)], (255, 50, 50))

        # 5. Draw Ball (Sphere)
        if self.balls:
            for ball in self.balls:
                if not ball['lost']:
                    bx, by = ball['pos']
                    bz = self.ball_radius # Radius above floor
                    
                    # Shadow
                    shadow_center = self._project_3d(bx, by, 0)
                    shadow_rim = self._project_3d(bx + self.ball_radius, by, 0)
                    shadow_rad = int(np.linalg.norm(np.array(shadow_rim) - np.array(shadow_center)))
                    cv2.circle(frame, shadow_center, shadow_rad, (10, 10, 10), -1)
                    
                    # Ball
                    ball_center = self._project_3d(bx, by, bz)
                    ball_rim = self._project_3d(bx + self.ball_radius, by, bz)
                    ball_rad = int(np.linalg.norm(np.array(ball_rim) - np.array(ball_center)))
                    
                    # Simple shading
                    cv2.circle(frame, ball_center, ball_rad, (180, 180, 180), -1)
                    # Highlight
                    hl_offset = int(ball_rad * 0.3)
                    cv2.circle(frame, (ball_center[0]-hl_offset, ball_center[1]-hl_offset), int(ball_rad*0.3), (255, 255, 255), -1)
        else:
             text = "GAME OVER"
             font = cv2.FONT_HERSHEY_SIMPLEX
             scale = 1
             thickness = 2
             text_size = cv2.getTextSize(text, font, scale, thickness)[0]
             text_x = (self.width - text_size[0]) // 2
             text_y = (self.height + text_size[1]) // 2
             cv2.putText(frame, text, (text_x, text_y), font, scale, (0, 0, 255), thickness)
        
        self.frame = frame



    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_state(self):
        """Get current simulation state for synchronization."""
        with self.lock:
            return {
                'balls': [b.copy() for b in self.balls],
                'left_angle': self.current_left_angle,
                'right_angle': self.current_right_angle,
                'score': self.score,
                'is_tilted': self.is_tilted,
                'drop_targets': list(self.drop_target_states),
                'bumpers': self.bumpers # Bumpers might change if randomized? No, layout is static per session usually.
            }

    def set_state(self, state):
        """Set simulation state from external source (e.g. training worker)."""
        with self.lock:
            if 'balls' in state:
                self.balls = state['balls']
            if 'left_angle' in state:
                self.current_left_angle = state['left_angle']
            if 'right_angle' in state:
                self.current_right_angle = state['right_angle']
            if 'score' in state:
                self.score = state['score']
            if 'is_tilted' in state:
                self.is_tilted = state['is_tilted']
            if 'drop_targets' in state:
                self.drop_target_states = state['drop_targets']
            
            # Force render frame
            self._draw_frame()

    @property
    def ball_lost(self):
        # Return true only if ALL balls are lost
        return len(self.balls) == 0

    def get_ball_status(self):
        # Return the ball closest to the bottom (highest Y)
        with self.lock:
            if not self.balls:
                return None
            
            # Sort by Y descending (bottom first)
            active_balls = [b for b in self.balls if not b['lost']]
            if not active_balls:
                return None
                
            lowest_ball = max(active_balls, key=lambda b: b['pos'][1])
            return lowest_ball['pos'], lowest_ball['vel']

    def adjust_camera(self, key):
        """Adjust camera parameters based on key input."""
        speed = 0.1
        zoom_speed = 0.1
        
        with self.lock:
            if key == 'ArrowUp':
                self.cam_y -= speed * self.height # Move Up (Y decreases in screen space? No, Y is Up/Down in 3D world usually)
                # In _project_3d: y_cam = y - camY. 
                # If we want to move camera "Up" relative to table, we decrease camY (if Y is down) or increase (if Y is up).
                # Table coords: Y=0 is top, Y=1.2 is bottom.
                # Camera Y=2.5 (default).
                # So decreasing camY moves camera closer to top of table (Up).
                self.cam_y -= speed * self.height
            elif key == 'ArrowDown':
                self.cam_y += speed * self.height
            elif key == 'ArrowLeft':
                self.cam_x -= speed * self.width
            elif key == 'ArrowRight':
                self.cam_x += speed * self.width
            elif key == 'PageUp':
                self.cam_z += speed * self.width # Move Back/Up
            elif key == 'PageDown':
                self.cam_z -= speed * self.width
            elif key == 'Home': # Zoom In
                self.focal_length *= (1.0 + zoom_speed)
            elif key == 'End': # Zoom Out
                self.focal_length *= (1.0 - zoom_speed)
            
            logger.info(f"Camera Adjusted: X={self.cam_x:.2f}, Y={self.cam_y:.2f}, Z={self.cam_z:.2f}, Focal={self.focal_length:.2f}")

    def stop(self):
        self.running = False
        self.thread.join()
        logger.info("Simulated camera stopped")
    def check_zones(self, x, y):
        """
        Check if a point (in table coordinates) is within any active zones (in screen coordinates).
        Projects the point to 3D screen space before checking.
        """
        if not self.zone_manager:
            return {'left': False, 'right': False}
            
        # Project ball position (at ball height) to screen space
        sx, sy = self._project_3d(x, y, self.ball_radius)
        
        return self.zone_manager.get_zone_status(sx, sy)


class ZoneManager:
    def set_contours(self, contours):
        # contours: list of {'type': 'left'|'right', 'cnt': np.array}
        self.contours = contours

    def __init__(self, frame_width, frame_height, layout: PinballLayout = None):
        self.layout = layout if layout else PinballLayout()
        self.contours = []
        
        # Initialize contours from layout
        for zone in self.layout.zones:
            points = []
            for p in zone['points']:
                points.append([int(p['x'] * frame_width), int(p['y'] * frame_height)])
            
            cnt = np.array(points, dtype=np.int32)
            self.contours.append({
                'type': zone['type'],
                'cnt': cnt
            })

    def get_zone_status(self, x, y):
        """
        Returns dictionary with 'left' and 'right' boolean status.
        """
        in_left = False
        in_right = False
        
        for zone in self.contours:
            if cv2.pointPolygonTest(zone['cnt'], (x, y), False) >= 0:
                if zone['type'] == 'left':
                    in_left = True
                elif zone['type'] == 'right':
                    in_right = True
            
        return {
            'left': in_left,
            'right': in_right
        }

    def draw_zones(self, frame):
        for zone in self.contours:
            color = (0, 255, 0) if zone['type'] == 'left' else (0, 255, 255)
            cv2.polylines(frame, [zone['cnt']], True, color, 2)
        return frame


class BallTracker:
    def __init__(self):
        # HSV range for a silver ball (needs calibration)
        self.lower_silver = np.array([0, 0, 150])
        self.upper_silver = np.array([180, 50, 255])

    def process_frame(self, frame):
        if frame is None:
            return None, None

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_silver, self.upper_silver)
        
        # Mask out plunger areas to prevent false positives (e.g. kickback plunger)
        h, w = mask.shape[:2]
        # Left Plunger (Kickback) - Bottom Left
        cv2.rectangle(mask, (0, int(h * 0.8)), (int(w * 0.15), h), 0, -1)
        # Right Plunger - Right side
        cv2.rectangle(mask, (int(w * 0.85), int(h * 0.5)), (w, h), 0, -1)
        
        # Mask out rail areas to prevent false positives
        # Left rail area (X: 0.15-0.3, Y: 0.6-0.9)
        cv2.rectangle(mask, (int(w * 0.13), int(h * 0.55)), (int(w * 0.32), int(h * 0.90)), 0, -1)
        # Right rail area (X: 0.7-0.85, Y: 0.6-0.9)
        cv2.rectangle(mask, (int(w * 0.68), int(h * 0.55)), (int(w * 0.87), int(h * 0.90)), 0, -1)
        
        # Morphological operations to remove noise
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        ball_pos = None
        if contours:
            # Assume largest contour is the ball
            c = max(contours, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            if radius > 5: # Minimum size filter
                ball_pos = (int(x), int(y))
                cv2.circle(frame, ball_pos, int(radius), (0, 0, 255), 2)

        return ball_pos, frame


class ScoreReader:
    def __init__(self):
        import pytesseract
        # Configure pytesseract path if needed, e.g.:
        # pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
        pass

    def get_score(self, frame):
        # Crop to scoreboard area (needs calibration)
        # Example: top 10% of screen
        height, width = frame.shape[:2]
        roi = frame[0:int(height*0.15), int(width*0.6):width] 
        
        # Preprocessing for OCR
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        
        try:
            text = pytesseract.image_to_string(thresh, config='--psm 7 outputbase digits')
            score = int(''.join(filter(str.isdigit, text)))
            return score
        except:
            return 0
