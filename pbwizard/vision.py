import threading
import time
import os
import logging
import json

import cv2
import numpy as np

from pbwizard import constants


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
        self.left_flipper_x_min = 0.2
        self.left_flipper_x_max = 0.4
        self.left_flipper_y_min = 0.8
        self.left_flipper_y_max = 0.9
        
        self.right_flipper_x_min = 0.6
        self.right_flipper_x_max = 0.8
        self.right_flipper_y_min = 0.8
        self.right_flipper_y_max = 0.9
        
        self.bumpers = [
            {'x': 0.5, 'y': 0.3, 'radius_ratio': 0.05, 'value': 100},
            {'x': 0.3, 'y': 0.4, 'radius_ratio': 0.04, 'value': 50},
            {'x': 0.7, 'y': 0.4, 'radius_ratio': 0.04, 'value': 50}
        ]
        
        self.guide_lines_y = 0.65
        
        self.drop_targets = [
            {'x': 0.4, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500},
            {'x': 0.5, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500},
            {'x': 0.6, 'y': 0.1, 'width': 0.03, 'height': 0.01, 'value': 500}
        ]
        
        if filepath:
            self.load_from_file(filepath)
        elif config:
            self.load(config)

    def load_from_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            self.load(config)
        except Exception as e:
            logger.error(f"Failed to load layout from {filepath}: {e}")

    def load(self, config):
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
            
        if 'guide_lines' in config:
            self.guide_lines_y = config['guide_lines'].get('y', self.guide_lines_y)
            
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
            "bumpers": self.bumpers,
            "drop_targets": self.drop_targets,
            "guide_lines": {
                "y": self.guide_lines_y
            }
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
    FLIPPER_LENGTH = 0.2  # Normalized width
    LEFT_DOWN_ANGLE = -30
    LEFT_UP_ANGLE = 20
    RIGHT_DOWN_ANGLE = 210
    RIGHT_UP_ANGLE = 160
    GRAVITY = 0.08
    SUB_STEPS = 20
    FRICTION = 0.999
    RESTITUTION = 0.5
    
    MAX_BALLS = 5
    
    # Tilt Settings
    TILT_THRESHOLD = 8.0
    NUDGE_COST = 4.0
    TILT_DECAY = 0.05

    def __init__(self, width=constants.DEFAULT_WIDTH, height=constants.DEFAULT_HEIGHT, headless=False):
        self.width = width
        self.height = height
        self.headless = headless
        self.last_model = None  # Track last loaded model
        self.layout = PinballLayout() # Removed 'layout' parameter from init, so always create new
        self.zone_manager = ZoneManager(width, height, self.layout)
        
        # Instance physics parameters (initialized from class constants)
        self.gravity = self.GRAVITY
        self.friction = self.FRICTION
        self.restitution = self.RESTITUTION
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_length = self.FLIPPER_LENGTH
        
        # Tilt Parameters
        self.tilt_threshold = self.TILT_THRESHOLD
        self.nudge_cost = self.NUDGE_COST
        self.tilt_decay = self.TILT_DECAY
        
        # Flipper Angles (Symmetric Control)
        self.flipper_resting_angle = -30.0
        self.flipper_stroke_angle = 50.0

        self.auto_start_enabled = True # Default to True for easier testing
        
        # Load Assets
        self.assets = {}
        self._load_assets()
        
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.running = False
        self.lock = threading.RLock()
        
        # Ball State (List of balls)
        self.balls = [] # List of dicts: {'pos': np.array, 'vel': np.array, 'lost': bool}
        self.ball_radius = int(width * 0.025) # Scale ball with width
        
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
        
        # Flipper zones (calculated from layout)
        # Flipper zones (calculated from layout)
        self.left_flipper_rect = None
        self.right_flipper_rect = None
        self.guide_lines = []
        
        self._update_flipper_rects()
        
        # Score and Bumpers
        self.score = 0
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
        self.cam_x = width / 2
        self.cam_y = height * 1.5  # Behind the flippers
        self.cam_z = width * 1.5   # Up in the air
        self.focal_length = width * 1.2
        
        # Calculate Pitch to look at center of table (width/2, height/2, 0)
        # Vector from Cam to Target
        target_y = height / 2
        target_z = 0
        dy = target_y - self.cam_y
        dz = target_z - self.cam_z
        
        # We want to rotate such that the new Y component is 0
        # y' = y*cos(p) - z*sin(p) = 0  => tan(p) = y/z
        self.pitch = np.arctan2(dy, dz)

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

        # Right Flipper: Pivot at x_max, length extends to left
        r_x_max = self.layout.right_flipper_x_max
        r_x_min = r_x_max - self.flipper_length
        
        self.right_flipper_rect = (
            int(self.width * r_x_min),
            int(self.height * self.layout.right_flipper_y_min),
            int(self.width * r_x_max),
            int(self.height * self.layout.right_flipper_y_max)
        )
        
        # Update Guide Lines (Funnel to flippers)
        # Left pivot is bottom-left of rect (x_min, y_max)
        l_pivot = (self.left_flipper_rect[0], self.left_flipper_rect[3])
        # Right pivot is bottom-right of rect (x_max, y_max)
        r_pivot = (self.right_flipper_rect[2], self.right_flipper_rect[3])
        
        self.guide_lines = [
            (np.array([0, self.height * self.layout.guide_lines_y]), np.array(l_pivot)),
            (np.array([self.width, self.height * self.layout.guide_lines_y]), np.array(r_pivot))
        ]

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
        sy = int(-cy * scale + self.height / 2) # Invert Y for correct screen orientation
        
        return (sx, sy)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop)
        self.thread.start()
        logger.info("Simulated camera started")

    def update_physics_params(self, params):
        changes = []
        if 'gravity' in params:
            val = float(params['gravity'])
            if val != self.gravity:
                self.gravity = val
                changes.append(f"Gravity: {val}")
        if 'friction' in params:
            val = float(params['friction'])
            if val != self.friction:
                self.friction = val
                changes.append(f"Friction: {val}")
        if 'restitution' in params:
            val = float(params['restitution'])
            if val != self.restitution:
                self.restitution = val
                changes.append(f"Restitution: {val}")
        if 'flipper_speed' in params:
            val = float(params['flipper_speed'])
            if val != self.flipper_speed:
                self.flipper_speed = val
                changes.append(f"Flipper Speed: {val}")
            
        if 'flipper_resting_angle' in params:
            self.flipper_resting_angle = float(params['flipper_resting_angle'])
        if 'flipper_stroke_angle' in params:
            self.flipper_stroke_angle = float(params['flipper_stroke_angle'])
            
        if 'flipper_length' in params:
            val = float(params['flipper_length'])
            if val != self.flipper_length:
                self.flipper_length = val
                self._update_flipper_rects()
                if self.zone_manager:
                    self.zone_manager.update_zones(self.width, self.height)
                changes.append(f"Flipper Length: {val}")
                
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
            
        if changes:
            logger.info(f"Physics updated: {', '.join(changes)}")

    def save_config(self, filepath="config.json"):
        config = {
            'gravity': self.gravity,
            'friction': self.friction,
            'restitution': self.restitution,
            'flipper_speed': self.flipper_speed,
            'flipper_resting_angle': self.flipper_resting_angle,
            'flipper_stroke_angle': self.flipper_stroke_angle,
            'flipper_length': self.flipper_length,
            'tilt_threshold': self.tilt_threshold,
            'nudge_cost': self.nudge_cost,
            'tilt_decay': self.tilt_decay,
            'last_model': getattr(self, 'last_model', None)
        }
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
            return False
        
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            self.update_physics_params(config)
            if 'last_model' in config:
                self.last_model = config['last_model']
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def reset_to_defaults(self):
        """Reset all physics parameters to class constants and save."""
        self.gravity = self.GRAVITY
        self.friction = self.FRICTION
        self.restitution = self.RESTITUTION
        self.flipper_speed = self.FLIPPER_SPEED
        self.flipper_length = self.FLIPPER_LENGTH
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
            'flipper_length': self.flipper_length,
            'tilt_threshold': self.tilt_threshold,
            'nudge_cost': self.nudge_cost,
            'tilt_decay': self.tilt_decay
        }

    def load_layout(self, layout_config):
        """Load a new table layout from a dictionary."""
        with self.lock:
            self.layout.load(layout_config)
            
            # Re-initialize components dependent on layout
            self.zone_manager = ZoneManager(self.width, self.height, self.layout)
            self._update_flipper_rects()
            
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
            
            # Reset game state
            self.score = 0
            self.balls = []
            self.tilt_value = 0.0
            self.is_tilted = False
            logger.info("Layout loaded and simulation reset")
            return True

    def launch_ball(self):
        with self.lock:
            if len(self.balls) == 0:
                self.score = 0
                self.tilt_value = 0.0
                self.is_tilted = False
                logger.info("Sim: Score Reset (New Game)")
            self.add_ball()
            self.flipper_speed = self.FLIPPER_SPEED
            # Reset targets
            self.drop_target_states = [True] * len(self.layout.drop_targets)
            logger.info("Sim: New Game Started")
        
        # Load config if exists
        self.load_config()


    def add_ball(self):
        if len(self.balls) >= self.MAX_BALLS:
            logger.warning(f"Sim: Max balls ({self.MAX_BALLS}) reached, cannot add more.")
            return

        new_ball = {
            'pos': np.array([self.width / 2 + np.random.uniform(-20, 20), self.height * 0.15], dtype=float),
            'vel': np.array([np.random.uniform(-2, 2), np.random.uniform(2, 5)], dtype=float),
            'lost': False
        }
        self.balls.append(new_ball)
        logger.info(f"Sim: Ball Added. Total balls: {len(self.balls)}")

    @property
    def left_flipper_active(self):
        return self._left_flipper_inputs > 0

    @property
    def right_flipper_active(self):
        return self._right_flipper_inputs > 0

    def trigger_left(self):
        self._left_flipper_inputs += 1

    def release_left(self):
        if self._left_flipper_inputs > 0:
            self._left_flipper_inputs -= 1

    def trigger_right(self):
        self._right_flipper_inputs += 1

    def release_right(self):
        if self._right_flipper_inputs > 0:
            self._right_flipper_inputs -= 1

    def nudge(self, dx, dy):
        """Apply a sudden velocity change to all balls (simulate tilt)."""
        with self.lock:
            if self.is_tilted:
                return

            # Accumulate Tilt
            self.tilt_value += self.nudge_cost
            if self.tilt_value > self.tilt_threshold:
                self.is_tilted = True
                logger.info("TILT! Game Over for this ball.")
                # Could also drain ball immediately, but let's just kill flippers
            
            for ball in self.balls:
                if not ball['lost']:
                    ball['vel'][0] += dx
                    ball['vel'][1] += dy
                    # Add some randomness
                    ball['vel'][0] += np.random.uniform(-0.5, 0.5)
                    ball['vel'][1] += np.random.uniform(-0.5, 0.5)
            
            # Record nudge for UI visualization
            self.last_nudge = {
                'time': time.time(),
                'direction': 'left' if dx < 0 else 'right'
            }
            logger.debug(f"Sim: Nudge applied ({dx}, {dy})")

    def nudge_left(self):
        # Nudge table to the left (ball moves right relative to table? No, table moves left under ball)
        # If table moves left, ball appears to move right.
        # But usually "Nudge Left" means pushing the table from the right side towards the left.
        # This imparts a force to the left.
        self.nudge(-5.0, -2.0) # Push left and slightly up

    def nudge_right(self):
        self.nudge(5.0, -2.0) # Push right and slightly up

    def _get_flipper_line_from_angle(self, rect, angle, side):
        # Calculate flipper line segment from a specific angle
        if side == 'left':
            pivot = np.array([rect[0], rect[3]]) # Bottom-left
            length = rect[2] - rect[0]
            rad = np.radians(angle)
            end = pivot + np.array([length * np.cos(rad), -length * np.sin(rad)])
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

        for i, target in enumerate(self.layout.drop_targets):
            if not self.drop_target_states[i]: continue # Already hit

            # Simple AABB collision for targets
            tx, ty = target['x'] * self.width, target['y'] * self.height
            tw, th = target['width'] * self.width, target['height'] * self.height
            
            bx, by = ball['pos']
            
            if (bx > tx - tw/2 and bx < tx + tw/2 and
                by > ty - th/2 and by < ty + th/2):
                
                # Hit!
                self.drop_target_states[i] = False
                self.score += target['value']
                ball['vel'][1] *= -1 # Bounce back
                
                # Check if all targets hit
                if not any(self.drop_target_states):
                    logger.info("MULTIBALL ACTIVATED!")
                    self.add_ball()
                    # Reset targets after a short delay or immediately? 
                    # For now, reset immediately so they can be hit again
                    self.drop_target_states = [True] * len(self.layout.drop_targets)

    def _simulation_loop(self):
        dt = 1.0 / self.SUB_STEPS 

        while self.running:
            with self.lock:
                # Remove lost balls
                self.balls = [b for b in self.balls if not b['lost']]
                
                # Decay Tilt
                if self.tilt_value > 0:
                    self.tilt_value = max(0, self.tilt_value - self.tilt_decay)
                
                if not self.balls:
                    # Auto-start logic
                    if self.auto_start_enabled:
                        current_time = time.time()
                        if not hasattr(self, 'game_over_time') or self.game_over_time is None:
                            self.game_over_time = current_time
                        
                        # Wait 1 second before restart
                        if current_time - self.game_over_time > 1.0:
                            self.launch_ball()
                            self.game_over_time = None
                    else:
                        self.game_over_time = None
                    pass
                else:
                    self.game_over_time = None

                for _ in range(self.SUB_STEPS):
                    # Update Flipper Angles
                    self._update_flipper_angles(dt)
                    
                    for ball in self.balls:
                        if ball['lost']: continue
                        
                        prev_pos = ball['pos'].copy()
                        
                        # Physics
                        ball['vel'][1] += self.gravity * dt
                        ball['pos'] += ball['vel'] * dt
                        
                        # Collisions
                        self._handle_wall_collisions(ball)
                        if ball['lost']: continue
                        
                        self._handle_flipper_collisions(ball, prev_pos)
                        self._check_bumper_collision(ball)
                        self._check_drop_target_collision(ball)
                        
                        for p1, p2 in self.guide_lines:
                            self._check_line_collision(ball, p1, p2, active=False, prev_pos=prev_pos)

                self._draw_frame()

                if not self.headless:
                    self._draw_frame()
            
            if not self.headless:
                time.sleep(0.016) # ~60 FPS
            else:
                time.sleep(0.001) # Yield for eventlet

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

    def _draw_frame(self):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # --- 3D Rendering ---
        
        # 1. Draw Floor
        # Project 4 corners of the table
        c1 = self._project_3d(0, 0, 0)
        c2 = self._project_3d(self.width, 0, 0)
        c3 = self._project_3d(self.width, self.height, 0)
        c4 = self._project_3d(0, self.height, 0)
        
        floor_cnt = np.array([c1, c2, c3, c4])
        cv2.fillPoly(frame, [floor_cnt], (30, 30, 30)) # Dark gray floor
        
        # Draw Grid on floor
        for i in range(0, self.width, 50):
            p1 = self._project_3d(i, 0, 0)
            p2 = self._project_3d(i, self.height, 0)
            cv2.line(frame, p1, p2, (40, 40, 40), 1)
        for i in range(0, self.height, 50):
            p1 = self._project_3d(0, i, 0)
            p2 = self._project_3d(self.width, i, 0)
            cv2.line(frame, p1, p2, (40, 40, 40), 1)

        # Draw Zones (Projected)
        # Left Zone
        lz = self.zone_manager.left_flipper_zone
        lz_pts = [
            self._project_3d(lz['x_min'], lz['y_min'], 0),
            self._project_3d(lz['x_max'], lz['y_min'], 0),
            self._project_3d(lz['x_max'], lz['y_max'], 0),
            self._project_3d(lz['x_min'], lz['y_max'], 0)
        ]
        cv2.polylines(frame, [np.array(lz_pts)], True, (0, 150, 0), 1)
        
        # Right Zone
        rz = self.zone_manager.right_flipper_zone
        rz_pts = [
            self._project_3d(rz['x_min'], rz['y_min'], 0),
            self._project_3d(rz['x_max'], rz['y_min'], 0),
            self._project_3d(rz['x_max'], rz['y_max'], 0),
            self._project_3d(rz['x_min'], rz['y_max'], 0)
        ]
        cv2.polylines(frame, [np.array(rz_pts)], True, (0, 150, 0), 1)

        # 2. Draw Walls (Simple extrusion)
        wall_height = 40
        walls = [
            ((0, 0), (self.width, 0)), # Top
            ((self.width, 0), (self.width, self.height)), # Right
            ((self.width, self.height), (0, self.height)), # Bottom
            ((0, self.height), (0, 0)) # Left
        ]
        
        for p1_2d, p2_2d in walls:
            b1 = self._project_3d(p1_2d[0], p1_2d[1], 0)
            b2 = self._project_3d(p2_2d[0], p2_2d[1], 0)
            t1 = self._project_3d(p1_2d[0], p1_2d[1], wall_height)
            t2 = self._project_3d(p2_2d[0], p2_2d[1], wall_height)
            
            wall_cnt = np.array([b1, b2, t2, t1])
            cv2.fillPoly(frame, [wall_cnt], (60, 60, 60))
            cv2.polylines(frame, [wall_cnt], True, (100, 100, 100), 1)

        # 3. Draw Bumpers (Cylinders)
        for bumper in self.bumpers:
            bx, by = bumper['pos']
            br = bumper['radius']
            
            # Base
            center_base = self._project_3d(bx, by, 0)
            # Top
            center_top = self._project_3d(bx, by, 20)
            
            # Approximate radius in perspective (simplified)
            # Project a point on the rim
            rim_pt = self._project_3d(bx + br, by, 0)
            proj_radius = int(np.linalg.norm(np.array(rim_pt) - np.array(center_base)))
            
            cv2.circle(frame, center_base, proj_radius, (0, 0, 150), -1)
            cv2.circle(frame, center_top, proj_radius, (0, 0, 255), -1)
            cv2.circle(frame, center_top, proj_radius, (0, 0, 255), -1)
            # Connect sides? (Optional for simple view)

        # 3.5 Draw Drop Targets
        target_height = 20
        for i, target in enumerate(self.layout.drop_targets):
            if self.drop_target_states[i]: # Only draw if active (up)
                tx = target['x'] * self.width
                ty = target['y'] * self.height
                tw = target['width'] * self.width
                th = target['height'] * self.height # Thickness in Y
                
                # Base rectangle corners
                c1 = (tx - tw/2, ty - th/2)
                c2 = (tx + tw/2, ty - th/2)
                c3 = (tx + tw/2, ty + th/2)
                c4 = (tx - tw/2, ty + th/2)
                
                # Project base and top
                poly_base = [self._project_3d(p[0], p[1], 0) for p in [c1, c2, c3, c4]]
                poly_top = [self._project_3d(p[0], p[1], target_height) for p in [c1, c2, c3, c4]]
                
                # Draw sides (Front face is most important)
                # Front face is between c4 and c3 (highest Y, closest to camera)
                front_face = np.array([poly_base[3], poly_base[2], poly_top[2], poly_top[3]])
                cv2.fillPoly(frame, [front_face], (0, 200, 255))
                
                # Top face
                cv2.fillPoly(frame, [np.array(poly_top)], (0, 255, 255))
                
                # Outline
                cv2.polylines(frame, [front_face], True, (0, 100, 150), 1)
                cv2.polylines(frame, [np.array(poly_top)], True, (0, 100, 150), 1)

        # 4. Draw Flippers (Prisms)
        flipper_height = 15
        for side, rect, angle in [('left', self.left_flipper_rect, self.current_left_angle), 
                                  ('right', self.right_flipper_rect, self.current_right_angle)]:
            p1, p2 = self._get_flipper_line_from_angle(rect, angle, side)
            
            # Thickness vector (perpendicular to flipper line)
            vec = p2 - p1
            length = np.linalg.norm(vec)
            if length > 0:
                perp = np.array([-vec[1], vec[0]]) / length * 10 # 10px width
                
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

    def stop(self):
        self.running = False
        self.thread.join()
        logger.info("Simulated camera stopped")


