import pymunk
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Collision type constants (must be integers for pymunk)
COLLISION_TYPE_BALL = 1
COLLISION_TYPE_WALL = 2
COLLISION_TYPE_FLIPPER = 3
COLLISION_TYPE_BUMPER = 4
COLLISION_TYPE_DROP_TARGET = 5
COLLISION_TYPE_PLUNGER = 6
COLLISION_TYPE_LEFT_PLUNGER = 7

# Mapping for logging
COLLISION_LABELS = {
    1: "ball",
    2: "wall",
    3: "flipper",
    4: "bumper",
    5: "drop_target",
    6: "plunger_stop",
    7: "left_plunger"
}

class PymunkEngine:
    def __init__(self, layout, width, height):
        self.layout = layout
        self.width = width
        self.height = height
        
        # Physics Space
        self.space = pymunk.Space()
        self.space.gravity = (0.0, 2500.0) # Pixels/s^2 (Snappy gravity)
        
        self.balls = []
        self.flippers = {}
        self.balls = []
        self.flippers = {}
        self.score = 0  # Track score in physics engine
        self.flipper_speed = 30.0 # Default speed
        self.is_tilted = False # Track tilt state
        self.drop_target_shapes = [] # Track drop target shapes for removal
        self.launch_angle = 0.0 # Launch angle in degrees (0 = Up)
        
        self._setup_static_geometry()
        self._setup_flippers()
        self._setup_collision_logging()
        
    def _setup_collision_logging(self):
        """Setup collision handlers to log what ball hits and award scores"""
        # Score values for different features
        SCORE_VALUES = {
            COLLISION_TYPE_BUMPER: 100,
            COLLISION_TYPE_DROP_TARGET: 500
        }
        
        handler = self.space.add_default_collision_handler()
        def begin_collision(arbiter, space, data):
            shapes = arbiter.shapes
            type_a = shapes[0].collision_type
            type_b = shapes[1].collision_type
            if type_a == COLLISION_TYPE_BALL or type_b == COLLISION_TYPE_BALL:
                other = type_b if type_a == COLLISION_TYPE_BALL else type_a
                label = COLLISION_LABELS.get(other, f"unknown({other})")
                
                # Award score for certain collision types
                score_value = SCORE_VALUES.get(other, 0)
                if score_value > 0:
                    self.score += score_value
                    logger.debug(f"BALL COLLISION: hit {label} (+{score_value} points, total: {self.score})")
                else:
                    logger.debug(f"BALL COLLISION: hit {label}")
                
                # Add random horizontal deflection to prevent stuck bouncing
                ball_shape = shapes[0] if type_a == COLLISION_TYPE_BALL else shapes[1]
                ball_body = ball_shape.body
                # Add random ±50 px/s horizontal velocity
                import random
                random_vx = random.uniform(-50, 50)
                ball_body.velocity = (ball_body.velocity.x + random_vx, ball_body.velocity.y)

                # Auto-launch if hitting plunger while it's resting
                if other == COLLISION_TYPE_PLUNGER and self.plunger_state == 'resting':
                    logger.debug("Ball touched plunger while resting - AUTO LAUNCH")
                    self.release_plunger()

                # Auto-launch for left plunger (Kickback)
                if other == COLLISION_TYPE_LEFT_PLUNGER and self.left_plunger_state == 'resting':
                    logger.debug("Ball touched left plunger - KICKBACK")
                    self.fire_left_plunger()

            return True
        handler.begin = begin_collision
        
    def _setup_static_geometry(self):
        # Walls
        thickness = 10.0
        # Left
        self._add_static_segment((0, 0), (0, self.height), thickness=thickness)
        # Right
        self._add_static_segment((self.width, 0), (self.width, self.height), thickness=thickness)
        # Top
        self._add_static_segment((0, 0), (self.width, 0), thickness=thickness)
        
        # Top Arch (Deflector from Plunger Lane to Playfield) - Right Side
        # From top-right (above plunger lane) to top-center
        # Plunger wall is at 0.85 width.
        # Arch should start at (width, 0.15 * height) and go to (0.6 * width, 0)
        p1 = (self.width, self.height * 0.15)
        p2 = (self.width * 0.6, 0)
        self._add_static_segment(p1, p2, thickness=thickness)
        
        # Triangle Guide - Left Side (mirror of right arch)
        # From top-left corner to center-top area
        left_tri_p1 = (0, self.height * 0.15)  # Top-left, down slightly from corner
        left_tri_p2 = (self.width * 0.4, 0)     # Top-center area
        left_tri_p3 = (0, 0)                     # Top-left corner
        self._add_static_triangle(left_tri_p1, left_tri_p2, left_tri_p3)
            
        # Bumpers
        for b in self.layout.bumpers:
            pos = (b['x'] * self.width, b['y'] * self.height)
            radius = 20.0 # Pixels
            self._add_static_circle(pos, radius, elasticity=1.5)
            
        # Drop Targets
        for t in self.layout.drop_targets:
            x = t['x'] * self.width
            y = t['y'] * self.height
            w = t['width'] * self.width
            h = t['height'] * self.height
            cx = x + w/2
            cy = y + h/2
            shape = self._add_static_box((cx, cy), (w, h), elasticity=0.5, collision_type=COLLISION_TYPE_DROP_TARGET)
            self.drop_target_shapes.append(shape)
            
        # Upper Deck - DISABLED to remove invisible collisions
        # if self.layout.upper_deck:
        #     ud = self.layout.upper_deck
        #     x = ud['x'] * self.width
        #     y = ud['y'] * self.height
        #     w = ud['width'] * self.width
        #     h = ud['height'] * self.height
        #     cx = x + w/2
        #     cy = y + h/2
        #     self._add_static_box((cx, cy), (w, h), elasticity=0.2)
            
        # Plunger Lane
        # Vertical wall separating plunger from playfield
        lane_x = self.width * 0.85
        # self._add_static_segment((lane_x, self.height * 0.3), (lane_x, self.height), thickness=5.0)
        logger.info(f"Plunger Wall: x={lane_x}")
        
        # Plunger (Kinematic Body)
        # It starts at a resting position (holding the ball)
        # When pulled, it moves down. When released, it shoots up.
        self.plunger_rest_y = self.height * 0.95
        self.plunger_max_pull = 100.0 # Max pull distance
        self.plunger_width = self.width - lane_x - 10 # Slightly narrower than lane
        self.plunger_height = 40.0
        
        # Create Plunger Body
        self.plunger_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.plunger_body.position = (lane_x + (self.width - lane_x)/2, self.plunger_rest_y + self.plunger_height/2)
        
        # Create Plunger Shape - "Divot" style
        # Instead of one box, use 3 shapes: Base, Left Lip, Right Lip
        # Base
        base_h = self.plunger_height
        base_shape = pymunk.Poly.create_box(self.plunger_body, (self.plunger_width, base_h))
        base_shape.elasticity = 0.0
        base_shape.friction = 0.8
        base_shape.collision_type = COLLISION_TYPE_PLUNGER
        
        # Lips to center the ball
        lip_w = 10.0
        lip_h = 20.0 # Stick up above base
        # Offsets relative to body center
        # Body center is at (cx, cy)
        # Left Lip: x = -width/2 + lip_w/2, y = -base_h/2 - lip_h/2 (Up is negative Y relative to body?)
        # Wait, Pymunk local coords: Y is down?
        # If body is at Y=970. Top surface is 950.
        # We want lips at 940 (sticking up).
        # So relative Y should be negative.
        
        # Let's define shapes manually relative to (0,0) center of body
        # Box: (-w/2, -h/2) to (w/2, h/2)
        
        # Left Lip
        # Define vertices manually relative to body center
        # Top-Left, Top-Right, Bottom-Right, Bottom-Left
        # Base Top Y is -self.plunger_height/2
        # Lip goes up by lip_h
        ll_x1 = -self.plunger_width/2
        ll_x2 = -self.plunger_width/2 + lip_w
        ll_y1 = -self.plunger_height/2 - lip_h
        ll_y2 = -self.plunger_height/2
        
        l_lip_verts = [(ll_x1, ll_y1), (ll_x2, ll_y1), (ll_x2, ll_y2), (ll_x1, ll_y2)]
        l_lip_shape = pymunk.Poly(self.plunger_body, l_lip_verts)
        l_lip_shape.elasticity = 0.0
        l_lip_shape.friction = 0.1
        l_lip_shape.collision_type = COLLISION_TYPE_PLUNGER

        # Right Lip
        rl_x1 = self.plunger_width/2 - lip_w
        rl_x2 = self.plunger_width/2
        rl_y1 = -self.plunger_height/2 - lip_h
        rl_y2 = -self.plunger_height/2
        
        r_lip_verts = [(rl_x1, rl_y1), (rl_x2, rl_y1), (rl_x2, rl_y2), (rl_x1, rl_y2)]
        r_lip_shape = pymunk.Poly(self.plunger_body, r_lip_verts)
        r_lip_shape.elasticity = 0.0
        r_lip_shape.friction = 0.1
        r_lip_shape.collision_type = COLLISION_TYPE_PLUNGER

        self.space.add(self.plunger_body, base_shape, l_lip_shape, r_lip_shape)
        self.plunger_shape = base_shape # Keep reference for rendering (approx)
        
        self.plunger_target_y = self.plunger_rest_y
        self.plunger_state = 'resting' # resting, pulling, releasing
        self.plunger_pull_strength = 0.0 # 0.0 to 1.0
        self.plunger_release_speed = 1500.0 # Configurable release speed

        # --- Left Plunger (Kickback) ---
        # Symmetric to right plunger
        self.left_plunger_rest_y = self.height * 0.95
        self.left_plunger_height = 40.0
        # Left lane is at x ~ 0.15 * width (guessed, need to check layout or assume symmetry)
        # Right lane wall was at 0.85 width. So left lane wall is at 0.15 width.
        # Left plunger is between 0 and 0.15 width (minus margin)
        left_lane_x = self.width * 0.15
        self.left_plunger_width = left_lane_x - 10
        
        self.left_plunger_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.left_plunger_body.position = (left_lane_x / 2, self.left_plunger_rest_y + self.left_plunger_height/2)
        
        # Left Plunger Shape - Divot
        l_base_shape = pymunk.Poly.create_box(self.left_plunger_body, (self.left_plunger_width, self.left_plunger_height))
        l_base_shape.elasticity = 0.1
        l_base_shape.friction = 0.8
        l_base_shape.collision_type = COLLISION_TYPE_LEFT_PLUNGER
        
        # Lips for Left Plunger
        # Re-use lip dimensions
        # Left Lip
        ll_l_lip_verts = [
            (ll_x1, ll_y1), (ll_x2, ll_y1), (ll_x2, ll_y2), (ll_x1, ll_y2)
        ]
        ll_l_lip_shape = pymunk.Poly(self.left_plunger_body, ll_l_lip_verts)
        ll_l_lip_shape.elasticity = 0.1
        ll_l_lip_shape.friction = 0.8
        ll_l_lip_shape.collision_type = COLLISION_TYPE_LEFT_PLUNGER
        
        # Right Lip
        ll_r_lip_verts = [
            (rl_x1, ll_y1), (rl_x2, ll_y1), (rl_x2, ll_y2), (rl_x1, rl_y2)
        ]
        ll_r_lip_shape = pymunk.Poly(self.left_plunger_body, ll_r_lip_verts)
        ll_r_lip_shape.elasticity = 0.1
        ll_r_lip_shape.friction = 0.8
        ll_r_lip_shape.collision_type = COLLISION_TYPE_LEFT_PLUNGER
        
        self.space.add(self.left_plunger_body, l_base_shape, ll_l_lip_shape, ll_r_lip_shape)
        
        self.left_plunger_target_y = self.left_plunger_rest_y
        self.left_plunger_state = 'resting' # resting, firing

    def pull_plunger(self, strength):
        """Pull the plunger back (down). Strength 0.0 to 1.0"""
        self.plunger_state = 'pulling'
        self.plunger_pull_strength = np.clip(strength, 0.0, 1.0)
        # Target Y is rest + pull distance
        target_y = self.plunger_rest_y + (self.plunger_max_pull * self.plunger_pull_strength)
        # Move instantly or lerp? Let's lerp in update
        self.plunger_target_y = target_y

    def release_plunger(self):
        """Release the plunger to shoot forward."""
        self.plunger_state = 'releasing'
        # Target is slightly ABOVE rest to ensure contact/follow through
        self.plunger_target_y = self.plunger_rest_y - 10 
        
    def fire_left_plunger(self):
        """Fire the left plunger (Kickback)."""
        self.left_plunger_state = 'firing'
        # Target is slightly ABOVE rest
        self.left_plunger_target_y = self.left_plunger_rest_y - 10

    def _update_left_plunger(self, dt):
        if not hasattr(self, 'left_plunger_body'): return
        
        current_y = self.left_plunger_body.position.y
        target_pos_y = self.left_plunger_target_y + self.left_plunger_height/2
        
        if self.left_plunger_state == 'firing':
            # Move FAST upward
            speed = 2500.0
            
            if current_y > target_pos_y:
                new_y = current_y - speed * dt
                if new_y < target_pos_y:
                    new_y = target_pos_y
                    self.left_plunger_state = 'resting'
                
                self.left_plunger_body.position = (self.left_plunger_body.position.x, new_y)
                self.left_plunger_body.velocity = (0, -speed)
            else:
                self.left_plunger_state = 'resting'
                self.left_plunger_body.velocity = (0, 0)
                self.left_plunger_body.position = (self.left_plunger_body.position.x, target_pos_y)
                
        else: # Resting
             target = self.left_plunger_rest_y + self.left_plunger_height/2
             if abs(current_y - target) > 1.0:
                 speed = 100.0
                 direction = 1.0 if target > current_y else -1.0
                 new_y = current_y + direction * speed * dt
                 self.left_plunger_body.position = (self.left_plunger_body.position.x, new_y)
                 self.left_plunger_body.velocity = (0, direction * speed)
             else:
                 self.left_plunger_body.position = (self.left_plunger_body.position.x, target)
                 self.left_plunger_body.velocity = (0, 0) 
        
    def _update_plunger(self, dt):
        if not hasattr(self, 'plunger_body'): return
        
        current_y = self.plunger_body.position.y
        target_pos_y = self.plunger_target_y + self.plunger_height/2
        
        if self.plunger_state == 'releasing':
            # Move FAST upward (Negative Y direction)
            speed = self.plunger_release_speed # Pixels/sec - Configurable
            
            # We want to move from current_y (high value) to target_pos_y (low value)
            if current_y > target_pos_y:
                new_y = current_y - speed * dt
                if new_y < target_pos_y:
                    new_y = target_pos_y
                    self.plunger_state = 'resting'
                
                self.plunger_body.position = (self.plunger_body.position.x, new_y)
                # Set velocity for collision transfer - UP is NEGATIVE Y
                self.plunger_body.velocity = (0, -speed)
            else:
                self.plunger_state = 'resting'
                self.plunger_body.velocity = (0, 0)
                self.plunger_body.position = (self.plunger_body.position.x, target_pos_y)
                
        elif self.plunger_state == 'pulling':
            # Move down (Positive Y)
            speed = 300.0
            diff = target_pos_y - current_y
            if abs(diff) > 1.0:
                direction = 1.0 if diff > 0 else -1.0
                new_y = current_y + direction * speed * dt
                self.plunger_body.position = (self.plunger_body.position.x, new_y)
                self.plunger_body.velocity = (0, direction * speed)
            else:
                 self.plunger_body.velocity = (0, 0)
        
        else: # Resting
             # Ensure at rest
             target = self.plunger_rest_y + self.plunger_height/2
             # Lerp to rest if needed (e.g. after release overshoot)
             if abs(current_y - target) > 1.0:
                 speed = 100.0
                 direction = 1.0 if target > current_y else -1.0
                 new_y = current_y + direction * speed * dt
                 self.plunger_body.position = (self.plunger_body.position.x, new_y)
                 self.plunger_body.velocity = (0, direction * speed)
             else:
                 self.plunger_body.position = (self.plunger_body.position.x, target)
                 self.plunger_body.velocity = (0, 0)

    def _add_static_segment(self, p1, p2, thickness=1.0, elasticity=0.5, collision_type=COLLISION_TYPE_WALL):
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.elasticity = elasticity
        shape.friction = 0.5
        shape.collision_type = collision_type
        self.space.add(shape)
        
    def _add_static_circle(self, pos, radius, elasticity=0.8, collision_type=COLLISION_TYPE_BUMPER):
        body = self.space.static_body
        shape = pymunk.Circle(body, radius, pos)
        shape.elasticity = elasticity
        shape.friction = 0.5
        shape.collision_type = collision_type
        self.space.add(shape)
        
    def _add_static_box(self, pos, size, elasticity=0.5, collision_type=COLLISION_TYPE_DROP_TARGET):
        body = self.space.static_body
        shape = pymunk.Poly.create_box(body, size)
        shape.body.position = pos
        shape.elasticity = elasticity
        shape.friction = 0.5
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape

    def _setup_flippers(self):
        # Left Flipper - pivot at BOTTOM-left to match visuals
        l_pivot = (self.layout.left_flipper_x_min * self.width, self.layout.left_flipper_y_max * self.height)
        self.flippers['left'] = self._create_flipper(l_pivot, 'left')
        
        # Right Flipper - pivot at BOTTOM-right to match visuals
        r_pivot = (self.layout.right_flipper_x_max * self.width, self.layout.right_flipper_y_max * self.height)
        self.flippers['right'] = self._create_flipper(r_pivot, 'right')
        
        self.flippers['upper'] = []

    def update_flipper_length(self, length_ratio):
        """Update flipper length and rebuild flippers."""
        self.flipper_length_ratio = length_ratio
        
        # Remove existing flippers
        for side, flipper in self.flippers.items():
            if side == 'upper':
                for f in flipper:
                    self.space.remove(f['body'], f['shape'])
            else:
                self.space.remove(flipper['body'], flipper['shape'])
        
        self.flippers = {}
        self._setup_flippers()

    def _create_flipper(self, pivot, side, length_scale=1.0):
        # Flipper Body (Kinematic)
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pivot
        
        # Use stored ratio or default
        ratio = getattr(self, 'flipper_length_ratio', 0.12)
        length = self.width * ratio * length_scale 
        thickness = 10.0 # Pixels
        
        if side == 'left':
            p1 = (0, 0)
            p2 = (length, 0)
        else:
            p1 = (0, 0)
            p2 = (-length, 0)
            
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.elasticity = 1.2  # High elasticity for strong ball bounce
        shape.friction = 0.1
        shape.collision_type = COLLISION_TYPE_FLIPPER  # Re-enabled with fixed positioning
        self.space.add(body, shape)
        
        return {
            'body': body,
            'shape': shape,
            'side': side,
            'angle': 0.0,
            'target_angle': 0.0
        }

    def add_ball(self, pos):
        mass = 1.0
        radius = 12.0 # Pixels
        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)
        body.position = pos
        shape = pymunk.Circle(body, radius)
        shape.elasticity = 0.7
        shape.friction = 0.5
        shape.collision_type = COLLISION_TYPE_BALL
        self.space.add(body, shape)
        self.balls.append(body)
        return body

    def nudge(self, dx, dy):
        """Apply an impulse to all balls to simulate a table nudge."""
        # Nudging the table moves the table under the ball.
        # Relative to the table, the ball moves in the opposite direction of the nudge?
        # No, if I push the table LEFT, the ball (due to inertia) effectively moves RIGHT relative to the table.
        # But usually "Nudge Left" means "I want the ball to go Left".
        # So let's just apply impulse in the direction of dx, dy.
        # Scale up for physics engine (vision used small pixels)
        scale = 50.0 
        impulse = (dx * scale, dy * scale)
        
        for b in self.balls:
            b.activate()
            b.apply_impulse_at_local_point(impulse)
            
        logger.info(f"NUDGE Applied: {impulse}")

    def set_tilt(self, tilted):
        """Set tilt state."""
        self.is_tilted = tilted
        if tilted:
            # Disable flippers immediately
            for side in ['left', 'right']:
                self.actuate_flipper(side, False) # Pass False to deactivate

    def _add_static_triangle(self, p1, p2, p3):
        """Add a static triangular shape to the space."""
        body = self.space.static_body
        verts = [p1, p2, p3]
        shape = pymunk.Poly(body, verts)
        shape.elasticity = 0.5
        shape.friction = 0.5
        shape.collision_type = COLLISION_TYPE_WALL
        self.space.add(shape)
        return shape

    def launch_plunger(self):
        # Find ball in plunger lane
        # Lane wall is at 0.75*width, ball should be right of that
        lane_x = self.width * 0.75
        
        launched = False
        for b in self.balls:
            if b.position.x > lane_x and b.position.y > self.height * 0.5:
                # Apply upward impulse with angle
                # Reduced from -15000 to -1000 to prevent tunneling (v ~ 1000 px/s)
                speed = 1000 * b.mass
                angle_rad = np.radians(self.launch_angle)
                
                # 0 degrees = Straight Up (0, -1)
                # Positive angle = Right (sin > 0)
                # Negative angle = Left (sin < 0)
                impulse_x = speed * np.sin(angle_rad)
                impulse_y = -speed * np.cos(angle_rad)
                
                impulse = (impulse_x, impulse_y) 
                b.activate() # Force wake up
                b.apply_impulse_at_local_point(impulse)
                launched = True
                logger.info(f"PLUNGER LAUNCH! Angle: {self.launch_angle}°, Impulse: {impulse}, Pos: {b.position}, Vel: {b.velocity}")
        
        return launched

    def update(self, dt):
        # Remove lost balls (below height + margin)
        # Iterate copy to modify list
        for b in self.balls[:]:
            if b.position.y > self.height + 100:
                self.space.remove(b, *b.shapes)
                self.balls.remove(b)
                
        # Update Flipper Physics (Kinematic rotation)
        # Use dynamic speed (default 30.0)
        flipper_speed = self.flipper_speed 
        
        # Update Plunger
        self._update_plunger(dt)
        self._update_left_plunger(dt)
        
        # Configurable angles (degrees)
        rest_angle = -30 # Down
        up_angle = 30    # Up
        
        # Convert to radians
        # Left: Rest is +30 (down-right), Up is -30 (up-right)?
        # Coordinate system: Y down.
        # 0 is Right.
        # +Angle is Clockwise (Down).
        # So Rest (+30) is Down-Right.
        # Up (-30) is Up-Right.
        
        l_rest = np.radians(30)  # Down-Right (Positive angle for Down on Left Flipper)
        l_up = np.radians(-30)   # Up-Right
        
        r_rest = np.radians(-30) # Down-Left (Symmetric to Left)
        r_up = np.radians(30)    # Up-Left (Symmetric to Left)
        
        # Actuation logic
        for side, flipper in self.flippers.items():

            if side == 'upper': continue
            self._update_single_flipper(flipper, dt, l_rest, l_up, r_rest, r_up)
                
        # Sub-stepping for stability (Prevent tunneling)
        steps = 5
        sub_dt = dt / steps
        for _ in range(steps):
            self.space.step(sub_dt)
            
        # Debug Log
        if self.balls and np.random.random() < 0.02: # ~2% chance
            b = self.balls[0]
            logger.debug(f"Ball Pos: {b.position}, Vel: {b.velocity}")

    def _update_single_flipper(self, flipper, dt, l_rest, l_up, r_rest, r_up):
        body = flipper['body']
        side = flipper['side']
        
        target = 0
        if side == 'left':
            target = l_up if flipper.get('active') else l_rest
        else:
            # Right
            target = r_up if flipper.get('active') else r_rest

        # Debug Log
        if np.random.random() < 0.01:
             logger.debug(f"Phys Flip: Side={side}, Active={flipper.get('active')}, Target={np.degrees(target):.1f}, Current={np.degrees(body.angle):.1f}")

        # Simple P-controller for angle
        current = body.angle
        diff = target - current
        
        # Limit speed
        max_speed = 15.0 * dt
        change = np.clip(diff, -max_speed, max_speed)
        
        # For Kinematic bodies, we set velocity and let the simulation move it.
        # This ensures collisions are handled correctly.
        # If we manually set angle AND velocity, it moves twice (once manually, once by step).
        # body.angle += change # REMOVED
        body.angular_velocity = change / dt

    def actuate_flipper(self, side, active):
        if self.is_tilted:
            return # Flippers disabled during tilt
            
        if side in self.flippers:
            self.flippers[side]['active'] = active
        elif side == 'upper':
             # Activate all upper flippers?
             for f in self.flippers['upper']:
                 f['active'] = active

    def get_state(self):
        # Return state dict for frontend
        ball_data = []
        for b in self.balls:
            # Normalize to 0-1
            nx = b.position.x / self.width
            ny = b.position.y / self.height
            ball_data.append({'x': nx, 'y': ny, 'vx': b.velocity.x, 'vy': b.velocity.y})
            
        flipper_data = {
            'left_angle': np.degrees(self.flippers['left']['body'].angle),
            'right_angle': np.degrees(self.flippers['right']['body'].angle),
            'upper_angles': [np.degrees(f['body'].angle) for f in self.flippers['upper']]
        }
        
        plunger_data = {
            'y': self.plunger_body.position.y if hasattr(self, 'plunger_body') else 0,
            'state': getattr(self, 'plunger_state', 'resting')
        }
        
        left_plunger_data = {
            'y': self.left_plunger_body.position.y if hasattr(self, 'left_plunger_body') else 0,
            'state': getattr(self, 'left_plunger_state', 'resting')
        }
        
        return {
            'balls': ball_data,
            'flippers': flipper_data,
            'plunger': plunger_data,
            'left_plunger': left_plunger_data
        }
