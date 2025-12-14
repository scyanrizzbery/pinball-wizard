import logging
import time
import threading
import hashlib
import random

import pymunk
import numpy as np

from pbwizard.config import PhysicsConfig


logger = logging.getLogger(__name__)


# Collision type constants (must be integers for pymunk)
COLLISION_TYPE_BALL = 1
COLLISION_TYPE_WALL = 2
COLLISION_TYPE_FLIPPER = 3
COLLISION_TYPE_BUMPER = 4
COLLISION_TYPE_DROP_TARGET = 5
COLLISION_TYPE_PLUNGER = 6
COLLISION_TYPE_LEFT_PLUNGER = 7
COLLISION_TYPE_RAIL = 8
COLLISION_TYPE_MOTHERSHIP = 9

# Mapping for logging
COLLISION_LABELS = {
    1: "ball",
    2: "wall",
    3: "flipper",
    4: "bumper",
    5: "drop_target",
    6: "plunger_stop",
    7: "left_plunger",
    8: "rail",
    9: "mothership"
}


class Physics:

    def _layout_to_world(self, x_norm: float, y_norm: float) -> tuple[float, float]:
        px = x_norm * self.width
        # Use consistent Y mapping (downward-positive) matching other geometry
        # Previously this inverted Y with (1.0 - y_norm) * height, which mirrored rails.
        py = y_norm * self.height
        return px, py

    def _clear_rail_shapes(self):
        for s in getattr(self, "rail_shapes", []):
            try:
                self.space.remove(s)
            except Exception:
                pass
        self.rail_shapes = []

    def _create_thick_line_poly(self, p1, p2, thickness):
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = np.hypot(dx, dy)
        if length == 0:
            return []
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        r = thickness / 2.0
        return [
            (p1[0] + px * r, p1[1] + py * r),
            (p2[0] + px * r, p2[1] + py * r),
            (p2[0] - px * r, p2[1] - py * r),
            (p1[0] - px * r, p1[1] - py * r),
        ]