class ZoneManager:
    def update_zones(self, frame_width, frame_height):
        # Calculate zones based on layout and flipper rotation
        # Left Flipper: Pivot at (x_min, y_max)
        l_len = (self.layout.left_flipper_x_max - self.layout.left_flipper_x_min) * frame_width
        l_y_pivot = self.layout.left_flipper_y_max * frame_height
        
        # Add padding
        padding = 50
        
        self.left_flipper_zone = {
            'x_min': int(self.layout.left_flipper_x_min * frame_width - padding),
            'x_max': int(self.layout.left_flipper_x_max * frame_width + l_len * 0.2 + padding), 
            'y_min': int(l_y_pivot - l_len * np.sin(np.radians(20)) - padding),
            'y_max': int(l_y_pivot + l_len * np.sin(np.radians(30)) + padding)
        }
        
        r_len = (self.layout.right_flipper_x_max - self.layout.right_flipper_x_min) * frame_width
        r_y_pivot = self.layout.right_flipper_y_max * frame_height

        self.right_flipper_zone = {
            'x_min': int(self.layout.right_flipper_x_min * frame_width - r_len * 0.2 - padding),
            'x_max': int(self.layout.right_flipper_x_max * frame_width + padding),
            'y_min': int(r_y_pivot - r_len * np.sin(np.radians(20)) - padding), 
            'y_max': int(r_y_pivot + r_len * np.sin(np.radians(30)) + padding)
        }

    def __init__(self, frame_width, frame_height, layout: PinballLayout = None):
        self.layout = layout if layout else PinballLayout()
        self.update_zones(frame_width, frame_height)

    def is_in_zone(self, x, y, zone):
        return (zone['x_min'] <= x <= zone['x_max'] and
                zone['y_min'] <= y <= zone['y_max'])

    def get_zone_status(self, x, y):
        return {
            'left': self.is_in_zone(x, y, self.left_flipper_zone),
            'right': self.is_in_zone(x, y, self.right_flipper_zone)
        }

    def draw_zones(self, frame):
        # Draw left zone
        cv2.rectangle(frame, 
                      (self.left_flipper_zone['x_min'], self.left_flipper_zone['y_min']),
                      (self.left_flipper_zone['x_max'], self.left_flipper_zone['y_max']),
                      (0, 255, 0), 2)
        # Draw right zone
        cv2.rectangle(frame, 
                      (self.right_flipper_zone['x_min'], self.right_flipper_zone['y_min']),
                      (self.right_flipper_zone['x_max'], self.right_flipper_zone['y_max']),
                      (0, 255, 0), 2)
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