class PymunkEngine(Physics):
    def __init__(self, layout, width, height, seed=None, config: PhysicsConfig = None):
        self.layout = layout
        
        # Initialize Config
        if config:
            self.config = config
        else:
            self.config = PhysicsConfig()
            # Try to load initial values from layout if present (legacy support / initial load)
            if hasattr(layout, 'physics_params') and layout.physics_params:
                self.config.update(layout.physics_params)

        # Deterministic Seeding
        if seed is None:
            # Generate a random seed if none provided (simulating "luck")
            seed = str(time.time_ns())
        self.seed = str(seed)
        
        # Initialize RNGs with seed
        # Use hashlib to create a robust integer seed from string
        seed_int = int(hashlib.sha256(self.seed.encode('utf-8')).hexdigest(), 16) % (2**32)
        self.rng = random.Random(seed_int)
        np.random.seed(seed_int)
        
        # Generate Game Hash (Seed + Layout Name + Config Hash)
        # This is what ensures the "Game" is unique
        config_hash = self.config.get_hash()
        layout_name = layout.name if hasattr(layout, 'name') else 'custom'
        self.game_hash = hashlib.sha256((f"{self.seed}_{layout_name}_{config_hash}").encode('utf-8')).hexdigest()[:16]
        logger.info(f"Physics Initialized. Seed: {self.seed}, Game Hash: {self.game_hash}, Config Hash: {config_hash}")

        self.width = width
        self.height = height
        
        # Physics Space
        self.space = pymunk.Space()

        # Apply initial physics settings from config
        self._update_gravity()  # Set initial gravity based on tilt
        
        # Legacy attribute support (properties could be better but sticking to direct access for now where possible or redirecting)
        # To avoid breaking extensive external access immediately, we might want properties or just update usages.
        # Given the task is to "remove hasattr stuff in vision.py to a solid interface", using self.config explicit is better.
        

        
        self.balls = []
        self.flippers = {}
        self.bumper_states = [] # List of flash timers (0.0 to 1.0)
        self.bumper_health = [] # List of health values (0 to 100)
        self.bumper_respawn_timers = [] # List of respawn timers (0.0 means active)
        self.bumper_shape_map = {} # Map shape to index
        self.drop_target_states = [] # List of drop target states (True = up, False = down)
        self.drop_target_shape_map = {} # Map shape to index
        self.score = 0  # Track score in physics engine
        
        self.is_tilted = False # Track tilt state
        self.tilt_value = 0.0 # Analog tilt value (accumulates with nudges)
        self.drop_target_shapes = [] # Track drop target shapes for removal
        
        # Combo System (State) - Config is in self.config
        self.combo_count = 0
        self.combo_timer = 0.0
        self.last_hit_time = 0.0
        self.score_multiplier = 1.0
        
        # Rail tracking
        self.rail_shapes = []
        
        # Event tracking for RL
        self.events = []
        
        # Simulation Time (Deterministic Replacement for time.time())
        self.simulation_time = 0.0
        
        # Mothership State
        
        # Mothership State
        self.mothership_active = False
        self.mothership_body = None
        self.mothership_shape = None
        self.mothership_health = 0
        self.mothership_max_health = 500
        
        self.lock = threading.RLock()
        self._is_stepping = False
        
        self._setup_static_geometry()
        self._setup_flippers()
        self._setup_collision_logging()


    @property
    def auto_plunge_enabled(self):
        """Proxy to config value."""
        return self.config.auto_plunge_enabled

    @auto_plunge_enabled.setter
    def auto_plunge_enabled(self, value):
        self.config.auto_plunge_enabled = value
        
    def apply_config_changes(self):
        """Apply any changes made to the configuration."""
        self._update_gravity()
        self._update_materials()
        self._rebuild_flippers()
        self._rebuild_rails()

    def _update_materials(self):
        """Update friction, restitution, and mass for existing shapes/bodies."""
        # Update generic static walls/shapes if needed? 
        # Usually walls have their own friction/elasticity, but we can override if using global defaults.
        # For now, let's assume we want to update everything to match current config globals if reasonable.
        # Or at least the BALLS.
        
        for ball in self.balls:
            # Update Mass
            ball.mass = self.config.ball_mass
            
            # Update Shapes (Friction/Restitution)
            for shape in ball.shapes:
                shape.friction = self.config.friction
                shape.elasticity = self.config.restitution
                
        logger.info(f"Updated materials: friction={self.config.friction}, restitution={self.config.restitution}, ball_mass={self.config.ball_mass}")

    def _update_gravity(self):
        """Update the gravity vector based on the table tilt angle (pitch)."""
        angle_rad = np.radians(self.config.table_tilt)
        # Gravity acts down the slope (Y-axis).
        # We assume X-axis is level (no roll).
        gravity_x = 0
        gravity_y = self.config.gravity_magnitude * np.sin(angle_rad)
        self.space.gravity = (gravity_x, gravity_y)
        logger.info(f"Gravity updated: tilt={self.config.table_tilt}°, vector=({gravity_x:.1f}, {gravity_y:.1f})")

    def _setup_collision_logging(self):
        """Setup collision handlers to log what ball hits and award scores"""
        # Score values for different features
        SCORE_VALUES = {
            COLLISION_TYPE_BUMPER: 10,
            COLLISION_TYPE_DROP_TARGET: 500,

            COLLISION_TYPE_MOTHERSHIP: 50
        }
        
        # Setup collision handler - API changed in pymunk 7.x
        handler = None
        try:
            # Pymunk 6.x API
            handler = self.space.add_default_collision_handler()
            logger.info("Using pymunk 6.x collision handler API")
        except AttributeError:
            # Pymunk 7.x API or fallback - use wildcard handler for BALLS
            # Since all scoring events involve a ball, this covers our needs.
            try:
                handler = self.space.add_wildcard_collision_handler(COLLISION_TYPE_BALL)
                logger.info("Using pymunk wildcard collision handler for BALL")
            except Exception as e:
                import pymunk
                logger.error(f"Pymunk version {pymunk.version}: Could not set up collision handler: {e}")
                
        # --- Specific Handler for Plunger Launch ---

        # Add specific handler for Ball <-> Plunger to fix "swimming" physics
        try:
             h = self.space.add_collision_handler(COLLISION_TYPE_BALL, COLLISION_TYPE_PLUNGER)
             def plunger_handler(arbiter, space, data):
                 # Only apply impulse if plunger is FIRING
                 if self.plunger_state in ['firing', 'releasing']:
                     ball_body = arbiter.shapes[0].body
                     
                     # Calculate impulse vector based on launch_angle
                     angle_deg = getattr(self.config, 'launch_angle', 0.0)
                     angle_rad = np.radians(angle_deg)
                     speed = self.config.plunger_release_speed
                     
                     vel_x = speed * np.sin(angle_rad) # Right is +X
                     vel_y = -speed * np.cos(angle_rad) # Up is -Y
                     
                     # Apply direct velocity setting for cleaner launch (avoids physics jitter)
                     ball_body.velocity = (vel_x, vel_y)
                     ball_body.angular_velocity = 0 # Stop spin for clean launch
                     
                     return False # Ignore physical collision to prevent "pushing" conflict
                     
                 return True
             # Use pre_solve instead of begin, because ball is often ALREADY touching plunger when it fires
             h.pre_solve = plunger_handler
             logger.info("Added specific plunger collision handler (pre_solve)")
        except Exception as e:
             logger.error(f"Failed to add plunger handler: {e}")

        
        if handler is None:
            logger.error("Failed to create collision handler")
            return

        def begin_collision(arbiter, space, data):
            shapes = arbiter.shapes
            type_a = shapes[0].collision_type
            type_b = shapes[1].collision_type
            
            # log every collision for debugging
            # logger.info(f"DEBUG: Collision {type_a} <-> {type_b}")

            if type_a == COLLISION_TYPE_BALL or type_b == COLLISION_TYPE_BALL:
                other = type_b if type_a == COLLISION_TYPE_BALL else type_a
                label = COLLISION_LABELS.get(other, f"unknown({other})")
                
                # Debug logging for bumper
                if other == COLLISION_TYPE_BUMPER:
                    logger.debug(f"DEBUG: Ball hit BUMPER! Label={label}")
                
                # Award score for certain collision types
                score_value = SCORE_VALUES.get(other, 0)
                
                # Record event for RL and Sound

                if score_value > 0:
                    # Combo detection - check if this is a scoring hit
                    current_time = self.simulation_time
                    time_since_last_hit = current_time - self.last_hit_time
                    
                    # Combo logic: consecutive hits within combo_window
                    if self.combo_count > 0 and time_since_last_hit <= self.config.combo_window:
                        # Extend existing combo
                        self.combo_count += 1
                        self.combo_timer = self.config.combo_window  # Reset timer
                        logger.debug(f"COMBO x{self.combo_count}! Time since last: {time_since_last_hit:.2f}s")
                    else:
                        # Start new combo (either first hit ever, or combo expired)
                        if self.combo_count == 0 or time_since_last_hit > self.config.combo_window:
                            logger.debug(f"Starting new combo chain (prev: {self.combo_count}, time: {time_since_last_hit:.2f}s)")
                        self.combo_count = 1
                        self.combo_timer = self.config.combo_window
                    
                    self.last_hit_time = current_time
                    
                    # Calculate multiplier based on combo
                    sim_multiplier = 1.0
                    if self.config.combo_multiplier_enabled and self.combo_count > 1:
                        sim_multiplier = float(self.combo_count)
                    
                    # Multiball Bonus: 2x Multiplier if more than 1 ball is in play
                    if len(self.balls) > 1:
                        sim_multiplier *= 2.0
                        
                    self.score_multiplier = min(
                        sim_multiplier, 
                        self.config.multiplier_max
                    )
                    
                    # Apply multiplier to score
                    final_score = int(score_value * self.score_multiplier)
                    self.score += final_score
                    
                    # Award combo bonus for maintaining chains
                    if self.combo_count > 2:
                        combo_bonus = self.config.base_combo_bonus * (self.combo_count - 1)
                        self.score += combo_bonus
                        logger.debug(f"Combo bonus: +{combo_bonus} points")
                    
                    if self.score_multiplier > 1.0:
                        logger.debug(f"BALL COLLISION: hit {label} (+{score_value} x{self.score_multiplier:.1f} = {final_score} points, total: {self.score})")
                    else:
                        logger.debug(f"BALL COLLISION: hit {label} (+{score_value} points, total: {self.score})")
                    
                    # Flash Bumper if hit and apply deflection force
                    if other == COLLISION_TYPE_BUMPER:
                        bumper_shape = shapes[0] if type_a == COLLISION_TYPE_BUMPER else shapes[1]
                        ball_shape = shapes[0] if type_a == COLLISION_TYPE_BALL else shapes[1]

                        if bumper_shape in self.bumper_shape_map:
                            idx = self.bumper_shape_map[bumper_shape]
                            self.bumper_states[idx] = 1.0
                            
                            # Decrease Bumper Health
                            if idx < len(self.bumper_health):
                                # Scale damage by score multiplier (higher combo = more damage)
                                base_damage = 10
                                damage = base_damage * (self.score_multiplier if self.score_multiplier >= 1.0 else 1.0)
                                self.bumper_health[idx] = max(0, self.bumper_health[idx] - damage)
                                logger.debug(f"Bumper {idx} hit! Health: {self.bumper_health[idx]}")
                                
                                if self.bumper_health[idx] <= 0:
                                    # Destroy Bumper
                                    # Set respawn timer from config
                                    respawn_time = getattr(self.config, 'bumper_respawn_time', 10.0)
                                    self.bumper_respawn_timers[idx] = respawn_time
                                    self.space.remove(bumper_shape)
                                    logger.info(f"Bumper {idx} destroyed! Respawning in {respawn_time}s")
                                    
                                    # Check if all bumpers are destroyed
                                    # Logic: If all bumpers have health <= 0, then we might summon mothership.
                                    # BUT: Mothership only spawns if they are ALL down at the same time.
                                    # This check is better done in the update loop where we manage timers.
                                    pass

                            # Apply active deflection force (like a real pinball bumper)
                            ball_body = ball_shape.body
                            bumper_pos = bumper_shape.body.position
                            ball_pos = ball_body.position

                            # Calculate direction from bumper to ball
                            dx = ball_pos.x - bumper_pos.x
                            dy = ball_pos.y - bumper_pos.y
                            distance = np.hypot(dx, dy)

                            if distance > 0:
                                # Normalize direction
                                dx /= distance
                                dy /= distance


                                # Apply impulse force (adjustable strength)
                                bumper_force = self.config.bumper_force
                                impulse_x = dx * bumper_force
                                impulse_y = dy * bumper_force

                                # Apply impulse at contact point for realistic physics
                                ball_body.apply_impulse_at_world_point(
                                    (impulse_x, impulse_y),
                                    ball_pos
                                )
                                logger.debug(f"Bumper {idx} deflected ball with force {bumper_force}")
                                
                    if other == COLLISION_TYPE_MOTHERSHIP:
                         old_health = self.mothership_health
                         self.mothership_health -= (10 * self.score_multiplier)
                         logger.info(f"👽 Mothership HIT! Health: {old_health} -> {self.mothership_health} (Max: {self.mothership_max_health})")
                         
                         if self.mothership_health <= 0:
                             logger.info("💥 MOTHERSHIP DESTROYED! 💥")
                             # Award massive bonus
                             bonus = 50000 * self.score_multiplier
                             self.score += int(bonus)
                             final_score += int(bonus)
                             
                             # Clean up physics body safe - Use UNIQUE KEY
                             self.space.add_post_step_callback(self._remove_mothership_safe, "remove_ms")
                             
                             # Reset all bumpers to active - Use UNIQUE KEY
                             self.space.add_post_step_callback(self._reset_bumpers_safe, "reset_bumpers")
                             
                             # Start Multiball (add 2 balls)
                             for _ in range(2):
                                 lane_x = self.width * (0.9 + self.rng.uniform(-0.02, 0.02))
                                 lane_y = self.height * 0.5
                                 self.add_ball((lane_x, lane_y))
                                 
                             self.events.append({
                                'type': 'mothership_destroyed',
                                'score': int(bonus),
                                'total_score': self.score
                             })
                             
                             # Destroy Shake
                             self.events.append({
                                 'type': 'nudge',
                                 'direction': {'x': 0, 'y': 0}, # Omni-directional shake
                                 'time': self.simulation_time,
                                 'intensity': 2.0 # Strong shake
                             })

                         else:
                             # Default hit event for shake
                             # If not destroyed, still shake a bit
                             self.events.append({
                                 'type': 'nudge', # Reuse nudge/shake logic
                                 'direction': {'x': 0, 'y': 0},
                                 'time': self.simulation_time,
                                 'intensity': 0.5 # Small shake
                             })
                    # Handle Drop Target if hit
                    if other == COLLISION_TYPE_DROP_TARGET:
                        # Check global bank cooldown (prevents instant re-trigger if ball trapped)
                        if getattr(self, 'drop_target_timer', 0) > 0:
                            return True

                        drop_target_shape = shapes[0] if type_a == COLLISION_TYPE_DROP_TARGET else shapes[1]
                        if drop_target_shape in self.drop_target_shape_map:
                            idx = self.drop_target_shape_map[drop_target_shape]
                            if idx < len(self.drop_target_states) and self.drop_target_states[idx]:
                                # Mark as hit (down)
                                self.drop_target_states[idx] = False
                                logger.info(f"🎯 Drop target {idx} HIT! State changed to False")
                                # Remove safely using post-step callback
                                self.space.add_post_step_callback(self._remove_drop_target_safe, drop_target_shape)
                                logger.debug(f"Drop target {idx} hit! Scheduled for removal.")

                                # Check if all drop targets are now down
                                if len(self.drop_target_states) > 0 and all(not state for state in self.drop_target_states):
                                    # All drop targets hit! Trigger MULTIBALL!
                                    logger.info("🎯 All drop targets hit! MULTIBALL ACTIVATED! 🎉")
                                    # Reset targets physically and physically (Defer to post-step to be safe)
                                    self.space.add_post_step_callback(self._reset_drop_targets_safe, None)

                                    # Award bonus score (e.g., 10000 points for multiball activation)
                                    bonus_score = 10000 * self.score_multiplier
                                    self.score += int(bonus_score)
                                    final_score += int(bonus_score)

                                    # Add a new ball to plunger lane (multiball!), max 5 balls
                                    if len(self.balls) < 5:
                                        lane_x = self.width * 0.94
                                        # Random spacing to prevent overlap/explosion
                                        offset_y = self.rng.uniform(-40, 40)
                                        lane_y = (self.height * 0.9) + offset_y
                                        self.add_ball((lane_x, lane_y))
                                        logger.info(f"🎱 Multiball: Added ball #{len(self.balls)} to plunger lane at Y={lane_y:.1f}")
                                    else:
                                        logger.info("🎱 Multiball: Max balls reached, no new ball added.")

                                    # Log the multiball event
                                    self.events.append({
                                        'type': 'multiball_start',
                                        'score': int(bonus_score),
                                        'total_score': self.score,
                                        'combo_count': self.combo_count,
                                        'multiplier': self.score_multiplier,
                                        'ball_count': len(self.balls)
                                    })

                else:
                    logger.debug(f"BALL COLLISION: hit {label}")
                    final_score = 0

                # Record event for RL and Sound (AFTER updates)
                logger.debug(f"Physics: Creating event for collision: label={label}, score={final_score}, combo={self.combo_count}")
                self.events.append({
                    'type': 'collision',
                    'label': label,
                    'score': final_score,
                    'total_score': self.score,
                    'combo_count': self.combo_count,
                    'multiplier': self.score_multiplier
                })
                
                # Random deflection removed - was causing "swimming" ball motion

                # Ball touched plunger - no auto-launch, frontend controls this
                if other == COLLISION_TYPE_PLUNGER and self.plunger_state == 'resting':
                    logger.debug("Ball touched plunger while resting")

                # Auto-launch for left plunger (Kickback)
                if other == COLLISION_TYPE_LEFT_PLUNGER and self.left_plunger_state == 'resting':
                    logger.debug("Ball touched left plunger - KICKBACK")
                    self.fire_left_plunger()

            return True
        handler.begin = begin_collision

    def _setup_static_geometry(self):

        # Walls - Use high elasticity (0.9) so ball bounces off instead of sliding
        thickness = 10.0
        wall_elasticity = 0.9
        # Left
        self._add_static_segment((0, 0), (0, self.height), thickness=thickness, elasticity=wall_elasticity)
        # Right
        self._add_static_segment((self.width, 0), (self.width, self.height), thickness=thickness, elasticity=wall_elasticity)
        # Top
        self._add_static_segment((0, 0), (self.width, 0), thickness=thickness, elasticity=wall_elasticity)
        
        # Top Arch (Deflector from Plunger Lane to Playfield) - Right Side
        # From top-right (above plunger lane) to top-center
        # Plunger wall is at 0.85 width.
        # Arch should start at (width, 0.15 * height) and go to (0.6 * width, 0)
        p1 = (self.width, self.height * 0.15)
        p2 = (self.width * 0.6, 0)
        self._add_static_segment(p1, p2, thickness=thickness, elasticity=wall_elasticity)
        
        # Triangle Guide - Left Side (mirror of right arch)
        # From top-left corner to center-top area
        left_tri_p1 = (0, self.height * 0.15)  # Top-left, down slightly from corner
        left_tri_p2 = (self.width * 0.4, 0)     # Top-center area
        left_tri_p3 = (0, 0)                     # Top-left corner
        self._add_static_triangle(left_tri_p1, left_tri_p2, left_tri_p3)
            
        # Bumpers
        # Bumpers
        self.bumper_states = []
        self.bumper_health = []
        self.bumper_shape_map = {}
        for i, b in enumerate(self.layout.bumpers):
            pos = (b['x'] * self.width, b['y'] * self.height)
            radius = 20.0 # Pixels
            if 'radius_ratio' in b:
                radius = b['radius_ratio'] * self.width
            shape = self._add_static_circle(pos, radius, elasticity=1.5)
            self.bumper_states.append(0.0)
            self.bumper_health.append(100)
            self.bumper_respawn_timers.append(0.0)
            self.bumper_shape_map[shape] = i


        # Drop Targets
        self.drop_target_states = []
        self.drop_target_shape_map = {}
        logger.info(f"Creating {len(self.layout.drop_targets)} drop targets...")
        for i, t in enumerate(self.layout.drop_targets):
            x = t['x'] * self.width
            y = t['y'] * self.height
            w = t['width'] * self.width
            h = t['height'] * self.height
            cx = x + w/2
            cy = y + h/2
            shape = self._add_static_box((cx, cy), (w, h), elasticity=0.5, collision_type=COLLISION_TYPE_DROP_TARGET)
            self.drop_target_shapes.append(shape)
            self.drop_target_states.append(True)  # True = up/active
            self.drop_target_shape_map[shape] = i
            logger.info(f"Drop target {i} created at ({cx:.1f}, {cy:.1f}), size ({w:.1f}x{h:.1f}), state: {self.drop_target_states[i]}")
            
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
        
        self._setup_plunger()


        # Setup Slingshots (Triangular bumpers above flippers)

        self._setup_slingshots()

        # Setup Rails (as Polygons for robust collision)
        self._rebuild_rails()




    def _reset_drop_targets_safe(self, space, key):
        """Reset drop targets, suitable for post-step callback."""
        self.reset_drop_targets()
        return True

    def reset_drop_targets(self):
        """Reset all drop targets to the 'up' position."""
        logger.info("Resetting drop targets...")
        
        # 1. Remove any existing shapes to be safe (if not already removed)
        try:
            for shape in self.drop_target_shapes:
                if shape in self.space.shapes:
                    self.space.remove(shape)
                    logger.debug(f"Removed existing drop target shape from space")
        except Exception as e:
            logger.warning(f"Error clearing drop targets: {e}")
            
        self.drop_target_shapes = []
        self.drop_target_shape_map = {}
        self.drop_target_states = []
        
        # 2. Re-create all targets from layout
        for i, t in enumerate(self.layout.drop_targets):
            x = t['x'] * self.width
            y = t['y'] * self.height
            w = t['width'] * self.width
            h = t['height'] * self.height
            cx = x + w/2
            cy = y + h/2
            
            # Create fresh shape/body (using static body)
            shape = self._add_static_box((cx, cy), (w, h), elasticity=0.5, collision_type=COLLISION_TYPE_DROP_TARGET)
            
            self.drop_target_shapes.append(shape)
            self.drop_target_states.append(True)
            self.drop_target_shape_map[shape] = i
            
            # Verify shape was added to space
            if shape in self.space.shapes:
                logger.debug(f"Drop target {i} successfully added to physics space at ({cx:.1f}, {cy:.1f})")
            else:
                logger.error(f"Drop target {i} NOT in physics space after creation!")
            
        # Set Cooldown to prevent immediate re-trigger by trapped balls
        self.drop_target_timer = getattr(self.config, 'drop_target_cooldown', 2.0)
            
        logger.info(f"Reset {len(self.drop_target_shapes)} drop targets. Total shapes in space: {len(self.space.shapes)}")

    def _remove_drop_target_safe(self, space, shape):
        """Safely remove a drop target shape (called via post-step callback)."""
        if shape in space.shapes:
            space.remove(shape)
            logger.debug("Drop target shape removed from physics space.")
            return True
        return False

    def update_bumpers(self, bumpers_data):
        """Update bumper positions dynamically."""
        # Remove existing bumper shapes
        for shape in list(self.bumper_shape_map.keys()):
            self.space.remove(shape)
            
        self.bumper_states = []
        self.bumper_health = []
        self.bumper_respawn_timers = []
        self.bumper_shape_map = {}
        
        # Re-create bumpers
        for i, b in enumerate(bumpers_data):
            pos = (b['x'] * self.width, b['y'] * self.height)
            radius = 20.0
            shape = self._add_static_circle(pos, radius, elasticity=1.5)
            self.bumper_states.append(0.0)
            self.bumper_health.append(100)
            self.bumper_respawn_timers.append(0.0)
            self.bumper_shape_map[shape] = i


    def _handle_plunger_hit(self, arbiter, space, data):
        """Custom handler for plunger launch to fix 'swimming' physics."""
        # Only override if plunger is actively firing
        if self.plunger_state not in ['firing', 'releasing']:
            return True # Normal collision

        ball_shape = arbiter.shapes[0]
        ball_body = ball_shape.body
        
        # Calculate boost without overriding physics completely
        # Just help it along if it's too slow? 
        # Actually, let's trust the physics engine with better Material Properties (Elasticity).
        # Returning True enables normal collision response.
        
        # We can add a slight speed boost if needed, but let's try pure kinetic first.
        # But maybe ensure we don't have angular velocity messing it up.
        ball_body.angular_velocity *= 0.1 # Dampen spin significantly during launch
        
        return True # Enable physical collision (Kinetic transfer)

    def _setup_plunger(self):
        """Setup plunger physics bodies and shapes."""
        # Plunger Lane
        # Vertical wall separating plunger from playfield - high elasticity for bounce
        lane_x = self.width * 0.85
        # SHORTENED WALL: REMOVED entirely per user request to allow full launch freedom
        # self._add_static_segment((lane_x, self.height * 0.6), (lane_x, self.height), thickness=5.0, elasticity=0.9, friction=0.0)
        logger.info(f"Plunger Wall: REMOVED")

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
        base_shape.elasticity = 0.8 # High bounciness for kinetic transfer
        base_shape.friction = 0.0 # No friction to prevent 'grabbing'
        base_shape.collision_type = COLLISION_TYPE_PLUNGER
        
        # Lips to center the ball
        lip_w = 10.0
        lip_h = 20.0 # Stick up above base
        
        # Left Lip
        ll_x1 = -self.plunger_width/2
        ll_x2 = -self.plunger_width/2 + lip_w
        ll_y1 = -self.plunger_height/2 - lip_h
        ll_y2 = -self.plunger_height/2
        
        l_lip_verts = [(ll_x1, ll_y1), (ll_x2, ll_y1), (ll_x2, ll_y2), (ll_x1, ll_y2)]
        l_lip_shape = pymunk.Poly(self.plunger_body, l_lip_verts)
        l_lip_shape.elasticity = 0.5
        l_lip_shape.friction = 0.0
        l_lip_shape.collision_type = COLLISION_TYPE_PLUNGER

        # Right Lip
        rl_x1 = self.plunger_width/2 - lip_w
        rl_x2 = self.plunger_width/2
        rl_y1 = -self.plunger_height/2 - lip_h
        rl_y2 = -self.plunger_height/2
        
        r_lip_verts = [(rl_x1, rl_y1), (rl_x2, rl_y1), (rl_x2, rl_y2), (rl_x1, rl_y2)]
        r_lip_shape = pymunk.Poly(self.plunger_body, r_lip_verts)
        r_lip_shape.elasticity = 0.5
        r_lip_shape.friction = 0.0
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
        l_base_shape.friction = 0.01
        l_base_shape.collision_type = COLLISION_TYPE_LEFT_PLUNGER
        
        # Lips for Left Plunger
        # Re-use lip dimensions
        # Left Lip
        ll_l_lip_verts = [
            (ll_x1, ll_y1), (ll_x2, ll_y1), (ll_x2, ll_y2), (ll_x1, ll_y2)
        ]
        ll_l_lip_shape = pymunk.Poly(self.left_plunger_body, ll_l_lip_verts)
        ll_l_lip_shape.elasticity = 0.1
        ll_l_lip_shape.friction = 0.01
        ll_l_lip_shape.collision_type = COLLISION_TYPE_LEFT_PLUNGER
        
        # Right Lip
        ll_r_lip_verts = [
            (rl_x1, ll_y1), (rl_x2, ll_y1), (rl_x2, ll_y2), (rl_x1, rl_y2)
        ]
        ll_r_lip_shape = pymunk.Poly(self.left_plunger_body, ll_r_lip_verts)
        ll_r_lip_shape.elasticity = 0.1
        ll_r_lip_shape.friction = 0.01
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

    def fire_plunger(self):
        """Fire the plunger directly (instant activation like left plunger)."""
        self.plunger_state = 'firing'
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
        
        # Update Plunger Angle to match config
        angle_deg = getattr(self.config, 'launch_angle', 0.0)
        angle_rad = np.radians(angle_deg)
        # Note: Pymunk body angle is rotation. 0 = upright.
        # If we want the CUP to rotate, we set body.angle
        # Positive angle = Tilted Right.
        self.plunger_body.angle = -angle_rad # Invert for Pymunk coord system if needed?
        # Test: If angle=30 (Right), we want plunger to point right.
        # vector (sin(30), -cos(30)).
        # body.angle should rotate the shape.
        self.plunger_body.angle = angle_rad

        if self.plunger_state == 'firing' or self.plunger_state == 'releasing':
            # Move FAST upward (or along angle)
            speed = self.plunger_release_speed # Configurable speed
            
            # Calculate velocity vector
            vel_x = speed * np.sin(angle_rad)
            vel_y = -speed * np.cos(angle_rad) # UP is negative Y

            # Check limit based on Y position (simplification, assuming vertical travel dominates)
            # Ideally we should check distance from rest.
            # But 'target_pos_y' logic assumes vertical movement.
            # Let's keep Y-check for limit but apply angled velocity.
            
            if current_y > target_pos_y:
                # Move towards target
                # Note: We are manually setting position for Y, but X needs to move too?
                # KINEMATIC bodies move by velocity if step() is called.
                # But here we are manually lerping 'new_y'.
                # We should probably trust velocity for the impulse, but manually position for limits.
                
                new_y = current_y + vel_y * dt
                # Adjust X as well?
                current_x = self.plunger_body.position.x
                new_x = current_x + vel_x * dt
                
                if new_y < target_pos_y: # Overshot top
                    new_y = target_pos_y
                    # Resync X to center? X should be handled by limit logic.
                    # Just stop.
                    self.plunger_state = 'resting'
                    self.plunger_body.velocity = (0, 0)
                    # Force position to rest?
                    # self.plunger_body.position = (current_x, target_pos_y) 
                    # This might drift X. Ideally reset X to center of lane.
                    center_x = self.width * 0.955 # Center of lane
                    self.plunger_body.position = (center_x, target_pos_y)
                else:
                    self.plunger_body.position = (new_x, new_y)
                    self.plunger_body.velocity = (vel_x, vel_y)
            else:
                self.plunger_state = 'resting'
                self.plunger_body.velocity = (0, 0)
                center_x = self.width * 0.955
                self.plunger_body.position = (center_x, target_pos_y)
                    
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

    def _add_static_segment(self, p1, p2, thickness=1.0, elasticity=0.5, friction=0.01, collision_type=COLLISION_TYPE_WALL):
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape
        
    def _add_static_circle(self, pos, radius, elasticity=0.8, collision_type=COLLISION_TYPE_BUMPER):
        body = self.space.static_body
        shape = pymunk.Circle(body, radius, pos)
        shape.elasticity = elasticity
        shape.friction = 0.01
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape
    
    def _create_thick_line_poly(self, p1, p2, thickness):
        """Create a polygon representing a thick line between p1 and p2."""
        # Calculate direction vector
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = np.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return []
        
        # Unit vector along line
        ux = dx / length
        uy = dy / length
        
        # Perpendicular vector (rotate 90 degrees)
        px = -uy
        py = ux
        
        # Half thickness
        r = thickness / 2.0
        
        # Four corners (CCW winding)
        c1 = (p1[0] + px*r, p1[1] + py*r)  # Start + perp
        c2 = (p2[0] + px*r, p2[1] + py*r)  # End + perp
        c3 = (p2[0] - px*r, p2[1] - py*r)  # End - perp
        c4 = (p1[0] - px*r, p1[1] - py*r)  # Start - perp
        
        return [c1, c2, c3, c4]
        
    def _add_static_poly(self, vertices, elasticity=0.5, friction=0.01, collision_type=COLLISION_TYPE_WALL):
        """Add a static polygon to the physics space."""
        shape = pymunk.Poly(self.space.static_body, vertices)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape

    def _add_static_box(self, pos, size, elasticity=0.5, collision_type=COLLISION_TYPE_DROP_TARGET):
        """Add a static box shape at a specific position.

        NOTE: Previously this set shape.body.position = pos, which MODIFIED the
        shared static_body.position and caused all shapes attached to it to shift.
        Fixed by creating a box with vertices already at the correct position.
        """
        body = self.space.static_body
        # Create box vertices centered at pos, not at origin
        w, h = size
        half_w, half_h = w / 2, h / 2
        vertices = [
            (pos[0] - half_w, pos[1] - half_h),  # Top-Left
            (pos[0] - half_w, pos[1] + half_h),  # Bottom-Left
            (pos[0] + half_w, pos[1] + half_h),  # Bottom-Right
            (pos[0] + half_w, pos[1] - half_h),  # Top-Right
        ]
        shape = pymunk.Poly(body, vertices)
        shape.elasticity = elasticity
        shape.friction = 0.01
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape

    def _setup_slingshots(self):
        """Create triangular slingshot bumpers above the flippers."""
        # DISABLED: Slingshots were causing invisible collisions when bumpers removed
        # TODO: Make slingshots optional or tied to bumper existence in layout
        pass
        # # Left Slingshot
        # l_pivot_x = self.layout.left_flipper_x_min * self.width
        # l_pivot_y = self.layout.left_flipper_y_max * self.height
        # 
        # # Define triangle points relative to flipper pivot
        # # P1: Bottom-Left (near pivot)
        # # P2: Top-Right (Inner)
        # # P3: Top-Left (Outer/Inlane side)
        # 
        # # Offset slightly to the right of the pivot (since pivot is the heel)
        # l_p1 = (l_pivot_x + 25, l_pivot_y - 20)
        # l_p2 = (l_pivot_x + 70, l_pivot_y - 120)
        # l_p3 = (l_pivot_x + 25, l_pivot_y - 120)
        # 
        # self._add_static_triangle(l_p1, l_p2, l_p3, elasticity=1.5, collision_type=COLLISION_TYPE_BUMPER)
        # 
        # # Right Slingshot
        # r_pivot_x = self.layout.right_flipper_x_max * self.width
        # r_pivot_y = self.layout.right_flipper_y_max * self.height
        # 
        # # Mirror of Left
        # r_p1 = (r_pivot_x - 25, r_pivot_y - 20)
        # r_p2 = (r_pivot_x - 70, r_pivot_y - 120)
        # r_p3 = (r_pivot_x - 25, r_pivot_y - 120)
        # 
        # self._add_static_triangle(r_p1, r_pivot_y, r_p3, elasticity=1.5, collision_type=COLLISION_TYPE_BUMPER)

    def _setup_flippers(self):
        # Apply flipper spacing from config
        spacing = getattr(self.config, 'flipper_spacing', 0.0)
        
        # Left Flipper - pivot at BOTTOM-left to match visuals
        # Add spacing to move IT RIGHT (positive X)
        l_x = (self.layout.left_flipper_x_min + spacing) * self.width
        l_pivot = (l_x, self.layout.left_flipper_y_max * self.height)
        self.flippers['left'] = self._create_flipper(l_pivot, 'left')
        
        # Right Flipper - pivot at BOTTOM-right to match visuals
        # Subtract spacing to move IT LEFT (negative X)
        r_x = (self.layout.right_flipper_x_max - spacing) * self.width
        r_pivot = (r_x, self.layout.right_flipper_y_max * self.height)
        self.flippers['right'] = self._create_flipper(r_pivot, 'right')
        
        self.flippers['upper'] = []

    def update_flipper_spacing(self, spacing):
        """Update flipper spacing and rebuild flippers."""
        self.config.flipper_spacing = spacing
        self._rebuild_flippers()

    def update_flipper_length(self, length_ratio):
        """Update flipper length and rebuild flippers."""
        self.flipper_length_ratio = length_ratio
        self._rebuild_flippers()

    def update_flipper_width(self, width_ratio):
        """Update flipper width (thickness) and rebuild flippers."""
        self.flipper_width_ratio = width_ratio
        self._rebuild_flippers()

    def update_flipper_tip_width(self, width_ratio):
        """Update flipper tip width (thickness) and rebuild flippers."""
        self.flipper_tip_width_ratio = width_ratio
        self._rebuild_flippers()

    def update_flipper_elasticity(self, elasticity):
        """Update flipper elasticity and rebuild flippers."""
        self.flipper_elasticity = elasticity
        self._rebuild_flippers()

    def update_table_tilt(self, tilt_angle):
        """Update table tilt angle and recalculate gravity vector."""
        self.table_tilt = tilt_angle
        self._update_gravity()

    def _rebuild_flippers(self):
        """Remove and recreate flippers with current settings."""
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
        ratio = self.config.flipper_length
        length = self.width * ratio * length_scale 
        
        # Use stored width ratio or default (0.025 ~ 11px)
        width_ratio = self.config.flipper_width
        tip_width_ratio = self.config.flipper_tip_width # Default to base width if not set
        
        base_width = self.width * width_ratio
        tip_width = self.width * tip_width_ratio
        
        # Poly radius for smoothing (subtract from width to keep visual size accurate)
        poly_radius = 2.0
        
        base_radius = (base_width / 2.0) - poly_radius
        tip_radius = (tip_width / 2.0) - poly_radius
        
        if base_radius < 1.0: base_radius = 1.0
        if tip_radius < 1.0: tip_radius = 1.0

        if side == 'left':
            # Points Right [0, length]
            vertices = [
                (0, -base_radius),
                (0, base_radius),
                (length, tip_radius),
                (length, -tip_radius)
            ]
        else:
            # Points Left [-length, 0]
            vertices = [
                (0, -base_radius),
                (0, base_radius),
                (-length, tip_radius),
                (-length, -tip_radius)
            ]
            
        shape = pymunk.Poly(body, vertices, radius=poly_radius)
        shape.elasticity = self.config.flipper_elasticity
        shape.friction = self.config.flipper_friction
        shape.collision_type = COLLISION_TYPE_FLIPPER
        self.space.add(body, shape)
        
        return {
            'body': body,
            'shape': shape,
            'side': side,
            'angle': 0.0,
            'target_angle': 0.0
        }

    def reset_game(self):
        """Reset the physics engine state for a new game."""
        # 1. Clear Balls
        for b in self.balls[:]:
            self.remove_ball(b)
        self.balls = []
        self.active_balls = []
        
        # 2. Reset Score and Rules
        self.score = 0
        self.combo_count = 0
        self.combo_timer = 0.0
        self.multiplier = 1.0
        
        # 3. Reset Feature States
        self.bumper_states = [0.0] * len(self.layout.bumpers)
        self.bumper_health = [100] * len(self.layout.bumpers) # Reset to full health
        
        # Reset drop targets (recreates physics bodies)
        self.reset_drop_targets()
        
        # 4. Reset Kickbacks/Other
        self.kickback_cooldowns = {}
        
        # Reset Mothership
        if self.mothership_active:
             self._remove_mothership_immediate()
        
        logger.info("Physics Engine State Reset")

    def add_ball(self, pos):
        with self.lock:
            # Always use callback to ensure thread/step safety (bypass locking check issues)
            self.space.add_post_step_callback(self._add_ball_safe, pos)
            return None

    def _add_ball_safe(self, space, pos):
        """Internal method to add ball, safe to call from callback."""
        # Check if we're in the middle of a reset (ignore old callbacks)
        if getattr(self, '_resetting', False):
            logger.debug("Ignoring add_ball callback during reset")
            return

        # User Request Fix: A tilt should only cost a ball, not the game.
        # Reset tilt state when a new ball is spawned so the new ball is playable.
        if self.is_tilted:
            self.is_tilted = False
            self.tilt_value = 0.0
            logger.info("Tilt Reset for new ball.")

        pos = tuple(pos) # Ensure tuple
        
        # Check max balls limit
        if len(self.balls) >= 5:
            # Check if any balls are "dead" / NaN
            self.balls = [b for b in self.balls if not np.isnan(b.position.x)]
            
            if len(self.balls) >= 10:
                logger.warning(f"Max balls (10) reached, ignoring add_ball request.")
                return None
            
        mass = self.config.ball_mass
        radius = self.config.ball_radius if hasattr(self.config, 'ball_radius') else 12.0
        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)
        body.position = pos
        shape = pymunk.Circle(body, radius)
        shape.elasticity = self.config.restitution
        shape.friction = self.config.friction
        shape.collision_type = COLLISION_TYPE_BALL
        self.space.add(body, shape)
        self.balls.append(body)
        return body

    def remove_ball(self, ball):
        """Remove a ball from the physics space and tracking list."""
        if ball in self.balls:
            # Check if b has shapes attached (our custom monkey-patch)
            if hasattr(ball, 'shapes'):
                self.space.remove(ball, *ball.shapes)
            else:
                # Fallback: remove body, but might leave phantom shapes?
                # Pymunk doesn't easily let us find shapes for a body without iterating.
                self.space.remove(ball)
                
            self.balls.remove(ball)
            logger.debug(f"Ball removed: {ball.position}")

    def nudge(self, dx, dy, check_tilt=True):
        """Apply an impulse to all balls to simulate a table nudge."""
        with self.lock:
            # Nudging the table moves the table under the ball.
            # Relative to the table, the ball moves in the opposite direction of the nudge?
            # No, if I push the table LEFT, the ball (due to inertia) effectively moves RIGHT relative to the table.
            # But usually "Nudge Left" means "I want the ball to go Left".
            # So let's just apply impulse in the direction of dx, dy.
            # Scale up for physics engine (vision used small pixels)
            scale = 400.0  # Increased from 50.0 to 400.0 for effectiveness
            
            # User Request: "nudge left moves ... opposite direction"
            # Inverting sign of impulse to match requested direction.
            impulse = (-dx * scale, -dy * scale)
            
            # Accumulate Tilt
            if check_tilt and hasattr(self.config, 'nudge_cost'):
                self.tilt_value += self.config.nudge_cost
                
            # Check Threshold
            threshold = getattr(self.config, 'tilt_threshold', 10.0)
            if self.tilt_value > threshold:
                if not self.is_tilted:
                    logger.warning(f"TILT! Value {self.tilt_value:.1f} > {threshold}")
                    self.set_tilt(True)
            else:
                # Just a warning?
                pass
            
            for b in self.balls:
                b.activate()
                b.apply_impulse_at_local_point(impulse)
                
            logger.info(f"NUDGE Applied: {impulse}")

    def set_tilt(self, tilted):
        """Set tilt state."""
        self.is_tilted = tilted
        if tilted:
            # Disable flippers immediately
            for side in ['left', 'right', 'upper']:
                self.actuate_flipper(side, False) # Pass False to deactivate

    def _add_static_triangle(self, p1, p2, p3, elasticity=0.5, collision_type=COLLISION_TYPE_WALL):
        """Add a static triangular shape to the space."""
        body = self.space.static_body
        verts = [p1, p2, p3]
        shape = pymunk.Poly(body, verts)
        shape.elasticity = elasticity
        shape.friction = 0.01
        shape.collision_type = collision_type
        self.space.add(shape)
        return shape

    def launch_plunger(self):
        # Cooldown check (0.5s)
        current_time = self.simulation_time
        if hasattr(self, 'last_launch_time') and current_time - self.last_launch_time < 0.5:
            return False
            
        # Find ball in plunger lane
        # Lane wall is at 0.75*width, ball should be right of that
        lane_x = self.width * 0.75
        
        launched = False
        for b in self.balls:
            if b.position.x > lane_x and b.position.y > self.height * 0.5:
                # Calculate launch velocity based on angle
                # Increase base speed to ensure ball clears the lane (Fix for immediate drains)
                base_speed = self.config.plunger_release_speed * 1.5
                angle_rad = np.radians(self.config.launch_angle)
                
                # 0 degrees = Straight Up (0, -1)
                # Positive angle = Right (sin > 0)
                # Negative angle = Left (sin < 0)
                vel_x = base_speed * np.sin(angle_rad)
                vel_y = -base_speed * np.cos(angle_rad)
                
                # Launch from current position - let ball travel naturally
                b.activate()
                b.velocity = (vel_x, vel_y)
                
                launched = True
                self.last_launch_time = current_time
                logger.info(f"Launch plunger: angle={self.config.launch_angle}°, velocity=({vel_x:.1f}, {vel_y:.1f})")
        
        return launched

    def get_events(self):
        """Return and clear recent events."""
        events = self.events[:]
        self.events.clear()
        return events

    def update_bumpers(self, bumpers_data):
        """Update physics bumpers to match new layout data."""
        # 1. Remove old bumpers
        if hasattr(self, 'bumper_shape_map'):
            for shape in self.bumper_shape_map.keys():
                self.space.remove(shape)
                # Note: Static bodies generally aren't removed/recreated for each shape, 
                # but we used self.space.static_body so we don't remove the body.
        
        # 2. Update layout reference (optional, but good for consistency)
        self.layout.bumpers = bumpers_data
        
        # 3. Recreate Bumpers
        self.bumper_states = []
        self.bumper_shape_map = {}
        
        for i, b in enumerate(bumpers_data):
            pos = (b['x'] * self.width, b['y'] * self.height)
            radius = 20.0 # Pixels (Make sure this matches init)
            if 'radius_ratio' in b:
                radius = b['radius_ratio'] * self.width
            
            shape = self._add_static_circle(pos, radius, elasticity=1.5)
            self.bumper_states.append(0.0)
            self.bumper_shape_map[shape] = i
        
        logger.info(f"Updated physics bumpers: {len(bumpers_data)} bumpers active")

    def reset(self):
        # To truly clear pending callbacks and state, it's safer to recreate the space
        # IF we can re-setup everything quickly.
        # But we already remove all shapes/bodies.
        # Pymunk doesn't have a public API to clear callbacks.
        # However, _add_ball_safe checks max limit.
        
        # Clear existing objects
        logger.info(f"Reset: Clearing space. Balls before: {len(self.balls)}")
        for shape in self.space.shapes:
            self.space.remove(shape)
        for body in self.space.bodies:
            self.space.remove(body)
        for constraint in self.space.constraints:
            self.space.remove(constraint)
            
        # Pymunk does not expose a way to clear post_step_callbacks directly
        # But we can try to clear them if possible, or just rely on robust callback logic.
        # Best way: Recreate space? No, expensive.
        # We will add a 'resetting' flag that callbacks can check.
        self._resetting = True
        
        # Re-initialize static geometry (includes drop targets, bumpers, plunger, walls)
        self._setup_static_geometry()
        self._setup_flippers()
        self._setup_collision_logging()
        
        self._setup_collision_logging()
        
        # Reset game state variables
        self.simulation_time = 0.0 # Reset simulation time
        self.balls = []
        self.active_balls = [] # Clear active ball references
        self.score = 0
        self.tilt_value = 0.0
        self.is_tilted = False
        self.bumper_states = [0.0] * len(self.layout.bumpers)
        self.drop_target_states = [True] * len(self.layout.drop_targets)
        self.drop_target_timer = 0.0
        self.combo_count = 0 
        self.combo_timer = 0.0
        self.score_multiplier = 1.0
        
        self.mothership_active = False
        self.mothership_body = None
        self.mothership_shape = None
        self.mothership_health = 0
        
        self._resetting = False
        
        # Add the initial ball *after* reset, using the same callback mechanism
        self.space.add_post_step_callback(self._add_ball_safe, (self.width * 0.93, self.height * 0.8)) # Plunger lane
        
        logger.info("Physics engine reset and initial ball added via callback.")

    def update(self, dt):
        with self.lock:
            # Update Simulation Time
            self.simulation_time += dt

            # Update bumper flash timers
            for i in range(len(self.bumper_states)):
                if self.bumper_states[i] > 0:
                    self.bumper_states[i] -= dt * 5.0 # Decay speed
                    if self.bumper_states[i] < 0:
                        self.bumper_states[i] = 0.0
                        
            # Update bumper respawn timers
        if self.bumper_respawn_timers:
            active_bumpers_count = 0
            
            for i in range(len(self.bumper_respawn_timers)):
                if self.bumper_respawn_timers[i] > 0:
                    # Bumper is dead/respawning
                    # Only decrement timer if Mothership is NOT active
                    if not self.mothership_active:
                        self.bumper_respawn_timers[i] -= dt
                    
                    if self.bumper_respawn_timers[i] <= 0:
                        # Respawn Bumper
                        self.bumper_respawn_timers[i] = 0.0
                        self.bumper_health[i] = 100
                        
                        # Find shape and add back to space
                        for shape, idx in self.bumper_shape_map.items():
                            if idx == i:
                                if shape not in self.space.shapes:
                                    self.space.add(shape)
                                    logger.info(f"Bumper {i} respawned!")
                                break
                        
                        # It is now active
                        active_bumpers_count += 1
                else:
                    # Bumper is active (timer <= 0)
                    active_bumpers_count += 1
            
            # Check for Mothership Spawn Condition
            # Mothership spawns if NO bumpers are active (count == 0) AND we have bumpers at all
            if active_bumpers_count == 0 and len(self.bumper_respawn_timers) > 0 and not self.mothership_active:
                if hasattr(self, 'spawn_mothership'):
                     self.spawn_mothership()
        # Tilt Decay
        if self.tilt_value > 0:
            decay_rate = getattr(self.config, 'tilt_decay', 0.1) * 60.0 # Config usually small per frame?
            # Or if config is per second, we multiply by dt?
            # Existing comments said tilt_decay=0.03.
            # If 0.03 per frame?
            decay = decay_rate * dt
            self.tilt_value -= max(0.01, decay) # Ensure some decay
            if self.tilt_value < 0:
                self.tilt_value = 0.0
        
        # Handle drop target removal
        for i, is_up in enumerate(self.drop_target_states):
            if not is_up and i < len(self.drop_target_shapes):
                shape = self.drop_target_shapes[i]
                if shape in self.space.shapes:
                    self.space.remove(shape)
                    logger.debug(f"Removed drop target {i} shape from physics space")

        # Update combo timer
        self.update_combo_timer(dt)
        
        # Consolidate ball status checks (Drain, Stuck, Out of Bounds)
        # This function now handles removal, so we don't do it here.
        # But we need to ensure it's called. It's called below.
        
        # Check for stuck balls (and now DRAIN logic too)
        self.check_stuck_ball(dt)
                
        # Update Flipper Physics (Kinematic rotation)
        # Use dynamic speed (default 30.0)
        flipper_speed = self.config.flipper_speed 
        
        # Update Plunger
        self._update_plunger(dt)
        self._update_left_plunger(dt)
        
        # Auto-activate plunger when ball is sitting on it
        # Only for single ball (main plunger), multiball handles separately below
        if len(self.balls) == 1 and hasattr(self, 'plunger_state'):
            lane_x = self.width * 0.75  # Plunger lane threshold
            ball = self.balls[0]

            # Check if ball is in plunger lane and stationary
            if (ball.position.x > lane_x and
                ball.position.y > self.height * 0.5 and
                ball.velocity.length < 100.0):  # Ball is relatively stationary (increased threshold)

                # Auto-fire plunger if in resting state
                # Check auto-plunge config (default True)
                auto_plunge = getattr(self, 'auto_plunge_enabled', True)
                if self.plunger_state == 'resting' and auto_plunge:
                    # Check cooldown to prevent rapid re-triggering
                    current_time = self.simulation_time
                    if not hasattr(self, 'last_auto_plunger_time'):
                        self.last_auto_plunger_time = 0

                    if current_time - self.last_auto_plunger_time > 1.0:  # 1 second cooldown
                        logger.info(f"Auto-firing plunger: Ball detected at {ball.position}")

                        # Use standard plunger mechanic for consistency
                        # This ensures launch_angle and wall collision logic is respected
                        self.fire_plunger()
                        logger.info(f"Auto-triggered plunger fire.")

                        self.last_auto_plunger_time = current_time

        # Multiball auto-launch: If there are balls already in play,
        # automatically launch any balls waiting in the plunger lane
        if len(self.balls) > 1:  # More than one ball exists
            lane_x = self.width * 0.75  # Plunger lane threshold

            # Count balls in play (not in plunger lane)
            balls_in_play = 0
            balls_in_plunger = []

            for b in self.balls:
                if b.position.x > lane_x and b.position.y > self.height * 0.5:
                    # Ball is in plunger lane
                    if b.velocity.length < 100.0:  # Ball is relatively stationary (increased threshold)
                        balls_in_plunger.append(b)
                else:
                    # Ball is in play area
                    balls_in_play += 1

            # Auto-launch any balls waiting in plunger lane during multiball
            # Changed: removed balls_in_play > 0 requirement to prevent all balls getting stuck in lane
            if len(balls_in_plunger) > 0:
                # Check cooldown to prevent continuous impulse application (the "phantom magnet" bug)
                current_time = self.simulation_time
                if not hasattr(self, 'last_multiball_launch_time'):
                    self.last_multiball_launch_time = 0

                if current_time - self.last_multiball_launch_time > 1.0:  # 1 second cooldown
                    for b in balls_in_plunger:
                        # Calculate launch velocity based on angle
                        base_speed = self.config.plunger_release_speed
                        angle_rad = np.radians(self.config.launch_angle)

                        vel_x = base_speed * np.sin(angle_rad)
                        vel_y = -base_speed * np.cos(angle_rad)

                        # Launch from current position - let ball travel naturally
                        b.activate()
                        b.velocity = (vel_x, vel_y)
                        logger.debug(f"Multiball auto-launch: velocity=({vel_x:.1f}, {vel_y:.1f})")

                    self.last_multiball_launch_time = current_time

        # Left Plunger (Kickback) Auto-Fire Proximity Check
        # Check if any ball is in the left plunger lane and stationary
        if hasattr(self, 'left_plunger_state') and self.left_plunger_state == 'resting':
            left_lane_x = self.width * 0.15 # Approx left lane boundary
            
            for b in self.balls:
                # Check if in left lane (x < boundary) and near bottom (y > 0.5 height)
                if b.position.x < left_lane_x and b.position.y > self.height * 0.5:
                     if b.velocity.length < 100.0: # Stationary (increased threshold)
                         # Check cooldown
                         current_time = time.time()
                         if not hasattr(self, 'last_left_plunger_time'):
                             self.last_left_plunger_time = 0
                         
                         if current_time - self.last_left_plunger_time > 1.0:
                             logger.info(f"Auto-firing LEFT plunger (Kickback): Ball detected at {b.position}")
                             self.fire_left_plunger()
                             self.last_left_plunger_time = current_time
                             
                             # Also wake up the ball to ensure it moves with the plunger
                             b.activate()

        # Check for stuck balls
        self.check_stuck_ball(dt)

        # Update Drop Target Cooldown Timer
        if hasattr(self, 'drop_target_timer') and self.drop_target_timer > 0:
            self.drop_target_timer -= dt


        
        # Configurable angles (degrees)
        # Use stored values or defaults
        rest_val = self.config.flipper_resting_angle
        up_val = self.config.flipper_stroke_angle
        
        # Convert to radians
        # Left Flipper (Points Right):
        # Rest (Down-Right) is Positive Angle (if rest_val is negative, negate it)
        # Up (Up-Right) is Negative Angle (if up_val is positive, negate it)
        # We assume config values are like: Rest=-30 (Down), Up=30 (Up)
        
        # If config is Rest=-51, Up=27.
        # Left Rest = +51. Left Up = -27.
        l_rest = np.radians(-rest_val) 
        l_up = np.radians(-up_val)
        
        # Right Flipper (Points Left):
        # Rest (Down-Left) is Negative Angle.
        # Up (Up-Left) is Positive Angle.
        r_rest = np.radians(rest_val)
        r_up = np.radians(up_val)
        
        # Actuation logic
        for side, flipper in self.flippers.items():

            if side == 'upper': continue
            self._update_single_flipper(flipper, dt, l_rest, l_up, r_rest, r_up)
                
        # Sub-stepping for stability (Prevent tunneling)
        steps = 10
        sub_dt = dt / steps
        self._is_stepping = True
        try:
            for _ in range(steps):
                self.space.step(sub_dt)
        finally:
            self._is_stepping = False
            
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
        max_speed = self.config.flipper_speed * dt
        change = np.clip(diff, -max_speed, max_speed)
        
        # For Kinematic bodies, we set velocity and let the simulation move it.
        # This ensures collisions are handled correctly.
        # If we manually set angle AND velocity, it moves twice (once manually, once by step).
        # body.angle += change # REMOVED
        body.angular_velocity = change / dt

    def actuate_flipper(self, side, active):
        with self.lock:
            # Physics changes must be safe if stepping? 
            # Actually, actuate_flipper only changes dict state ('active' flag), 
            # it doesn't add/remove bodies. So it should be fine.
            # BUT, let's be paranoid if it ever does more.
            # For now, just the flag update is safe.
            if self.is_tilted:
                active = False # Flippers disabled (forced down) during tilt
                
            if side in self.flippers:
                self.flippers[side]['active'] = active
            elif side == 'upper':
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
            'left_plunger': left_plunger_data,
            'drop_targets': self.drop_target_states,
            'bumper_states': self.bumper_states,
            'combo_count': getattr(self, 'combo_count', 0),
            'combo_timer': getattr(self, 'combo_timer', 0.0),
            'multiplier': getattr(self, 'score_multiplier', 1.0)
        }

    def update_combo_timer(self, dt):
        """Update combo timer and reset combo if expired."""
        if self.combo_count > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                logger.info(f"Combo expired! Final combo: x{self.combo_count}")
                self.combo_count = 0
                self.combo_timer = 0.0
                self.score_multiplier = 1.0
    
    def get_combo_status(self):
        """Return current combo state."""
        return {
            'combo_count': self.combo_count,
            'combo_timer': max(0.0, self.combo_timer),
            'combo_active': self.combo_count > 0
        }
    
    def get_multiplier(self):
        """Return current score multiplier."""
        return self.score_multiplier
    
    def update_rail_params(self, thickness=None, length_scale=None, angle_offset=None, x_offset=None, y_offset=None):
        """Update rail parameters and rebuild rails."""
        if thickness is not None:
            self.rail_thickness = thickness
        if length_scale is not None:
            self.rail_length_scale = length_scale
        if angle_offset is not None:
            self.rail_angle_offset = angle_offset
        if x_offset is not None:
            self.rail_x_offset = x_offset
        if y_offset is not None:
            self.rail_y_offset = y_offset
            
        self._rebuild_rails()

    def _rebuild_rails(self):
        try:
            self._clear_rail_shapes()
            # Ensure static body is at origin to prevent double offsets
            self.space.static_body.position = (0, 0)
            
            # Use config values, but force defaults for offsets to prevent misalignment
            # since UI controls were removed.
            thickness = self.config.guide_thickness
            length_scale = 1.0 
            angle_offset = 0.0 
            x_offset = 0.0 
            y_offset = 0.0 
            
            logger.info(f"Rebuilding rails with: thickness={thickness}, length_scale={length_scale}, angle_offset={angle_offset}, offsets=({x_offset}, {y_offset})")
            
            if hasattr(self.layout, 'rails') and self.layout.rails:
                for i, rail in enumerate(self.layout.rails):
                    try:
                        # Handle both dictionary and object access if needed
                        p1 = rail.get('p1', {})
                        p2 = rail.get('p2', {})
                        
                        # Apply offsets (normalized coordinates)
                        p1_x = p1.get('x', 0) + x_offset
                        p1_y = p1.get('y', 0) + y_offset
                        p2_x = p2.get('x', 0) + x_offset
                        p2_y = p2.get('y', 0) + y_offset
                        
                        w_p1 = self._layout_to_world(p1_x, p1_y)
                        w_p2 = self._layout_to_world(p2_x, p2_y)
                        
                        dx, dy = w_p1[0] - w_p2[0], w_p1[1] - w_p2[1]
                        length = np.hypot(dx, dy)
                        if length > 0:
                            ux, uy = dx / length, dy / length
                            scaled_length = length * length_scale
                            p1_final = (w_p2[0] + ux * scaled_length, w_p2[1] + uy * scaled_length)
                        else:
                            p1_final = w_p1
                            
                        vertices = self._create_thick_line_poly(p1_final, w_p2, thickness=thickness)
                        if vertices:
                            shape = self._add_static_poly(vertices, elasticity=0.8, friction=0.01, collision_type=8)
                            self.rail_shapes.append(shape)
                    except Exception as e:
                         logger.error(f"Error rebuilding rail {i}: {e}")
            logger.info(f"Rails rebuilt: {len(self.rail_shapes)} rails created")
        except Exception as e:
            logger.error(f"Error in _rebuild_rails: {e}")

    def check_stuck_ball(self, dt):
        """Check if any ball is stuck, out of bounds, or drained."""
        balls_to_remove = []
        
        for b in self.balls:
            # 1. Out of Bounds (Bottom) - DRAIN
            if b.position.y > self.height + 100:
                 if getattr(self, 'god_mode', False):
                     # Teleport to plunger lane
                     lane_x = self.width * 0.94 # Center of lane
                     lane_y = self.height * 0.9
                     b.position = (lane_x, lane_y)
                     b.velocity = (0, 0)
                     logger.info("God Mode: Ball rescued and teleported to plunger.")
                     continue # Skip removal
                 
                 logger.info(f"Ball drained (Y > bound): {b.position} (Vel: {b.velocity})")
                 balls_to_remove.append(b)
                 continue
            
            # 2. Out of Bounds (Top) - REMOVE
            if b.position.y < -300: # Way above top
                 logger.warning(f"Ball removed (Y < -300): {b.position} (Velocity: {b.velocity})")
                 balls_to_remove.append(b)
                 continue
                 
            # 3. Stuck Check
            speed = b.velocity.length
            # Threshold: 5.0 pixels/sec (very slow)
            if speed < 5.0:
                # Ignore if in plunger lane (x > 0.8 width)
                if b.position.x > self.width * 0.8:
                    b.stuck_timer = 0.0
                    b.stuck_event_sent = False
                    continue
                
                # Increment timer
                if not hasattr(b, 'stuck_timer'):
                    b.stuck_timer = 0.0
                b.stuck_timer += dt
                
                # Trigger after 5 seconds
                if b.stuck_timer > 5.0:
                    if not getattr(b, 'stuck_event_sent', False):
                        logger.info(f"Stuck ball detected at {b.position}!")
                        self.events.append({
                            'type': 'stuck_ball',
                            'timestamp': time.time()
                        })
                        b.stuck_event_sent = True
            else:
                b.stuck_timer = 0.0
                b.stuck_event_sent = False

        # Remove flagged balls
        for b in balls_to_remove:
            self.remove_ball(b)
            
        # Reset combo/multiplier if NO BALLS LEFT (only after processing removals)
        if len(self.balls) == 0 and balls_to_remove: 
             # Only if we actually removed something and now have 0
             if self.combo_count > 0 or self.score_multiplier > 1.0:
                  logger.debug("Last ball drained! Combo and Multiplier reset.")
                  self.combo_count = 0
                  self.combo_timer = 0.0
                  self.score_multiplier = 1.0

    def rescue_ball(self):
        """Rescue stuck balls by moving them to the plunger lane."""
        logger.info("Rescuing stuck ball(s)...")
        # Move all balls to plunger lane
        # Or just the stuck ones?
        # Simpler to just reset all balls to plunger to be safe.
        
        # Remove existing balls
        for b in self.balls:
            self.space.remove(b, *b.shapes)
        self.balls = []
        
        # Add new ball in plunger lane
        lane_x = self.width * 0.9
        lane_y = self.height * 0.9
        self.add_ball((lane_x, lane_y))
        logger.info("Ball rescued to plunger lane.")

    def spawn_mothership(self):
        """Spawn the Mothership Boss! (Scheduled safe)"""
        # Always schedule to ensure safety regardless of call context (update loop vs collision)
        self.space.add_post_step_callback(self._spawn_mothership_internal, "spawn_mothership")

    def _spawn_mothership_internal(self, space, key):
        """Internal spawn logic."""
        if self.mothership_active:
             return True

        logger.info("👽 SPAWNING MOTHERSHIP! 👽")
        self.mothership_active = True
        self.mothership_health = self.mothership_max_health
        
        # Position: Top center, large body
        pos = (self.width * 0.5, self.height * 0.25)
        self.mothership_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.mothership_body.position = pos
        
        # Shape: Large hexagon or circle
        # Visual Radius: 0.15, Ball Visual: 0.016, Ball Physics: 12.0
        # Scale = 750. New Radius = 0.15 * 750 = 112.5
        radius = 112.5
        # self.mothership_shape = pymunk.Circle(self.mothership_body, radius)
        # Use a poly for a more interesting shape (Hexagon)
        import math
        n_sides = 6
        verts = []
        for i in range(n_sides):
            angle = i * (2 * math.pi / n_sides)
            verts.append((radius * math.cos(angle), radius * math.sin(angle)))
            
        self.mothership_shape = pymunk.Poly(self.mothership_body, verts)
        self.mothership_shape.elasticity = 0.4
        self.mothership_shape.friction = 0.5
        self.mothership_shape.collision_type = COLLISION_TYPE_MOTHERSHIP
        
        self.space.add(self.mothership_body, self.mothership_shape)
        
        self.events.append({
            'type': 'mothership_spawn',
            'health': self.mothership_health
        })
        return True



    def _remove_mothership_safe(self, space, key):
        """Remove mothership safely."""
        if self.mothership_shape and self.mothership_shape in space.shapes:
            space.remove(self.mothership_shape)
        if self.mothership_body and self.mothership_body in space.bodies:
            space.remove(self.mothership_body)
            
        self.mothership_active = False
        self.mothership_shape = None
        self.mothership_body = None
        return True

    def _reset_bumpers_safe(self, space, key):
        """Reset bumpers to active state safely."""
        logger.info("Restoring all bumpers...")
        for i in range(len(self.bumper_health)):
            self.bumper_health[i] = 100
            self.bumper_respawn_timers[i] = 0.0
            
            # Restore Shape if missing
            for shape, idx in self.bumper_shape_map.items():
                if idx == i:
                    if shape not in self.space.shapes:
                        self.space.add(shape)
                    break
        return True
